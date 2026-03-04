"""
Post-simulation validation for ThermalEngine runs.

Checks energy balance, temperature plausibility, and physics consistency
after a simulation completes.  Used by batch runner and standalone
verification.

Usage:
    from twin.validate import validate_run
    issues = validate_run(engine)
    if issues:
        for issue in issues:
            print(f"  FAIL: {issue}")
"""

from __future__ import annotations

from typing import List

from twin.engine.engine import ThermalEngine


def validate_run(engine: ThermalEngine) -> List[str]:
    """Run post-simulation validation checks.

    Args:
        engine: A ThermalEngine that has completed a simulation run.

    Returns:
        List of issue descriptions.  Empty list means all checks passed.
    """
    issues: List[str] = []

    # 1. Energy balance residual
    balance = engine.energy_balance
    total_throughput = balance["in"] + balance["solar"] + abs(balance["loss"])
    if total_throughput > 0:
        relative_residual = abs(balance["residual"]) / total_throughput
        if relative_residual > 0.01:
            issues.append(
                f"Energy balance residual {balance['residual']:.4f} kWh "
                f"({relative_residual*100:.2f}% of throughput) — "
                f"exceeds 1% tolerance"
            )

    # 2. Room temperature plausibility
    for name, room in engine.state.rooms.items():
        if room.temp < -10.0:
            issues.append(
                f"Room '{name}' temp {room.temp:.1f}°C is implausibly low "
                f"(below -10°C)"
            )
        if room.temp > 40.0:
            issues.append(
                f"Room '{name}' temp {room.temp:.1f}°C is implausibly high "
                f"(above 40°C)"
            )

    # 3. Heat delivery vs HP state consistency
    if not engine.state.hp_on:
        if engine.state.heat_delivered_kw > 0:
            issues.append(
                f"HP is OFF but heat_delivered_kw={engine.state.heat_delivered_kw} > 0"
            )
        if engine.state.hp_power_kw > 0:
            issues.append(
                f"HP is OFF but hp_power_kw={engine.state.hp_power_kw} > 0"
            )

    # 4. Return temp sanity
    if engine.state.hp_on:
        if engine.state.return_temp > engine.state.flow_temp:
            issues.append(
                f"Return temp {engine.state.return_temp:.1f}°C > "
                f"flow temp {engine.state.flow_temp:.1f}°C — "
                f"thermodynamically impossible"
            )

    # 5. COP sanity (if HP is on)
    if engine.state.hp_on and engine.state.heat_delivered_kw > 0:
        implied_cop = engine.state.heat_delivered_kw / max(engine.state.hp_power_kw, 0.001)
        if implied_cop < 1.0:
            issues.append(
                f"Implied COP {implied_cop:.2f} < 1.0 — heat pump cannot be "
                f"less efficient than resistive heating"
            )
        if implied_cop > 8.0:
            issues.append(
                f"Implied COP {implied_cop:.2f} > 8.0 — exceeds plausible "
                f"ASHP range"
            )

    return issues
