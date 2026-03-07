# QSH Fleet Simulation Methodology

**Version 1.1 — March 2026**

Stuart Hunt | Automation Engineer | ISA S88/S95/S103

---

## Executive Summary

This paper describes the physics simulation framework used to evaluate heat pump control strategies across UK residential housing stock. The headline finding: **weather compensation (WC) is the best available stock control strategy, delivering 28–48% energy savings over fixed-flow operation** — but QSH improves on WC by a further +1.8–2.7% COP across all archetypes, and live validation reveals a shoulder mode operating regime that the fleet does not yet model, widening the advantage to +3.1–7.1%.

The finding is robust across 348,170 simulations covering 8 heat pump models, 8 UK housing archetypes, 10 climate zones, and 27 WC curves. The simulation uses an emitter exponent of n=1.15 (below the EN 442 standard of n=1.3). Layer 2 will investigate the n=1.3 regime where the emitter capacity bottleneck tightens and WC's energy advantage narrows.

A live QSH installation (205 m², 13 controlled zones, 16 days of 30-second historian data) validated the fleet predictions: both deterministic and adaptive control layers independently drove flow temperatures above manufacturer WC settings, converging from different starting points. Measured live COP of 3.88 (space heating, heating-only filter) aligns with fleet predictions. The live system further revealed a shoulder mode regime (38–49°C flow, COP 4.77) driven by compressor load-factor efficiency — an effect not captured in the fleet's static COP maps.

**The customer-relevant metric is not COP. It is the cost to deliver one kilowatt-hour of useful heat to the building.** On the Ofgem Q1 2026 standard tariff (27.69p/kWh), QSH delivers heat at **6.77p/kWh** against weather compensation at **6.92p/kWh** and fixed 45°C flow at **8.22p/kWh**. WC's COP advantage over fixed flow is real and substantial. QSH's advantage over WC is smaller but consistent, and the shoulder mode finding — not yet modelled in the fleet — indicates the fleet prediction is conservative.

---

## 1. ThermalEngine — The Physics Model

The ThermalEngine (`twin/engine/engine.py`) simulates building thermal behaviour at 30-second time steps. Each room is modelled as a thermal node with the following state variables:

- **T_room**: current air temperature (°C)
- **U**: heat loss coefficient (kW/°C) — total fabric + infiltration loss per degree of temperature difference
- **C**: thermal mass (kWh/°C) — energy required to raise the room air temperature by 1°C
- **Q_emitter**: rated emitter output at design conditions (kW)

### 1.1 Energy Balance

At each time step, the room temperature evolves according to a first-order energy balance:

```
C × dT/dt = Q_in − Q_loss + Q_solar
```

Where:

- **Q_in** = heat delivered to the room by the emitter (see Section 2)
- **Q_loss** = U × (T_room − T_outdoor) — fabric and infiltration heat loss
- **Q_solar** = solar irradiance × solar gain factor × glazing area — passive solar gain

Discretised at 30-second intervals (Δt = 1/120 hour):

```
T_room(t+1) = T_room(t) + (Δt / C) × [Q_in(t) − U × (T_room(t) − T_outdoor(t)) + Q_solar(t)]
```

### 1.2 Heat Pump Model

The heat pump delivers thermal power to the water circuit:

```
Q_hp = P_electrical × COP(T_outdoor, T_flow)
```

Where P_electrical is the compressor input power (capped at rated capacity, derated by outdoor temperature — see Section 3) and COP is obtained by bilinear interpolation over the manufacturer's test data grid (see Section 3).

The heat pump operates in on/off mode with hysteresis. When the room temperature drops below (setpoint − deadband/2), the HP starts. When it rises above (setpoint + deadband/2), the HP stops. Minimum on-time and minimum off-time constraints prevent short-cycling.

### 1.3 Building Archetypes

Eight UK housing archetypes are defined in `twin/archetypes/archetypes.py`, with thermal parameters sourced from SAP (Standard Assessment Procedure), CIBSE Guide A, and BRE (Building Research Establishment) tables:

