"""
ThermalEngine — physics stepping for the QSH digital twin.

Models:
  - Per-room heat loss (U x dT)
  - Per-room thermal mass (C x dT/dt)
  - Heat input from HP (via COP model + flow temp)
  - Heat distribution via valve positions and emitter model
  - Inter-room thermal coupling (optional)
  - Solar gains (optional)
  - Infiltration loss (optional)

The engine does NOT import from the pipeline, controllers, or HA.
It only depends on twin/ and signal.py.

Interface (PhysicsEngine-compatible):
  apply_outputs(OutputBlock) -> None
  step(outdoor_temp, solar_irradiance) -> None
  get_input_block() -> InputBlock
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..signal import InputBlock, OutputBlock

logger = logging.getLogger(__name__)

SECONDS_PER_STEP = 30.0
HOURS_PER_STEP = SECONDS_PER_STEP / 3600.0


class TwinConfigError(ValueError):
    """Raised when twin/engine config is invalid or incomplete."""

    pass


@dataclass
class RoomState:
    """Thermal state of a single room."""

    name: str = ""
    temp: float = 20.0  # Current air temperature [C]
    u_kw_per_c: float = 0.05  # Heat loss coefficient [kW/C]
    c_kwh_per_c: float = 1.0  # Thermal mass [kWh/C]
    solar_factor: float = 0.0  # Solar gain multiplier
    area_m2: float = 15.0  # Floor area [m2]
    ceiling_m: float = 2.4  # Ceiling height [m]
    emitter_kw: float = 1.5  # Emitter rated output [kW]


@dataclass
class BuildingState:
    """Full building thermal state."""

    rooms: Dict[str, RoomState] = field(default_factory=dict)
    outdoor_temp: float = 5.0
    solar_irradiance: float = 0.0  # [kW/m2]
    hp_on: bool = True
    flow_temp: float = 35.0
    return_temp: float = 30.0
    hp_power_kw: float = 0.0
    heat_delivered_kw: float = 0.0
    hot_water_active: bool = False


class ThermalEngine:
    """
    Step building physics forward one timestep (30 seconds).

    Usage:
        engine = ThermalEngine(full_config)
        engine.apply_outputs(pipeline_output_block)
        engine.step(outdoor_temp, solar_irradiance)
        input_block = engine.get_input_block()
    """

    def __init__(self, config: Dict):
        """
        Args:
            config: Full HOUSE_CONFIG dict (includes 'rooms', 'twin', etc.)

        Raises:
            TwinConfigError: If config is missing required fields or has
                             invalid physics parameters.
        """
        self.state = BuildingState()
        self._config = config

        # -- Validate config --
        rooms_config = config.get("rooms", {})
        if not rooms_config:
            raise TwinConfigError("config['rooms'] is empty -- cannot build twin")

        twin_cfg = config.get("twin", {})
        physics = twin_cfg.get("physics", {})
        per_room_physics = physics.get("per_room", {})

        # Warn if twin physics reference rooms not in config
        unknown_rooms = set(per_room_physics.keys()) - set(rooms_config.keys())
        if unknown_rooms:
            logger.warning(
                "ThermalEngine: twin physics reference unknown rooms: %s (ignoring -- check twin profile YAML)",
                unknown_rooms,
            )

        self._coupling = physics.get("coupling", [])
        self._infiltration_ach = physics.get("infiltration", {}).get("ach", 0.5)

        # Start conditions
        start = twin_cfg.get("simulation", {}).get("start_conditions", {})
        start_temps = start.get("room_temps", {})

        # Initialise per-room state from config
        facings = config.get("facings", {})
        emitters = config.get("emitter_kw", {})
        ceilings = config.get("ceiling_heights", {})

        for room_name, area_m2 in rooms_config.items():
            room_phys = per_room_physics.get(room_name, {})
            # Physics from twin config, or derive from thermal section
            u = room_phys.get("u_kw_per_c", self._default_u(area_m2, config))
            c = room_phys.get("c_kwh_per_c", self._default_c(area_m2, config))
            sf = room_phys.get("solar_gain_factor", 0.0)

            # -- Validate physics bounds --
            if u <= 0:
                raise TwinConfigError(f"Room '{room_name}': u_kw_per_c={u} must be > 0")
            if c <= 0:
                raise TwinConfigError(
                    f"Room '{room_name}': c_kwh_per_c={c} must be > 0 "
                    f"(thermal mass cannot be zero -- simulation would diverge)"
                )
            if area_m2 <= 0:
                raise TwinConfigError(f"Room '{room_name}': area_m2={area_m2} must be > 0")
            if not (0.0 <= sf <= 10.0):
                logger.warning(
                    "Room '%s': solar_gain_factor=%.2f looks unusual (expected 0-10), proceeding anyway",
                    room_name,
                    sf,
                )

            self.state.rooms[room_name] = RoomState(
                name=room_name,
                temp=start_temps.get(room_name, 20.0),
                u_kw_per_c=u,
                c_kwh_per_c=c,
                solar_factor=sf,
                area_m2=area_m2,
                ceiling_m=ceilings.get(room_name, 2.4),
                emitter_kw=emitters.get(room_name, 1.5),
            )

        # COP model — use data-driven map if available, else Carnot fraction
        from .cop_model import create_cop_model

        data_cop = create_cop_model(twin_cfg)
        self._cop_fn = data_cop if data_cop is not None else self._default_cop

        # HP config
        hp_cfg = twin_cfg.get("heat_pump", {})
        self._hp_capacity_kw = hp_cfg.get("capacity_kw", 6.0)
        if self._hp_capacity_kw <= 0:
            raise TwinConfigError(f"heat_pump.capacity_kw={self._hp_capacity_kw} must be > 0")
        self._hp_min_mod_kw = hp_cfg.get("min_modulation_kw", 2.0)

        # Valve positions (updated by apply_outputs)
        self._valve_positions: Dict[str, float] = {r: 75.0 for r in rooms_config}

        # Emitter model config
        emitter_cfg = twin_cfg.get("emitters", {})
        self._emitter_exponent = emitter_cfg.get("exponent", 1.3)
        self._design_flow_temp = emitter_cfg.get("design_flow_temp", 55.0)
        self._design_return_temp = emitter_cfg.get("design_return_temp", 45.0)

        # Energy balance tracking (kWh cumulative)
        self._energy_in_kwh = 0.0       # Total heat delivered to rooms
        self._energy_loss_kwh = 0.0     # Total fabric + infiltration loss
        self._energy_solar_kwh = 0.0    # Total solar gain
        self._energy_stored_kwh = 0.0   # Total change in thermal mass (C × ΔT)

        logger.info(
            "ThermalEngine: %d rooms, HP %.1f kW, physics from %s",
            len(self.state.rooms),
            self._hp_capacity_kw,
            "twin config" if per_room_physics else "defaults",
        )

    # -- PhysicsEngine interface --

    def apply_outputs(self, outputs: OutputBlock) -> None:
        """Receive pipeline control decisions for next physics step."""
        self.state.flow_temp = outputs.applied_flow or outputs.optimal_flow
        self.state.hp_on = outputs.applied_mode != "off"

        # Valve positions from OutputBlock
        if outputs.valve_setpoints:
            for room, pos in outputs.valve_setpoints.items():
                if room in self._valve_positions:
                    self._valve_positions[room] = pos

    def step(self, outdoor_temp: float, solar_irradiance: float = 0.0) -> None:
        """
        Advance building physics by one timestep (30 seconds).

        Core equation per room:
            dT = (Q_in - Q_loss - Q_infil + Q_solar + Q_coupling) / C x dt

        Where:
            Q_loss  = U x (T_room - T_outdoor)           [kW]
            Q_infil = V x ACH x 0.33 x (T_room - T_out) / 3600  [kW]
            Q_in    = share of HP heat delivery            [kW]
            Q_solar = solar_factor x irradiance            [kW]
            Q_coupling = sum k_ij x (T_j - T_i)           [kW]
            C = thermal mass                               [kWh/C]
        """
        self.state.outdoor_temp = outdoor_temp
        self.state.solar_irradiance = solar_irradiance

        # Calculate HP heat delivery
        if self.state.hp_on:
            cop = self._cop_fn(outdoor_temp, self.state.flow_temp)
            hp_capacity = self._estimate_capacity(outdoor_temp, self.state.flow_temp)

            # Defrost derating: HP loses capacity when outdoor is cold
            # Placeholder: linear ramp 0% at 7°C to 10% at -5°C
            # Will be calibrated from sysid defrost cycle data
            defrost_derating = 1.0
            if outdoor_temp < 7.0:
                defrost_derating = max(0.85, 1.0 - 0.10 * (7.0 - outdoor_temp) / 12.0)
            hp_capacity *= defrost_derating

            self.state.heat_delivered_kw = hp_capacity
            self.state.hp_power_kw = hp_capacity / max(cop, 1.0)
        else:
            self.state.heat_delivered_kw = 0.0
            self.state.hp_power_kw = 0.0
            cop = 0.0

        # Distribute heat to rooms using emitter model
        from .emitter_model import emitter_output

        emitter_cfg = self._config.get("twin", {}).get("emitters", {})

        # Calculate per-room emitter output
        per_room_q: Dict[str, float] = {}
        total_emitter_demand = 0.0
        for room_name, room in self.state.rooms.items():
            valve_frac = self._valve_positions.get(room_name, 75.0) / 100.0
            q_emitter = (
                emitter_output(
                    rated_kw=room.emitter_kw,
                    flow_temp=self.state.flow_temp,
                    return_temp=self.state.return_temp,
                    room_temp=room.temp,
                    exponent=emitter_cfg.get("exponent", self._emitter_exponent),
                    design_flow=emitter_cfg.get("design_flow_temp", self._design_flow_temp),
                    design_return=emitter_cfg.get("design_return_temp", self._design_return_temp),
                )
                * valve_frac
            )
            per_room_q[room_name] = q_emitter
            total_emitter_demand += q_emitter

        # Scale emitter demands so total doesn't exceed HP capacity
        if total_emitter_demand > 0 and self.state.hp_on:
            scale = min(1.0, self.state.heat_delivered_kw / total_emitter_demand)
        else:
            scale = 0.0

        for room_name, room in self.state.rooms.items():
            # Heat input — emitter output scaled to HP capacity
            q_in = per_room_q[room_name] * scale if self.state.hp_on else 0.0

            # Fabric heat loss
            q_loss = room.u_kw_per_c * (room.temp - outdoor_temp)

            # Infiltration loss
            volume_m3 = room.area_m2 * room.ceiling_m
            q_infil = volume_m3 * self._infiltration_ach * 0.33 * (room.temp - outdoor_temp) / 3600.0

            # Solar gain
            q_solar = room.solar_factor * solar_irradiance

            # Temperature change -- with numerical stability clamp
            if room.c_kwh_per_c > 0:
                dt = (q_in - q_loss - q_infil + q_solar) / room.c_kwh_per_c * HOURS_PER_STEP

                # Accumulate energy balance BEFORE clamp (clamp destroys energy — tracked via residual)
                self._energy_in_kwh += q_in * HOURS_PER_STEP
                self._energy_loss_kwh += (q_loss + q_infil) * HOURS_PER_STEP
                self._energy_solar_kwh += q_solar * HOURS_PER_STEP
                self._energy_stored_kwh += room.c_kwh_per_c * dt

                # Clamp per-step change to +/-2C -- prevents runaway if
                # physics params are misconfigured (e.g. tiny C, huge U)
                dt = max(-2.0, min(2.0, dt))
                room.temp += dt

            # Hard clamp: no room goes below -40C or above 60C
            # (physically implausible -- flags a config problem)
            if room.temp < -40.0 or room.temp > 60.0:
                logger.warning(
                    "Room '%s' temp %.1fC out of plausible range -- clamping (check U/C physics params)",
                    room_name,
                    room.temp,
                )
                room.temp = max(-40.0, min(60.0, room.temp))

        # Inter-room coupling
        for coupling in self._coupling:
            room_a, room_b, k = coupling[0], coupling[1], coupling[2]
            if room_a in self.state.rooms and room_b in self.state.rooms:
                ra = self.state.rooms[room_a]
                rb = self.state.rooms[room_b]
                q_transfer = k * (rb.temp - ra.temp) * HOURS_PER_STEP
                if ra.c_kwh_per_c > 0:
                    ra.temp += q_transfer / ra.c_kwh_per_c
                if rb.c_kwh_per_c > 0:
                    rb.temp -= q_transfer / rb.c_kwh_per_c

        # Calculate return temp from flow and room temps
        if self.state.hp_on and self.state.rooms:
            avg_room = sum(r.temp for r in self.state.rooms.values()) / len(self.state.rooms)
            # Delta-T varies with flow temp: ~5K at low flow, ~8K at high flow
            # Linear model: dT = 3.0 + 0.1 * (flow - 25), clamped [3, 12]
            delta_t = max(3.0, min(12.0, 3.0 + 0.1 * (self.state.flow_temp - 25.0)))
            self.state.return_temp = max(avg_room, self.state.flow_temp - delta_t)

    def get_input_block(self) -> InputBlock:
        """Build an InputBlock from current building state."""
        rooms = {name: rs.temp for name, rs in self.state.rooms.items()}
        valve_pcts = dict(self._valve_positions)
        avg_valve = sum(valve_pcts.values()) / len(valve_pcts) if valve_pcts else 75.0

        cop = self._cop_fn(self.state.outdoor_temp, self.state.flow_temp) if self.state.hp_on else 0.0

        return InputBlock(
            # Temperatures
            room_temps=rooms,
            independent_sensors={},
            trv_temps=dict(rooms),
            outdoor_temp=self.state.outdoor_temp,
            target_temp=self._config.get("overtemp_protection", 21.0),
            # Heat source
            hp_flow_temp=self.state.flow_temp,
            hp_return_temp=self.state.return_temp,
            hp_power=self.state.hp_power_kw,
            hp_cop=cop,
            delta_t=self.state.flow_temp - self.state.return_temp,
            flow_rate=0.0,
            # Valves
            valve_positions=valve_pcts,
            avg_open_frac=avg_valve / 100.0,
            # Energy
            tariff_rates=[],
            solar_production=0.0,
            grid_power=0.0,
            battery_soc=50.0,
            current_rate=0.245,
            export_rate=0.15,
            # System state
            control_enabled=True,
            hot_water_active=self.state.hot_water_active,
            # Flow limits
            flow_min=self._config.get("flow_min", 25.0),
            flow_max=self._config.get("flow_max", 55.0),
            # Forecast / HW
            forecast_state=None,
            hw_state=None,
            # Signal quality
            signal_quality={f"room_temps.{r}": "good" for r in rooms},
            # Capability flags
            has_live_cop=True,
            has_live_delta_t=True,
            has_live_power=True,
            has_live_return_temp=True,
            has_live_flow_rate=False,
            has_solar=False,
            has_battery=False,
            # Timestamp -- caller patches this from virtual clock
            timestamp=0.0,
        )

    @property
    def energy_balance(self) -> dict:
        """Return cumulative energy balance [kWh]. For testing/validation."""
        return {
            "in": self._energy_in_kwh,
            "loss": self._energy_loss_kwh,
            "solar": self._energy_solar_kwh,
            "stored": self._energy_stored_kwh,
            "residual": (
                self._energy_in_kwh
                + self._energy_solar_kwh
                - self._energy_loss_kwh
                - self._energy_stored_kwh
            ),
        }

    # -- Internal --

    def _default_cop(self, outdoor_temp: float, flow_temp: float) -> float:
        """Simple Carnot-fraction COP model. Fallback when no cop_map provided."""
        dt = max(flow_temp - outdoor_temp, 5.0)
        carnot = (flow_temp + 273.15) / dt
        return min(carnot * 0.38, 4.8)  # 38% Carnot efficiency, capped

    def _estimate_capacity(self, outdoor_temp: float, flow_temp: float) -> float:
        """Estimate HP heat output [kW] as function of temperature lift.

        Piecewise-linear derating based on manufacturer data envelope:
          lift <= 15K: 100% capacity (low-temp heating)
          15K < lift <= 30K: linear derating to 75%
          30K < lift <= 45K: linear derating to 50%
          lift > 45K: linear derating to 40% (clamped)

        These breakpoints are conservative and will be replaced by
        per-unit curves after sysid data arrives.
        """
        lift = max(0.0, flow_temp - outdoor_temp)
        if lift <= 15.0:
            derating = 1.0
        elif lift <= 30.0:
            derating = 1.0 - 0.25 * (lift - 15.0) / 15.0  # 1.0 → 0.75
        elif lift <= 45.0:
            derating = 0.75 - 0.25 * (lift - 30.0) / 15.0  # 0.75 → 0.50
        else:
            derating = max(0.40, 0.50 - 0.10 * (lift - 45.0) / 15.0)  # 0.50 → 0.40
        return self._hp_capacity_kw * derating

    @staticmethod
    def _default_u(area_m2: float, config: Dict) -> float:
        """Derive U from peak_loss_kw if no per-room physics given."""
        peak_loss = config.get("peak_loss", 6.0)
        peak_ext = config.get("peak_ext", -3.0)
        total_area = sum(config.get("rooms", {}).values()) or 1.0
        dt_design = config.get("overtemp_protection", 21.0) - peak_ext
        u_total = peak_loss / max(dt_design, 1.0)
        return u_total * (area_m2 / total_area)

    @staticmethod
    def _default_c(area_m2: float, config: Dict) -> float:
        """Derive C from thermal_mass_per_m2 if no per-room physics given."""
        c_per_m2 = config.get("thermal_mass_per_m2", 0.03)
        return area_m2 * c_per_m2
