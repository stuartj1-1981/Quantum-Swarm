"""
Generate building archetype profiles for QSH fleet simulation.

Produces YAML profiles for common UK dwelling types, ready for use
with twin/batch.py.

Usage:
    python -m qsh.twin.archetypes --output /mnt/d/qsh-data/profiles/
    python -m qsh.twin.archetypes --list
    python -m qsh.twin.archetypes --output profiles/ --archetypes semi_1970s newbuild_2020s
"""

from __future__ import annotations

import argparse
import logging
import os
from datetime import date
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Compass direction -> solar gain factor (matches config.COMPASS_SOLAR_GAIN).
# South-facing gets maximum solar gain (1.0), north-facing minimal (0.10).
# Duplicated here to avoid importing config.py which runs YAML loading at
# import time.
COMPASS_SOLAR_GAIN = {
    "N": 0.10,
    "NE": 0.15,
    "E": 0.30,
    "SE": 0.60,
    "S": 1.00,
    "SW": 0.60,
    "W": 0.30,
    "NW": 0.15,
    "interior": 0.20,
}

# ── Default COP map — typical mid-range UK ASHP ─────────────────────
# Calibrated so bilinear interpolation at (outdoor=5, flow=33) ≈ 3.9,
# matching live system data (28 Feb 2026).
DEFAULT_COP_MAP = [
    # Row: outdoor=-10°C (Scottish design conditions — Carnot degradation)
    {"outdoor": -10, "flow": 25, "cop": 2.5},
    {"outdoor": -10, "flow": 35, "cop": 2.1},
    {"outdoor": -10, "flow": 45, "cop": 1.8},
    {"outdoor": -10, "flow": 55, "cop": 1.5},
    # Row: flow=25°C (very low flow — max COP operating point)
    {"outdoor": -5, "flow": 25, "cop": 3.2},
    {"outdoor":  0, "flow": 25, "cop": 3.7},
    {"outdoor":  5, "flow": 25, "cop": 4.3},
    {"outdoor": 10, "flow": 25, "cop": 4.8},
    {"outdoor": 15, "flow": 25, "cop": 5.2},
    # Row: flow=35°C
    {"outdoor": -5, "flow": 35, "cop": 2.8},
    {"outdoor":  0, "flow": 35, "cop": 3.2},
    {"outdoor":  5, "flow": 35, "cop": 3.8},
    {"outdoor": 10, "flow": 35, "cop": 4.3},
    {"outdoor": 15, "flow": 35, "cop": 4.8},
    # Row: flow=45°C
    {"outdoor": -5, "flow": 45, "cop": 2.2},
    {"outdoor":  0, "flow": 45, "cop": 2.6},
    {"outdoor":  5, "flow": 45, "cop": 3.0},
    {"outdoor": 10, "flow": 45, "cop": 3.5},
    {"outdoor": 15, "flow": 45, "cop": 3.9},
    # Row: flow=55°C
    {"outdoor": -5, "flow": 55, "cop": 1.8},
    {"outdoor":  0, "flow": 55, "cop": 2.1},
    {"outdoor":  5, "flow": 55, "cop": 2.5},
    {"outdoor": 10, "flow": 55, "cop": 2.8},
    {"outdoor": 15, "flow": 55, "cop": 3.2},
]

# ── UK Dwelling Archetypes ───────────────────────────────────────────

