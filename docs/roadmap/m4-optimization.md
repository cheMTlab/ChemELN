# M4: Reaction screening & optimization campaigns (design)

**Goal:** a chemist sets up an optimization campaign for a reaction in minutes and enters or imports results with almost no manual data handling. Every variable is followed on live graphs, including over time within a run. Models explain the relations between variables, extrapolate where to go next, and say how confident they are.

**Decisions from the design review (2026-11-25):**
- **Data:** handle end-point *and* time-course data.
- **Analysis screens:** two layers, a plain-language default plus an expert details panel.
- **Equipment:** manual vials, HTE plates, flow chemistry and automated platforms.
- **Additions accepted:** hidden-variable capture, cost and green goals, learning from past campaigns, robot export.

## 1. Concepts
| Object | What it is |
|---|---|
| **Campaign** | One optimization effort for one reaction, linked to its ELN reaction scheme. Has one or more **goals** (maximise yield, ee ≥ 95 %, minimise cost/g, maximise greenness) and a **mode**: batch, HTE plate, flow, or automated platform |
| **Variable** (controlled) | A factor you change. *Continuous* (T, time, concentration, equiv., catalyst loading, residence time, flow rate, light intensity), *discrete* (0.5/1/2 mol %), or *categorical* (solvent, base, ligand, photocatalyst), with choices **picked from the inventory**. Categoricals can carry descriptors (solvent polarity, ligand cone angle, pKa) so models can generalise and suggest untested options |
| **Context variable** (captured automatically) | Things nobody sets deliberately but which can matter: reagent **lot number, bottle age, opened date, supplier, purity** (from the inventory containers actually used), operator, date, equipment ID, ambient humidity if a sensor is linked. Recorded on every run without typing (see §5) |
| **Response** | A measured outcome: yield, conversion, selectivity, ee/er, d.r., purity, by-product ratio, isolated mass, or a **derived** response from a formula (space–time yield, TON/TOF, cost/g, E-factor, PMI) |
| **Run** | One set of variable values + responses. Each run *is* an ELN experiment, so amounts, reagents used and stock deductions come for free. Status: planned / running / done / **failed** (failed runs are kept as data, see §7) |
| **Time series** (optional per run) | Responses measured at several times: manual sampling, in-situ IR/NMR/UV, or online HPLC. Stored as (t, value) series per response |
| **Batch / plate** | Runs done together: a 24/48/96/384-well plate with a visual plate map, a set of flasks, or one flow sequence |