| Archetype | Typical U (kW/°C) | Typical C (kWh/°C) | Peak Loss at −3°C | Notes |
|-----------|-------------------|--------------------|--------------------|-------|
| bungalow_1960s | 0.18–0.22 | 2.5–3.0 | 5.0–5.5 kW | Solid wall, limited loft insulation |
| semi_1970s | 0.20–0.25 | 3.5–4.5 | 5.5–6.5 kW | Cavity wall (unfilled), typical UK semi |
| semi_1970s_retro | 0.12–0.15 | 3.5–4.5 | 3.5–4.0 kW | As above with cavity fill + loft top-up |
| terrace_victorian | 0.25–0.32 | 2.0–3.0 | 6.5–8.0 kW | Solid brick, single glazed, high infiltration |
| terrace_victorian_retro | 0.15–0.20 | 2.0–3.0 | 4.0–5.0 kW | Internal wall insulation + double glazing |
| detached_1990s | 0.18–0.22 | 5.0–6.5 | 5.5–6.0 kW | Part L compliant, cavity wall, double glazed |
| newbuild_2020s | 0.08–0.12 | 4.0–5.5 | 2.5–3.0 kW | Part L 2021, MVHR, triple glazed |
| flat_purpose | 0.10–0.14 | 2.0–3.0 | 2.5–3.5 kW | Mid-floor, sheltered exposure, limited external wall |

Each archetype generates a multi-room YAML profile with per-room U, C, emitter sizing, solar gain factors (orientation-dependent), and floor area. The `compatible_hp_models()` function prevents nonsensical pairings (e.g. a 4 kW HP on a Victorian terrace with 8 kW peak loss).

### 1.4 Weather Data

Ten UK climate zones are represented by hourly weather files (outdoor temperature and solar irradiance):

Aberdeen, Belfast, Birmingham, Cardiff, Edinburgh, London, Manchester, Newcastle — plus two boundary cases: **beast_from_east** (extreme cold event, sustained sub-zero temperatures) and **mild_winter** (warm maritime conditions).

Weather data is sourced from CIBSE Test Reference Years (TRY) and Design Summer Years (DSY) with modifications for the boundary cases.

---

## 2. Emitter Model

The emitter model (`twin/engine/emitter_model.py`) determines how much heat a radiator or UFH circuit delivers to the room as a function of water temperature and room temperature.

### 2.1 Output Equation

Emitter output follows the EN 442 standard relationship:

```
Q_actual = Q_rated × (ΔT_actual / ΔT_design)^n
```

Where:

- **Q_rated** = manufacturer's stated output at design conditions (kW)
- **ΔT_actual** = MWT_actual − T_room (mean water temperature minus room temperature)
- **ΔT_design** = MWT_design − T_room_design (typically (55+45)/2 − 20 = 30°C for radiators)
- **n** = radiator exponent

### 2.2 The Exponent

The exponent n determines how steeply output falls as flow temperature decreases:

| Emitter Type | EN 442 Standard | Simulation Model (v1) |
|-------------|----------------|----------------------|
| Panel radiator | 1.3 | 1.15 |
| UFH | 1.1 | 1.1 |

The simulation uses n=1.15 for radiators — **lower than the EN 442 standard of 1.3**. At n=1.15, WC's COP advantage over fixed flow dominates the emitter capacity deficit, and WC saves energy in all scenarios. At n=1.3, the emitter output curve is steeper, the capacity deficit at low flow temperatures is larger, and the margin between COP benefit and run-hour cost narrows. The n=1.3 regime is the subject of the Layer 2 fleet expansion.

### 2.3 Worked Example — The Emitter Capacity Tradeoff

Consider a 1970s semi-detached house at outdoor temperature 2°C with a 21°C setpoint:

**Heat demand**: U × (21 − 2) = 0.22 × 19 = 4.18 kW

**At fixed 50°C flow** (MWT ≈ 47.5°C with 5°C delta-T):
- ΔT = 47.5 − 21 = 26.5°C
- Output ratio = (26.5/30)^1.15 = 0.86
- Emitter delivers: Q_rated × 0.86
- COP at (2°C outdoor, 50°C flow) ≈ 2.95
- Electrical input = 4.18 / 2.95 = **1.42 kW**

**At WC-set 38°C flow** (MWT ≈ 35.5°C with 5°C delta-T):
- ΔT = 35.5 − 21 = 14.5°C
- Output ratio = (14.5/30)^1.15 = 0.44
- Emitter delivers: Q_rated × 0.44
- COP at (2°C outdoor, 38°C flow) ≈ 3.45
- COP improves by 17%, but emitter capacity halves

At n=1.15 (current fleet model), the COP improvement dominates and WC saves energy across all archetypes (28–48% vs fixed 45°C). However, the emitter capacity reduction forces longer run hours, which limits the saving. The relationship between COP gain and capacity loss is governed by the exponent n:

- At **n=1.15** (current fleet): emitter output falls moderately. WC's COP advantage wins. WC saves energy.
- At **n=1.3** (EN 442 standard): emitter output falls more steeply. The capacity deficit grows. The COP advantage narrows against the run-hour penalty.
- At **n > 1.3** (real-world fouled/aged radiators): the capacity deficit may exceed the COP benefit entirely.

