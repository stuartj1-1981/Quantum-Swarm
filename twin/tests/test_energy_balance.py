"""
Energy balance verification tests for ThermalEngine.

The non-negotiable invariant: every kWh the heat pump produces must go
somewhere.  These tests verify:

1. heat_delivered_kw <= hp_capacity (HP can't exceed rated output)
2. heat_delivered_kw <= total_emitter_demand (can't deliver more than
   emitters reject)
3. hp_power_kw = heat_delivered_kw / COP (no phantom electrical draw)
4. Cumulative energy balance residual ≈ 0

Run with:
    pytest twin/tests/test_energy_balance.py -v
"""

from __future__ import annotations

import pytest

from twin.engine.engine import ThermalEngine, SECONDS_PER_STEP
from twin.engine.emitter_model import emitter_output
from twin.signal import OutputBlock


def _make_config(
    hp_capacity_kw: float = 6.0,
    flow_temp: float = 45.0,
    rooms: dict | None = None,
    emitter_kw: dict | None = None,
) -> dict:
    """Build a minimal valid ThermalEngine config."""
    if rooms is None:
        rooms = {"lounge": 20.0, "bedroom": 12.0}
    if emitter_kw is None:
        emitter_kw = {r: 1.5 for r in rooms}

    return {
        "rooms": rooms,
        "emitter_kw": emitter_kw,
        "peak_loss": 6.0,
        "peak_ext": -3.0,
        "overtemp_protection": 21.0,
        "thermal_mass_per_m2": 0.03,
        "flow_min": 25.0,
        "flow_max": 55.0,
        "twin": {
            "enabled": True,
            "heat_pump": {
                "capacity_kw": hp_capacity_kw,
                "min_modulation_kw": 2.0,
            },
            "emitters": {
                "exponent": 1.15,
                "design_flow_temp": 55.0,
                "design_return_temp": 45.0,
            },
            "physics": {
                "infiltration": {"ach": 0.5},
            },
            "cop_map": [
                {"outdoor": -5, "flow": 25, "cop": 3.2},
                {"outdoor": -5, "flow": 35, "cop": 2.8},
                {"outdoor": -5, "flow": 45, "cop": 2.3},
                {"outdoor": -5, "flow": 55, "cop": 1.8},
                {"outdoor": 5, "flow": 25, "cop": 4.3},
                {"outdoor": 5, "flow": 35, "cop": 3.8},
                {"outdoor": 5, "flow": 45, "cop": 3.2},
                {"outdoor": 5, "flow": 55, "cop": 2.5},
                {"outdoor": 15, "flow": 25, "cop": 5.2},
                {"outdoor": 15, "flow": 35, "cop": 4.8},
                {"outdoor": 15, "flow": 45, "cop": 4.1},
                {"outdoor": 15, "flow": 55, "cop": 3.2},
            ],
        },
    }


