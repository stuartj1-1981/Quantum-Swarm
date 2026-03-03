"""
Weather compensation curve library for QSH fleet simulation.

Each curve maps outdoor temperature -> target flow temperature.
Curves are piecewise-linear, defined by a list of (outdoor, flow) breakpoints.
Between breakpoints, linear interpolation applies.
Outside the range, the nearest endpoint value is used (clamped).

Sources:
    - Manufacturer installer manuals (EN 14511 test conditions)
    - MCS MIS 3005 (generic guidance)
    - Typical installer commissioning settings

Curve naming convention:
    {manufacturer}_{setting}
    e.g. "cosy_moderate", "daikin_steep"
"""

from __future__ import annotations

import logging
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


def wc_flow_temp(
    outdoor_temp: float,
    curve_points: List[Tuple[float, float]],
    min_flow: float = 25.0,
    max_flow: float = 55.0,
) -> float:
    """Calculate weather-compensated flow temperature.

    Args:
        outdoor_temp: Current outdoor temperature [C]
        curve_points: List of (outdoor_temp, flow_temp) breakpoints,
                      sorted by outdoor_temp ascending.
        min_flow: Minimum flow temperature [C]
        max_flow: Maximum flow temperature [C]

    Returns:
        Target flow temperature [C], clamped to [min_flow, max_flow].
    """
    if not curve_points:
        return max_flow

    # Below lowest outdoor point: use lowest flow value
    if outdoor_temp <= curve_points[0][0]:
        flow = curve_points[0][1]
    # Above highest outdoor point: use highest flow value
    elif outdoor_temp >= curve_points[-1][0]:
        flow = curve_points[-1][1]
    else:
        # Linear interpolation between bracketing points
        for i in range(len(curve_points) - 1):
            o_lo, f_lo = curve_points[i]
            o_hi, f_hi = curve_points[i + 1]
            if o_lo <= outdoor_temp <= o_hi:
                frac = (outdoor_temp - o_lo) / (o_hi - o_lo)
                flow = f_lo + frac * (f_hi - f_lo)
                break
        else:
            flow = curve_points[-1][1]

    return max(min_flow, min(max_flow, flow))


# -- Manufacturer WC Curves ------------------------------------------------
#
# Each entry: (outdoor_temp_C, flow_temp_C)
# Sorted ascending by outdoor temperature.
# Flow decreases as outdoor increases (less heat needed).
#
# Three settings per manufacturer where available:
#   - steep:    aggressive drop (good for well-insulated, oversized HP)
#   - moderate: typical installer default
#   - flat:     conservative (for leaky buildings, undersized HP)