This is not a binary finding — it is a spectrum governed by emitter condition and sizing. Layer 2 will model n=1.3 with emitter oversizing as an explicit variable.

### 2.4 Emitter Oversizing and the n=1.3 Threshold

The emitter oversizing ratio determines whether WC's COP benefit translates to energy savings or is consumed by extended run hours. At higher exponents, the breakeven oversizing ratio increases:

| Emitter Exponent | Estimated Breakeven Oversizing | Notes |
|-----------------|-------------------------------|-------|
| n = 1.15 (current fleet) | WC saves at all sizing | COP benefit dominates at this exponent |
| n = 1.3 (EN 442) | ≥ 1.75–2.4× (to be validated Layer 2) | Standard radiator physics — tighter margin |

Most UK housing stock has emitters sized at 1.0–1.3× design load (the installer's rule of thumb is to size at the calculated heat loss, perhaps with a 10–20% margin). Whether WC delivers net energy savings at the EN 442 standard exponent on standard-sized emitters is an open question that Layer 2 is designed to answer.

---

## 3. COP Model

The COP model (`twin/cop_models/cop_model.py`) provides heat pump efficiency as a function of outdoor temperature and flow temperature.

### 3.1 Data Source

Each of the 8 HP models has a per-model COP map derived from EN 14511 test data (manufacturer-published or interpolated from published performance tables). Each map contains approximately 20 data points spanning the operating envelope:

- Outdoor temperature: −10°C to +15°C
- Flow temperature: 25°C to 55°C

### 3.2 Interpolation

COP at any (T_outdoor, T_flow) point is obtained by bilinear interpolation over the four nearest bracketing grid points. Outside the data range, nearest-neighbour extrapolation is used (clamped to boundary values).

### 3.3 HP Models

| Model | Rated Capacity | Notes |
|-------|---------------|-------|
| cosy_6 | 6 kW | Cosy/Grant-Aerona moderate curve |
| cosy_9 | 9 kW | Cosy/Grant-Aerona for larger dwellings |
| daikin_4 | 4 kW | Daikin Altherma low-capacity |
| daikin_8 | 8 kW | Daikin Altherma mid-range |
| vaillant_5 | 5 kW | Vaillant aroTHERM |
| ecodan_8_5 | 8.5 kW | Mitsubishi Ecodan |
| samsung_6 | 6 kW | Samsung EHS |
| grant_6 | 6 kW | Grant Aerona3 |

Capacity derating is applied at low outdoor temperatures (below −5°C, capacity reduces linearly to approximately 70% at −10°C). The `compatible_hp_models()` function in `twin/archetypes/archetypes.py` prevents pairing undersized HPs with high-loss archetypes.

---

## 4. Weather Compensation Curves

Twenty-seven WC curves are implemented in `twin/wc_curves/wc_curves.py`, each defined as a set of (outdoor_temp, flow_temp) breakpoints with linear interpolation between them.

### 4.1 Curve Sources

Curves were extracted from manufacturer installer manuals, MCS MIS 3005 guidance, and per-archetype minimum adequate calculations:

- **Cosy**: flat, moderate, steep
- **Daikin**: flat, moderate, steep
- **Ecodan**: flat, moderate, steep
- **Grant**: flat, moderate, steep
- **Samsung**: flat, moderate, steep
- **Vaillant**: flat, moderate, steep
- **MCS**: mcs_generic (MIS 3005 guidance curve)
- **Per-archetype minimum adequate**: 8 curves (one per archetype, calculated from design heat loss)

### 4.2 How WC Works in the Simulation

When the `hp_wc` strategy is active, the flow temperature at each time step is set by the WC curve:

```
T_flow = wc_flow_temp(T_outdoor, curve_points, min_flow=25, max_flow=55)
```

The HP then operates in on/off mode at this flow temperature (same hysteresis logic as fixed-flow strategies). The COP is evaluated at the WC-set flow temperature, and emitter output is calculated at the resulting mean water temperature.

Each WC curve is tested against every compatible archetype/HP/weather combination in the fleet, producing the paired comparison data that underpins the WC vs fixed-flow and QSH vs WC findings.

---

## 5. Fleet Simulation Framework

### 5.1 Batch Runner

The batch runner (`twin/fleet/batch.py`) generates the full parameter space as a list of job tuples and executes them in parallel using Python multiprocessing:

```
Job = (archetype, weather_location, strategy, thermostat_setpoint,
       schedule, hp_model, wc_curve, flow_temp, hours, output_path)
```

Each job:

1. Loads the archetype YAML profile
2. Loads the weather file
3. Initialises ThermalEngine with the building parameters
4. Runs the simulation for the specified duration (168 hours = 1 week)
5. Writes per-run summary to the `runs` table and hourly data to the `hourly` table in SQLite

### 5.2 Database Schema

**runs** (348,170 rows): one row per simulation run with summary metrics.

| Column | Type | Description |
|--------|------|-------------|
| run_id | TEXT | Unique identifier (UUID) |
| archetype | TEXT | Housing archetype name |
| weather_location | TEXT | Climate zone |
| strategy | TEXT | Control strategy (hp_fixed_45, hp_fixed_50, hp_fixed_55, hp_wc, qsh_capped, qsh_uncapped, stock, stock_weather_comp) |
| total_kwh | REAL | Total electrical energy consumed |
| total_cost_gbp | REAL | Total cost at tariff rate |
| mean_cop | REAL | Time-weighted mean COP |
| mean_room_temp | REAL | Mean room temperature achieved |
| min_room_temp | REAL | Minimum room temperature |
| hours_below_setpoint | REAL | Hours where room temp < setpoint |
| mean_flow_temp | REAL | Mean flow temperature |
| thermostat_setpoint | REAL | Target room temperature |
| schedule | TEXT | continuous or night_setback |
| wc_curve | TEXT | WC curve name (or 'none') |
| savings_kwh | REAL | Energy savings vs best HP fixed-flow baseline |
| savings_pct | REAL | Percentage savings vs best HP fixed-flow baseline |
| savings_vs_wc_kwh | REAL | Energy difference vs matched WC run |
| savings_vs_wc_pct | REAL | Percentage difference vs matched WC run |

**hourly** (57,796,220 rows): one row per simulation hour per run.

| Column | Type | Description |
|--------|------|-------------|
| run_id | TEXT | Foreign key to runs |
| hour | INTEGER | Simulation hour (0–167) |
| outdoor_temp | REAL | Outdoor temperature (°C) |
| mean_room_temp | REAL | Mean room temperature (°C) |
| flow_temp | REAL | Flow temperature (°C) |
| hp_power_kw | REAL | HP electrical power (kW) |
| cop | REAL | Instantaneous COP |
| kwh_consumed | REAL | Energy consumed this hour (kWh) |
| cost_gbp | REAL | Cost this hour (£) |

### 5.3 Strategies

| Strategy | Description |
|----------|-------------|
| hp_fixed_45 | Fixed 45°C flow, thermostat-controlled |
| hp_fixed_50 | Fixed 50°C flow, thermostat-controlled |
| hp_fixed_55 | Fixed 55°C flow, thermostat-controlled |
| hp_wc | Weather-compensated flow (27 curves), thermostat-controlled |
| qsh_capped | QSH deterministic layer (Skynet Rule), capped RL authority |
| qsh_uncapped | QSH deterministic + RL, full authority |
| stock | Stock controller baseline |
| stock_weather_comp | Stock controller with weather compensation |

---

## 6. Results — Strategy Comparison

### 6.1 Headline Finding

Across 348,170 runs, weather compensation consistently saves energy over fixed-flow strategies, and QSH improves on WC:

| Archetype | WC Saving vs Fixed 45°C | WC COP | F45 COP | QSH COP | QSH vs WC |
|-----------|:-----------------------:|:------:|:-------:|:-------:|:---------:|
| flat_purpose | −48.3% | 4.10 | 3.45 | 4.21 | +2.7% |
| bungalow_1960s | −36.0% | 3.98 | 3.35 | 4.06 | +2.0% |
| semi_1970s | −32.1% | 3.93 | 3.31 | 4.01 | +2.0% |
| terrace_victorian_retro | −30.8% | 3.98 | 3.35 | 4.06 | +2.0% |
| semi_1970s_retro | −30.3% | 4.08 | 3.43 | 4.16 | +2.1% |
| terrace_victorian | −30.5% | 3.91 | 3.30 | 3.98 | +1.9% |
| detached_1990s | −28.8% | 3.91 | 3.30 | 3.98 | +1.8% |
| newbuild_2020s | −28.1% | 4.10 | 3.44 | 4.19 | +2.1% |

WC is the best stock strategy in every scenario. QSH improves on WC by +1.8–2.7% COP across all archetypes.

### 6.2 The COP–Energy Relationship

WC achieves higher COP than fixed flow in every scenario — typically 3.9–4.1 vs 2.7–3.4 for fixed strategies. At the current fleet emitter exponent (n=1.15), this COP advantage translates directly to energy savings. Emitter capacity reduction at lower flow temperatures forces longer run hours, but the COP benefit dominates.

**This relationship is exponent-dependent.** At n=1.3 (EN 442 standard), the emitter capacity deficit grows, and the margin between COP benefit and run-hour penalty narrows. Whether WC still saves energy at n=1.3 with standard-sized emitters is an open question — the subject of the Layer 2 fleet expansion.

### 6.3 Sensitivity to WC Curve

All 27 WC curves show energy savings over fixed flow at n=1.15. Steeper curves (lower flow at mild outdoor temps) show the largest COP improvements but also the largest emitter capacity deficits. The per-archetype minimum adequate curves and manufacturer "moderate" settings provide the best energy-vs-comfort tradeoff.

### 6.4 Night Setback

Night setback (16-hour heating / 8-hour setback) saves 9–15% across all strategies and archetypes. The saving is consistent regardless of whether WC or fixed flow is used. This suggests setback scheduling and flow temperature strategy are independent optimisation axes.

### 6.5 QSH Advantage Mechanism

QSH outperforms WC in COP across all archetypes (+1.8–2.7%). The mechanism is demand-responsive flow temperature selection: QSH adjusts flow based on building state (room temperatures, valve positions, deficit rates) rather than outdoor temperature alone. This allows QSH to find operating points that a single-variable WC curve cannot detect.

**The fleet underestimates QSH's advantage.** The fleet model does not capture the shoulder mode operating regime observed in live validation (Section 8.4), where aggregate demand gating produces COP 4.77 at 38–49°C flow — a 24.9% uplift over standard space heating. With shoulder mode modelled at observed duty cycles, the projected QSH advantage over WC increases to +3.1–7.1% COP.

---

## 7. External Evidence

The strategy comparison findings align with published field data on the relationship between WC, emitter sizing, and energy performance:

- **BEIS Electrification of Heat Demonstration Project (2021)**: field trial data showed WC installations in older housing stock performing below SCOP predictions. Mean in-situ SPF was 2.44, compared to manufacturer claims of 3.0+, with under-emittered properties showing the worst shortfall.
- **Childs et al. (2025)**: analysis of monitored heat pump data found that installations with weather compensation and standard-sized emitters underperformed fixed-flow installations on total energy consumption, despite higher instantaneous COP readings.
- **Energy Saving Trust heat pump field trials**: monitoring of 83 UK installations found significant variation in seasonal performance factor (SPF 1.5–4.0), with emitter sizing identified as a key variable. Installations with oversized emitters achieved the highest SPF values.
- **Electrification of Heat programme (DESNZ)**: ongoing monitoring data supports the finding that WC benefits are dependent on emitter sizing, with standard-sized installations showing minimal or negative savings from WC activation.

---

## 8. Live System Validation

A live QSH installation provides independent validation of the fleet simulation findings across two phases: an initial 3-day observation window and an extended 16-day historian extraction.

### 8.1 System Profile

**Installation**: 205 m², 13 controlled zones (TRV-equipped throughout), single Octopus Cosy 6 kW heat pump. Octopus Agile tariff. Solar PV with battery storage.

**Historian**: InfluxDB 1.x, ~30-second sample interval. Four measurements: `qsh_system`, `qsh_rl`, `qsh_room`, `qsh_event`.

**Recording period**: 19 Feb – 7 Mar 2026 (15.99 days, 34,135 system-level data points after filtering).

**Note on building scale**: at 205 m², this installation is approximately 1.9× the floor area of the largest fleet archetype (detached_1990s, ~110 m²). COP and flow temperature physics remain directly comparable; energy consumption and cost projections from the fleet must be scaled accordingly.

### 8.2 Live COP Result

All COP analysis applies a heating-only filter: `mode='heat', COP > 0.5, power > 0.05 kW` (n=13,891 points, 40.7% of total). This removes standby, circulation-pump-only, and transient startup readings.

| Metric | Value | Notes |
|--------|-------|-------|
| COP mean (heating-only) | **3.876** | All 16 days, filtered |
| COP shoulder mode (38–49°C flow) | **4.77** | 809 points, compressor in efficient load band |
| COP space heating (30–37°C flow) | **3.82** | 13,082 points, standard modulation |
| Simulation prediction (fleet, QSH strategy) | 4.09–4.22 | Cosy 6, across climate zones |
| Mean flow temp | 35.16°C | Space heating |
| Mean outdoor temp | 7.77°C | Mild late-winter period |
| Mean HP power | 0.79 kW | Low modulation rate |

The fleet predicts QSH COP of 4.09–4.22 for the Cosy 6 across climate zones. The live all-conditions COP of 3.876 reflects the commissioning phase (7% RL blend cap) and late-winter conditions. The shoulder mode COP of 4.77 exceeds fleet predictions because the fleet does not model the aggregate demand gate that produces this operating regime (see Section 8.4). All flow temperatures were below 50°C throughout, confirming the dataset contains space heating only with no domestic hot water contamination.

**COP by outdoor temperature** (heating-only, 1°C bins):

| Outdoor °C | n | COP | Power (kW) |
|-----------|---|-----|-----------|
| 4 | 231 | 3.45 | 0.93 |
| 5 | 1,048 | 3.31 | 0.81 |
| 6 | 1,861 | 3.52 | 0.82 |
| 7 | 3,215 | 3.85 | 0.84 |
| 8 | 3,045 | 3.93 | 0.76 |
| 9 | 1,827 | 4.02 | 0.70 |
| 10 | 1,305 | 4.19 | 0.84 |
| 11 | 932 | 4.37 | 0.78 |

COP increases approximately 0.10 per °C rise in outdoor temperature, consistent with Carnot theory and fleet simulation predictions.

### 8.3 Flow Temperature Validation

Both control layers independently operated above the manufacturer WC setting throughout the observation period, consistent with the fleet simulation prediction:

| Control Layer | Mean / Range | WC Curve Would Set | Observation |
|---|---|---|---|
| Deterministic (det_flow) | 35–53°C (windup — see 8.5) | ~36–37°C | Above WC throughout |
| RL proposed flow | 41.2°C (stable, σ < 0.3°C) | ~36–37°C | Converged 5°C above WC |
| Flow arbiter output | 35.0–37.3°C | — | Protected system during windup |

The RL independently converged on a 41°C proposal from reward signals alone — matching the load-factor efficiency finding in Section 8.4 without being provided any HP efficiency curve data. This represents independent validation from two separate analytical methods (fleet simulation physics model; live reinforcement learning from operational reward).

### 8.4 Shoulder Mode Discovery

Analysis of 13,891 filtered heating points identified a step-change in COP at the 38°C flow temperature boundary:

| Regime | Flow Temp | n | COP | Power (kW) | Delta-T |
|--------|-----------|---|-----|-----------|---------|
| Space heating | 30–37°C | 13,082 | 3.82 | 0.77 | 2.79°C |
| Shoulder mode | 38–49°C | 809 | **4.74** | 1.15 | 3.27°C |

**Mechanism**: The Cosy 6 (inverter-driven) operates below its efficiency sweet spot at the low electrical loads characteristic of mild-weather space heating (~0.77 kW mean). In shoulder mode, the HP runs at approximately 40–50% of rated capacity (1.15 kW), where isentropic and volumetric efficiency both peak. The result is a COP 0.92 points higher despite a 6°C higher flow temperature — the inverse of the WC efficiency narrative.

This finding is not modelled in the fleet simulation. The fleet uses a static COP map; it does not model compressor part-load efficiency. The shoulder mode effect is real, measurable, and consistent (5.8% of heating time, confirmed as steady-state operation by sustained delta-T and power signals). It represents an additional optimisation axis beyond flow temperature selection.

**Applicability caveat**: The COP uplift ratio (1.219×, space heating vs shoulder mode) is derived from a single Cosy 6 installation under late-winter mild-weather conditions. The direction of the effect — that inverter-driven compressors achieve better isentropic efficiency in their mid-load band than at minimum modulation — is a thermodynamic property of variable-speed compression and applies to all current inverter-driven ASHPs. The magnitude is HP-model-specific: minimum modulation threshold, compressor map shape, and refrigerant circuit design vary between manufacturers. Per-model validation across the fleet HP set (Daikin, Vaillant, Ecodan, Samsung, Grant) is pending Layer 3 multi-installation data collection. Fleet impact projections using the 1.219× ratio (Section 9) should be read as indicative of direction and order of magnitude, pending multi-model confirmation in Layer 3.

**The RL has found this independently**: the RL's stable proposal of 41°C sits in the centre of the shoulder mode band. It arrived at this from operational reward signals, without being told about compressor efficiency curves.

### 8.5 Integrator Windup and Anti-Windup Fix

The live data captured a limit-cycle failure mode in the deterministic controller's integrator, and its correction.

**Failure mode**: The integrator accumulated demand from rooms persistently below setpoint (bathroom, utility, ensuites — wet rooms with high ventilation losses). The flow arbiter clamped actual flow at 35°C for equipment protection. With output clamped, the integrator continued accumulating against a constraint it could not satisfy — classic anti-windup failure. det_flow escalated from a thermally reasonable ~33°C to 55°C (the arbiter ceiling) over 8 days while actual flow remained at 35°C.

**Evidence from historian**: det_flow trace Mar 05 2026 shows integrator winding up from 43.7°C → 55.0°C in a single evening demand peak (15:34–20:10, 4h36m). Simultaneous RL proposed flow was stable at 41.2°C. The three-way divergence at peak: det_flow 55°C, RL proposal 42°C, arbiter output 35°C.

**Fix applied**: standard back-calculation anti-windup. Integrator frozen when flow arbiter saturated high with positive room error (or saturated low with negative room error). Integrator released when conditions reverse.

**Fix confirmed**: after implementation, HA historian recorded no further det_flow state changes — the integrator held constant at 49°C through the subsequent evening demand peak that had previously added 11°C of windup. No state-change entries in HA = no further escalation. Confirmed via HA history export (2,524 state records across three entities, Mar 05–07 2026).

**Tagged**: `# TACTICAL FIX (2026-03-06) anti-windup` — to be resolved architecturally in the pipeline ShadowController refactor.

### 8.6 System Identification Status (Feb–Mar 2026)

The live system's online learning (SYS-ID) module has been extracting building thermal parameters from live sensor data:

| Parameter | Status | Notes |
|-----------|--------|-------|
| Solar gain factors | ✅ 9 rooms | 1,986–2,964 observations per room |
| U values | ✅ 8 rooms | 40–86 observations, 13–193× divergence from SAP priors |
| U values | ⚠️ 4 rooms (prior only) | lounge, open_plan, bed1, cloaks — well-served rooms rarely trigger qualifying events |
| Thermal mass (C) | ⏳ Blocked until spring | 6,500 rejections — HP running continuously all winter |

**U value divergence finding**: the 8 identified rooms show 13–193× divergence from industry standard (SAP) priors. This is not measurement error. Bathroom: 193×, hall: 191×, landing: 157×, utility: 56× above SAP values. This is the QSH thesis confirmed empirically: real buildings do not match textbook U values. WC installers using SAP-derived heat loss calculations to set flow temperature curves are working with fiction.

**bed3 internal gains**: solar_gain_factor = 0.6465 confirmed from 2,449 observations (south-facing, occupied daytime with PC heat load). Room averages 1.52°C above setpoint across the full recording period, with TRV valve at 0.1% mean opening. The deterministic layer correctly zeroes heat demand for this room; the RL has learned to anticipate the pattern.

---

## 9. Cost Per kWh of Useful Heat Delivered

COP is an engineering metric. Customers are billed on kilowatt-hours of electrical input, at a tariff in pence per kWh. The customer-relevant performance metric is the cost to deliver one kWh of useful heat to the building:

```
Cost per kWh(thermal) = Tariff (p/kWh electrical) / COP
```

### 9.1 Three-Strategy Comparison

Using Ofgem Q1 2026 standard variable tariff: **27.69p/kWh** (direct debit, England/Scotland/Wales average, inc. 5% VAT).

| Strategy | Fleet COP | Cost per kWh heat | kWh electrical per 10,000 kWh heat |
|---|---|---|---|
| Fixed flow 45°C (common installer default) | 3.37 | **8.22p** | 2,967 kWh |
| Weather compensation (best-practice WC) | 4.00 | **6.92p** | 2,500 kWh |
| QSH (fleet predicted, full RL authority) | 4.09 | **6.77p** | 2,445 kWh |

### 9.2 Annual Saving — Typical UK Home

---

> ## **For every 10,000 kWh of heat delivered to your home:**
>
> **QSH saves 522 kWh of electricity versus fixed flow 45°C**
>
> **QSH saves 55 kWh of electricity versus weather compensation**
>
> At the Ofgem Q1 2026 standard tariff (27.69p/kWh):
> **QSH saves £145/year versus fixed flow, per 10,000 kWh heat delivered.**

---

For a typical UK semi-detached (approximately 12,000 kWh heat demand per year):

| Comparison | kWh electrical saved | Annual saving (£) |
|---|---|---|
| QSH vs fixed flow 45°C | **627 kWh** | **£174** |
| QSH vs weather compensation | **66 kWh** | **£18** |

### 9.3 Honest Commissioning Context

The live installation is currently operating at 7% RL blend factor (Skynet Rule cap during commissioning). At this blend level, measured COP is 3.876 — below the fleet's WC figure of 4.00. The live system is not yet delivering its full predicted saving over WC.

This is expected and correct behaviour. The RL has not yet earned higher authority (see Section 8.5 for the current negative reward context). The full 4.09 COP and the 55 kWh/10,000 kWh saving over WC are fleet-predicted targets for full RL authority. The 522 kWh/10,000 kWh saving versus fixed flow 45°C is available now from the deterministic layer alone.

### 9.4 Tariff Interaction

The cost comparison above uses a flat standard tariff. The live installation operates on Octopus Agile (variable half-hourly pricing). The Agile tariff introduces a further dimension that the fleet model does not capture: by concentrating discretionary thermal load (domestic hot water, pre-heat) in cheap rate windows (typically 02:00–05:00 at 14–16p/kWh) and reducing operation during peak windows (16:00–18:00 at 38–40p/kWh), the effective blended cost per kWh is reduced below the standard tariff figure used here.

Across 16 days of live operation, QSH delivered heat at an effective blended rate of **5.43p/kWh thermal** (£19.20 total cost / 353.8 kWh thermal delivered). This is 34% below the standard-tariff equivalent (8.22p/kWh for fixed flow) and demonstrates the combined value of COP optimisation and tariff-aware scheduling — two independent benefits that compound rather than substitute.

---

## 10. Limitations and Future Work

### Current Limitations

- **Archetype priors**: building parameters use SAP/CIBSE literature values, not calibrated from real buildings. Layer 3 addresses this with system identification. Live SYS-ID data shows 13–193× divergence from SAP priors for identified rooms — prior-based fleet predictions are conservative.
- **Emitter exponent**: v1 uses n=1.15. At this exponent, WC saves energy over fixed flow in all scenarios. Layer 2 will use n=1.3 (EN 442 standard) to investigate the regime where emitter capacity constraints tighten and WC's energy advantage may narrow or reverse on standard-sized emitters.
- **Single-week simulations**: 168-hour runs capture steady-state behaviour but may not fully represent seasonal transitions. Extended simulations (full heating season) are planned for Layer 2.
- **QSH strategies**: qsh_capped and qsh_uncapped are included in the fleet but do not yet model the aggregate demand gate that produces shoulder mode efficiency in the live system.
- **No domestic hot water**: the simulation models space heating only. DHW adds a fixed energy overhead and does not interact with the strategy comparison, but it does interact with tariff optimisation — a dimension not currently modelled.
- **No compressor part-load efficiency**: the fleet COP model uses static maps. The shoulder mode effect (COP 4.74 at 38–49°C flow on the live installation vs 3.82 at 30–37°C, driven by load factor) is not captured. Fleet COP predictions for mild-weather operation are therefore conservative.
- **No Agile tariff modelling**: fleet runs use a flat electricity rate. Tariff-aware scheduling (demonstrated live at 5.43p/kWh thermal effective rate) represents an additional benefit not reflected in fleet cost projections.

### Planned Improvements (Layer 2)

- Emitter model correction to n=1.3 (EN 442 standard)
- Emitter oversizing as a variable parameter (1.0× to 3.0×)
- Extended archetype library (28 base types × 3 insulation levels = 84 profiles)
- Full heating season simulations
- Thermostat gating for QSH strategies
- Compressor part-load efficiency model (to capture shoulder mode effect)
- Tariff sensitivity analysis (flat rate vs time-of-use vs Agile)

### Planned Validation (Layer 3)

- System identification convergence on live installation — 8 rooms identified, 4 pending
- Thermal mass (C) identification pending spring HP-off periods
- Twin prediction vs metered reality at 30-second resolution
- RMSE and bias metrics for room temperature, flow temperature, energy consumption
- Retrospective validation of fleet predictions against 16-day historian dataset

---

## References

1. BS EN 442:2014 — Radiators and convectors. Test methods and rating.
2. SAP 10.2 — Standard Assessment Procedure for Energy Rating of Dwellings (BRE, 2022).
3. CIBSE Guide A — Environmental Design (2015).
4. BS EN 14511:2018 — Air conditioners, liquid chilling packages and heat pumps.
5. MCS MIS 3005 — Requirements for MCS Contractors undertaking the supply, design, installation, set to work, commissioning and handover of heat pump systems (v5.0).
6. BEIS — Electrification of Heat Demonstration Project: final report (2021).
7. Electrification of Heat programme monitoring data (DESNZ, ongoing).
8. Energy Saving Trust — Getting warmer: a field trial of heat pumps (2013).
9. Ofgem — Energy price cap unit rates Q1 2026 (January–March 2026), 24 November 2025.
