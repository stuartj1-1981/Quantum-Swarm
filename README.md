# QSH — Quantum Swarm Heating

**Physics-based thermal optimisation for residential heat pumps.**

A digital twin fleet simulation framework that models heat pump performance across UK housing archetypes, climate zones, and control strategies. Built by a process control engineer (ISA S88/S95/S103, 28 years) who watched a heat pump controller hunt and overshoot in patterns that wouldn't survive a factory floor audit.

## Headline Finding

Weather compensation (WC) uses **22–31% more energy** than fixed 50°C flow temperature on standard UK housing stock.

This is not a marginal effect. It is a structural penalty: lowering flow temperature improves COP, but reduces emitter output by a power law (EN 442). On standard-sized radiators the output drops faster than the COP improves. The heat pump runs longer. Total consumption goes up.

| Archetype | WC Penalty vs Fixed 50°C | WC Mean COP | Fixed 50°C Mean COP |
|-----------|------------------------:|:-----------:|:-------------------:|
| terrace_victorian | +30.5% | 3.93 | 2.96 |
| terrace_victorian_retro | +29.9% | 3.99 | 3.01 |
| semi_1970s_retro | +28.4% | 4.10 | 3.09 |
| detached_1990s | +26.3% | 3.92 | 2.96 |
| newbuild_2020s | +25.2% | 4.12 | 3.10 |
| flat_purpose | +23.7% | 4.13 | 3.10 |
| semi_1970s | +22.8% | 3.95 | 2.98 |
| bungalow_1960s | +22.2% | 4.00 | 3.02 |

*Source: fleet.db — 34,719 runs across 9 HP models, 8 archetypes, 10 UK climate zones, 19 manufacturer WC curves.*

The simulation model is **generous to WC**: emitter exponent n=1.15 (EN 442 standard is n=1.3) with a low-temperature output boost. The real-world penalty is likely larger than shown above.

A live QSH installation (2016 build, 5 kW peak loss at −3°C) independently validated this finding — both deterministic and adaptive control layers drove flow temperatures 3–5°C above manufacturer WC curves, converging from different starting points.

## What This Repository Contains

| Path | Description |
|------|-------------|
| `engine.py` | ThermalEngine — physics stepping model (per-room heat loss, thermal mass, solar gains, emitter output) |
| `archetypes.py` | UK housing archetype generator (8 types from Victorian terrace to 2020s newbuild) |
| `batch.py` and `fleet_report.py` | Fleet simulation batch runner (parallel execution, SQLite output) |
| `cop_model.py` | COP bilinear interpolation from manufacturer/EN 14511 data grids |
| `emitter_model.py` | Radiator/UFH output model (LMTD correction, EN 442 basis) |
| `wc_curves.py` | 19 manufacturer weather compensation curves (Cosy, Daikin, Ecodan, Grant, Samsung, Vaillant, MCS) |
| `weather.py` | Climate zone weather data loader |
| `fleet.db` | Full fleet simulation results — 34,719 runs, 5.76M hourly rows (SQLite, queryable) |
| `methodology.md` | Full methodology paper: energy balance, emitter physics, WC analysis, fleet framework |

## Quick Start

### Prerequisites

Python 3.10+ and SQLite3. No GPU required — fleet simulations run on CPU.

```bash
# Clone the repository
git clone https://github.com/[your-org]/qsh.git
cd qsh

# Install dependencies
pip install pyyaml numpy
```

### 1. Query the Fleet Results

The fastest way to explore is to query `fleet.db` directly:

```bash
# WC penalty by archetype (the headline finding)
sqlite3 fleet.db "
  SELECT
    archetype,
    ROUND(AVG(CASE WHEN strategy='hp_wc' THEN total_kwh END), 1) as wc_kwh,
    ROUND(AVG(CASE WHEN strategy='hp_fixed_50' THEN total_kwh END), 1) as fixed50_kwh,
    ROUND((AVG(CASE WHEN strategy='hp_wc' THEN total_kwh END)
         - AVG(CASE WHEN strategy='hp_fixed_50' THEN total_kwh END))
         / AVG(CASE WHEN strategy='hp_fixed_50' THEN total_kwh END) * 100, 1) as penalty_pct
  FROM runs
  WHERE strategy IN ('hp_wc', 'hp_fixed_50')
  GROUP BY archetype
  ORDER BY penalty_pct DESC;
"

# Best strategy per archetype and weather zone
sqlite3 fleet.db "
  SELECT archetype, weather_location, strategy,
         ROUND(MIN(total_kwh), 1) as min_kwh,
         ROUND(mean_cop, 2) as cop
  FROM runs
  WHERE thermostat_setpoint = 21.0 AND schedule = 'continuous'
  GROUP BY archetype, weather_location
  ORDER BY archetype, weather_location;
"

# Hourly profile for a specific run
sqlite3 fleet.db "
  SELECT hour, outdoor_temp, mean_room_temp, flow_temp, hp_power_kw, cop, kwh_consumed
  FROM hourly
  WHERE run_id = (SELECT run_id FROM runs WHERE archetype='semi_1970s'
                  AND weather_location='london' AND strategy='hp_fixed_50'
                  AND hp_model='cosy_6' LIMIT 1)
  ORDER BY hour LIMIT 24;
"
```

