"""
Heat pump model definitions for QSH fleet simulation.

Each model specifies rated capacity, minimum modulation, capacity derating
at low outdoor temperatures, default WC curve, and sizing limits to prevent
nonsensical archetype pairings (e.g. 4 kW HP on 8 kW peak loss building).

COP data for each model lives in the per-model YAML files under
twin/cop_models/.  This module provides the metadata wrapper.

Usage:
    from twin.hp_models import HP_MODELS, compatible_hp_models

    # Get model definition
    model = HP_MODELS["cosy_6"]

    # Filter models compatible with a given peak loss
    models = compatible_hp_models(peak_loss_kw=6.0)
"""

from __future__ import annotations

from typing import Dict, List

HP_MODELS: Dict[str, dict] = {
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
        "cop_yaml": "cosy_6.yaml",
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
        "cop_yaml": "cosy_9.yaml",
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
        "cop_yaml": "daikin_4.yaml",
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
        "cop_yaml": "daikin_8.yaml",
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
        "cop_yaml": "vaillant_5.yaml",
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
        "cop_yaml": "ecodan_8_5.yaml",
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
        "cop_yaml": "samsung_6.yaml",
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
        "cop_yaml": "grant_6.yaml",
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
        "cop_yaml": "generic.yaml",
    },
}


def compatible_hp_models(peak_loss_kw: float) -> List[str]:
    """Return HP model keys whose sizing range covers the given peak loss.

    Prevents nonsensical pairings like a 4 kW HP on an 8 kW peak loss
    building, or a 9 kW HP on a 3 kW flat.

    Args:
        peak_loss_kw: Building peak heat loss at design outdoor temp [kW].

    Returns:
        List of HP model keys that are appropriately sized.
    """
    result = []
    for key, model in HP_MODELS.items():
        sizing = model["sizing"]
        if sizing["min_peak_loss_kw"] <= peak_loss_kw <= sizing["max_peak_loss_kw"]:
            result.append(key)
    return result