UK_ARCHETYPES: Dict[str, Dict[str, Any]] = {
    # semi_1970s: 85m² cavity wall semi-detached
    # SAP ref: RdSAP Band D/E, ~250-300 kWh/m²/yr
    # Peak loss 7.0 kW at -3°C design: U_eff = 7.0 / (21 - (-3)) = 0.29 kW/°C
    # Cross-check: 0.29/85 × 1000 = ~3.4 W/m²K envelope — plausible for uninsulated cavity
    "semi_1970s": {
        "label": "1970s Semi-Detached",
        "total_area": 85,
        "peak_loss": 7.0,
        "peak_ext": -3,
        "hp_capacity_kw": 8.5,
        "infiltration_ach": 0.7,
        "heat_up_tau_h": 1.0,
        "emitter_exponent": 1.15,
        "notes": "Cavity wall, partial insulation, common UK stock",
        "rooms": {
            "lounge": 18.0,
            "kitchen_diner": 25.0,
            "bedroom_1": 15.0,
            "bedroom_2": 12.0,
            "bathroom": 5.0,
            "hall": 10.0,
        },
        "facings": {
            "lounge": "S",
            "kitchen_diner": "N",
            "bedroom_1": "S",
            "bedroom_2": "N",
            "bathroom": "interior",
            "hall": "interior",
        },
        "emitter_kw": {
            "lounge": 2.0,
            "kitchen_diner": 2.2,
            "bedroom_1": 1.2,
            "bedroom_2": 1.0,
            "bathroom": 0.6,
            "hall": 0.8,
        },
        "ceiling_heights": {
            "lounge": 2.4,
            "kitchen_diner": 2.4,
            "bedroom_1": 2.4,
            "bedroom_2": 2.4,
            "bathroom": 2.4,
            "hall": 2.4,
        },
    },
    # semi_1970s_retro: 85m² retrofitted semi-detached (EWI, loft, floor)
    # SAP ref: RdSAP Band C, ~150-200 kWh/m²/yr
    # Peak loss 4.5 kW at -3°C: U_eff = 4.5 / 24 = 0.19 kW/°C
    # Cross-check: 0.19/85 × 1000 = ~2.2 W/m²K — plausible post-retrofit
    "semi_1970s_retro": {
        "label": "1970s Semi (Retrofitted)",
        "total_area": 85,
        "peak_loss": 4.5,
        "peak_ext": -3,
        "hp_capacity_kw": 6.0,
        "infiltration_ach": 0.4,
        "heat_up_tau_h": 1.2,
        "emitter_exponent": 1.15,
        "notes": "EWI, loft, floor insulation done",
        "rooms": {
            "lounge": 18.0,
            "kitchen_diner": 25.0,
            "bedroom_1": 15.0,
            "bedroom_2": 12.0,
            "bathroom": 5.0,
            "hall": 10.0,
        },
        "facings": {
            "lounge": "S",
            "kitchen_diner": "N",
            "bedroom_1": "S",
            "bedroom_2": "N",
            "bathroom": "interior",
            "hall": "interior",
        },
        "emitter_kw": {
            "lounge": 1.6,
            "kitchen_diner": 1.8,
            "bedroom_1": 1.0,
            "bedroom_2": 0.8,
            "bathroom": 0.5,
            "hall": 0.6,
        },
        "ceiling_heights": {
            "lounge": 2.4,
            "kitchen_diner": 2.4,
            "bedroom_1": 2.4,
            "bedroom_2": 2.4,
            "bathroom": 2.4,
            "hall": 2.4,
        },
    },
    # detached_1990s: 120m² Part-L compliant detached
    # SAP ref: RdSAP Band C/D, ~200-250 kWh/m²/yr
    # Peak loss 8.0 kW at -3°C: U_eff = 8.0 / 24 = 0.33 kW/°C
    # Cross-check: 0.33/120 × 1000 = ~2.8 W/m²K — reasonable for 1990s fabric
    "detached_1990s": {
        "label": "1990s Detached",
        "total_area": 120,
        "peak_loss": 8.0,
        "peak_ext": -3,
        "hp_capacity_kw": 10.0,
        "infiltration_ach": 0.5,
        "heat_up_tau_h": 1.0,
        "emitter_exponent": 1.15,
        "notes": "Part-L compliant, reasonable fabric",
        "rooms": {
            "lounge": 25.0,
            "kitchen_diner": 28.0,
            "bedroom_1": 16.0,
            "bedroom_2": 14.0,
            "bedroom_3": 12.0,
            "bathroom": 7.0,
            "hall": 12.0,
            "utility": 6.0,
        },
        "facings": {
            "lounge": "S",
            "kitchen_diner": "NW",
            "bedroom_1": "S",
            "bedroom_2": "N",
            "bedroom_3": "E",
            "bathroom": "interior",
            "hall": "interior",
            "utility": "N",
        },
        "emitter_kw": {
            "lounge": 2.2,
            "kitchen_diner": 2.4,
            "bedroom_1": 1.4,
            "bedroom_2": 1.2,
            "bedroom_3": 1.0,
            "bathroom": 0.6,
            "hall": 0.8,
            "utility": 0.5,
        },
        "ceiling_heights": {
            "lounge": 2.4,
            "kitchen_diner": 2.4,
            "bedroom_1": 2.4,
            "bedroom_2": 2.4,
            "bedroom_3": 2.4,
            "bathroom": 2.4,
            "hall": 2.4,
            "utility": 2.4,
        },
    },
    # terrace_victorian: 75m² solid-wall Victorian mid-terrace
    # SAP ref: RdSAP Band E/F, ~300-400 kWh/m²/yr
    # Peak loss 8.5 kW at -3°C: U_eff = 8.5 / 24 = 0.35 kW/°C
    # Cross-check: 0.35/75 × 1000 = ~4.7 W/m²K — high, as expected for solid walls + high ceilings
    "terrace_victorian": {
        "label": "Victorian Mid-Terrace",
        "total_area": 75,
        "peak_loss": 8.5,
        "peak_ext": -3,
        "hp_capacity_kw": 10.0,
        "infiltration_ach": 1.0,
        "heat_up_tau_h": 1.5,
        "emitter_exponent": 1.25,
        "notes": "Solid walls, high ceilings, draughty",
        "rooms": {
            "front_reception": 16.0,
            "rear_reception": 14.0,
            "kitchen": 12.0,
            "bedroom_1": 14.0,
            "bedroom_2": 10.0,
            "bathroom": 5.0,
            "hall": 4.0,
        },
        "facings": {
            "front_reception": "N",
            "rear_reception": "S",
            "kitchen": "S",
            "bedroom_1": "N",
            "bedroom_2": "S",
            "bathroom": "interior",
            "hall": "interior",
        },
        "emitter_kw": {
            "front_reception": 2.4,
            "rear_reception": 2.0,
            "kitchen": 1.6,
            "bedroom_1": 1.8,
            "bedroom_2": 1.2,
            "bathroom": 0.8,
            "hall": 0.6,
        },
        "ceiling_heights": {
            "front_reception": 2.7,
            "rear_reception": 2.7,
            "kitchen": 2.7,
            "bedroom_1": 2.7,
            "bedroom_2": 2.7,
            "bathroom": 2.7,
            "hall": 2.7,
        },
    },
    # terrace_victorian_retro: 75m² retrofitted Victorian (IWI, draught-proofed)
    # SAP ref: RdSAP Band C/D, ~180-250 kWh/m²/yr
    # Peak loss 5.0 kW at -3°C: U_eff = 5.0 / 24 = 0.21 kW/°C
    # Cross-check: 0.21/75 × 1000 = ~2.8 W/m²K — plausible post-IWI
    "terrace_victorian_retro": {
        "label": "Victorian Terrace (Retrofitted)",
        "total_area": 75,
        "peak_loss": 5.0,
        "peak_ext": -3,
        "hp_capacity_kw": 6.0,
        "infiltration_ach": 0.5,
        "heat_up_tau_h": 1.2,
        "emitter_exponent": 1.15,
        "notes": "IWI, draught-proofed, secondary glazing",
        "rooms": {
            "front_reception": 16.0,
            "rear_reception": 14.0,
            "kitchen": 12.0,
            "bedroom_1": 14.0,
            "bedroom_2": 10.0,
            "bathroom": 5.0,
            "hall": 4.0,
        },
        "facings": {
            "front_reception": "N",
            "rear_reception": "S",
            "kitchen": "S",
            "bedroom_1": "N",
            "bedroom_2": "S",
            "bathroom": "interior",
            "hall": "interior",
        },
        "emitter_kw": {
            "front_reception": 1.6,
            "rear_reception": 1.4,
            "kitchen": 1.2,
            "bedroom_1": 1.2,
            "bedroom_2": 0.8,
            "bathroom": 0.6,
            "hall": 0.4,
        },
        "ceiling_heights": {
            "front_reception": 2.7,
            "rear_reception": 2.7,
            "kitchen": 2.7,
            "bedroom_1": 2.7,
            "bedroom_2": 2.7,
            "bathroom": 2.7,
            "hall": 2.7,
        },
    },
    # newbuild_2020s: 95m² Part-L 2021 new build with MVHR
    # SAP ref: RdSAP Band A/B, ~50-100 kWh/m²/yr
    # Peak loss 3.5 kW at -3°C: U_eff = 3.5 / 24 = 0.15 kW/°C
    # Cross-check: 0.15/95 × 1000 = ~1.5 W/m²K — consistent with Part-L 2021 fabric
    "newbuild_2020s": {
        "label": "2020s New Build",
        "total_area": 95,
        "peak_loss": 3.5,
        "peak_ext": -3,
        "hp_capacity_kw": 5.0,
        "infiltration_ach": 0.3,
        "heat_up_tau_h": 3.5,
        "emitter_exponent": 1.1,
        "notes": "Part-L 2021, MVHR, low fabric loss",
        "rooms": {
            "lounge": 20.0,
            "kitchen_diner": 22.0,
            "bedroom_1": 14.0,
            "bedroom_2": 12.0,
            "bedroom_3": 10.0,
            "bathroom": 6.0,
            "hall": 7.0,
            "en_suite": 4.0,
        },
        "facings": {
            "lounge": "S",
            "kitchen_diner": "SW",
            "bedroom_1": "S",
            "bedroom_2": "N",
            "bedroom_3": "E",
            "bathroom": "interior",
            "hall": "interior",
            "en_suite": "interior",
        },
        "emitter_kw": {
            "lounge": 1.2,
            "kitchen_diner": 1.4,
            "bedroom_1": 0.8,
            "bedroom_2": 0.7,
            "bedroom_3": 0.6,
            "bathroom": 0.4,
            "hall": 0.4,
            "en_suite": 0.3,
        },
        "ceiling_heights": {
            "lounge": 2.4,
            "kitchen_diner": 2.4,
            "bedroom_1": 2.4,
            "bedroom_2": 2.4,
            "bedroom_3": 2.4,
            "bathroom": 2.4,
            "hall": 2.4,
            "en_suite": 2.4,
        },
    },
    # bungalow_1960s: 70m² single-storey, large roof area
    # SAP ref: RdSAP Band D/E, ~250-350 kWh/m²/yr
    # Peak loss 6.0 kW at -3°C: U_eff = 6.0 / 24 = 0.25 kW/°C
    # Cross-check: 0.25/70 × 1000 = ~3.6 W/m²K — elevated due to large roof-to-floor ratio
    "bungalow_1960s": {
        "label": "1960s Bungalow",
        "total_area": 70,
        "peak_loss": 6.0,
        "peak_ext": -3,
        "hp_capacity_kw": 7.0,
        "infiltration_ach": 0.7,
        "heat_up_tau_h": 1.0,
        "emitter_exponent": 1.15,
        "notes": "Large roof area, often poorly insulated",
        "rooms": {
            "lounge": 20.0,
            "kitchen": 14.0,
            "bedroom_1": 14.0,
            "bedroom_2": 10.0,
            "bathroom": 6.0,
            "hall": 6.0,
        },
        "facings": {
            "lounge": "S",
            "kitchen": "N",
            "bedroom_1": "SE",
            "bedroom_2": "NW",
            "bathroom": "interior",
            "hall": "interior",
        },
        "emitter_kw": {
            "lounge": 2.0,
            "kitchen": 1.4,
            "bedroom_1": 1.2,
            "bedroom_2": 0.8,
            "bathroom": 0.6,
            "hall": 0.6,
        },
        "ceiling_heights": {
            "lounge": 2.4,
            "kitchen": 2.4,
            "bedroom_1": 2.4,
            "bedroom_2": 2.4,
            "bathroom": 2.4,
            "hall": 2.4,
        },
    },
    # flat_purpose: 55m² mid-floor purpose-built flat
    # SAP ref: RdSAP Band C/D, ~150-200 kWh/m²/yr
    # Peak loss 3.0 kW at -3°C: U_eff = 3.0 / 24 = 0.125 kW/°C
    # Cross-check: 0.125/55 × 1000 = ~2.3 W/m²K — low due to sheltered mid-floor position
    "flat_purpose": {
        "label": "Purpose-Built Flat",
        "total_area": 55,
        "peak_loss": 3.0,
        "peak_ext": -3,
        "hp_capacity_kw": 4.0,
        "infiltration_ach": 0.4,
        "heat_up_tau_h": 0.8,
        "emitter_exponent": 1.15,
        "notes": "Mid-floor, sheltered, low losses",
        "rooms": {
            "lounge": 18.0,
            "kitchen": 10.0,
            "bedroom_1": 12.0,
            "bedroom_2": 8.0,
            "bathroom": 4.0,
            "hall": 3.0,
        },
        "facings": {
            "lounge": "S",
            "kitchen": "N",
            "bedroom_1": "E",
            "bedroom_2": "W",
            "bathroom": "interior",
            "hall": "interior",
        },
        "emitter_kw": {
            "lounge": 1.0,
            "kitchen": 0.6,
            "bedroom_1": 0.7,
            "bedroom_2": 0.5,
            "bathroom": 0.3,
            "hall": 0.2,
        },
        "ceiling_heights": {
            "lounge": 2.4,
            "kitchen": 2.4,
            "bedroom_1": 2.4,
            "bedroom_2": 2.4,
            "bathroom": 2.4,
            "hall": 2.4,
        },
    },
}


