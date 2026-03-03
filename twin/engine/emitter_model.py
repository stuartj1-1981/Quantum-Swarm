"""
Emitter model for the QSH digital twin.

Models radiator/UFH heat output as a function of mean water temperature
and room temperature, using the standard LMTD correction:

    Q_actual = Q_rated * (LMTD_actual / LMTD_design) ^ n

Where:
    LMTD = (flow - return) / ln((flow - room) / (return - room))
    n = 1.3 for radiators, 1.1 for UFH

For numerical stability, uses arithmetic mean water temp (MWT) instead
of true LMTD when flow ≈ return (delta-T < 1°C).
"""

from __future__ import annotations

import logging
import math
from typing import Dict

logger = logging.getLogger(__name__)

# Standard design conditions (EN 442)
DEFAULT_DESIGN_FLOW = 55.0  # °C
DEFAULT_DESIGN_RETURN = 45.0  # °C
DEFAULT_DESIGN_ROOM = 20.0  # °C
DEFAULT_EXPONENT_RAD = 1.15
DEFAULT_EXPONENT_UFH = 1.1


def mean_water_temp(flow_temp: float, return_temp: float) -> float:
    """Arithmetic mean water temperature."""
    return (flow_temp + return_temp) / 2.0


def log_mean_temp_diff(flow_temp: float, return_temp: float, room_temp: float) -> float:
    """Log Mean Temperature Difference (LMTD).

    Falls back to arithmetic mean delta when flow ≈ return
    to avoid division by zero in ln.
    """
    dt_flow = flow_temp - room_temp
    dt_return = return_temp - room_temp

    # Guard against non-physical or zero values
    if dt_flow <= 0.1 or dt_return <= 0.1:
        return max(0.0, mean_water_temp(flow_temp, return_temp) - room_temp)

    if abs(dt_flow - dt_return) < 0.01:
        # Flow ≈ return: LMTD ≈ arithmetic mean
        return (dt_flow + dt_return) / 2.0

    return (dt_flow - dt_return) / math.log(dt_flow / dt_return)


def emitter_output(
    rated_kw: float,
    flow_temp: float,
    return_temp: float,
    room_temp: float,
    exponent: float = DEFAULT_EXPONENT_RAD,
    design_flow: float = DEFAULT_DESIGN_FLOW,
    design_return: float = DEFAULT_DESIGN_RETURN,
    design_room: float = DEFAULT_DESIGN_ROOM,
) -> float:
    """Calculate actual emitter heat output [kW].

    Uses LMTD correction with a low-temperature boost factor.
    The standard LMTD power law under-predicts output at low flow temps
    (<40°C) because convective heat transfer dominates over radiant at
    low surface temperatures, following a lower effective exponent.
    The boost factor compensates for this by linearly ramping from 1.0
    at design flow (55°C) to a maximum of 1.6 at flow=25°C.
    """
    lmtd_actual = log_mean_temp_diff(flow_temp, return_temp, room_temp)
    lmtd_design = log_mean_temp_diff(design_flow, design_return, design_room)

    if lmtd_design <= 0:
        return 0.0

    ratio = lmtd_actual / lmtd_design
    if ratio <= 0:
        return 0.0

    output = rated_kw * (ratio**exponent)

    # Low-temperature boost: compensates for LMTD under-prediction at low flow temps.
    # At design flow (55°C) boost = 1.0 (no correction).
    # At 25°C flow, boost = 1.6 (60% more output than pure LMTD predicts).
    # Linear ramp between 25°C and 55°C.
    # Above design flow, no boost applied.
    if flow_temp < design_flow:
        max_boost = 1.6
        boost = 1.0 + (max_boost - 1.0) * max(0.0, (design_flow - flow_temp) / (design_flow - 25.0))
        boost = min(boost, max_boost)
        output *= boost

    # Clamp to prevent unrealistic values
    return max(0.0, min(output, rated_kw * 2.0))


def total_emitter_output(
    rooms: Dict[str, float],
    valve_positions: Dict[str, float],
    flow_temp: float,
    return_temp: float,
    room_temps: Dict[str, float],
    emitter_config: dict,
) -> Dict[str, float]:
    """Calculate per-room emitter output [kW].

    Args:
        rooms: {room_name: emitter_rated_kw}
        valve_positions: {room_name: valve_pct (0-100)}
        flow_temp: System flow temperature [°C]
        return_temp: System return temperature [°C]
        room_temps: {room_name: current_temp_c}
        emitter_config: Twin emitter config section

    Returns:
        {room_name: actual_output_kw}
    """
    exponent = emitter_config.get("exponent", DEFAULT_EXPONENT_RAD)
    design_flow = emitter_config.get("design_flow_temp", DEFAULT_DESIGN_FLOW)
    design_return = emitter_config.get("design_return_temp", DEFAULT_DESIGN_RETURN)

    result = {}
    for room, rated_kw in rooms.items():
        valve_frac = valve_positions.get(room, 75.0) / 100.0
        room_temp = room_temps.get(room, 20.0)

        q = emitter_output(
            rated_kw=rated_kw,
            flow_temp=flow_temp,
            return_temp=return_temp,
            room_temp=room_temp,
            exponent=exponent,
            design_flow=design_flow,
            design_return=design_return,
        )
        result[room] = q * valve_frac

    return result
