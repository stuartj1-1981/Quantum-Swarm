"""
Generate COP model and WC curve YAML files for the QSH public repo.

Extracts data from hp_models.py and wc_curves.py into individual YAML files
so each model/curve is self-contained with source citation and full data.

Usage:
    python generate_yamls.py
"""

import os
import yaml

# ── Output directories (relative to repo root) ──
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_SCRIPT_DIR)
COP_DIR = os.path.join(_REPO_ROOT, "twin", "cop_models")
WC_DIR = os.path.join(_REPO_ROOT, "twin", "wc_curves")

os.makedirs(COP_DIR, exist_ok=True)
os.makedirs(WC_DIR, exist_ok=True)


# ── COP Maps ──────────────────────────────────────────────────────────
# Grid: outdoor [-7, -2, 2, 7, 12] x flow [25, 35, 45, 55]
# 20 points per model, EN 14511 basis

COP_MODELS = {
    "cosy_6": {
        "label": "Octopus Cosy 6kW",
        "manufacturer": "Octopus Energy (Midea OEM)",
        "model_reference": "Cosy 6",
        "source": "MCS certificate + field data calibration",
        "test_standard": "EN 14511",
        "capacity_kw": 6.0,
        "min_modulation_kw": 2.0,
        "default_wc_curve": "cosy_moderate",
        "derating_points": [[-7, 0.65], [-2, 0.85], [2, 0.92], [7, 1.0], [12, 1.0]],
        "sizing": {"min_peak_loss_kw": 3.0, "max_peak_loss_kw": 7.2},
        "cop_map": [
            {"outdoor": -7, "flow": 25, "cop": 2.9},
            {"outdoor": -2, "flow": 25, "cop": 3.4},
            {"outdoor":  2, "flow": 25, "cop": 3.9},
            {"outdoor":  7, "flow": 25, "cop": 4.5},
            {"outdoor": 12, "flow": 25, "cop": 5.0},
            {"outdoor": -7, "flow": 35, "cop": 2.5},
            {"outdoor": -2, "flow": 35, "cop": 2.9},
            {"outdoor":  2, "flow": 35, "cop": 3.4},
            {"outdoor":  7, "flow": 35, "cop": 3.9},
            {"outdoor": 12, "flow": 35, "cop": 4.5},
            {"outdoor": -7, "flow": 45, "cop": 2.0},
            {"outdoor": -2, "flow": 45, "cop": 2.4},
            {"outdoor":  2, "flow": 45, "cop": 2.8},
            {"outdoor":  7, "flow": 45, "cop": 3.2},
            {"outdoor": 12, "flow": 45, "cop": 3.7},
            {"outdoor": -7, "flow": 55, "cop": 1.6},
            {"outdoor": -2, "flow": 55, "cop": 1.9},
            {"outdoor":  2, "flow": 55, "cop": 2.3},
            {"outdoor":  7, "flow": 55, "cop": 2.6},
            {"outdoor": 12, "flow": 55, "cop": 3.0},
        ],
    },
    "cosy_9": {
        "label": "Octopus Cosy 9kW",
        "manufacturer": "Octopus Energy (Midea OEM)",
        "model_reference": "Cosy 9",
        "source": "MCS certificate",
        "test_standard": "EN 14511",
        "capacity_kw": 9.0,
        "min_modulation_kw": 3.0,
        "default_wc_curve": "cosy_moderate",
        "derating_points": [[-7, 0.60], [-2, 0.80], [2, 0.90], [7, 1.0], [12, 1.0]],
        "sizing": {"min_peak_loss_kw": 5.0, "max_peak_loss_kw": 10.8},
        "cop_map": [
            {"outdoor": -7, "flow": 25, "cop": 2.7},
            {"outdoor": -2, "flow": 25, "cop": 3.2},
            {"outdoor":  2, "flow": 25, "cop": 3.7},
            {"outdoor":  7, "flow": 25, "cop": 4.3},
            {"outdoor": 12, "flow": 25, "cop": 4.8},
            {"outdoor": -7, "flow": 35, "cop": 2.3},
            {"outdoor": -2, "flow": 35, "cop": 2.7},
            {"outdoor":  2, "flow": 35, "cop": 3.2},
            {"outdoor":  7, "flow": 35, "cop": 3.7},
            {"outdoor": 12, "flow": 35, "cop": 4.2},
            {"outdoor": -7, "flow": 45, "cop": 1.9},
            {"outdoor": -2, "flow": 45, "cop": 2.2},
            {"outdoor":  2, "flow": 45, "cop": 2.6},
            {"outdoor":  7, "flow": 45, "cop": 3.0},
            {"outdoor": 12, "flow": 45, "cop": 3.5},
            {"outdoor": -7, "flow": 55, "cop": 1.5},
            {"outdoor": -2, "flow": 55, "cop": 1.8},
            {"outdoor":  2, "flow": 55, "cop": 2.1},
            {"outdoor":  7, "flow": 55, "cop": 2.4},
            {"outdoor": 12, "flow": 55, "cop": 2.8},
        ],
    },
    "daikin_4": {
        "label": "Daikin Altherma 3 4kW",
        "manufacturer": "Daikin",
        "model_reference": "EHBH04D3V / ERGA04DV",
        "source": "Daikin technical data book",
        "test_standard": "EN 14511",
        "capacity_kw": 4.0,
        "min_modulation_kw": 1.5,
        "default_wc_curve": "daikin_moderate",
        "derating_points": [[-7, 0.70], [-2, 0.85], [2, 0.93], [7, 1.0], [12, 1.0]],
        "sizing": {"min_peak_loss_kw": 2.0, "max_peak_loss_kw": 4.8},
        "cop_map": [
            {"outdoor": -7, "flow": 25, "cop": 3.1},
            {"outdoor": -2, "flow": 25, "cop": 3.6},
            {"outdoor":  2, "flow": 25, "cop": 4.2},
            {"outdoor":  7, "flow": 25, "cop": 4.8},
            {"outdoor": 12, "flow": 25, "cop": 5.3},
            {"outdoor": -7, "flow": 35, "cop": 2.7},
            {"outdoor": -2, "flow": 35, "cop": 3.1},
            {"outdoor":  2, "flow": 35, "cop": 3.6},
            {"outdoor":  7, "flow": 35, "cop": 4.2},
            {"outdoor": 12, "flow": 35, "cop": 4.8},
            {"outdoor": -7, "flow": 45, "cop": 2.2},
            {"outdoor": -2, "flow": 45, "cop": 2.5},
            {"outdoor":  2, "flow": 45, "cop": 2.9},
            {"outdoor":  7, "flow": 45, "cop": 3.4},
            {"outdoor": 12, "flow": 45, "cop": 3.9},
            {"outdoor": -7, "flow": 55, "cop": 1.7},
            {"outdoor": -2, "flow": 55, "cop": 2.0},
            {"outdoor":  2, "flow": 55, "cop": 2.4},
            {"outdoor":  7, "flow": 55, "cop": 2.7},
            {"outdoor": 12, "flow": 55, "cop": 3.1},
        ],
    },
    "daikin_8": {
        "label": "Daikin Altherma 3 8kW",
        "manufacturer": "Daikin",
        "model_reference": "EHBH08D9W / ERGA08DV",
        "source": "Daikin technical data book",
        "test_standard": "EN 14511",
        "capacity_kw": 8.0,
        "min_modulation_kw": 2.5,
        "default_wc_curve": "daikin_moderate",
        "derating_points": [[-7, 0.62], [-2, 0.82], [2, 0.91], [7, 1.0], [12, 1.0]],
        "sizing": {"min_peak_loss_kw": 4.5, "max_peak_loss_kw": 9.6},
        "cop_map": [
            {"outdoor": -7, "flow": 25, "cop": 2.8},
            {"outdoor": -2, "flow": 25, "cop": 3.3},
            {"outdoor":  2, "flow": 25, "cop": 3.8},
            {"outdoor":  7, "flow": 25, "cop": 4.4},
            {"outdoor": 12, "flow": 25, "cop": 4.9},
            {"outdoor": -7, "flow": 35, "cop": 2.4},
            {"outdoor": -2, "flow": 35, "cop": 2.8},
            {"outdoor":  2, "flow": 35, "cop": 3.3},
            {"outdoor":  7, "flow": 35, "cop": 3.8},
            {"outdoor": 12, "flow": 35, "cop": 4.3},
            {"outdoor": -7, "flow": 45, "cop": 2.0},
            {"outdoor": -2, "flow": 45, "cop": 2.3},
            {"outdoor":  2, "flow": 45, "cop": 2.7},
            {"outdoor":  7, "flow": 45, "cop": 3.1},
            {"outdoor": 12, "flow": 45, "cop": 3.6},
            {"outdoor": -7, "flow": 55, "cop": 1.6},
            {"outdoor": -2, "flow": 55, "cop": 1.8},
            {"outdoor":  2, "flow": 55, "cop": 2.2},
            {"outdoor":  7, "flow": 55, "cop": 2.5},
            {"outdoor": 12, "flow": 55, "cop": 2.9},
        ],
    },
    "vaillant_5": {
        "label": "Vaillant Arotherm+ 5kW",
        "manufacturer": "Vaillant",
        "model_reference": "VWL 55/6 A 230V S3",
        "source": "Vaillant engineering manual",
        "test_standard": "EN 14511",
        "capacity_kw": 5.0,
        "min_modulation_kw": 1.8,
        "default_wc_curve": "vaillant_moderate",
        "derating_points": [[-7, 0.68], [-2, 0.84], [2, 0.92], [7, 1.0], [12, 1.0]],
        "sizing": {"min_peak_loss_kw": 2.5, "max_peak_loss_kw": 6.0},
        "cop_map": [
            {"outdoor": -7, "flow": 25, "cop": 3.0},
            {"outdoor": -2, "flow": 25, "cop": 3.5},
            {"outdoor":  2, "flow": 25, "cop": 4.1},
            {"outdoor":  7, "flow": 25, "cop": 4.7},
            {"outdoor": 12, "flow": 25, "cop": 5.2},
            {"outdoor": -7, "flow": 35, "cop": 2.6},
            {"outdoor": -2, "flow": 35, "cop": 3.0},
            {"outdoor":  2, "flow": 35, "cop": 3.5},
            {"outdoor":  7, "flow": 35, "cop": 4.1},
            {"outdoor": 12, "flow": 35, "cop": 4.6},
            {"outdoor": -7, "flow": 45, "cop": 2.1},
            {"outdoor": -2, "flow": 45, "cop": 2.5},
            {"outdoor":  2, "flow": 45, "cop": 2.9},
            {"outdoor":  7, "flow": 45, "cop": 3.3},
            {"outdoor": 12, "flow": 45, "cop": 3.8},
            {"outdoor": -7, "flow": 55, "cop": 1.7},
            {"outdoor": -2, "flow": 55, "cop": 2.0},
            {"outdoor":  2, "flow": 55, "cop": 2.3},
            {"outdoor":  7, "flow": 55, "cop": 2.6},
            {"outdoor": 12, "flow": 55, "cop": 3.1},
        ],
    },
    "ecodan_8_5": {
        "label": "Mitsubishi Ecodan 8.5kW",
        "manufacturer": "Mitsubishi Electric",
        "model_reference": "PUZ-WM85VAA",
        "source": "Mitsubishi technical handbook",
        "test_standard": "EN 14511",
        "capacity_kw": 8.5,
        "min_modulation_kw": 3.0,
        "default_wc_curve": "ecodan_moderate",
        "derating_points": [[-7, 0.58], [-2, 0.78], [2, 0.89], [7, 1.0], [12, 1.0]],
        "sizing": {"min_peak_loss_kw": 5.0, "max_peak_loss_kw": 10.2},
        "cop_map": [
            {"outdoor": -7, "flow": 25, "cop": 2.7},
            {"outdoor": -2, "flow": 25, "cop": 3.2},
            {"outdoor":  2, "flow": 25, "cop": 3.7},
            {"outdoor":  7, "flow": 25, "cop": 4.3},
            {"outdoor": 12, "flow": 25, "cop": 4.8},
            {"outdoor": -7, "flow": 35, "cop": 2.3},
            {"outdoor": -2, "flow": 35, "cop": 2.7},
            {"outdoor":  2, "flow": 35, "cop": 3.2},
            {"outdoor":  7, "flow": 35, "cop": 3.7},
            {"outdoor": 12, "flow": 35, "cop": 4.2},
            {"outdoor": -7, "flow": 45, "cop": 1.9},
            {"outdoor": -2, "flow": 45, "cop": 2.2},
            {"outdoor":  2, "flow": 45, "cop": 2.6},
            {"outdoor":  7, "flow": 45, "cop": 3.0},
            {"outdoor": 12, "flow": 45, "cop": 3.5},
            {"outdoor": -7, "flow": 55, "cop": 1.5},
            {"outdoor": -2, "flow": 55, "cop": 1.8},
            {"outdoor":  2, "flow": 55, "cop": 2.1},
            {"outdoor":  7, "flow": 55, "cop": 2.4},
            {"outdoor": 12, "flow": 55, "cop": 2.8},
        ],
    },
    "samsung_6": {
        "label": "Samsung EHS Mono 6kW",
        "manufacturer": "Samsung",
        "model_reference": "AE060RXYDEG",
        "source": "Samsung installer manual",
        "test_standard": "EN 14511",
        "capacity_kw": 6.0,
        "min_modulation_kw": 2.0,
        "default_wc_curve": "samsung_moderate",
        "derating_points": [[-7, 0.63], [-2, 0.82], [2, 0.91], [7, 1.0], [12, 1.0]],
        "sizing": {"min_peak_loss_kw": 3.0, "max_peak_loss_kw": 7.2},
        "cop_map": [
            {"outdoor": -7, "flow": 25, "cop": 2.8},
            {"outdoor": -2, "flow": 25, "cop": 3.3},
            {"outdoor":  2, "flow": 25, "cop": 3.8},
            {"outdoor":  7, "flow": 25, "cop": 4.4},
            {"outdoor": 12, "flow": 25, "cop": 4.9},
            {"outdoor": -7, "flow": 35, "cop": 2.4},
            {"outdoor": -2, "flow": 35, "cop": 2.8},
            {"outdoor":  2, "flow": 35, "cop": 3.3},
            {"outdoor":  7, "flow": 35, "cop": 3.8},
            {"outdoor": 12, "flow": 35, "cop": 4.3},
            {"outdoor": -7, "flow": 45, "cop": 2.0},
            {"outdoor": -2, "flow": 45, "cop": 2.3},
            {"outdoor":  2, "flow": 45, "cop": 2.7},
            {"outdoor":  7, "flow": 45, "cop": 3.1},
            {"outdoor": 12, "flow": 45, "cop": 3.6},
            {"outdoor": -7, "flow": 55, "cop": 1.6},
            {"outdoor": -2, "flow": 55, "cop": 1.8},
            {"outdoor":  2, "flow": 55, "cop": 2.2},
            {"outdoor":  7, "flow": 55, "cop": 2.5},
            {"outdoor": 12, "flow": 55, "cop": 2.9},
        ],
    },
    "grant_6": {
        "label": "Grant Aerona3 6kW",
        "manufacturer": "Grant",
        "model_reference": "HPID6",
        "source": "Grant technical data",
        "test_standard": "EN 14511",
        "capacity_kw": 6.0,
        "min_modulation_kw": 2.0,
        "default_wc_curve": "grant_moderate",
        "derating_points": [[-7, 0.60], [-2, 0.80], [2, 0.90], [7, 1.0], [12, 1.0]],
        "sizing": {"min_peak_loss_kw": 3.0, "max_peak_loss_kw": 7.2},
        "cop_map": [
            {"outdoor": -7, "flow": 25, "cop": 2.6},
            {"outdoor": -2, "flow": 25, "cop": 3.1},
            {"outdoor":  2, "flow": 25, "cop": 3.6},
            {"outdoor":  7, "flow": 25, "cop": 4.2},
            {"outdoor": 12, "flow": 25, "cop": 4.7},
            {"outdoor": -7, "flow": 35, "cop": 2.2},
            {"outdoor": -2, "flow": 35, "cop": 2.6},
            {"outdoor":  2, "flow": 35, "cop": 3.1},
            {"outdoor":  7, "flow": 35, "cop": 3.6},
            {"outdoor": 12, "flow": 35, "cop": 4.1},
            {"outdoor": -7, "flow": 45, "cop": 1.8},
            {"outdoor": -2, "flow": 45, "cop": 2.1},
            {"outdoor":  2, "flow": 45, "cop": 2.5},
            {"outdoor":  7, "flow": 45, "cop": 2.9},
            {"outdoor": 12, "flow": 45, "cop": 3.4},
            {"outdoor": -7, "flow": 55, "cop": 1.4},
            {"outdoor": -2, "flow": 55, "cop": 1.7},
            {"outdoor":  2, "flow": 55, "cop": 2.0},
            {"outdoor":  7, "flow": 55, "cop": 2.3},
            {"outdoor": 12, "flow": 55, "cop": 2.7},
        ],
    },
    "generic": {
        "label": "Generic Mid-Range ASHP",
        "manufacturer": "Generic",
        "model_reference": "Calibrated mid-range UK ASHP",
        "source": "Calibrated to live system data (outdoor=5, flow=33) ~ COP 3.9",
        "test_standard": "EN 14511 (interpolated)",
        "capacity_kw": 6.0,
        "min_modulation_kw": 2.0,
        "default_wc_curve": "mcs_generic",
        "derating_points": [[-7, 0.65], [-2, 0.85], [2, 0.92], [7, 1.0], [12, 1.0]],
        "sizing": {"min_peak_loss_kw": 2.0, "max_peak_loss_kw": 7.2},
        "cop_map": [
            {"outdoor": -10, "flow": 25, "cop": 2.5},
            {"outdoor": -10, "flow": 35, "cop": 2.1},
            {"outdoor": -10, "flow": 45, "cop": 1.8},
            {"outdoor": -10, "flow": 55, "cop": 1.5},
            {"outdoor":  -5, "flow": 25, "cop": 3.2},
            {"outdoor":   0, "flow": 25, "cop": 3.7},
            {"outdoor":   5, "flow": 25, "cop": 4.3},
            {"outdoor":  10, "flow": 25, "cop": 4.8},
            {"outdoor":  15, "flow": 25, "cop": 5.2},
            {"outdoor":  -5, "flow": 35, "cop": 2.8},
            {"outdoor":   0, "flow": 35, "cop": 3.2},
            {"outdoor":   5, "flow": 35, "cop": 3.8},
            {"outdoor":  10, "flow": 35, "cop": 4.3},
            {"outdoor":  15, "flow": 35, "cop": 4.8},
            {"outdoor":  -5, "flow": 45, "cop": 2.3},
            {"outdoor":   0, "flow": 45, "cop": 2.7},
            {"outdoor":   5, "flow": 45, "cop": 3.2},
            {"outdoor":  10, "flow": 45, "cop": 3.7},
            {"outdoor":  15, "flow": 45, "cop": 4.1},
            {"outdoor":  -5, "flow": 55, "cop": 1.8},
            {"outdoor":   0, "flow": 55, "cop": 2.1},
            {"outdoor":   5, "flow": 55, "cop": 2.5},
            {"outdoor":  10, "flow": 55, "cop": 2.9},
            {"outdoor":  15, "flow": 55, "cop": 3.2},
        ],
    },
}

