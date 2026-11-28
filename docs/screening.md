# Reaction screening & optimization

A **campaign** optimises one reaction. It works for manual vials, HTE plates, flow reactors and robots.

1. **Variables** are what you change:
   - continuous ranges, such as temperature, time or catalyst loading;
   - discrete numbers, such as equivalents;
   - categories, such as solvent, base or ligand.
2. **Responses** are what you measure. Each response has a goal: maximise, minimise, hit a target, or only record. Responses also have weights. Typical choices are yield, selectivity, cost, E-factor and ee.
3. **Design.** CheMTlab can generate:
   - a full factorial;
   - a Latin hypercube, a space-filling first screen that scales to many variables;
   - centre-point replicates, to measure noise;
   - one factor at a time;
   - random points.

   The run order is randomised. For HTE campaigns, runs are assigned to wells (A1, A2…) across as many plates as needed.
4. **Runs.** Enter results in the grid, or import a CSV with a `run` (or `well`) column and one column per response. *Export CSV* gives the run list for a robot, Excel or Python. Each run can record the inventory **lot barcodes** it used, so lot-to-lot effects become visible.
5. **Analysis** comes in two layers:
   - *Plain language*. For example: "Temperature: optimum near 82 °C", "Solvent: best choice EtOH/H₂O", "Raising Pd loading from 0.5 to 5 mol% increases yield by about 11 %", plus whether variables interact.
   - *Expert details*. Model terms, coefficients, standard errors, t-values, R², adjusted R², Q² (leave-one-out) and RMSE, with plots of effects and of predicted vs measured values.

   The model grows with the data: linear, then quadratic, then two-way interactions. It always keeps at least 3 residual degrees of freedom.
6. **What next?**
   - CheMTlab suggests diverse runs with the best predicted combined goal (weighted desirability across responses). It adds one run in the most uncertain region, to learn rather than to win.
   - *What if…?* predicts any condition, with a 95 % range.
   - Anything outside the tested region is clearly flagged as **extrapolation**.

The planned next phases are in [the M4 design](roadmap/m4-optimization.md): Bayesian optimisation, time courses, flow mode and closed-loop robots.
