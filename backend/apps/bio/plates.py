"""Plate layout helpers, plate-reader import, QC (Z′) and dose-response fitting."""

from __future__ import annotations

import csv
import io
import math
import re
import string

import numpy as np
from django.db import transaction

from .models import PLATE_FORMATS, Measurement, Plate, Well, WellRole, row_label


def parse_well(name: str, fmt: int) -> tuple[int, int]:
    m = re.fullmatch(r"\s*([A-Za-z]{1,2})\s*0*(\d{1,2})\s*", name or "")
    if not m:
        raise ValueError(f"Bad well name {name!r}")
    letters, col = m.group(1).upper(), int(m.group(2)) - 1
    up = string.ascii_uppercase
    row = (
        up.index(letters)
        if len(letters) == 1
        else (up.index(letters[0]) + 1) * 26 + up.index(letters[1])
    )
    rows, cols = PLATE_FORMATS[fmt]
    if not (0 <= row < rows and 0 <= col < cols):
        raise ValueError(f"Well {name} is outside a {fmt}-well plate")
    return row, col


@transaction.atomic
def create_wells(plate: Plate) -> None:
    rows, cols = plate.shape
    Well.objects.bulk_create(
        [Well(plate=plate, row=r, col=c) for r in range(rows) for c in range(cols)],
        ignore_conflicts=True,
    )


@transaction.atomic
def copy_layout(source: Plate, target: Plate) -> None:
    if source.format != target.format:
        raise ValueError("Plates have different formats.")
    src = {(w.row, w.col): w for w in source.wells.all()}
    fields = [
        "role",
        "label",
        "compound_id",
        "strain_id",
        "plasmid_id",
        "sample_id",
        "concentration",
        "concentration_unit",
        "volume_ul",
        "replicate",
        "group_label",
    ]
    for w in target.wells.all():
        s = src.get((w.row, w.col))
        if s:
            for f in fields:
                setattr(w, f, getattr(s, f))
            w.save()


@transaction.atomic
def apply_layout(plate: Plate, wells: list[str], values: dict) -> int:
    """Set the same properties on many wells (selection in the editor)."""
    allowed = {
        "role",
        "label",
        "compound",
        "strain",
        "plasmid",
        "sample",
        "concentration",
        "concentration_unit",
        "volume_ul",
        "replicate",
        "group_label",
        "excluded",
    }
    update = {}
    for k, v in values.items():
        if k not in allowed:
            raise ValueError(f"Unknown field {k}")
        update[k + "_id" if k in {"compound", "strain", "plasmid", "sample"} else k] = v or (
            None
            if k
            in {
                "compound",
                "strain",
                "plasmid",
                "sample",
                "concentration",
                "volume_ul",
                "replicate",
            }
            else v
        )
    coords = [parse_well(w, plate.format) for w in wells]
    n = 0
    for r, c in coords:
        n += Well.objects.filter(plate=plate, row=r, col=c).update(**update)
    return n


@transaction.atomic
def dilution_series(
    plate: Plate,
    *,
    start_well: str,
    direction: str,
    steps: int,
    top: float,
    factor: float,
    unit: str = "µM",
    label: str = "",
    compound=None,
    replicates: int = 1,
) -> int:
    """Serial dilution along a row (direction='row') or column; replicates go to the next
    rows/columns. Wells get role=sample and a shared group_label for curve fitting."""
    r0, c0 = parse_well(start_well, plate.format)
    rows, cols = plate.shape
    group = label or (compound.name if compound else f"Series {start_well}")
    n = 0
    for rep in range(replicates):
        for i in range(steps):
            r, c = (r0 + rep, c0 + i) if direction == "row" else (r0 + i, c0 + rep)
            if r >= rows or c >= cols:
                raise ValueError("The series does not fit on the plate.")
            n += Well.objects.filter(plate=plate, row=r, col=c).update(
                role=WellRole.SAMPLE,
                concentration=top / (factor**i),
                concentration_unit=unit,
                label=group,
                group_label=group,
                replicate=rep + 1,
                compound=compound,
            )
    return n


