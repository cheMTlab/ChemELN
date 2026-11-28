"""Response-surface modelling for screening campaigns, with two-layer output.

* Plain layer: short sentences a bench chemist can act on.
* Expert layer: model terms, coefficients, standard errors, R², adjusted R², Q² (leave-one-out),
  RMSE, residuals.

Numpy only (no scipy). Continuous/discrete variables are coded to [-1, 1]; categorical ones
are one-hot encoded against the first level. Model size grows with the data: linear → + squares
→ + two-way interactions, keeping at least 3 residual degrees of freedom. Predictions outside
the explored region are always labelled as extrapolation.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass

import numpy as np


@dataclass
class Var:
    id: str
    name: str
    kind: str
    unit: str
    low: float | None
    high: float | None
    levels: list

    @property
    def numeric(self) -> bool:
        return self.kind in ("continuous", "discrete")

    def bounds(self) -> tuple[float, float]:
        if self.kind == "continuous":
            return float(self.low), float(self.high)
        nums = [float(x) for x in self.level_values()]
        return min(nums), max(nums)

    def level_values(self) -> list:
        return [lv["value"] if isinstance(lv, dict) else lv for lv in self.levels]

    def code(self, x: float) -> float:
        lo, hi = self.bounds()
        return 0.0 if hi == lo else (2 * (float(x) - lo) / (hi - lo)) - 1

    def decode(self, c: float) -> float:
        lo, hi = self.bounds()
        return lo + (c + 1) / 2 * (hi - lo)


def make_vars(variables: list[dict]) -> list[Var]:
    return [
        Var(
            str(v["id"]),
            v["name"],
            v["kind"],
            v.get("unit", ""),
            v.get("low"),
            v.get("high"),
            v.get("levels") or [],
        )
        for v in variables
    ]


# --- design matrix -------------------------------------------------------------------------


class Encoder:
    def __init__(self, vars_: list[Var], order: str):
        self.vars = vars_
        self.order = order  # "linear" | "quadratic" | "interactions"
        self.terms: list[str] = ["Intercept"]
        self.cat_levels: dict[str, list] = {}
        for v in vars_:
            if v.numeric:
                self.terms.append(v.name)
            else:
                lv = v.level_values()
                self.cat_levels[v.id] = lv
                self.terms += [f"{v.name}[{x}]" for x in lv[1:]]
        num = [v for v in vars_ if v.numeric]
        if order in ("quadratic", "interactions"):
            self.terms += [f"{v.name}²" for v in num]
        if order == "interactions":
            self.terms += [f"{a.name}×{b.name}" for a, b in itertools.combinations(num, 2)]

    def row(self, factors: dict) -> list[float]:
        out = [1.0]
        coded = {}
        for v in self.vars:
            x = factors.get(v.id)
            if v.numeric:
                c = v.code(x)
                coded[v.id] = c
                out.append(c)
            else:
                out += [1.0 if x == lv else 0.0 for lv in self.cat_levels[v.id][1:]]
        num = [v for v in self.vars if v.numeric]
        if self.order in ("quadratic", "interactions"):
            out += [coded[v.id] ** 2 for v in num]
        if self.order == "interactions":
            out += [coded[a.id] * coded[b.id] for a, b in itertools.combinations(num, 2)]
        return out

    def matrix(self, runs: list[dict]) -> np.ndarray:
        return np.array([self.row(r) for r in runs], dtype=float)


def _choose_order(vars_: list[Var], n: int) -> str:
    for order in ("interactions", "quadratic", "linear"):
        p = len(Encoder(vars_, order).terms)
        if n - p >= 3:
            return order
    return "linear"


# --- fitting -------------------------------------------------------------------------------


@dataclass
class Fit:
    encoder: Encoder
    beta: np.ndarray
    xtx_inv: np.ndarray
    sigma: float
    dof: int
    y: np.ndarray
    yhat: np.ndarray
    X: np.ndarray

    def predict(self, factors: dict) -> tuple[float, float]:
        x = np.array(self.encoder.row(factors))
        mean = float(x @ self.beta)
        se = float(self.sigma * math.sqrt(max(0.0, 1 + x @ self.xtx_inv @ x))) if self.dof else 0
        return mean, se


def fit_model(vars_: list[Var], runs: list[dict], y: list[float], order: str | None = None):
    order = order or _choose_order(vars_, len(y))
    enc = Encoder(vars_, order)
    X = enc.matrix(runs)
    Y = np.array(y, dtype=float)
    # Ridge-stabilised normal equations (tiny penalty, not on intercept).
    penalty = np.eye(X.shape[1]) * 1e-8
    penalty[0, 0] = 0
    xtx_inv = np.linalg.pinv(X.T @ X + penalty)
    beta = xtx_inv @ X.T @ Y
    yhat = X @ beta
    dof = max(0, len(Y) - np.linalg.matrix_rank(X))
    sse = float(((Y - yhat) ** 2).sum())
    sigma = math.sqrt(sse / dof) if dof else 0.0
    return Fit(enc, beta, xtx_inv, sigma, dof, Y, yhat, X)


def _metrics(fit: Fit) -> dict:
    y, yhat = fit.y, fit.yhat
    n, p = len(y), len(fit.beta)
    sst = float(((y - y.mean()) ** 2).sum())
    sse = float(((y - yhat) ** 2).sum())
    r2 = 1 - sse / sst if sst > 0 else 0.0
    adj = 1 - (1 - r2) * (n - 1) / (n - p) if n - p > 0 else None
    H = fit.X @ fit.xtx_inv @ fit.X.T
    lev = np.clip(np.diag(H), 0, 0.999999)
    press = float((((y - yhat) / (1 - lev)) ** 2).sum())
    q2 = 1 - press / sst if sst > 0 else None
    return {
        "n": n,
        "terms": p,
        "r2": round(r2, 4),
        "r2_adj": None if adj is None else round(adj, 4),
        "q2": None if q2 is None else round(q2, 4),
        "rmse": round(math.sqrt(sse / n), 4) if n else None,
        "residual_dof": fit.dof,
    }


def _quality_word(q2, r2) -> str:
    score = q2 if q2 is not None else r2
    if score is None or score < 0.3:
        return "weak: treat suggestions as rough hints and collect more data"
    if score < 0.6:
        return "moderate: trends are probably real, exact numbers are not"
    if score < 0.85:
        return "good"
    return "very good"


# --- public API ----------------------------------------------------------------------------


def observed_data(variables, runs, response_id):
    rows, y = [], []
    for r in runs:
        val = (r.get("results") or {}).get(str(response_id))
        if r.get("status") == "done" and val not in (None, ""):
            try:
                y.append(float(val))
            except (TypeError, ValueError):
                continue
            rows.append({str(k): v for k, v in r["factors"].items()})
    return rows, y


def main_effects(vars_: list[Var], rows: list[dict], y: list[float], bins: int = 5) -> list:
    out = []
    Y = np.array(y)
    for v in vars_:
        xs = [r.get(v.id) for r in rows]
        points = []
        if v.numeric:
            lo, hi = v.bounds()
            edges = np.linspace(lo, hi, bins + 1)
            vals = np.array([float(x) for x in xs])
            for i in range(bins):
                mask = (vals >= edges[i]) & (
                    (vals <= edges[i + 1]) if i == bins - 1 else (vals < edges[i + 1])
                )
                if mask.any():
                    points.append(
                        {
                            "x": round(float(vals[mask].mean()), 4),
                            "mean": round(float(Y[mask].mean()), 4),
                            "n": int(mask.sum()),
                        }
                    )
        else:
            for lv in v.level_values():
                mask = np.array([x == lv for x in xs])
                if mask.any():
                    points.append(
                        {"x": lv, "mean": round(float(Y[mask].mean()), 4), "n": int(mask.sum())}
                    )
        out.append(
            {
                "variable": v.id,
                "name": v.name,
                "unit": v.unit,
                "numeric": v.numeric,
                "points": points,
            }
        )
    return out


def analyse(variables: list[dict], response: dict, runs: list[dict]) -> dict:
    vars_ = make_vars(variables)
    rows, y = observed_data(variables, runs, response["id"])
    name, unit = response["name"], response.get("unit", "")
    result = {"response": str(response["id"]), "name": name, "n": len(y)}
    if not y:
        result["plain"] = [f"No finished runs with a value for {name} yet."]
        return result
    Y = np.array(y)
    best_i = int(Y.argmin() if response.get("goal") == "minimize" else Y.argmax())
    result["observed"] = {
        "min": round(float(Y.min()), 4),
        "max": round(float(Y.max()), 4),
        "mean": round(float(Y.mean()), 4),
        "best_factors": rows[best_i],
        "best_value": round(float(Y[best_i]), 4),
    }
    result["main_effects"] = main_effects(vars_, rows, y)
    plain = [f"Best so far: {Y[best_i]:.4g} {unit} ({len(y)} finished runs)."]
    min_runs = 1 + sum(1 if v.numeric else max(1, len(v.levels) - 1) for v in vars_) + 2
    if len(y) < min_runs:
        plain.append(
            f"Need at least {min_runs} finished runs to fit a model ({min_runs - len(y)} more)."
        )
        result["plain"] = plain
        return result

    fit = fit_model(vars_, rows, y)
    metrics = _metrics(fit)
    terms = []
    for i, t in enumerate(fit.encoder.terms):
        se = math.sqrt(max(0.0, fit.xtx_inv[i, i])) * fit.sigma if fit.dof else None
        tval = (fit.beta[i] / se) if se else None
        terms.append(
            {
                "term": t,
                "coef": round(float(fit.beta[i]), 5),
                "se": None if se is None else round(se, 5),
                "t": None if tval is None else round(float(tval), 3),
                "significant": bool(tval is not None and abs(tval) >= 2),
            }
        )

    # Importance: swing of the prediction when one variable moves, the others at the centre.
    centre = {v.id: (v.decode(0) if v.numeric else v.level_values()[0]) for v in vars_}
    importance = []
    for v in vars_:
        if v.numeric:
            lo, hi = v.bounds()
            grid = np.linspace(lo, hi, 21)
            preds = [fit.predict({**centre, v.id: float(g)})[0] for g in grid]
            k_max, k_min = int(np.argmax(preds)), int(np.argmin(preds))
            importance.append(
                {
                    "variable": v.id,
                    "name": v.name,
                    "swing": round(max(preds) - min(preds), 4),
                    "best_at": round(
                        float(grid[k_max if response.get("goal") != "minimize" else k_min]), 4
                    ),
                    "direction": "up" if preds[-1] > preds[0] else "down",
                    "curve": [
                        {"x": round(float(g), 4), "y": round(p, 4)}
                        for g, p in zip(grid, preds, strict=True)
                    ],
                }
            )
        else:
            preds = {str(lv): fit.predict({**centre, v.id: lv})[0] for lv in v.level_values()}
            best = (min if response.get("goal") == "minimize" else max)(preds, key=preds.get)
            importance.append(
                {
                    "variable": v.id,
                    "name": v.name,
                    "swing": round(max(preds.values()) - min(preds.values()), 4),
                    "best_at": best,
                    "levels": {k: round(p, 4) for k, p in preds.items()},
                }
            )
    importance.sort(key=lambda d: -d["swing"])

    quality = _quality_word(metrics["q2"], metrics["r2"])
    plain.append(
        f"The model explains {metrics['r2'] * 100:.0f} % of the variation in {name} "
        f"(prediction quality {quality})."
    )
    for imp in importance[:3]:
        if imp["swing"] <= 0:
            continue
        if "curve" in imp:
            v = next(x for x in vars_ if x.id == imp["variable"])
            lo, hi = v.bounds()
            curve = [p["y"] for p in imp["curve"]]
            peak_inside = 0 < int(np.argmax(curve)) < len(curve) - 1
            if peak_inside and response.get("goal") != "minimize":
                plain.append(
                    f"{imp['name']}: optimum near {imp['best_at']:.3g} {v.unit} "
                    f"(changes {name} by up to {imp['swing']:.3g} {unit})."
                )
            else:
                verb = "increases" if imp["direction"] == "up" else "decreases"
                plain.append(
                    f"Raising {imp['name']} from {lo:.3g} to {hi:.3g} {v.unit} {verb} {name} "
                    f"by about {imp['swing']:.3g} {unit}."
                )
        else:
            plain.append(
                f"{imp['name']}: best choice {imp['best_at']} "
                f"(spread {imp['swing']:.3g} {unit} between choices)."
            )
    sig_inter = [t["term"] for t in terms if "×" in t["term"] and t["significant"]]
    if sig_inter:
        plain.append(
            "Variables interact (" + ", ".join(sig_inter) + "): the best setting of one "
            "depends on the other, so change them together."
        )

    result.update(
        {
            "plain": plain,
            "model": {
                "order": fit.encoder.order,
                "metrics": metrics,
                "terms": terms,
                "residuals": [
                    {"observed": round(float(a), 4), "predicted": round(float(b), 4)}
                    for a, b in zip(fit.y, fit.yhat, strict=True)
                ],
            },
            "importance": importance,
        }
    )
    return result


def _explored(vars_, rows):
    box = {}
    for v in vars_:
        if v.numeric:
            vals = [float(r[v.id]) for r in rows if r.get(v.id) is not None]
            box[v.id] = (min(vals), max(vals)) if vals else v.bounds()
        else:
            box[v.id] = {r.get(v.id) for r in rows}
    return box


def is_extrapolation(vars_, box, factors) -> list[str]:
    reasons = []
    for v in vars_:
        x = factors.get(v.id)
        if v.numeric:
            lo, hi = box[v.id]
            if float(x) < lo - 1e-9 or float(x) > hi + 1e-9:
                reasons.append(f"{v.name} = {x} is outside the tested range {lo:g}–{hi:g}")
        elif x not in box[v.id]:
            reasons.append(f"{v.name} = {x} was never tested")
    return reasons


def predict(variables, response, runs, factors: dict) -> dict:
    vars_ = make_vars(variables)
    rows, y = observed_data(variables, runs, response["id"])
    if len(y) < 3:
        raise ValueError("Not enough finished runs to predict.")
    fit = fit_model(vars_, rows, y)
    mean, se = fit.predict({str(k): v for k, v in factors.items()})
    reasons = is_extrapolation(
        vars_, _explored(vars_, rows), {str(k): v for k, v in factors.items()}
    )
    return {
        "prediction": round(mean, 4),
        "interval95": [round(mean - 2 * se, 4), round(mean + 2 * se, 4)] if se else None,
        "extrapolation": bool(reasons),
        "warnings": reasons,
    }


def desirability(value, response, ymin, ymax) -> float:
    if ymax == ymin:
        return 1.0
    goal = response.get("goal")
    if goal == "minimize":
        d = (ymax - value) / (ymax - ymin)
    elif goal == "target" and response.get("target") is not None:
        span = max(abs(ymax - response["target"]), abs(response["target"] - ymin)) or 1
        d = 1 - abs(value - response["target"]) / span
    else:
        d = (value - ymin) / (ymax - ymin)
    return float(min(1.0, max(1e-6, d)))


def suggest(variables, responses, runs, k: int = 4, explore: bool = True, seed=None) -> dict:
    """Propose the next runs from the fitted models (weighted desirability over goals)."""
    vars_ = make_vars(variables)
    active = [r for r in responses if r.get("goal") != "monitor"]
    if not active:
        raise ValueError("Give at least one response a goal (maximize, minimize, target).")
    fits = []
    for resp in active:
        rows, y = observed_data(variables, runs, resp["id"])
        if len(y) < 3:
            raise ValueError(f"Not enough finished runs with {resp['name']} to suggest.")
        fits.append((resp, fit_model(vars_, rows, y), min(y), max(y), rows))
    rows_all = fits[0][4]
    box = _explored(vars_, rows_all)
    rng = np.random.default_rng(seed)
    from .design import random_design

    cands = random_design(
        [
            {
                "id": v.id,
                "kind": "continuous" if v.kind == "continuous" else v.kind,
                "low": v.low,
                "high": v.high,
                "levels": v.levels,
                "name": v.name,
            }
            for v in vars_
        ],
        4000,
        seed=int(rng.integers(1 << 31)),
    )
    scored = []
    for c in cands:
        ds, preds, unc = [], {}, 0.0
        for resp, fit, lo, hi, _ in fits:
            m, se = fit.predict(c)
            preds[str(resp["id"])] = round(m, 3)
            ds.append(desirability(m, resp, lo, hi) ** resp.get("weight", 1.0))
            unc += se / ((hi - lo) or 1)
        total_w = sum(r.get("weight", 1.0) for r, *_ in fits)
        score = float(np.prod(ds) ** (1 / total_w))
        scored.append((score, unc, c, preds))
    scored.sort(key=lambda t: -t[0])

    def far_enough(c, chosen):
        for o in chosen:
            dist = sum(
                (v.code(c[v.id]) - v.code(o[v.id])) ** 2 if v.numeric else float(c[v.id] != o[v.id])
                for v in vars_
            )
            if dist < 0.15:
                return False
        return True

    picked = []
    for score, _unc, c, preds in scored:
        if len(picked) >= (k - 1 if explore else k):
            break
        if far_enough(c, [p["factors"] for p in picked]):
            reasons = is_extrapolation(vars_, box, c)
            picked.append(
                {
                    "factors": c,
                    "predicted": preds,
                    "score": round(score, 3),
                    "purpose": "exploit",
                    "extrapolation": bool(reasons),
                    "warnings": reasons,
                }
            )
    if explore:
        score, unc, c, preds = max(scored, key=lambda t: t[1])
        reasons = is_extrapolation(vars_, box, c)
        picked.append(
            {
                "factors": c,
                "predicted": preds,
                "score": round(score, 3),
                "purpose": "explore (most uncertain region)",
                "extrapolation": bool(reasons),
                "warnings": reasons,
            }
        )
    return {"suggestions": picked}