## 2. Workflow
1. **Define:** pick the reaction and the mode, then add variables, ranges and goals. Templates are available (Pd cross-coupling, photoredox, amide coupling, hydrogenation, flow).
2. **Design:** choose a strategy. CheMTlab shows the number of runs and the material each one needs from the inventory.
   - Screening: full/fractional factorial, Plackett–Burman, definitive screening design, Latin hypercube, one-factor-at-a-time.
   - Optimization: response-surface designs (central composite, Box–Behnken) or **Bayesian optimization** that suggests the next batch, including multi-objective goals ([BayBE](https://github.com/emdgroup/baybe), Apache-2.0; runs on the server).
   - **Warm start** from similar earlier campaigns on this instance (§6).
   - Constraints: forbidden combinations (e.g. solvent boiling point < T), total volume, budget.
3. **Execute:**
   - Manual: printable run sheet or plate map with amounts calculated from stock solutions in the inventory, plus barcode labels per vial.
   - HTE: plate-map editor (drag variables across rows and columns, randomise positions to avoid edge effects).
   - Robots: export worklists (§8).
   - Flow: sequence of steady states, with equilibration times calculated from reactor volume and flow rate.
4. **Enter results (easy data handling):**
   - an editable spreadsheet grid (paste straight from Excel); CSV/XLSX import with saved column mappings;
   - LC-MS/HPLC/GC area exports mapped to wells or vials automatically, with **internal-standard calibration curves** turning areas into yields; calibrations are reused across campaigns;
   - plate-reader exports; robot result files;
   - from M6, instrument files arriving through the drop-folder agent fill responses directly;
   - validation flags outliers, missing values and impossible values (yield > 100 %, mass balance off) before they reach the models.
5. **Monitor (live dashboard):** see §3.
6. **Analyse & extrapolate:** see §4.
7. **Conclude:** promote the best conditions to a new ELN procedure (with a scale-up checklist). Export the campaign as CSV/XLSX, JSON, RO-Crate, or an [Open Reaction Database](https://open-reaction-database.org) record, for publications and FAIR data.

## 3. Graphs
All charts are interactive (zoom, hover to see the run and open its ELN entry) and exportable as SVG/PNG for papers.

**Campaign level**
- Progress: best result so far vs run/batch number, with the BO model's expected improvement.
- Response vs each variable (scatter + trend); main-effects and interaction plots.
- Plate heatmaps (spot edge effects or a bad dispensing column); 2-variable grid heatmaps.
- Contour and 3-D response surfaces from the fitted model, with tested points overlaid.
- Parallel-coordinates plot: all variables at once, filter by brushing.
- Pareto front for multi-objective goals (e.g. yield vs cost/g vs greenness).
- Context-variable view: response coloured by reagent lot, operator or date (§5).

**Run level (time-course)**
- Concentration/conversion vs time for every species, with several runs overlaid.
- Initial-rate determination, fitted rate constants, half-life.
- Kinetic analysis for mechanism: variable time normalisation analysis (VTNA) and reaction-progress kinetic analysis (RPKA) overlays to estimate reaction orders. Catalyst deactivation/induction detection (same-excess experiments).
- Flow: response vs residence time; steady-state detection on online data.

## 4. Models & extrapolation (two layers)
**Default layer (for chemists):** plain-language findings, ranked variables and a suggested next step, for example:
> "Temperature has the largest effect (+18 % yield per 20 °C). Solvent × base interaction matters: Cs₂CO₃ works only in polar solvents. Predicted optimum: 85 °C, DMAc, 1.5 equiv Cs₂CO₃ → 91 % ± 4 %. That point is inside the tested region."

The optional LLM can phrase this summary if an admin enables it. Without it, the summary comes from templates.

**Details layer (for experts):** ANOVA tables, coefficients, p-values, R²/Q², residual plots, cross-validation, model comparison, design power and aliasing.

Models:
- multiple linear / quadratic regression (classic DoE);
- random forest + SHAP for variable importance when relations are non-linear;
- Gaussian process (the BayBE surrogate) with **uncertainty bands**, used for predictions and extrapolation;
- kinetic models for time-course data (simple rate laws fitted per run; parameters can themselves become responses, e.g. k vs T → Arrhenius/Eyring plot).

**Extrapolation is always labelled.** Predictions outside the tested region are shown hatched, with widened uncertainty and a warning. Every model fit is stored with its data snapshot and package versions, so it can be reproduced.

## 5. Hidden-variable capture
Because runs use inventory containers, each run records the container ID, **lot, supplier, purity, opened date and age**, plus operator, date and equipment, with no extra typing. CheMTlab then:
- includes these as optional factors in the models, and warns when one explains a large share of variance ("runs using K₃PO₄ lot B12 average 22 % lower yield");
- shows a "suspect reagent" panel, with a link to mark that container for re-testing or disposal in the inventory.

This is a feature standalone ELNs or inventories can't offer.

## 6. Learning from past campaigns
- Every finished campaign becomes reusable knowledge on the instance (subject to group permissions).
- When a new campaign starts, CheMTlab finds similar ones (same reaction class or similar substrates, by reaction fingerprint) and offers to **warm-start** the model (BayBE transfer learning), cutting the number of runs needed.
- Shows a "what worked before" panel: the best conditions from similar campaigns.
- From M7 (federation), institutions can opt in to share anonymised campaign data with each other.

## 7. Failed and negative results
Failed runs (no conversion, decomposition, insoluble, exotherm) are recorded with a reason code and kept in the models. The model learns where *not* to go, and the campaign export includes them, supporting publication of negative data.

## 8. Cost and green goals
- **Cost per gram of product** is calculated from inventory prices (container price ÷ amount) and the amounts used.
- **Greenness:** solvent scores from the CHEM21 selection guide, PMI, E-factor, and hazard penalties from GHS data in the inventory.
- These can be goals or constraints ("maximise yield, keep cost < €5/g, avoid 'hazardous' solvents").

## 9. Robots and automated platforms
- **Export:** worklists in vendor-neutral CSV, plus adapters for Opentrons (Python protocol), Chemspeed and Unchained Labs import formats. Plate maps carry over.
- **Import:** robot logs (actual dispensed amounts replace planned ones) and analysis results.
- **Closed loop (self-driving lab):** an API endpoint where a platform asks "next batch?", gets suggestions, runs them and posts results back. A human-approval step is on by default.

## 10. Delivery inside M4
| Phase | Scope |
|---|---|
| **M4a: core** | Campaigns, variables, responses, runs as ELN experiments; classic DoE designs; spreadsheet/CSV entry with validation; main graphs (progress, scatter, main effects, heatmaps); regression with two-layer output; failed runs |
| **M4b: smart optimization** | Bayesian optimization (single + multi-objective, constraints); HTE plate editor; LC/GC area import with calibration; hidden-variable capture; cost & green goals; GP surfaces with extrapolation labelling; Pareto front |
| **M4c: time & automation** | Time-course data and kinetic analysis (VTNA/RPKA, Arrhenius); flow mode with steady-state detection; robot export/import; closed-loop API; warm start from past campaigns |

## 11. Technical notes
- Backend app `apps/campaigns`. Analysis uses pandas, statsmodels, scikit-learn, SHAP, BayBE and SciPy (kinetic fits), run in Celery jobs so the UI never blocks.
- Data model: `Campaign`, `Variable`, `Response`, `Run` (FK to ELN `Experiment`), `RunValue`, `TimePoint`, `Plate`/`Well`, `Calibration`, `ModelFit` (data snapshot hash + versions + serialized result).
- Charts: Plotly in the React app. The large spreadsheet grid uses an open-source data grid (e.g. AG Grid Community, MIT).
- All licences are AGPL-compatible (Apache-2.0, MIT, BSD).