# ── WC Curves ──────────────────────────────────────────────────────────
WC_CURVES = {
    "mcs_generic": {
        "label": "MCS MIS 3005 Generic Linear",
        "source": "MCS MIS 3005 guidance for panel radiator systems",
        "points": [[-5, 46.25], [0, 42.5], [5, 38.75], [10, 35.0], [15, 31.25], [20, 27.5]],
        "min_flow": 25.0,
        "max_flow": 50.0,
    },
    "cosy_steep": {
        "label": "Octopus Cosy — Steep (Curve 1)",
        "source": "Octopus Energy installer manual, Cosy 6/9 WC settings",
        "points": [[-5, 50.0], [0, 45.0], [5, 38.0], [10, 32.0], [15, 28.0], [20, 25.0]],
        "min_flow": 25.0,
        "max_flow": 50.0,
    },
    "cosy_moderate": {
        "label": "Octopus Cosy — Moderate (Curve 3, default)",
        "source": "Octopus Energy installer manual, Cosy 6/9 WC settings",
        "points": [[-5, 52.0], [0, 47.0], [5, 42.0], [10, 37.0], [15, 33.0], [20, 30.0]],
        "min_flow": 25.0,
        "max_flow": 52.0,
    },
    "cosy_flat": {
        "label": "Octopus Cosy — Flat (Curve 5)",
        "source": "Octopus Energy installer manual, Cosy 6/9 WC settings",
        "points": [[-5, 55.0], [0, 50.0], [5, 47.0], [10, 43.0], [15, 40.0], [20, 37.0]],
        "min_flow": 30.0,
        "max_flow": 55.0,
    },
    "daikin_steep": {
        "label": "Daikin Altherma 3 — Steep (Heating Curve 1)",
        "source": "Daikin Altherma 3 technical data book, installer WC settings",
        "points": [[-5, 48.0], [0, 42.0], [5, 36.0], [10, 30.0], [15, 26.0], [20, 25.0]],
        "min_flow": 25.0,
        "max_flow": 48.0,
    },
    "daikin_moderate": {
        "label": "Daikin Altherma 3 — Moderate (Heating Curve 3, default)",
        "source": "Daikin Altherma 3 technical data book, installer WC settings",
        "points": [[-5, 52.0], [0, 47.0], [5, 41.0], [10, 36.0], [15, 32.0], [20, 28.0]],
        "min_flow": 25.0,
        "max_flow": 52.0,
    },
    "daikin_flat": {
        "label": "Daikin Altherma 3 — Flat (Heating Curve 5)",
        "source": "Daikin Altherma 3 technical data book, installer WC settings",
        "points": [[-5, 55.0], [0, 51.0], [5, 47.0], [10, 43.0], [15, 40.0], [20, 37.0]],
        "min_flow": 30.0,
        "max_flow": 55.0,
    },
    "vaillant_steep": {
        "label": "Vaillant Arotherm+ — Steep (Curve 0.4)",
        "source": "Vaillant Arotherm+ engineering manual, heating curve gradient",
        "points": [[-5, 47.0], [0, 42.0], [5, 36.0], [10, 31.0], [15, 27.0], [20, 25.0]],
        "min_flow": 25.0,
        "max_flow": 47.0,
    },
    "vaillant_moderate": {
        "label": "Vaillant Arotherm+ — Moderate (Curve 0.6, default)",
        "source": "Vaillant Arotherm+ engineering manual, heating curve gradient",
        "points": [[-5, 53.0], [0, 47.0], [5, 42.0], [10, 37.0], [15, 33.0], [20, 29.0]],
        "min_flow": 25.0,
        "max_flow": 53.0,
    },
    "vaillant_flat": {
        "label": "Vaillant Arotherm+ — Flat (Curve 0.8)",
        "source": "Vaillant Arotherm+ engineering manual, heating curve gradient",
        "points": [[-5, 55.0], [0, 51.0], [5, 48.0], [10, 44.0], [15, 41.0], [20, 38.0]],
        "min_flow": 30.0,
        "max_flow": 55.0,
    },
    "ecodan_steep": {
        "label": "Mitsubishi Ecodan — Steep (Zone 1 Low)",
        "source": "Mitsubishi Ecodan technical handbook, WC zone settings",
        "points": [[-5, 48.0], [0, 43.0], [5, 37.0], [10, 32.0], [15, 28.0], [20, 25.0]],
        "min_flow": 25.0,
        "max_flow": 48.0,
    },
    "ecodan_moderate": {
        "label": "Mitsubishi Ecodan — Moderate (Zone 1 Mid, default)",
        "source": "Mitsubishi Ecodan technical handbook, WC zone settings",
        "points": [[-5, 52.0], [0, 47.0], [5, 42.0], [10, 37.0], [15, 33.0], [20, 30.0]],
        "min_flow": 25.0,
        "max_flow": 52.0,
    },
    "ecodan_flat": {
        "label": "Mitsubishi Ecodan — Flat (Zone 1 High)",
        "source": "Mitsubishi Ecodan technical handbook, WC zone settings",
        "points": [[-5, 55.0], [0, 51.0], [5, 47.0], [10, 44.0], [15, 41.0], [20, 38.0]],
        "min_flow": 30.0,
        "max_flow": 55.0,
    },
    "samsung_steep": {
        "label": "Samsung EHS Mono — Steep (Law 1)",
        "source": "Samsung EHS Mono installer manual, water law settings",
        "points": [[-5, 47.0], [0, 41.0], [5, 35.0], [10, 30.0], [15, 26.0], [20, 25.0]],
        "min_flow": 25.0,
        "max_flow": 47.0,
    },
    "samsung_moderate": {
        "label": "Samsung EHS Mono — Moderate (Law 3, default)",
        "source": "Samsung EHS Mono installer manual, water law settings",
        "points": [[-5, 51.0], [0, 46.0], [5, 41.0], [10, 36.0], [15, 32.0], [20, 28.0]],
        "min_flow": 25.0,
        "max_flow": 51.0,
    },
    "samsung_flat": {
        "label": "Samsung EHS Mono — Flat (Law 5)",
        "source": "Samsung EHS Mono installer manual, water law settings",
        "points": [[-5, 55.0], [0, 51.0], [5, 47.0], [10, 43.0], [15, 40.0], [20, 37.0]],
        "min_flow": 30.0,
        "max_flow": 55.0,
    },
    "grant_steep": {
        "label": "Grant Aerona3 — Steep (Curve A)",
        "source": "Grant Aerona3 technical data, WC curve settings",
        "points": [[-5, 48.0], [0, 43.0], [5, 37.0], [10, 31.0], [15, 27.0], [20, 25.0]],
        "min_flow": 25.0,
        "max_flow": 48.0,
    },
    "grant_moderate": {
        "label": "Grant Aerona3 — Moderate (Curve C, default)",
        "source": "Grant Aerona3 technical data, WC curve settings",
        "points": [[-5, 52.0], [0, 47.0], [5, 42.0], [10, 37.0], [15, 33.0], [20, 29.0]],
        "min_flow": 25.0,
        "max_flow": 52.0,
    },
    "grant_flat": {
        "label": "Grant Aerona3 — Flat (Curve E)",
        "source": "Grant Aerona3 technical data, WC curve settings",
        "points": [[-5, 55.0], [0, 51.0], [5, 48.0], [10, 44.0], [15, 41.0], [20, 38.0]],
        "min_flow": 30.0,
        "max_flow": 55.0,
    },
}