# ── Profile generation ───────────────────────────────────────────────


def generate_profile(archetype_key: str) -> Dict[str, Any]:
    """Generate a complete YAML-ready profile dict for a given archetype.

    Args:
        archetype_key: Key into UK_ARCHETYPES (e.g. 'semi_1970s').

    Returns:
        Dict ready for yaml.dump(), matching the schema expected by
        batch.py load_profile() and engine.py ThermalEngine.__init__().

    Raises:
        KeyError: If archetype_key not in UK_ARCHETYPES.
    """
    if archetype_key not in UK_ARCHETYPES:
        raise KeyError(f"Unknown archetype '{archetype_key}'. Available: {sorted(UK_ARCHETYPES.keys())}")

    arch = UK_ARCHETYPES[archetype_key]
    rooms = dict(arch["rooms"])
    room_names = list(rooms.keys())

    # Start conditions: bedrooms at 16C, living spaces at 18C
    start_temps: Dict[str, float] = {}
    for name in room_names:
        if "bedroom" in name:
            start_temps[name] = 16.0
        else:
            start_temps[name] = 18.0

    # Room control mode: all indirect for fleet sim
    room_control_mode = {name: "indirect" for name in room_names}

    # Generate mock entity mappings for pipeline compatibility.
    # The pipeline (build_pipeline / run_cycle) and RL state builder
    # expect config["entities"] to exist.  The MockDriver never calls
    # HA, so these synthetic IDs just need to satisfy key lookups.
    entities: Dict[str, str] = {}
    for room_name in room_names:
        entities[f"{room_name}_temp_set_hum"] = f"climate.mock_{room_name}"
        entities[f"{room_name}_heating"] = f"number.mock_{room_name}_heating"

    # Top-level control / sensor entities (referenced by EnergyController,
    # HardwareController, CycleController, etc.)
    entities["pid_target_temperature"] = "input_number.mock_pid_target_temperature"
    entities["dfan_control_toggle"] = "input_boolean.mock_dfan_control"
    entities["flow_min_temp"] = "input_number.mock_flow_min_temperature"
    entities["flow_max_temp"] = "input_number.mock_flow_max_temperature"

    profile: Dict[str, Any] = {
        "_archetype": {
            "key": archetype_key,
            "label": arch["label"],
            "generated": str(date.today()),
        },
        "rooms": rooms,
        "facing_directions": dict(arch["facings"]),
        "facings": {
            room: COMPASS_SOLAR_GAIN.get(direction, COMPASS_SOLAR_GAIN["interior"])
            for room, direction in arch["facings"].items()
        },
        "emitter_kw": dict(arch["emitter_kw"]),
        "ceiling_heights": dict(arch["ceiling_heights"]),
        "room_control_mode": room_control_mode,
        "entities": entities,
        "zone_sensor_map": {},
        "overtemp_protection": 21.0,
        "flow_min": 25.0,
        "flow_max": 55.0,
        "peak_loss": arch["peak_loss"],
        "peak_ext": arch["peak_ext"],
        "thermal_mass_per_m2": 0.03,
        "has_flow_control": True,
        "has_cop_sensor": False,
        "has_delta_t_sensor": False,
        "has_outdoor_sensor": False,
        "has_return_temp_sensor": False,
        "has_flow_rate_sensor": False,
        "heat_source_type": "heat_pump",
        "heat_source_efficiency": 3.0,
        "hp_min_output_kw": 2.0,
        "control_method": "ha_service",
        "hp_flow_service": {},
        "hp_hvac_service": {},
        "fallback_rates": {
            "cheap": 0.1495,
            "standard": 0.245,
            "peak": 0.40,
        },
        "persistent_zones": [],
        "nudge_budget": 3.0,
        "heat_up_tau_h": arch["heat_up_tau_h"],
        "driver": "mock",
        "twin": {
            "enabled": True,
            "physics": {
                "per_room": {},  # Empty = use defaults derived from peak_loss
                "infiltration": {
                    "ach": arch["infiltration_ach"],
                },
            },
            "heat_pump": {
                "capacity_kw": arch["hp_capacity_kw"],
                "cop_map": DEFAULT_COP_MAP,
            },
            "emitters": {
                "exponent": arch.get("emitter_exponent", 1.15),
                "design_flow_temp": 55.0,
                "design_return_temp": 45.0,
            },
            "simulation": {
                "start_conditions": {
                    "room_temps": start_temps,
                    "outdoor_temp": 5.0,
                },
            },
        },
    }

    return profile


