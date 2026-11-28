"""Design-of-experiments generators and well assignment. Pure functions (numpy only)."""

import itertools
import string

import numpy as np

MAX_RUNS = 2000


def _levels(var: dict, n_continuous: int) -> list:
    if var["kind"] == "continuous":
        lo, hi = var["low"], var["high"]
        if n_continuous <= 1:
            return [lo]
        return [round(float(x), 6) for x in np.linspace(lo, hi, n_continuous)]
    return [lvl["value"] if isinstance(lvl, dict) else lvl for lvl in var["levels"]]


def full_factorial(variables: list[dict], levels_per_continuous: int = 3) -> list[dict]:
    grids = [_levels(v, levels_per_continuous) for v in variables]
    count = int(np.prod([len(g) for g in grids])) if grids else 0
    if count > MAX_RUNS:
        raise ValueError(f"Full factorial would need {count} runs (max {MAX_RUNS}).")
    return [
        {v["id"]: val for v, val in zip(variables, combo, strict=True)}
        for combo in itertools.product(*grids)
    ]


def latin_hypercube(variables: list[dict], n: int, seed: int | None = None) -> list[dict]:
    """Space-filling design: each continuous range is cut into n strata, used once each."""
    rng = np.random.default_rng(seed)
    runs = [{} for _ in range(n)]
    for v in variables:
        if v["kind"] == "continuous":
            strata = (rng.permutation(n) + rng.random(n)) / n
            vals = v["low"] + strata * (v["high"] - v["low"])
            for r, x in zip(runs, vals, strict=True):
                r[v["id"]] = round(float(x), 4)
        else:
            lv = _levels(v, 0)
            picks = np.resize(rng.permutation(len(lv)), n)
            rng.shuffle(picks)
            for r, i in zip(runs, picks, strict=True):
                r[v["id"]] = lv[int(i)]
    return runs


def random_design(variables: list[dict], n: int, seed: int | None = None) -> list[dict]:
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        run = {}
        for v in variables:
            if v["kind"] == "continuous":
                run[v["id"]] = round(float(rng.uniform(v["low"], v["high"])), 4)
            else:
                lv = _levels(v, 0)
                run[v["id"]] = lv[int(rng.integers(len(lv)))]
        out.append(run)
    return out


def center_points(variables: list[dict], n: int) -> list[dict]:
    """Replicates at the centre: estimate noise and detect curvature."""
    run = {}
    for v in variables:
        if v["kind"] == "continuous":
            run[v["id"]] = round((v["low"] + v["high"]) / 2, 4)
        else:
            lv = _levels(v, 0)
            run[v["id"]] = lv[len(lv) // 2]
    return [dict(run) for _ in range(n)]


def one_factor_at_a_time(variables: list[dict], levels_per_continuous: int = 5) -> list[dict]:
    base = center_points(variables, 1)[0]
    out = [dict(base)]
    for v in variables:
        for val in _levels(v, levels_per_continuous):
            if val != base[v["id"]]:
                out.append({**base, v["id"]: val})
    return out


GENERATORS = {
    "full_factorial": "Every combination of levels",
    "latin_hypercube": "Space-filling sample (good first screen with many variables)",
    "random": "Random points",
    "center_points": "Replicates at the centre (noise estimate)",
    "ofat": "One factor at a time around the centre",
}


def generate(kind: str, variables: list[dict], n: int = 12, levels: int = 3, seed=None):
    if not variables:
        raise ValueError("Add at least one variable first.")
    for v in variables:
        if v["kind"] == "continuous" and (v["low"] is None or v["high"] is None):
            raise ValueError(f"Variable {v['name']} needs a low and a high value.")
        if v["kind"] != "continuous" and not v["levels"]:
            raise ValueError(f"Variable {v['name']} needs at least one level.")
    if kind == "full_factorial":
        return full_factorial(variables, levels)
    if n < 1 or n > MAX_RUNS:
        raise ValueError(f"Number of runs must be 1–{MAX_RUNS}.")
    if kind == "latin_hypercube":
        return latin_hypercube(variables, n, seed)
    if kind == "random":
        return random_design(variables, n, seed)
    if kind == "center_points":
        return center_points(variables, n)
    if kind == "ofat":
        return one_factor_at_a_time(variables, levels)
    raise ValueError(f"Unknown design {kind!r}")


PLATE_SHAPES = {6: (2, 3), 12: (3, 4), 24: (4, 6), 48: (6, 8), 96: (8, 12), 384: (16, 24)}


def well_names(fmt: int) -> list[str]:
    rows, cols = PLATE_SHAPES[fmt]
    letters = string.ascii_uppercase
    return [f"{letters[r]}{c + 1}" for r in range(rows) for c in range(cols)]


def assign_wells(n_runs: int, fmt: int) -> list[tuple[int, str]]:
    names = well_names(fmt)
    return [(i // len(names) + 1, names[i % len(names)]) for i in range(n_runs)]
