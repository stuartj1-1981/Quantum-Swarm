# QSH — Quantum Swarm Heating

**Physics-based thermal optimisation for residential heat pumps.**

A digital twin fleet simulation framework that models heat pump performance across UK housing archetypes, climate zones, and control strategies. Built by a process control engineer (ISA S88/S95/S106, 28 years) who watched a heat pump controller hunt and overshoot in patterns that wouldn't survive a factory floor audit.

---

## The Metric That Matters

People are not charged on COP. They are charged on kWh of electrical input.

The correct performance metric is the cost to deliver one kWh of useful heat to your home:

```
Cost per kWh(thermal) = Tariff (p/kWh electrical) / COP
```

At the Ofgem Q1 2026 standard tariff (27.69p/kWh):

| Strategy | COP | Cost per kWh heat delivered |
|---|---|---|
| Fixed flow 45°C — common installer default | 3.37 | 8.22p |
| Weather compensation — best-practice WC | 4.00 | 6.92p |
| **QSH — fleet predicted, full authority** | **4.09** | **6.77p** |

---

> ## For every 10,000 kWh of heat delivered to your home:
>
> ### QSH saves 522 kWh of electricity versus fixed flow 45°C
>
> ### QSH saves 55 kWh of electricity versus weather compensation
>
> **For a typical UK semi-detached (~12,000 kWh heat/year):**
> **QSH saves 627 kWh and £174 per year versus fixed flow.**
> **QSH saves 66 kWh and £18 per year versus weather compensation.**

---

These are fleet-predicted figures for QSH at full RL authority. The saving versus fixed flow is available from the deterministic layer alone — no machine learning required.

---

## The WC Finding

Weather compensation is the best strategy available from stock controllers. Across 348,170 fleet simulation runs, WC consistently achieves higher COP than fixed-flow strategies and delivers **28–48% energy savings** versus fixed 45°C flow:

| Archetype | WC Saving vs Fixed 45°C | WC Mean COP | Fixed 45°C Mean COP |
|-----------|------------------------:|:-----------:|:--------------------:|
| flat_purpose | −48.3% | 4.10 | 3.45 |
| bungalow_1960s | −36.0% | 3.98 | 3.35 |
| terrace_victorian_retro | −30.8% | 3.98 | 3.35 |
| semi_1970s | −32.1% | 3.93 | 3.31 |
| semi_1970s_retro | −30.3% | 4.08 | 3.43 |
| terrace_victorian | −30.5% | 3.91 | 3.30 |
| detached_1990s | −28.8% | 3.91 | 3.30 |
| newbuild_2020s | −28.1% | 4.10 | 3.44 |

*Source: fleet.db — 348,170 runs across 8 HP models, 8 archetypes, 10 UK climate zones, 27 WC curves.*

**But WC leaves performance on the table.** WC follows a single-variable outdoor-to-flow curve with no awareness of building state, zone demand, or compressor loading. QSH improves on WC by +1.8–2.7% COP across all archetypes — and live validation shows this fleet prediction is conservative, because the fleet does not yet model shoulder mode.

---

## The Shoulder Mode Finding

The live installation reveals an operating regime the fleet does not yet model: **shoulder mode**.

Every inverter-driven ASHP has a minimum modulation threshold — a load floor below which the compressor operates inefficiently or short-cycles. QSH monitors aggregate demand across all zones and gates HP operation on this threshold. When total demand is below threshold, the HP holds off. When demand aggregates above threshold, the HP runs properly loaded.

In mild conditions (outdoor ~9°C), this demand-gated operation produces flow temperatures of 38–49°C — and COP jumps:

| Operating Regime | Flow Temp | COP | HP Power | Mechanism |
|---|---|---|---|---|
| Standard space heating | 30–37°C | 3.82 | 0.77 kW | Below compressor sweet spot |
| **Shoulder mode** | **38–49°C** | **4.77** | **1.15 kW** | **Compressor in efficient load band** |

**COP uplift: +24.9%.** Higher flow temperature, higher COP — the inverse of the WC narrative. The mechanism is compressor load factor: at 0.77 kW mean demand, the HP operates below its isentropic efficiency peak. In shoulder mode at 1.15 kW, it hits the sweet spot. The RL independently converged on a 41°C flow proposal — in the centre of the shoulder efficiency band — from reward signals alone, without being provided HP efficiency data.

WC cannot achieve this. WC has no concept of aggregate demand — it fires the HP whenever any single zone calls for heat, regardless of load. At 9°C outdoor, WC sets flow to ~29°C and runs the compressor at low load. QSH holds off until demand justifies operation, then runs properly loaded at 38–49°C.