### 2. Run a Single Simulation

```bash
# Generate archetype profiles
python -m twin.archetypes --output profiles/ --archetypes semi_1970s

# Run a single 168-hour (1 week) simulation
python -m twin.batch \
    --profiles profiles/ \
    --weather twin/weather_data/ \
    --hours 168 \
    --workers 1 \
    --output results/
```

### 3. Run a Fleet Simulation

```bash
# Full fleet: all archetypes × strategies × weather zones
# ~34,000 runs — takes several hours on an M4 Max, longer on older hardware
python -m twin.batch \
    --profiles profiles/ \
    --weather twin/weather_data/ \
    --hours 168 \
    --workers 8 \
    --output results/
```

## Fleet Simulation Design

**34,719 runs** covering the following parameter space:

- **9 heat pump models**: Cosy 6kW, Cosy 9kW, Daikin 4kW, Daikin 8kW, Vaillant 5kW, Ecodan 8.5kW, Samsung 6kW, Grant 6kW, generic (each with per-model COP maps from EN 14511 data, capacity derating, and sizing filters to prevent nonsensical pairings)
- **8 UK housing archetypes**: bungalow_1960s, semi_1970s, semi_1970s_retro, terrace_victorian, terrace_victorian_retro, detached_1990s, newbuild_2020s, flat_purpose (parameters from SAP, CIBSE Guide A, BRE)
- **10 climate zones**: Aberdeen, Belfast, Birmingham, Cardiff, Edinburgh, London, Manchester, Newcastle, plus beast_from_east and mild_winter boundary cases
- **3 strategies**: hp_fixed_50, hp_fixed_55, hp_wc (with 19 manufacturer WC curves)
- **Thermostat setpoints**: 18–25°C
- **Schedules**: continuous, night_setback

Each run produces hourly data: outdoor temperature, room temperature, flow temperature, HP power, COP, energy consumed, and cost. All stored in `fleet.db` as queryable SQLite.

## The Emitter Capacity Problem

Weather compensation assumes that lowering flow temperature always saves energy because COP improves. This is true in isolation. But emitters are part of the system.

Radiator output follows a power law relationship with mean water temperature:

```
Q_actual = Q_rated × (MWT_actual − T_room) / (MWT_design − T_room))^n
```

Where n = 1.3 for standard radiators (EN 442). At lower flow temperatures, emitter output falls faster than COP improves. The heat pump must run longer — sometimes continuously — to maintain setpoint. The extra run hours more than offset the COP benefit.

**Breakeven point**: emitters must be oversized by ≥1.75× (simulation model, n=1.15) or ≥2.4× (EN 442 standard, n=1.3) before WC starts saving energy. The majority of UK housing stock falls below this threshold.

## Three-Layer Publishing Sequence

This repository is Layer 1 of a three-layer evidence base:

1. **Layer 1** : Methodology, fleet simulation framework, WC analysis, baseline results on archetype priors. *You are here.*
2. **Layer 2** : Expanded fleet dataset with additional archetypes, emitter model corrections (n=1.3), and full parameter sensitivity analysis.
3. **Layer 3** : Real-home validation — digital twin predictions vs metered performance at 30-second resolution.

## What Is QSH?

QSH is a hybrid deterministic + adaptive thermal optimisation system for residential heat pumps, currenlty running as a Home Assistant add-on but is system agnostic. It combines:

- **System identification**: online learning of building thermal parameters (heat loss coefficients, thermal mass, solar gains) from live sensor data
- **Deterministic control layer**: physics-based energy balance with COP-aware flow temperature selection, safety constraints, and comfort guarantees
- **Adaptive layer**: reinforcement learning for predictive optimisation, operating within the deterministic safety envelope

The deterministic layer alone — no AI, no machine learning, just engineering done properly — outperforms stock controllers by a significant margin.

## Methodology

See [docs/methodology.md](docs/methodology.md) for the full technical paper covering energy balance equations, the emitter model, COP interpolation, weather compensation analysis, and fleet simulation framework.

## Contributing

This is an active research project. If you work in heat pumps, energy policy, building physics, or process control — scrutiny is welcome. Open an issue or reach out on LinkedIn.

## Licence

Apache 2.0. See [LICENSE](LICENSE).
