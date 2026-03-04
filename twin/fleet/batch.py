"""
Batch runner for QSH digital twin fleet simulations.

Runs N simulations in parallel with different building profiles,
weather files, and control strategies. Collects results into SQLite.

Strategies:
  - stock:              Fixed flow temp baseline (no QSH control)
  - stock_weather_comp: Weather-compensated stock (MCS MIS 3005 linear curve)
  - hp_fixed_45/50/55:  Fixed flow HP baselines with thermostat
  - hp_wc:              Manufacturer weather compensation curves (Phase 3b)
  - qsh_capped:         Standard QSH with Skynet Rule (production behaviour)
  - qsh_uncapped:       QSH with blend_cap_override: 1.0 (full RL authority)

Usage:
    python -m qsh.twin.batch \\
        --profiles twin/profiles/ \\
        --weather twin/weather_data/ \\
        --hours 168 \\
        --workers 4 \\
        --output data/results/
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from multiprocessing import Pool
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# HP stock flow strategies (Phase 3a)
HP_FIXED_FLOWS = {
    "hp_fixed_45": 45.0,
    "hp_fixed_50": 50.0,
    "hp_fixed_55": 55.0,
}

# Schedules
HP_SCHEDULES = ("continuous", "night_setback")

# Thermostat setpoints
THERMOSTAT_SETPOINTS = (18.0, 19.0, 20.0, 21.0, 22.0, 23.0, 24.0, 25.0)

# QSH target temps
QSH_TARGETS = (19.0, 20.0, 21.0)

# All valid strategy base names (for argparse validation)
STRATEGIES = (
    "stock",                # Legacy: fixed 55°C, no thermostat (keep for back-compat)
    "stock_weather_comp",   # Weather-compensated stock (Phase 2)
    "hp_fixed_45",
    "hp_fixed_50",
    "hp_fixed_55",
    "hp_wc",                # Manufacturer weather compensation curves (Phase 3b)
    "qsh_capped",
    "qsh_uncapped",
)

CYCLES_PER_HOUR = 120  # 3600s / 30s per cycle


def thermostat_step(
    avg_room: float,
    thermostat_on: bool,
    setpoint: float,
    deadband: float = 0.5,
) -> bool:
    """Evaluate room thermostat with hysteresis deadband.

    Simple on/off thermostat modelling a standard UK domestic stat
    (Honeywell T6, Hive, Nest). Uses mean room temperature as sensor
    and maintains state across calls to prevent rapid cycling.

    Args:
        avg_room: Current mean room temperature [°C]
        thermostat_on: Previous thermostat state (True=heating, False=off)
        setpoint: Thermostat setpoint [°C]
        deadband: Half-width of deadband [°C] (default 0.5 = ±0.5°C)

    Returns:
        New thermostat state: True if heating should be ON, False if OFF.

    Behaviour:
        avg_room >= setpoint + deadband → OFF
        avg_room <= setpoint - deadband → ON
        otherwise → maintain previous state (hysteresis)
    """
    if avg_room >= setpoint + deadband:
        return False
    elif avg_room <= setpoint - deadband:
        return True
    return thermostat_on


def schedule_active(
    cycle: int,
    schedule: str,
    cycles_per_hour: int = 120,
) -> bool:
    """Determine if heating is active based on schedule and current cycle.

    Args:
        cycle: Current simulation cycle number (0-based)
        schedule: Schedule type. One of:
            'continuous' — heating available 24/7 (thermostat still controls)
            'night_setback' — heating 24/7 but setpoint reduced 23:00-06:00
            'timed' — heating only 05:30-09:00 and 16:30-22:30
        cycles_per_hour: Cycles per hour (default 120 = 30s steps)

    Returns:
        True if heating is AVAILABLE this cycle, False if OFF.

    For 'night_setback', always returns True (setpoint reduction handled
    separately by the caller, not by this function).
    """
    if schedule in ("continuous", "night_setback"):
        return True

    if schedule == "timed":
        # Determine hour-of-day within the simulation week
        # cycle 0 = 00:00 Monday
        total_hours = cycle / cycles_per_hour
        hour_of_day = total_hours % 24.0
        # ON periods: 05:30-09:00 and 16:30-22:30
        if 5.5 <= hour_of_day < 9.0:
            return True
        if 16.5 <= hour_of_day < 22.5:
            return True
        return False

    # Unknown schedule — default to continuous
    return True


def get_effective_setpoint(
    setpoint: float,
    cycle: int,
    schedule: str,
    setback_delta: float = 5.0,
    cycles_per_hour: int = 120,
) -> float:
    """Get effective thermostat setpoint, accounting for night setback.

    Args:
        setpoint: Base thermostat setpoint [°C]
        cycle: Current simulation cycle number (0-based)
        schedule: Schedule type ('continuous', 'night_setback', 'timed')
        setback_delta: Night setback reduction [°C] (default 5.0)
        cycles_per_hour: Cycles per hour (default 120)

    Returns:
        Effective setpoint [°C]. Reduced during setback period.
    """
    if schedule != "night_setback":
        return setpoint

    total_hours = cycle / cycles_per_hour
    hour_of_day = total_hours % 24.0
    # Setback period: 23:00-06:00
    if hour_of_day >= 23.0 or hour_of_day < 6.0:
        return setpoint - setback_delta
    return setpoint


# ── SQLite schema ─────────────────────────────────────────────────────

CREATE_RUNS_SQL = """
CREATE TABLE IF NOT EXISTS runs (
    run_id              TEXT PRIMARY KEY,
    timestamp           TEXT NOT NULL,
    archetype           TEXT NOT NULL,
    weather_location    TEXT NOT NULL,
    strategy            TEXT NOT NULL,
    hours_simulated     REAL NOT NULL,
    total_kwh           REAL,
    total_cost_gbp      REAL,
    mean_cop            REAL,
    mean_room_temp      REAL,
    min_room_temp       REAL,
    hours_below_setpoint REAL,
    mean_flow_temp      REAL,
    max_flow_temp       REAL,
    heat_source         TEXT,
    flow_strategy       TEXT,
    thermostat_setpoint REAL,
    schedule            TEXT,
    wc_curve            TEXT DEFAULT 'none',
    savings_kwh         REAL,
    savings_pct         REAL,
    mean_cop_improvement REAL,
    savings_vs_wc_kwh   REAL,
    savings_vs_wc_pct   REAL,
    skynet_cost_kwh     REAL,
    profile_yaml        TEXT,
    weather_csv         TEXT,
    config_hash         TEXT
);
"""

CREATE_HOURLY_SQL = """
CREATE TABLE IF NOT EXISTS hourly (
    run_id          TEXT NOT NULL REFERENCES runs(run_id),
    hour            INTEGER NOT NULL,
    outdoor_temp    REAL,
    mean_room_temp  REAL,
    flow_temp       REAL,
    hp_power_kw     REAL,
    cop             REAL,
    kwh_consumed    REAL,
    cost_gbp        REAL,
    PRIMARY KEY (run_id, hour)
);
"""


def init_db(db_path: str) -> sqlite3.Connection:
    """Create/open fleet results database with WAL mode."""
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(CREATE_RUNS_SQL)
    conn.execute(CREATE_HOURLY_SQL)
    conn.commit()
    return conn


# ── Config loading ────────────────────────────────────────────────────


def load_profile(yaml_path: str) -> Dict[str, Any]:
    """Load a building profile YAML and return as HOUSE_CONFIG dict.

    Uses qsh config.py parsing where possible, with twin sections preserved.
    """
    import yaml

    with open(yaml_path, "r") as f:
        raw = yaml.safe_load(f)

    # Minimal config assembly — the profile should contain all needed keys
    config = dict(raw)
    config.setdefault("driver", "mock")
    config.setdefault("twin", {})
    config["twin"].setdefault("enabled", True)

    # Defaults expected by the pipeline but not present in archetype profiles.
    # These mirror the defaults in config.py _build_house_config().
    import tempfile

    config.setdefault("heat_up_tau_h", 1.0)
    config.setdefault("nudge_budget", 3.0)
    config.setdefault("persistent_zones", [])
    config.setdefault("heat_source_type", "heat_pump")
    config.setdefault("heat_source_efficiency", 3.0)
    config.setdefault("hp_min_output_kw", 2.0)
    config.setdefault("has_flow_control", True)
    config.setdefault("has_cop_sensor", False)
    config.setdefault("has_delta_t_sensor", False)
    config.setdefault("has_return_temp_sensor", False)
    config.setdefault("has_flow_rate_sensor", False)
    config.setdefault("has_outdoor_sensor", True)
    config.setdefault("zone_sensor_map", {})
    config.setdefault("room_valve_hardware", {})
    config.setdefault("room_valve_scale", {})
    config.setdefault("room_trv_names", {})

    # Writable data directory (avoid /data on non-production systems)
    if config.get("driver") == "mock":
        sim_data_dir = os.path.join(tempfile.gettempdir(), "qsh_sim_data")
        os.makedirs(sim_data_dir, exist_ok=True)
        config.setdefault("data_dir", sim_data_dir)

    return config


def config_hash(config: dict) -> str:
    """SHA256 hash of serialized config for reproducibility."""
    serialized = json.dumps(config, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()[:16]


def apply_strategy(config: dict, strategy: str, **kwargs) -> dict:
    """Apply control strategy to config.

    Args:
        config: Base HOUSE_CONFIG dict
        strategy: Strategy identifier (e.g. 'hp_fixed_45', 'qsh_capped')
        **kwargs: Additional parameters:
            thermostat_setpoint: Setpoint for stock thermostat [°C]
            schedule: 'continuous' or 'night_setback'
            qsh_target: QSH target temp [°C] (for qsh strategies)

    Returns:
        Modified config dict with strategy parameters set.
    """
    cfg = dict(config)
    twin = dict(cfg.get("twin", {}))
    sim = dict(twin.get("simulation", {}))

    # Thermostat settings (applied to all stock HP strategies)
    thermostat_setpoint = kwargs.get("thermostat_setpoint", 21.0)
    schedule = kwargs.get("schedule", "continuous")

    if strategy == "stock":
        # Legacy: fixed flow at flow_max (55°C), no thermostat
        # Kept for backward compatibility — use hp_fixed_55 instead
        sim["fixed_flow_temp"] = cfg.get("flow_max", 55.0)
        sim["strategy"] = "stock"
    elif strategy == "stock_weather_comp":
        # Weather-compensated stock: flow varies with outdoor temp via linear curve.
        # Based on MCS MIS 3005 guidance for panel radiator systems.
        sim["weather_comp"] = {
            "enabled": True,
            "base_flow": 42.5,
            "slope": -0.75,
            "min_flow": 25.0,
            "max_flow": 50.0,
        }
        sim["strategy"] = "stock_weather_comp"
        sim["thermostat_setpoint"] = thermostat_setpoint
        sim["thermostat_deadband"] = 0.5
        sim["schedule"] = schedule
    elif strategy.startswith("hp_fixed_"):
        # HP fixed flow with thermostat
        flow_temp = HP_FIXED_FLOWS.get(strategy)
        if flow_temp is None:
            raise ValueError(f"Unknown HP fixed flow strategy: {strategy}")
        sim["fixed_flow_temp"] = flow_temp
        sim["strategy"] = strategy
        sim["thermostat_setpoint"] = thermostat_setpoint
        sim["thermostat_deadband"] = 0.5
        sim["schedule"] = schedule
    elif strategy == "hp_wc":
        # Manufacturer weather compensation: curve selection is a batch dimension,
        # not a config mutation. The curve key is passed via strategy_kwargs.
        sim["strategy"] = "hp_wc"
        sim["thermostat_setpoint"] = thermostat_setpoint
        sim["thermostat_deadband"] = 0.5
        sim["schedule"] = schedule
    elif strategy == "qsh_capped":
        sim["strategy"] = "qsh_capped"
        # QSH uses its own target temp, not the stock thermostat
        qsh_target = kwargs.get("qsh_target", 20.0)
        cfg["overtemp_protection"] = qsh_target
    elif strategy == "qsh_uncapped":
        sim["blend_cap_override"] = 1.0
        sim["strategy"] = "qsh_uncapped"
        qsh_target = kwargs.get("qsh_target", 20.0)
        cfg["overtemp_protection"] = qsh_target
    else:
        raise ValueError(f"Unknown strategy: {strategy}")

    twin["simulation"] = sim
    cfg["twin"] = twin
    return cfg


# ── Single simulation ─────────────────────────────────────────────────


def run_single_sim(args: Tuple) -> Dict[str, Any]:
    """Run a single simulation. Designed for multiprocessing.Pool.

    Args:
        args: Tuple of (config, weather_path, hours, strategy, profile_name, weather_name)

    Returns:
        Dict with run metrics
    """
    config, weather_path, hours, strategy, profile_name, weather_name, *extra = args
    strategy_kwargs = extra[0] if extra else {}
    run_id = str(uuid.uuid4())[:8]
    start_time = time.time()

    try:
        try:
            from qsh.drivers import create_driver  # external: requires full QSH install
        except ImportError:
            raise ImportError(
                f"Strategy '{strategy}' requires the full QSH package "
                f"(qsh.drivers). The public twin repo only supports stock "
                f"HP strategies (hp_fixed_*, hp_wc, stock, stock_weather_comp). "
                f"QSH strategies (qsh_capped, qsh_uncapped) require the "
                f"private QSH installation."
            )

        # Apply strategy
        cfg = apply_strategy(config, strategy, **strategy_kwargs)

        # Set weather source
        if weather_path:
            cfg.setdefault("twin", {}).setdefault("weather", {})["csv_path"] = weather_path

        # Create driver and pipeline
        driver = create_driver(cfg)
        driver.setup(cfg)

        # Only build RL pipeline for QSH strategies (not stock, WC, or fixed flow)
        controllers = None
        if strategy not in ("stock", "stock_weather_comp", "hp_wc") and not strategy.startswith("hp_fixed_"):
            from qsh.pipeline import build_pipeline, run_cycle  # external: requires full QSH install
            from qsh.debounce import ControlDebouncer  # external: requires full QSH install
            from qsh.rl_model import ActorCritic, AdaptiveStateBuilder  # external: requires full QSH install
            import torch.optim as optim

            state_builder = AdaptiveStateBuilder(cfg)
            model = ActorCritic(state_builder.state_dim, 2)
            optimizer = optim.Adam(model.parameters(), lr=1e-4)
            controllers = build_pipeline(
                cfg,
                zone_offsets={},
                model=model,
                optimizer=optimizer,
                checkpoint_path=None,
                debouncer=ControlDebouncer(),
            )

        # Thermostat + schedule state for stock HP strategies
        thermostat_on = True  # Start with HP on (cold start)
        sim_cfg = cfg.get("twin", {}).get("simulation", {})
        thermostat_setpoint = sim_cfg.get("thermostat_setpoint", 21.0)
        thermostat_deadband = sim_cfg.get("thermostat_deadband", 0.5)
        schedule = sim_cfg.get("schedule", "continuous")

        # Metrics accumulators
        total_cycles = int(hours * CYCLES_PER_HOUR)

        # Burn-in: first N hours excluded from metrics (initial warm-up)
        burn_in_hours = cfg.get("twin", {}).get("simulation", {}).get("burn_in_hours", 2)
        burn_in_cycles = int(burn_in_hours * CYCLES_PER_HOUR)

        prev_flow, prev_mode, prev_demand = 35.0, "heat", 0.0
        total_kwh = 0.0
        total_cost = 0.0
        cop_sum, cop_count = 0.0, 0
        flow_temps: List[float] = []
        room_temps_all: List[float] = []
        min_room_temp = 100.0
        hours_below_setpoint = 0.0
        setpoint = cfg.get("overtemp_protection", 21.0)
        hourly_data: List[Dict] = []

        # Per-hour accumulators
        hour_kwh = 0.0
        hour_cost = 0.0
        hour_cop_sum, hour_cop_count = 0.0, 0
        hour_room_sum, hour_room_count = 0.0, 0
        hour_flow_sum, hour_flow_count = 0.0, 0
        hour_power_sum, hour_power_count = 0.0, 0
        hour_outdoor = 5.0

        for cycle in range(total_cycles):
            inputs = driver.read_inputs(cfg)

            if strategy == "stock":
                # Legacy stock: fixed 55°C, always heat, no thermostat
                from twin.signal import OutputBlock
                fixed_flow = cfg["twin"]["simulation"].get("fixed_flow_temp", 55.0)
                out = OutputBlock(
                    optimal_flow=fixed_flow,
                    applied_flow=fixed_flow,
                    applied_mode="heat",
                )
                driver.write_outputs(out, cfg)
            elif strategy.startswith("hp_fixed_") or strategy == "stock_weather_comp":
                # HP fixed flow (or weather comp) with thermostat + schedule
                from twin.signal import OutputBlock

                # Get current mean room temp
                avg_room = (
                    sum(inputs.room_temps.values()) / len(inputs.room_temps)
                    if inputs.room_temps
                    else 20.0
                )

                # Check schedule
                heating_available = schedule_active(cycle, schedule)
                if not heating_available:
                    # Schedule says OFF — force heating off regardless of thermostat
                    thermostat_on = False
                    mode = "off"
                else:
                    # Schedule says ON — use thermostat
                    effective_sp = get_effective_setpoint(
                        thermostat_setpoint, cycle, schedule
                    )
                    thermostat_on = thermostat_step(
                        avg_room, thermostat_on, effective_sp, thermostat_deadband
                    )
                    mode = "heat" if thermostat_on else "off"

                # Determine flow temp
                if strategy == "stock_weather_comp":
                    wc = cfg["twin"]["simulation"].get("weather_comp", {})
                    outdoor = inputs.outdoor_temp
                    base = wc.get("base_flow", 42.5)
                    slope = wc.get("slope", -0.75)
                    flow = base + slope * outdoor
                    flow = max(wc.get("min_flow", 25.0), min(wc.get("max_flow", 50.0), flow))
                else:
                    flow = cfg["twin"]["simulation"].get("fixed_flow_temp", 55.0)

                out = OutputBlock(
                    optimal_flow=flow,
                    applied_flow=flow,
                    applied_mode=mode,
                )
                driver.write_outputs(out, cfg)
            elif strategy == "hp_wc":
                # Manufacturer weather compensation: flow varies per named curve
                from twin.signal import OutputBlock
                from twin.wc_curves import wc_flow_temp, WC_CURVES

                wc_curve = strategy_kwargs.get("wc_curve", "mcs_generic")
                curve_def = WC_CURVES.get(wc_curve, WC_CURVES["mcs_generic"])
                outdoor = inputs.outdoor_temp
                flow = wc_flow_temp(
                    outdoor_temp=outdoor,
                    curve_points=curve_def["points"],
                    min_flow=curve_def.get("min_flow", 25.0),
                    max_flow=curve_def.get("max_flow", 55.0),
                )

                # Get current mean room temp
                avg_room = (
                    sum(inputs.room_temps.values()) / len(inputs.room_temps)
                    if inputs.room_temps
                    else 20.0
                )

                # Check schedule
                heating_available = schedule_active(cycle, schedule)
                if not heating_available:
                    thermostat_on = False
                    mode = "off"
                else:
                    effective_sp = get_effective_setpoint(
                        thermostat_setpoint, cycle, schedule
                    )
                    thermostat_on = thermostat_step(
                        avg_room, thermostat_on, effective_sp, thermostat_deadband
                    )
                    mode = "heat" if thermostat_on else "off"

                out = OutputBlock(
                    optimal_flow=flow,
                    applied_flow=flow,
                    applied_mode=mode,
                )
                driver.write_outputs(out, cfg)
            else:
                # QSH strategies (existing code — no changes)
                from qsh.pipeline import run_cycle  # external: requires full QSH install
                ctx = run_cycle(
                    controllers,
                    cfg,
                    cycle,
                    prev_flow=prev_flow,
                    prev_mode=prev_mode,
                    prev_demand=prev_demand,
                    inputs=inputs,
                )
                if ctx.outputs:
                    driver.write_outputs(ctx.outputs, cfg)
                prev_flow = ctx.optimal_flow
                prev_mode = ctx.optimal_mode
                prev_demand = ctx.smoothed_demand

            driver.wait()

            # Re-read inputs AFTER physics step to capture current-cycle metrics
            post_inputs = driver.read_inputs(cfg)

            if cycle >= burn_in_cycles:
                # Collect metrics from post-step InputBlock (not pre-step)
                power_kw = post_inputs.hp_power
                cop = post_inputs.hp_cop
                rate = post_inputs.current_rate or 0.245
                avg_room = (
                    sum(post_inputs.room_temps.values()) / len(post_inputs.room_temps)
                    if post_inputs.room_temps
                    else 20.0
                )

                cycle_kwh = power_kw * (30.0 / 3600.0)
                cycle_cost = cycle_kwh * rate

                total_kwh += cycle_kwh
                total_cost += cycle_cost
                if cop > 0:
                    cop_sum += cop
                    cop_count += 1
                flow_temps.append(post_inputs.hp_flow_temp)
                room_temps_all.append(avg_room)
                min_room_temp = min(min_room_temp, min(post_inputs.room_temps.values()))
                if avg_room < setpoint:
                    hours_below_setpoint += 30.0 / 3600.0

                # Per-hour accumulators
                hour_kwh += cycle_kwh
                hour_cost += cycle_cost
                if cop > 0:
                    hour_cop_sum += cop
                    hour_cop_count += 1
                hour_room_sum += avg_room
                hour_room_count += 1
                hour_flow_sum += post_inputs.hp_flow_temp
                hour_flow_count += 1
                hour_power_sum += power_kw
                hour_power_count += 1
                hour_outdoor = post_inputs.outdoor_temp

            # Hourly rollover
            if (cycle + 1) % CYCLES_PER_HOUR == 0:
                hour_num = (cycle + 1) // CYCLES_PER_HOUR - 1
                if cycle >= burn_in_cycles:
                    hourly_data.append(
                        {
                            "run_id": run_id,
                            "hour": hour_num,
                            "outdoor_temp": hour_outdoor,
                            "mean_room_temp": hour_room_sum / max(hour_room_count, 1),
                            "flow_temp": hour_flow_sum / max(hour_flow_count, 1),
                            "hp_power_kw": hour_power_sum / max(hour_power_count, 1),
                            "cop": hour_cop_sum / max(hour_cop_count, 1) if hour_cop_count else 0,
                            "kwh_consumed": hour_kwh,
                            "cost_gbp": hour_cost,
                        }
                    )
                hour_kwh = hour_cost = 0.0
                hour_cop_sum = hour_cop_count = 0
                hour_room_sum = hour_room_count = 0
                hour_flow_sum = hour_flow_count = 0
                hour_power_sum = hour_power_count = 0

        driver.teardown([])
        elapsed = time.time() - start_time
        metered_hours = hours - burn_in_hours

        return {
            "run_id": run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "archetype": profile_name,
            "weather_location": weather_name,
            "strategy": strategy,
            "hours_simulated": metered_hours,
            "total_kwh": total_kwh,
            "total_cost_gbp": total_cost,
            "mean_cop": cop_sum / max(cop_count, 1),
            "mean_room_temp": sum(room_temps_all) / max(len(room_temps_all), 1),
            "min_room_temp": min_room_temp,
            "hours_below_setpoint": hours_below_setpoint,
            "mean_flow_temp": sum(flow_temps) / max(len(flow_temps), 1),
            "max_flow_temp": max(flow_temps) if flow_temps else 0,
            "heat_source": "hp",
            "flow_strategy": strategy,
            "thermostat_setpoint": thermostat_setpoint,
            "schedule": schedule,
            "wc_curve": strategy_kwargs.get("wc_curve", "none"),
            "profile_yaml": profile_name,
            "weather_csv": weather_name,
            "config_hash": config_hash(cfg),
            "hourly_data": hourly_data,
            "elapsed_s": elapsed,
            "error": None,
        }

    except Exception as exc:
        logger.error("Simulation failed for %s × %s × %s: %s", profile_name, weather_name, strategy, exc)
        return {
            "run_id": run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "archetype": profile_name,
            "weather_location": weather_name,
            "strategy": strategy,
            "hours_simulated": hours,
            "error": str(exc),
        }


# ── Results storage ───────────────────────────────────────────────────


def store_result(conn: sqlite3.Connection, result: Dict) -> None:
    """Write a single simulation result to SQLite."""
    if result.get("error"):
        logger.warning("Skipping failed run %s: %s", result["run_id"], result["error"])
        return

    conn.execute(
        """
        INSERT OR REPLACE INTO runs (
            run_id, timestamp, archetype, weather_location, strategy,
            hours_simulated, total_kwh, total_cost_gbp, mean_cop,
            mean_room_temp, min_room_temp, hours_below_setpoint,
            mean_flow_temp, max_flow_temp,
            heat_source, flow_strategy, thermostat_setpoint, schedule,
            wc_curve,
            profile_yaml, weather_csv, config_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            result["run_id"],
            result["timestamp"],
            result["archetype"],
            result["weather_location"],
            result["strategy"],
            result["hours_simulated"],
            result.get("total_kwh"),
            result.get("total_cost_gbp"),
            result.get("mean_cop"),
            result.get("mean_room_temp"),
            result.get("min_room_temp"),
            result.get("hours_below_setpoint"),
            result.get("mean_flow_temp"),
            result.get("max_flow_temp"),
            result.get("heat_source"),
            result.get("flow_strategy"),
            result.get("thermostat_setpoint"),
            result.get("schedule"),
            result.get("wc_curve", "none"),
            result.get("profile_yaml"),
            result.get("weather_csv"),
            result.get("config_hash"),
        ),
    )

    # Insert hourly data
    for h in result.get("hourly_data", []):
        conn.execute(
            """
            INSERT OR REPLACE INTO hourly (
                run_id, hour, outdoor_temp, mean_room_temp,
                flow_temp, hp_power_kw, cop, kwh_consumed, cost_gbp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                h["run_id"],
                h["hour"],
                h.get("outdoor_temp"),
                h.get("mean_room_temp"),
                h.get("flow_temp"),
                h.get("hp_power_kw"),
                h.get("cop"),
                h.get("kwh_consumed"),
                h.get("cost_gbp"),
            ),
        )

    conn.commit()


def compute_savings(conn: sqlite3.Connection) -> None:
    """Compute savings: QSH vs best HP stock baseline per archetype/weather."""
    cursor = conn.execute("""
        SELECT DISTINCT archetype, weather_location FROM runs
        WHERE strategy LIKE 'qsh_%'
    """)
    for archetype, weather_location in cursor.fetchall():
        # Find best (lowest kWh) HP stock run for this combo
        stock_best = conn.execute("""
            SELECT MIN(total_kwh), mean_cop FROM runs
            WHERE archetype=? AND weather_location=?
              AND strategy LIKE 'hp_fixed_%'
              AND total_kwh IS NOT NULL
        """, (archetype, weather_location)).fetchone()

        if not stock_best or stock_best[0] is None:
            # Fall back to legacy 'stock' strategy
            stock_best = conn.execute("""
                SELECT total_kwh, mean_cop FROM runs
                WHERE archetype=? AND weather_location=? AND strategy='stock'
                ORDER BY timestamp DESC LIMIT 1
            """, (archetype, weather_location)).fetchone()

        if not stock_best or stock_best[0] is None:
            continue

        stock_kwh, stock_cop = stock_best

        for strategy in ("qsh_capped", "qsh_uncapped"):
            rows = conn.execute("""
                SELECT run_id, total_kwh, mean_cop FROM runs
                WHERE archetype=? AND weather_location=? AND strategy=?
                  AND total_kwh IS NOT NULL
            """, (archetype, weather_location, strategy)).fetchall()

            for row in rows:
                run_id, qsh_kwh, qsh_cop = row
                if stock_kwh == 0:
                    continue
                savings_kwh = stock_kwh - (qsh_kwh or 0)
                savings_pct = (savings_kwh / stock_kwh) * 100.0
                cop_improvement = (qsh_cop or 0) - (stock_cop or 0)
                conn.execute("""
                    UPDATE runs SET
                        savings_kwh=?, savings_pct=?, mean_cop_improvement=?
                    WHERE run_id=?
                """, (savings_kwh, savings_pct, cop_improvement, run_id))

    # Also compute savings vs best WC baseline per archetype/weather
    cursor2 = conn.execute("""
        SELECT DISTINCT archetype, weather_location FROM runs
        WHERE strategy LIKE 'qsh_%'
    """)
    for archetype, weather_location in cursor2.fetchall():
        # Find best (lowest kWh) WC run for this archetype/weather
        wc_best = conn.execute("""
            SELECT total_kwh, mean_cop FROM runs
            WHERE archetype=? AND weather_location=? AND strategy='hp_wc'
            AND thermostat_setpoint=21.0 AND schedule='continuous'
            AND total_kwh IS NOT NULL
            ORDER BY total_kwh ASC LIMIT 1
        """, (archetype, weather_location)).fetchone()

        if not wc_best or wc_best[0] is None:
            continue

        wc_kwh, wc_cop = wc_best

        for strategy in ("qsh_capped", "qsh_uncapped"):
            row = conn.execute("""
                SELECT run_id, total_kwh, mean_cop FROM runs
                WHERE archetype=? AND weather_location=? AND strategy=?
                AND total_kwh IS NOT NULL
                ORDER BY timestamp DESC LIMIT 1
            """, (archetype, weather_location, strategy)).fetchone()

            if row and wc_kwh and wc_kwh > 0:
                run_id, qsh_kwh, qsh_cop = row
                savings_vs_wc = wc_kwh - (qsh_kwh or 0)
                savings_vs_wc_pct = (savings_vs_wc / wc_kwh) * 100.0
                conn.execute("""
                    UPDATE runs SET savings_vs_wc_kwh=?, savings_vs_wc_pct=?
                    WHERE run_id=?
                """, (savings_vs_wc, savings_vs_wc_pct, run_id))

    conn.commit()


# ── Main batch runner ─────────────────────────────────────────────────


def discover_files(directory: str, extensions: Tuple[str, ...]) -> List[str]:
    """Find files with given extensions in directory."""
    result = []
    d = Path(directory)
    if not d.exists():
        return result
    for ext in extensions:
        result.extend(sorted(str(p) for p in d.glob(f"*{ext}")))
    return result


def run_batch(
    profiles_dir: str,
    weather_dir: str,
    hours: float = 168.0,
    workers: int = 4,
    output_dir: str = "data/results/",
    strategies: Optional[List[str]] = None,
    setpoints: Optional[List[float]] = None,
    schedules: Optional[List[str]] = None,
    qsh_targets: Optional[List[float]] = None,
    wc_curves: Optional[List[str]] = None,
) -> str:
    """Run batch simulations and store results.

    Args:
        profiles_dir: Directory containing building profile YAMLs
        weather_dir: Directory containing weather CSVs
        hours: Hours to simulate per run
        workers: Number of parallel workers
        output_dir: Directory for results database
        strategies: List of strategies to run (default: all)
        setpoints: Thermostat setpoints to test (default: 18-25)
        schedules: Heating schedules to test (default: continuous + night_setback)
        qsh_targets: QSH target temps to test (default: 19, 20, 21)
        wc_curves: WC curve keys for hp_wc strategy (default: moderate curves)

    Returns:
        Path to the fleet.db file
    """
    from twin.wc_curves import WC_MODERATE_CURVES

    if strategies is None:
        strategies = list(STRATEGIES)

    # Defaults
    setpoints = setpoints or list(THERMOSTAT_SETPOINTS)
    schedules = schedules or list(HP_SCHEDULES)
    qsh_targets = qsh_targets or list(QSH_TARGETS)
    wc_curves_list = wc_curves if wc_curves is not None else list(WC_MODERATE_CURVES)

    db_path = os.path.join(output_dir, "fleet.db")

    profiles = discover_files(profiles_dir, (".yaml", ".yml"))
    weather_files = discover_files(weather_dir, (".csv",))

    if not profiles:
        raise FileNotFoundError(f"No YAML profiles found in {profiles_dir}")
    if not weather_files:
        weather_files = [None]  # Use static weather

    # Build job list
    jobs = []
    for profile_path in profiles:
        profile_name = Path(profile_path).stem
        try:
            config = load_profile(profile_path)
        except Exception as exc:
            logger.error("Failed to load profile %s: %s", profile_path, exc)
            continue

        for weather_path in weather_files:
            weather_name = Path(weather_path).stem if weather_path else "static"
            for strategy in strategies:
                if strategy.startswith("hp_fixed_") or strategy == "stock_weather_comp":
                    # HP fixed flow / weather comp: iterate over setpoints × schedules
                    for sp in setpoints:
                        for sched in schedules:
                            kwargs = {
                                "thermostat_setpoint": sp,
                                "schedule": sched,
                            }
                            jobs.append((
                                config, weather_path, hours, strategy,
                                profile_name, weather_name, kwargs,
                            ))
                elif strategy == "hp_wc":
                    # Manufacturer WC: iterate curves × setpoints × schedules
                    for wc_curve in wc_curves_list:
                        for sp in setpoints:
                            for sched in schedules:
                                kwargs = {
                                    "thermostat_setpoint": sp,
                                    "schedule": sched,
                                    "wc_curve": wc_curve,
                                }
                                jobs.append((
                                    config, weather_path, hours, strategy,
                                    profile_name, weather_name, kwargs,
                                ))
                elif strategy.startswith("qsh_"):
                    # QSH: iterate over target temps only (no stock thermostat)
                    for target in qsh_targets:
                        kwargs = {"qsh_target": target}
                        jobs.append((
                            config, weather_path, hours, strategy,
                            profile_name, weather_name, kwargs,
                        ))
                else:
                    # Legacy stock or other — no iteration
                    jobs.append((
                        config, weather_path, hours, strategy,
                        profile_name, weather_name, {},
                    ))

    logger.info("Batch: %d jobs queued", len(jobs))

    if not jobs:
        raise ValueError("No valid jobs to run")

    # Run simulations
    conn = init_db(db_path)
    completed = 0
    total = len(jobs)

    if workers <= 1:
        # Sequential execution (for debugging)
        for job in jobs:
            result = run_single_sim(job)
            store_result(conn, result)
            completed += 1
            _log_progress(completed, total, result)
    else:
        with Pool(processes=workers) as pool:
            for result in pool.imap_unordered(run_single_sim, jobs):
                store_result(conn, result)
                completed += 1
                _log_progress(completed, total, result)

    # Post-process savings
    compute_savings(conn)
    conn.close()

    logger.info("Batch complete: %d/%d runs stored in %s", completed, total, db_path)
    return db_path


def _log_progress(completed: int, total: int, result: Dict) -> None:
    """Log batch progress."""
    if result.get("error"):
        logger.warning(
            "[%d/%d] %s × %s × %s → FAILED: %s",
            completed,
            total,
            result["archetype"],
            result["weather_location"],
            result["strategy"],
            result["error"],
        )
    else:
        sp = result.get("thermostat_setpoint", "")
        sched = result.get("schedule", "")
        wc = result.get("wc_curve", "none")
        wc_str = f" [{wc}]" if wc != "none" else ""
        cop = result.get("mean_cop", 0) or 0
        room = result.get("mean_room_temp", 0) or 0
        kwh = result.get("total_kwh", 0) or 0
        elapsed = result.get("elapsed_s", 0)
        logger.info(
            "[%d/%d] %s × %s × %s%s (sp=%.0f, %s) → COP %.2f, room %.1f°C, %.1f kWh (%.1fs)",
            completed,
            total,
            result["archetype"],
            result["weather_location"],
            result["strategy"],
            wc_str,
            sp,
            sched,
            cop,
            room,
            kwh,
            elapsed,
        )


# ── CLI ───────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="QSH Digital Twin — Batch Fleet Simulator",
    )
    parser.add_argument("--profiles", required=True, help="Directory containing building profile YAMLs")
    parser.add_argument("--weather", required=True, help="Directory containing weather CSVs")
    parser.add_argument("--hours", type=float, default=168.0, help="Hours to simulate per run (default: 168 = 1 week)")
    parser.add_argument("--workers", type=int, default=4, help="Number of parallel workers (default: 4)")
    parser.add_argument("--output", default="data/results/", help="Output directory for fleet.db")
    parser.add_argument(
        "--strategies", nargs="+", default=None, choices=STRATEGIES, help="Strategies to run (default: all)"
    )
    parser.add_argument(
        "--setpoints", nargs="+", type=float, default=None,
        help="Thermostat setpoints to test (default: 18-25 in 1°C steps)"
    )
    parser.add_argument(
        "--schedules", nargs="+", default=None,
        choices=["continuous", "night_setback", "timed"],
        help="Heating schedules to test (default: continuous + night_setback for HP)"
    )
    parser.add_argument(
        "--qsh-targets", nargs="+", type=float, default=None,
        help="QSH target temps to test (default: 19, 20, 21)"
    )
    parser.add_argument(
        "--burn-in", type=float, default=2.0,
        help="Burn-in hours excluded from metrics (default: 2)"
    )
    parser.add_argument(
        "--wc-curves", nargs="+", default=None,
        help="WC curve keys to simulate (default: moderate curves). "
        "Use 'all' for all curves, or list specific keys."
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    wc_curves = args.wc_curves
    if wc_curves and "all" in wc_curves:
        from twin.wc_curves import WC_ALL_CURVES
        wc_curves = list(WC_ALL_CURVES)

    run_batch(
        profiles_dir=args.profiles,
        weather_dir=args.weather,
        hours=args.hours,
        workers=args.workers,
        output_dir=args.output,
        strategies=args.strategies,
        setpoints=args.setpoints,
        schedules=args.schedules,
        qsh_targets=args.qsh_targets,
        wc_curves=wc_curves,
    )


if __name__ == "__main__":
    main()