def generate_all(output_dir: str, archetypes: List[str] | None = None) -> List[str]:
    """Write archetype profile YAMLs to output_dir.

    Args:
        output_dir: Directory to write YAML files into.
        archetypes: List of archetype keys to generate (default: all).

    Returns:
        List of file paths written.
    """
    import yaml

    keys = archetypes if archetypes else sorted(UK_ARCHETYPES.keys())
    os.makedirs(output_dir, exist_ok=True)

    written: List[str] = []
    for key in keys:
        profile = generate_profile(key)
        filename = f"{key}.yaml"
        filepath = os.path.join(output_dir, filename)

        with open(filepath, "w") as f:
            f.write(f"# Auto-generated QSH fleet simulation archetype: {UK_ARCHETYPES[key]['label']}\n")
            yaml.dump(profile, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

        logger.info("Wrote %s", filepath)
        written.append(filepath)

    return written


# ── CLI ──────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Generate building archetype profiles for QSH fleet simulation.",
    )
    parser.add_argument("--output", help="Output directory for YAML profiles")
    parser.add_argument(
        "--archetypes",
        nargs="+",
        default=None,
        help="Space-separated archetype keys (default: all)",
    )
    parser.add_argument("--list", action="store_true", help="Print available archetypes and exit")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.list:
        print("Available archetypes:")
        for key, arch in sorted(UK_ARCHETYPES.items()):
            print(f"  {key:30s} {arch['label']:40s} {arch['total_area']:>4d} m2  {arch['peak_loss']:.1f} kW peak")
        return

    if not args.output:
        parser.error("--output is required (unless using --list)")

    written = generate_all(args.output, args.archetypes)
    print(f"Generated {len(written)} archetype profiles in {args.output}")


if __name__ == "__main__":
    main()