WC_CURVES: Dict[str, Dict] = {
    # -- MCS MIS 3005 generic (current stock_weather_comp baseline) --
    "mcs_generic": {
        "label": "MCS MIS 3005 Generic Linear",
        "source": "MCS MIS 3005 guidance for panel radiator systems",
        "points": [(-5, 46.25), (0, 42.5), (5, 38.75), (10, 35.0), (15, 31.25), (20, 27.5)],
        "min_flow": 25.0,
        "max_flow": 50.0,
    },
    # -- Octopus Cosy (Midea OEM ASHP) --
    "cosy_steep": {
        "label": "Octopus Cosy — Steep (Curve 1)",
        "source": "Octopus Energy installer manual, Cosy 6/9 WC settings",
        "points": [(-5, 50.0), (0, 45.0), (5, 38.0), (10, 32.0), (15, 28.0), (20, 25.0)],
        "min_flow": 25.0,
        "max_flow": 50.0,
    },
    "cosy_moderate": {
        "label": "Octopus Cosy — Moderate (Curve 3, default)",
        "source": "Octopus Energy installer manual, Cosy 6/9 WC settings",
        "points": [(-5, 52.0), (0, 47.0), (5, 42.0), (10, 37.0), (15, 33.0), (20, 30.0)],
        "min_flow": 25.0,
        "max_flow": 52.0,
    },
    "cosy_flat": {
        "label": "Octopus Cosy — Flat (Curve 5)",
        "source": "Octopus Energy installer manual, Cosy 6/9 WC settings",
        "points": [(-5, 55.0), (0, 50.0), (5, 47.0), (10, 43.0), (15, 40.0), (20, 37.0)],
        "min_flow": 30.0,
        "max_flow": 55.0,
    },
    # -- Daikin Altherma 3 --
    "daikin_steep": {
        "label": "Daikin Altherma 3 — Steep (Heating Curve 1)",
        "source": "Daikin Altherma 3 technical data book, installer WC settings",
        "points": [(-5, 48.0), (0, 42.0), (5, 36.0), (10, 30.0), (15, 26.0), (20, 25.0)],
        "min_flow": 25.0,
        "max_flow": 48.0,
    },
    "daikin_moderate": {
        "label": "Daikin Altherma 3 — Moderate (Heating Curve 3, default)",
        "source": "Daikin Altherma 3 technical data book, installer WC settings",
        "points": [(-5, 52.0), (0, 47.0), (5, 41.0), (10, 36.0), (15, 32.0), (20, 28.0)],
        "min_flow": 25.0,
        "max_flow": 52.0,
    },
    "daikin_flat": {
        "label": "Daikin Altherma 3 — Flat (Heating Curve 5)",
        "source": "Daikin Altherma 3 technical data book, installer WC settings",
        "points": [(-5, 55.0), (0, 51.0), (5, 47.0), (10, 43.0), (15, 40.0), (20, 37.0)],
        "min_flow": 30.0,
        "max_flow": 55.0,
    },
    # -- Vaillant Arotherm+ --
    "vaillant_steep": {
        "label": "Vaillant Arotherm+ — Steep (Curve 0.4)",
        "source": "Vaillant Arotherm+ engineering manual, heating curve gradient",
        "points": [(-5, 47.0), (0, 42.0), (5, 36.0), (10, 31.0), (15, 27.0), (20, 25.0)],
        "min_flow": 25.0,
        "max_flow": 47.0,
    },
    "vaillant_moderate": {
        "label": "Vaillant Arotherm+ — Moderate (Curve 0.6, default)",
        "source": "Vaillant Arotherm+ engineering manual, heating curve gradient",
        "points": [(-5, 53.0), (0, 47.0), (5, 42.0), (10, 37.0), (15, 33.0), (20, 29.0)],
        "min_flow": 25.0,
        "max_flow": 53.0,
    },
    "vaillant_flat": {
        "label": "Vaillant Arotherm+ — Flat (Curve 0.8)",
        "source": "Vaillant Arotherm+ engineering manual, heating curve gradient",
        "points": [(-5, 55.0), (0, 51.0), (5, 48.0), (10, 44.0), (15, 41.0), (20, 38.0)],
        "min_flow": 30.0,
        "max_flow": 55.0,
    },
    # -- Mitsubishi Ecodan --
    "ecodan_steep": {
        "label": "Mitsubishi Ecodan — Steep (Zone 1 Low)",
        "source": "Mitsubishi Ecodan technical handbook, WC zone settings",
        "points": [(-5, 48.0), (0, 43.0), (5, 37.0), (10, 32.0), (15, 28.0), (20, 25.0)],
        "min_flow": 25.0,
        "max_flow": 48.0,
    },
    "ecodan_moderate": {
        "label": "Mitsubishi Ecodan — Moderate (Zone 1 Mid, default)",
        "source": "Mitsubishi Ecodan technical handbook, WC zone settings",
        "points": [(-5, 52.0), (0, 47.0), (5, 42.0), (10, 37.0), (15, 33.0), (20, 30.0)],
        "min_flow": 25.0,
        "max_flow": 52.0,
    },
    "ecodan_flat": {
        "label": "Mitsubishi Ecodan — Flat (Zone 1 High)",
        "source": "Mitsubishi Ecodan technical handbook, WC zone settings",
        "points": [(-5, 55.0), (0, 51.0), (5, 47.0), (10, 44.0), (15, 41.0), (20, 38.0)],
        "min_flow": 30.0,
        "max_flow": 55.0,
    },
    # -- Samsung EHS Mono --
    "samsung_steep": {
        "label": "Samsung EHS Mono — Steep (Law 1)",
        "source": "Samsung EHS Mono installer manual, water law settings",
        "points": [(-5, 47.0), (0, 41.0), (5, 35.0), (10, 30.0), (15, 26.0), (20, 25.0)],
        "min_flow": 25.0,
        "max_flow": 47.0,
    },
    "samsung_moderate": {
        "label": "Samsung EHS Mono — Moderate (Law 3, default)",
        "source": "Samsung EHS Mono installer manual, water law settings",
        "points": [(-5, 51.0), (0, 46.0), (5, 41.0), (10, 36.0), (15, 32.0), (20, 28.0)],
        "min_flow": 25.0,
        "max_flow": 51.0,
    },
    "samsung_flat": {
        "label": "Samsung EHS Mono — Flat (Law 5)",
        "source": "Samsung EHS Mono installer manual, water law settings",
        "points": [(-5, 55.0), (0, 51.0), (5, 47.0), (10, 43.0), (15, 40.0), (20, 37.0)],
        "min_flow": 30.0,
        "max_flow": 55.0,
    },
    # -- Grant Aerona3 --
    "grant_steep": {
        "label": "Grant Aerona3 — Steep (Curve A)",
        "source": "Grant Aerona3 technical data, WC curve settings",
        "points": [(-5, 48.0), (0, 43.0), (5, 37.0), (10, 31.0), (15, 27.0), (20, 25.0)],
        "min_flow": 25.0,
        "max_flow": 48.0,
    },
    "grant_moderate": {
        "label": "Grant Aerona3 — Moderate (Curve C, default)",
        "source": "Grant Aerona3 technical data, WC curve settings",
        "points": [(-5, 52.0), (0, 47.0), (5, 42.0), (10, 37.0), (15, 33.0), (20, 29.0)],
        "min_flow": 25.0,
        "max_flow": 52.0,
    },
    "grant_flat": {
        "label": "Grant Aerona3 — Flat (Curve E)",
        "source": "Grant Aerona3 technical data, WC curve settings",
        "points": [(-5, 55.0), (0, 51.0), (5, 48.0), (10, 44.0), (15, 41.0), (20, 38.0)],
        "min_flow": 30.0,
        "max_flow": 55.0,
    },
}

# All available curve keys for batch enumeration
WC_CURVE_KEYS = sorted(WC_CURVES.keys())

# Default curve subsets for quick runs
WC_MODERATE_CURVES = [k for k in WC_CURVE_KEYS if "moderate" in k or k == "mcs_generic"]

WC_ALL_CURVES = WC_CURVE_KEYS