**If shoulder mode were incorporated into the fleet model, the predicted QSH advantage over WC would increase from +1.8–2.7% COP to +3.1–7.1% COP**, depending on seasonal shoulder duty assumptions. At a 205 m² installation, this represents **370–740 kWh/yr additional electricity saving** beyond what the current fleet predicts.

---

## Live Validation

A live QSH installation (205 m², 13 controlled zones, Octopus Cosy 6) provides 16 days of 30-second resolution historian data against which fleet predictions have been tested.

**Measured shoulder mode COP: 4.77.** Fleet simulation predicted QSH COP of 4.09–4.22 for the Cosy 6 across climate zones. The live system exceeds fleet predictions because the fleet does not yet model the aggregate demand gate that produces shoulder mode efficiency. This is not measurement error — it is a real operating regime the fleet model has not yet been updated to capture.

Both the deterministic controller and the RL adaptive layer independently drove flow temperatures above the manufacturer WC setting, converging from different starting points — consistent with the fleet simulation's prediction that QSH finds higher-efficiency operating points than WC curves provide.

Live system identification has confirmed U values in 8 rooms showing **13–193× divergence from SAP industry priors**. This divergence is not error. It is the QSH thesis: real buildings do not match textbook values. WC installers setting curves from SAP heat loss calculations are working with fiction.

---

## What This Repository Contains

| Path | Description |
|------|-------------|
| `twin/engine/engine.py` | ThermalEngine — physics stepping model (per-room heat loss, thermal mass, solar gains, emitter output) |
| `twin/engine/emitter_model.py` | Radiator/UFH output model (LMTD correction, EN 442 basis) |
| `twin/archetypes/archetypes.py` | UK housing archetype generator (8 types from Victorian terrace to 2020s newbuild) |
| `twin/fleet/batch.py` | Fleet simulation batch runner (parallel execution, SQLite output) |
| `twin/fleet/fleet_report.py` | Report generation from fleet results database |
| `twin/cop_models/cop_model.py` | COP bilinear interpolation from manufacturer/EN 14511 data grids |
| `twin/wc_curves/wc_curves.py` | 27 manufacturer weather compensation curves (Cosy, Daikin, Ecodan, Grant, Samsung, Vaillant, MCS, plus per-archetype minimum adequate) |
| `twin/weather/weather.py` | Climate zone weather data loader |
| `docs/methodology.md` | Full methodology paper: energy balance, emitter physics, WC analysis, live validation, cost-per-kWh analysis |

---

## Quick Start

### Prerequisites

Python 3.10+ and SQLite3. No GPU required — fleet simulations run on CPU.

```bash
# Clone the repository
git clone https://github.com/stuartj1-1981/Quantum-Swarm.git
cd qsh

# Install dependencies
pip install pyyaml numpy
```

### 1. Query the Fleet Results

The fastest way to explore is to query `fleet.db` directly:

```bash
# QSH vs WC advantage by archetype
sqlite3 fleet.db "
  SELECT
    archetype,
    ROUND(AVG(CASE WHEN strategy='hp_wc' THEN mean_cop END), 2) as wc_cop,
    ROUND(AVG(CASE WHEN strategy='qsh_capped' THEN mean_cop END), 2) as qsh_cop,
    ROUND((AVG(CASE WHEN strategy='qsh_capped' THEN mean_cop END)
         - AVG(CASE WHEN strategy='hp_wc' THEN mean_cop END))
         / AVG(CASE WHEN strategy='hp_wc' THEN mean_cop END) * 100, 1) as qsh_advantage_pct
  FROM runs
  WHERE strategy IN ('hp_wc', 'qsh_capped')
  GROUP BY archetype
  ORDER BY qsh_advantage_pct DESC;
"

# Cost per kWh of heat delivered by strategy (standard tariff 27.69p)
sqlite3 fleet.db "
  SELECT
    strategy,
    ROUND(AVG(mean_cop), 3) as avg_cop,
    ROUND(27.69 / AVG(mean_cop), 2) as pence_per_kwh_heat
  FROM runs
  WHERE strategy IN ('hp_fixed_45', 'hp_wc', 'qsh_capped')
  GROUP BY strategy
  ORDER BY pence_per_kwh_heat;
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
                  LIMIT 1)
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
# ~348,000 runs — takes several hours on an M4 Max, longer on older hardware
python -m twin.batch \
    --profiles profiles/ \
    --weather twin/weather_data/ \
    --hours 168 \
    --workers 8 \
    --output results/
```

---

## Fleet Simulation Design

**348,170 runs** covering the following parameter space:

- **8 heat pump models**: Cosy 6kW, Cosy 9kW, Daikin 4kW, Daikin 8kW, Vaillant 5kW, Ecodan 8.5kW, Samsung 6kW, Grant 6kW (each with per-model COP maps from EN 14511 data, capacity derating, and sizing filters to prevent nonsensical pairings)
- **8 UK housing archetypes**: bungalow_1960s, semi_1970s, semi_1970s_retro, terrace_victorian, terrace_victorian_retro, detached_1990s, newbuild_2020s, flat_purpose (parameters from SAP, CIBSE Guide A, BRE)
- **10 climate zones**: Aberdeen, Belfast, Birmingham, Cardiff, Edinburgh, London, Manchester, Newcastle, plus beast_from_east and mild_winter boundary cases
- **8 strategies**: hp_fixed_45, hp_fixed_50, hp_fixed_55, hp_wc (with 27 WC curves), qsh_capped, qsh_uncapped, stock, stock_weather_comp
- **Thermostat setpoints**: 18–25°C
- **Schedules**: continuous, night_setback

Each run produces hourly data: outdoor temperature, room temperature, flow temperature, HP power, COP, energy consumed, and cost. All stored in `fleet.db` as queryable SQLite.

SHA-256 checksums for both databases (`fleet.db`, `qsh_live.db`) are documented in Appendix A of the [Correlation Technical Analysis](docs/QSH_Fleet_Correlation_Technical_Analysis.md). Verify checksums before use to confirm you are working with the same database versions used to produce the published results.

---

## The Emitter Capacity Problem

Weather compensation assumes that lowering flow temperature always saves energy because COP improves. This is true in isolation. But emitters are part of the system.

Radiator output follows a power law relationship with mean water temperature:

```
Q_actual = Q_rated × (MWT_actual − T_room) / (MWT_design − T_room))^n
```

Where n = 1.3 for standard radiators (EN 442). At lower flow temperatures, emitter output falls faster than COP improves. The heat pump must run longer — sometimes continuously — to maintain setpoint. At the current fleet emitter exponent (n=1.15, generous to WC), WC still delivers energy savings over fixed flow. At the EN 442 standard exponent (n=1.3), the emitter bottleneck tightens and WC's energy advantage narrows. This is the subject of Layer 2 investigation.

**Breakeven point**: the emitter oversizing ratio at which WC's COP advantage fully offsets the emitter capacity penalty is a function of the exponent n. The Layer 2 fleet expansion will model n=1.3 with emitter oversizing as an explicit variable to quantify the conditions under which WC ceases to save energy on standard UK housing stock.

---

## Three-Layer Publishing Sequence

| Layer | Status | Description |
|---|---|---|
| **Layer 1** | ✅ **You are here** | Methodology, fleet simulation framework, WC analysis, baseline results on archetype priors |
| **Layer 2** | ⏳ Planned | Expanded fleet: n=1.3 emitter model, emitter oversizing as variable, 84 archetype profiles, full heating season, QSH strategies with thermostat gating |
| **Layer 3** | ⏳ In progress | Real-home validation — SYS-ID convergence, digital twin predictions vs 30-second metered reality, RMSE/bias metrics. 16 days of live historian data collected; 8 of 13 rooms with identified U values |

---

## What Is QSH?

QSH is a hybrid deterministic + adaptive thermal optimisation system for residential heat pumps, currently running as a Home Assistant add-on but is system agnostic. It combines:

- **System identification**: online learning of building thermal parameters (heat loss coefficients, thermal mass, solar gains) from live sensor data. Live installation has identified real U values 13–193× above SAP priors.
- **Deterministic control layer**: physics-based energy balance with COP-aware flow temperature selection, safety constraints, and comfort guarantees. The deterministic layer alone outperforms stock controllers.
- **Adaptive layer**: reinforcement learning for predictive optimisation, operating within the deterministic safety envelope. The RL independently converges on the load-factor efficiency optimum — currently proposing 41°C flow on an installation where WC would set 36–37°C.

The deterministic layer alone — no AI, no machine learning, just engineering done properly — outperforms stock controllers by a significant margin. The RL provides incremental improvement on top of a sound deterministic foundation.

---

## Methodology

See [docs/methodology.md](docs/methodology.md) for the full technical paper covering energy balance equations, emitter model, COP interpolation, weather compensation analysis, fleet framework, 16-day live validation, and cost-per-kWh analysis.

---

## Contributing

This is an active research project. If you work in heat pumps, energy policy, building physics, or process control — scrutiny is welcome. Open an issue or reach out on LinkedIn.

---

## Licence

Apache 2.0. See [LICENSE](LICENSE).