# --- import ----------------------------------------------------------------------------------


def _num(x: str) -> float | None:
    x = (x or "").strip().replace(",", ".")
    if x in ("", "-", "NA", "N/A", "OVER", "OVRFLW", "#SAT"):
        return None
    try:
        return float(x)
    except ValueError:
        return None


@transaction.atomic
def import_readings(
    plate: Plate, text: str, channel: str = "signal", timepoint: float = 0.0, replace: bool = True
) -> dict:
    """Accepts the two common plate-reader exports:

    * grid: a block of rows A.. with one column per plate column (header 1..12 optional);
    * long: columns 'well' and 'value' (plus optional 'channel', 'time').
    """
    rows, cols = plate.shape
    text = text.lstrip("﻿")
    try:
        dialect = csv.Sniffer().sniff(text[:4000], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel_tab if "\t" in text else csv.excel
    table = [r for r in csv.reader(io.StringIO(text), dialect) if any(c.strip() for c in r)]
    wells = {(w.row, w.col): w for w in plate.wells.all()}
    values: list[tuple[Well, str, float, float]] = []
    header = [c.strip().lower() for c in table[0]] if table else []
    if "well" in header:
        iw = header.index("well")
        iv = next(
            (header.index(k) for k in ("value", "signal", "od", "rfu", "rlu", "ct") if k in header),
            len(header) - 1,
        )
        ic = header.index("channel") if "channel" in header else None
        it = header.index("time") if "time" in header else None
        for line in table[1:]:
            if len(line) <= max(iw, iv):
                continue
            v = _num(line[iv])
            if v is None:
                continue
            r, c = parse_well(line[iw], plate.format)
            values.append(
                (
                    wells[(r, c)],
                    line[ic].strip() if ic is not None else channel,
                    _num(line[it]) if it is not None and _num(line[it]) is not None else timepoint,
                    v,
                )
            )
    else:
        grid_rows = []
        for line in table:
            first = line[0].strip().upper()
            if first and first.isalpha() and len(first) <= 2:
                grid_rows.append([_num(x) for x in line[1 : 1 + cols]])
            elif (
                len(grid_rows) == 0
                and all(_num(x) is not None for x in line[:cols])
                and len(line) >= cols
            ):
                grid_rows.append([_num(x) for x in line[:cols]])
        if len(grid_rows) < rows:
            raise ValueError(
                f"Found {len(grid_rows)} data rows; a {plate.format}-well plate needs {rows}."
            )
        for r in range(rows):
            for c in range(cols):
                v = grid_rows[r][c] if c < len(grid_rows[r]) else None
                if v is not None:
                    values.append((wells[(r, c)], channel, timepoint, v))
    if not values:
        raise ValueError("No numeric readings found.")
    if replace:
        channels = {ch for _, ch, _, _ in values}
        Measurement.objects.filter(
            well__plate=plate, channel__in=channels, timepoint__in={t for *_, t, _ in values}
        ).delete()
    Measurement.objects.bulk_create(
        [Measurement(well=w, channel=ch, timepoint=t, value=v) for w, ch, t, v in values]
    )
    return {"imported": len(values), "channels": sorted({ch for _, ch, _, _ in values})}


# --- analysis --------------------------------------------------------------------------------


def four_pl(x, bottom, top, ec50, hill):
    return bottom + (top - bottom) / (1 + (x / ec50) ** hill)


def fit_4pl(conc: list[float], resp: list[float]) -> dict | None:
    """Levenberg–Marquardt fit of the 4-parameter logistic in log-concentration space."""
    x = np.array(conc, float)
    y = np.array(resp, float)
    mask = x > 0
    x, y = x[mask], y[mask]
    if len(np.unique(x)) < 4:
        return None
    lx = np.log10(x)
    # p = [bottom, top, log10 EC50, hill]
    p = np.array([y.min(), y.max(), float(np.median(lx)), 1.0])
    if np.corrcoef(lx, y)[0, 1] > 0:  # rising curve
        p[3] = -1.0

    def model(p, lx):
        return p[0] + (p[1] - p[0]) / (1 + 10 ** ((lx - p[2]) * p[3]))

    lam = 1e-2
    err = float(((model(p, lx) - y) ** 2).sum())
    for _ in range(200):
        J = np.empty((len(lx), 4))
        h = 1e-6
        f0 = model(p, lx)
        for j in range(4):
            dp = np.zeros(4)
            dp[j] = h * max(1.0, abs(p[j]))
            J[:, j] = (model(p + dp, lx) - f0) / dp[j]
        A = J.T @ J
        g = J.T @ (y - f0)
        try:
            step = np.linalg.solve(A + lam * np.diag(np.diag(A) + 1e-12), g)
        except np.linalg.LinAlgError:
            break
        p_new = p + step
        p_new[3] = float(np.clip(p_new[3], -10, 10))
        err_new = float(((model(p_new, lx) - y) ** 2).sum())
        if err_new < err:
            p, lam = p_new, lam / 3
            if abs(err - err_new) < 1e-12 * max(1.0, err):
                err = err_new
                break
            err = err_new
        else:
            lam *= 4
            if lam > 1e8:
                break
    sst = float(((y - y.mean()) ** 2).sum())
    r2 = 1 - err / sst if sst > 0 else 0.0
    ec50 = 10 ** p[2]
    in_range = x.min() <= ec50 <= x.max()
    curve_x = np.logspace(lx.min() - 0.3, lx.max() + 0.3, 60)
    return {
        "bottom": round(float(p[0]), 4),
        "top": round(float(p[1]), 4),
        "ec50": float(f"{ec50:.4g}"),
        "hill": round(float(p[3]), 3),
        "r2": round(r2, 4),
        "ec50_in_tested_range": bool(in_range),
        "curve": [
            {"x": float(f"{cx:.4g}"), "y": round(float(model(p, np.log10(cx))), 4)}
            for cx in curve_x
        ],
    }


def analyse_plate(plate: Plate, channel: str = "signal", timepoint: float | None = None) -> dict:
    wells = list(plate.wells.select_related("compound").all())
    meas = Measurement.objects.filter(well__plate=plate, channel=channel)
    if timepoint is not None:
        meas = meas.filter(timepoint=timepoint)
    else:
        last = meas.order_by("-timepoint").values_list("timepoint", flat=True).first()
        meas = meas.filter(timepoint=last) if last is not None else meas
    vals = {m.well_id: m.value for m in meas}
    rows, cols = plate.shape
    grid = [[None] * cols for _ in range(rows)]
    for w in wells:
        grid[w.row][w.col] = vals.get(w.id)

    def pick(role):
        return [vals[w.id] for w in wells if w.role == role and w.id in vals and not w.excluded]

    pos, neg, blank = pick(WellRole.POSITIVE), pick(WellRole.NEGATIVE), pick(WellRole.BLANK)
    blank_mean = float(np.mean(blank)) if blank else 0.0
    out = {
        "channel": channel,
        "channels": sorted(
            set(Measurement.objects.filter(well__plate=plate).values_list("channel", flat=True))
        ),
        "timepoints": sorted(
            set(
                Measurement.objects.filter(well__plate=plate, channel=channel).values_list(
                    "timepoint", flat=True
                )
            )
        ),
        "grid": grid,
        "rows": [row_label(i) for i in range(rows)],
        "cols": list(range(1, cols + 1)),
        "controls": {
            "positive": _stats(pos),
            "negative": _stats(neg),
            "blank": _stats(blank),
        },
        "plain": [],
    }
    if len(pos) >= 2 and len(neg) >= 2:
        sp, sn = float(np.std(pos, ddof=1)), float(np.std(neg, ddof=1))
        mp, mn = float(np.mean(pos)), float(np.mean(neg))
        z = 1 - 3 * (sp + sn) / abs(mp - mn) if mp != mn else None
        out["z_prime"] = None if z is None else round(z, 3)
        out["signal_window"] = round(abs(mp - mn) / max(abs(mn - blank_mean), 1e-12), 3)
        if z is not None:
            verdict = (
                "excellent"
                if z >= 0.5
                else "usable, but noisy"
                if z > 0
                else "not usable: controls overlap"
            )
            out["plain"].append(f"Assay quality Z′ = {z:.2f} ({verdict}).")
        # Normalised activity: 0 % = negative control, 100 % = positive control
        span = mp - mn
        norm = {}
        for w in wells:
            if w.id in vals and span:
                norm[w.name] = round(100 * (vals[w.id] - mn) / span, 2)
        out["percent_activity"] = norm
        hits = [
            {"well": w.name, "label": w.label, "activity": norm[w.name]}
            for w in wells
            if w.role == WellRole.SAMPLE
            and w.name in norm
            and not w.excluded
            and norm[w.name] >= 50
        ]
        out["hits"] = sorted(hits, key=lambda h: -h["activity"])
        out["plain"].append(f"{len(hits)} sample well(s) at ≥ 50 % activity.")
    else:
        out["plain"].append(
            "Mark at least two positive and two negative control wells to get Z′ and % activity."
        )

    # Dose-response per group label
    curves = []
    groups: dict[str, list[tuple[float, float]]] = {}
    for w in wells:
        if w.group_label and w.concentration and w.id in vals and not w.excluded:
            y = out.get("percent_activity", {}).get(w.name, vals[w.id])
            groups.setdefault(w.group_label, []).append((w.concentration, y))
    for label, pts in sorted(groups.items()):
        fit = fit_4pl([p[0] for p in pts], [p[1] for p in pts])
        unit = next((w.concentration_unit for w in wells if w.group_label == label), "")
        curves.append(
            {
                "label": label,
                "unit": unit,
                "points": [{"x": x, "y": round(y, 4)} for x, y in sorted(pts)],
                "fit": fit,
            }
        )
        if fit:
            note = (
                "" if fit["ec50_in_tested_range"] else " (outside the tested range: extrapolated)"
            )
            out["plain"].append(
                f"{label}: IC50/EC50 ≈ {fit['ec50']:.3g} {unit}{note}, R² {fit['r2']:.2f}."
            )
    out["curves"] = curves
    return out


def _stats(v):
    if not v:
        return None
    a = np.array(v)
    return {
        "n": len(v),
        "mean": round(float(a.mean()), 4),
        "sd": round(float(a.std(ddof=1)), 4) if len(v) > 1 else None,
        "cv": round(float(100 * a.std(ddof=1) / a.mean()), 2) if len(v) > 1 and a.mean() else None,
    }


def kinetic_series(plate: Plate, channel: str = "signal") -> dict:
    """Time courses per well (e.g. growth curves OD600)."""
    data: dict[str, list] = {}
    for m in Measurement.objects.filter(well__plate=plate, channel=channel).select_related("well"):
        data.setdefault(m.well.name, []).append({"t": m.timepoint, "v": m.value})
    for k in data:
        data[k].sort(key=lambda p: p["t"])
    rates = {}
    for k, pts in data.items():
        if len(pts) >= 3:
            ys = [p["v"] for p in pts]
            ts = [p["t"] for p in pts]
            best = 0.0
            for i in range(len(pts) - 2):  # max slope over 3-point windows (log for growth)
                y0, y2 = ys[i], ys[i + 2]
                if y0 > 0 and y2 > 0 and ts[i + 2] > ts[i]:
                    best = max(best, (math.log(y2) - math.log(y0)) / (ts[i + 2] - ts[i]))
            rates[k] = round(best, 5)
    return {"series": data, "max_specific_rate_per_min": rates}