def write_cop_yamls():
    """Write individual COP model YAML files."""
    for key, model in sorted(COP_MODELS.items()):
        filepath = os.path.join(COP_DIR, f"{key}.yaml")

        # Build clean output dict
        out = {
            "model_key": key,
            "label": model["label"],
            "manufacturer": model["manufacturer"],
            "model_reference": model["model_reference"],
            "source": model["source"],
            "test_standard": model["test_standard"],
            "capacity_kw": model["capacity_kw"],
            "min_modulation_kw": model["min_modulation_kw"],
            "default_wc_curve": model["default_wc_curve"],
            "sizing": model["sizing"],
            "derating_points": [
                {"outdoor_c": p[0], "capacity_fraction": p[1]}
                for p in model["derating_points"]
            ],
            "cop_map": model["cop_map"],
        }

        with open(filepath, "w") as f:
            f.write(f"# QSH COP Model: {model['label']}\n")
            f.write(f"# Source: {model['source']}\n")
            f.write(f"# Test standard: {model['test_standard']}\n")
            f.write(f"# Grid: outdoor_temp x flow_temp -> COP\n")
            f.write(f"# {len(model['cop_map'])} data points\n")
            f.write(f"#\n")
            f.write(f"# Used in QSH fleet simulation (fleet.db)\n")
            f.write(f"# See docs/methodology.md Section 3 for interpolation method\n\n")
            yaml.dump(out, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

        print(f"  COP: {filepath}")


def write_wc_yamls():
    """Write individual WC curve YAML files."""
    for key, curve in sorted(WC_CURVES.items()):
        filepath = os.path.join(WC_DIR, f"{key}.yaml")

        out = {
            "curve_key": key,
            "label": curve["label"],
            "source": curve["source"],
            "min_flow_c": curve["min_flow"],
            "max_flow_c": curve["max_flow"],
            "breakpoints": [
                {"outdoor_c": p[0], "flow_c": p[1]}
                for p in curve["points"]
            ],
        }

        with open(filepath, "w") as f:
            f.write(f"# QSH Weather Compensation Curve: {curve['label']}\n")
            f.write(f"# Source: {curve['source']}\n")
            f.write(f"#\n")
            f.write(f"# Piecewise-linear: outdoor_temp -> flow_temp\n")
            f.write(f"# Between breakpoints: linear interpolation\n")
            f.write(f"# Outside range: nearest endpoint (clamped)\n")
            f.write(f"#\n")
            f.write(f"# Used in QSH fleet simulation (fleet.db)\n")
            f.write(f"# See docs/methodology.md Section 4 for details\n\n")
            yaml.dump(out, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

        print(f"  WC:  {filepath}")


if __name__ == "__main__":
    print(f"Generating COP model YAMLs -> {COP_DIR}/")
    write_cop_yamls()
    print(f"\nGenerating WC curve YAMLs -> {WC_DIR}/")
    write_wc_yamls()
    print(f"\nDone. {len(COP_MODELS)} COP models, {len(WC_CURVES)} WC curves.")
