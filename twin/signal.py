"""
Signal dataclasses for the QSH digital twin.

Defines InputBlock (sensor readings into the pipeline) and OutputBlock
(control decisions out of the pipeline).  These are the interface
contract between the ThermalEngine and any control strategy.

Standalone version — no dependency on the full QSH pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class InputBlock:
    """Snapshot of all sensor readings at one timestep.

    Populated by ThermalEngine.get_input_block() and consumed by
    control strategies (batch runner, RL pipeline, etc.).
    """

    # -- Temperatures --
    room_temps: Dict[str, float] = field(default_factory=dict)
    independent_sensors: Dict[str, float] = field(default_factory=dict)
    trv_temps: Dict[str, float] = field(default_factory=dict)
    outdoor_temp: float = 5.0
    target_temp: float = 21.0

    # -- Heat source --
    hp_flow_temp: float = 35.0
    hp_return_temp: float = 30.0
    hp_power: float = 0.0
    hp_cop: float = 0.0
    delta_t: float = 5.0
    flow_rate: float = 0.0

    # -- Valves --
    valve_positions: Dict[str, float] = field(default_factory=dict)
    avg_open_frac: float = 0.75

    # -- Energy / tariff --
    tariff_rates: List[Any] = field(default_factory=list)
    solar_production: float = 0.0
    grid_power: float = 0.0
    battery_soc: float = 50.0
    current_rate: float = 0.245
    export_rate: float = 0.15

    # -- System state --
    control_enabled: bool = True
    hot_water_active: bool = False

    # -- Flow limits --
    flow_min: float = 25.0
    flow_max: float = 55.0

    # -- Forecast / HW --
    forecast_state: Optional[Any] = None
    hw_state: Optional[Any] = None

    # -- Signal quality --
    signal_quality: Dict[str, str] = field(default_factory=dict)

    # -- Capability flags --
    has_live_cop: bool = False
    has_live_delta_t: bool = False
    has_live_power: bool = False
    has_live_return_temp: bool = False
    has_live_flow_rate: bool = False
    has_solar: bool = False
    has_battery: bool = False

    # -- Timestamp --
    timestamp: float = 0.0


@dataclass
class OutputBlock:
    """Control decisions for one timestep.

    Produced by the control strategy and consumed by
    ThermalEngine.apply_outputs().
    """

    optimal_flow: float = 35.0
    applied_flow: Optional[float] = None
    applied_mode: str = "heat"          # "heat" | "off" | "cool"
    valve_setpoints: Optional[Dict[str, float]] = None