class TestEnergyConservation:
    """Verify the core energy balance invariant."""

    def test_heat_delivered_does_not_exceed_capacity(self):
        """heat_delivered_kw must never exceed HP rated capacity."""
        config = _make_config(hp_capacity_kw=6.0)
        engine = ThermalEngine(config)

        outputs = OutputBlock(optimal_flow=50.0, applied_flow=50.0, applied_mode="heat")
        engine.apply_outputs(outputs)

        for _ in range(120):  # 1 hour
            engine.step(outdoor_temp=2.0, solar_irradiance=0.0)
            assert engine.state.heat_delivered_kw <= 6.0 + 0.001, (
                f"heat_delivered_kw={engine.state.heat_delivered_kw} exceeds "
                f"HP capacity 6.0 kW"
            )

    def test_heat_delivered_does_not_exceed_emitter_demand(self):
        """heat_delivered_kw must never exceed what emitters can reject.

        Uses a deliberately oversized HP (20 kW) with small emitters (1 kW
        each) so emitter demand is well below HP capacity.
        """
        config = _make_config(
            hp_capacity_kw=20.0,
            emitter_kw={"lounge": 1.0, "bedroom": 1.0},
        )
        engine = ThermalEngine(config)

        outputs = OutputBlock(optimal_flow=45.0, applied_flow=45.0, applied_mode="heat")
        engine.apply_outputs(outputs)

        for _ in range(120):
            engine.step(outdoor_temp=5.0, solar_irradiance=0.0)

            # Calculate what emitters can actually reject at current conditions
            total_emitter_demand = 0.0
            for room_name, room in engine.state.rooms.items():
                valve_frac = engine._valve_positions.get(room_name, 75.0) / 100.0
                q = emitter_output(
                    rated_kw=room.emitter_kw,
                    flow_temp=engine.state.flow_temp,
                    return_temp=engine.state.return_temp,
                    room_temp=room.temp,
                    exponent=1.15,
                    design_flow=55.0,
                    design_return=45.0,
                )
                total_emitter_demand += q * valve_frac

            assert engine.state.heat_delivered_kw <= total_emitter_demand + 0.001, (
                f"heat_delivered_kw={engine.state.heat_delivered_kw:.3f} exceeds "
                f"total_emitter_demand={total_emitter_demand:.3f} — phantom energy"
            )

    def test_electrical_power_matches_delivery(self):
        """hp_power_kw must equal heat_delivered_kw / COP."""
        config = _make_config(hp_capacity_kw=6.0)
        engine = ThermalEngine(config)

        outputs = OutputBlock(optimal_flow=45.0, applied_flow=45.0, applied_mode="heat")
        engine.apply_outputs(outputs)

        for _ in range(120):
            engine.step(outdoor_temp=5.0, solar_irradiance=0.0)

            if engine.state.hp_on and engine.state.heat_delivered_kw > 0:
                cop = engine._cop_fn(5.0, engine.state.flow_temp)
                expected_power = engine.state.heat_delivered_kw / max(cop, 1.0)
                assert abs(engine.state.hp_power_kw - expected_power) < 0.001, (
                    f"hp_power_kw={engine.state.hp_power_kw:.4f} != "
                    f"heat_delivered/{cop:.2f}={expected_power:.4f}"
                )

    def test_energy_balance_residual_near_zero(self):
        """Cumulative energy balance residual must stay near zero.

        The residual is: energy_in + energy_solar - energy_loss - energy_stored.
        Non-zero residual means energy is being created or destroyed.
        """
        config = _make_config(hp_capacity_kw=6.0)
        engine = ThermalEngine(config)

        outputs = OutputBlock(optimal_flow=45.0, applied_flow=45.0, applied_mode="heat")
        engine.apply_outputs(outputs)

        # Run 2 hours of simulation
        for _ in range(240):
            engine.step(outdoor_temp=5.0, solar_irradiance=0.0)

        balance = engine.energy_balance
        residual = abs(balance["residual"])
        total_energy = balance["in"] + balance["solar"] + abs(balance["loss"])

        # Residual should be < 1% of total energy throughput
        if total_energy > 0:
            relative_residual = residual / total_energy
            assert relative_residual < 0.01, (
                f"Energy balance residual {residual:.4f} kWh is "
                f"{relative_residual*100:.2f}% of total throughput "
                f"{total_energy:.4f} kWh — energy conservation violated"
            )

    def test_hp_off_zero_delivery(self):
        """When HP is off, heat_delivered and hp_power must be zero."""
        config = _make_config()
        engine = ThermalEngine(config)

        outputs = OutputBlock(optimal_flow=45.0, applied_flow=45.0, applied_mode="off")
        engine.apply_outputs(outputs)

        engine.step(outdoor_temp=5.0)

        assert engine.state.heat_delivered_kw == 0.0
        assert engine.state.hp_power_kw == 0.0


class TestEmitterModel:
    """Verify emitter model behaviour at boundary conditions."""

    def test_emitter_output_positive_at_design(self):
        """Emitter must produce positive output at design conditions."""
        q = emitter_output(
            rated_kw=1.5,
            flow_temp=55.0,
            return_temp=45.0,
            room_temp=20.0,
        )
        assert q > 0.0

    def test_emitter_output_zero_when_cold(self):
        """Emitter produces zero when flow temp <= room temp."""
        q = emitter_output(
            rated_kw=1.5,
            flow_temp=19.0,
            return_temp=18.0,
            room_temp=20.0,
        )
        assert q == 0.0

    def test_emitter_output_decreases_with_lower_flow(self):
        """Lower flow temp must produce lower emitter output."""
        q_high = emitter_output(
            rated_kw=1.5, flow_temp=55.0, return_temp=45.0, room_temp=20.0
        )
        q_low = emitter_output(
            rated_kw=1.5, flow_temp=35.0, return_temp=30.0, room_temp=20.0
        )
        assert q_low < q_high
