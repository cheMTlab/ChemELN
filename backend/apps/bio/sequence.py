"""Small DNA helpers: cleaning, GC, Tm, reverse complement, GenBank parsing."""

import math
import re

_COMP = str.maketrans("ACGTRYKMSWBDHVNacgtrykmswbdhvn", "TGCAYRMKSWVHDBNtgcayrmkswvhdbn")


def clean(seq: str, allow_n: bool = True) -> str:
    seq = re.sub(r"[\s\d/]", "", seq or "").upper()
    allowed = "ACGTUNRYKMSWBDHV" if allow_n else "ACGTU"
    bad = sorted({c for c in seq if c not in allowed})
    if bad:
        raise ValueError(f"Invalid sequence characters: {''.join(bad)}")
    return seq.replace("U", "T")


def gc_content(seq: str) -> float:
    s = seq.upper()
    acgt = sum(s.count(b) for b in "ACGT")
    return round(100.0 * (s.count("G") + s.count("C")) / acgt, 2) if acgt else 0.0


def reverse_complement(seq: str) -> str:
    return seq.translate(_COMP)[::-1]


# SantaLucia 1998 unified nearest-neighbour parameters (ΔH kcal/mol, ΔS cal/mol·K)
_NN = {
    "AA": (-7.9, -22.2),
    "TT": (-7.9, -22.2),
    "AT": (-7.2, -20.4),
    "TA": (-7.2, -21.3),
    "CA": (-8.5, -22.7),
    "TG": (-8.5, -22.7),
    "GT": (-8.4, -22.4),
    "AC": (-8.4, -22.4),
    "CT": (-7.8, -21.0),
    "AG": (-7.8, -21.0),
    "GA": (-8.2, -22.2),
    "TC": (-8.2, -22.2),
    "CG": (-10.6, -27.2),
    "GC": (-9.8, -24.4),
    "GG": (-8.0, -19.9),
    "CC": (-8.0, -19.9),
}


def melting_temperature(seq: str, oligo_nm: float = 250.0, na_mm: float = 50.0) -> float | None:
    """Nearest-neighbour Tm with salt correction; Wallace rule for very short oligos."""
    s = re.sub(r"[^ACGT]", "", seq.upper())
    if len(s) < 8:
        return (
            float(2 * (s.count("A") + s.count("T")) + 4 * (s.count("G") + s.count("C")))
            if s
            else None
        )
    dh, ds = 0.0, 0.0
    for i in range(len(s) - 1):
        h, e = _NN[s[i : i + 2]]
        dh += h
        ds += e
    # initiation
    for end in (s[0], s[-1]):
        if end in "GC":
            dh += 0.1
            ds += -2.8
        else:
            dh += 2.3
            ds += 4.1
    ds += 0.368 * (len(s) - 1) * math.log(na_mm / 1000.0)
    tm = (dh * 1000) / (ds + 1.987 * math.log(oligo_nm * 1e-9 / 4)) - 273.15
    return round(tm, 1)


def parse_genbank(text: str) -> dict:
    """Minimal GenBank reader: name, topology, features (with labels) and sequence."""
    lines = (text or "").splitlines()
    if not lines or not lines[0].startswith("LOCUS"):
        raise ValueError("Not a GenBank file (missing LOCUS line).")
    head = lines[0].split()
    out = {
        "name": head[1] if len(head) > 1 else "",
        "circular": "circular" in lines[0].lower(),
        "definition": "",
        "features": [],
        "sequence": "",
    }
    section, feat = None, None
    seq_parts = []
    for line in lines[1:]:
        if line.startswith("DEFINITION"):
            out["definition"] = line[12:].strip()
        elif line.startswith("FEATURES"):
            section = "features"
        elif line.startswith("ORIGIN"):
            section = "origin"
        elif line.startswith("//"):
            break
        elif section == "features":
            if line[5:6] != " " and line[5:21].strip():
                key, loc = line[5:21].strip(), line[21:].strip()
                if key == "source":
                    feat = None
                    continue
                m = re.findall(r"(\d+)\.\.>?(\d+)", loc) or re.findall(r"(\d+)", loc)
                if not m:
                    feat = None
                    continue
                first, last = m[0], m[-1]
                start = int(first[0] if isinstance(first, tuple) else first)
                end = int(last[1] if isinstance(last, tuple) else last)
                feat = {
                    "type": key,
                    "name": key,
                    "start": start,
                    "end": end,
                    "strand": -1 if "complement" in loc else 1,
                }
                out["features"].append(feat)
            elif feat is not None:
                q = re.match(r'\s+/(label|gene|product|note)="?([^"]*)"?', line)
                if q and (feat["name"] == feat["type"] or q.group(1) == "label"):
                    feat["name"] = q.group(2)[:80]
        elif section == "origin":
            seq_parts.append(re.sub(r"[^A-Za-z]", "", line))
    out["sequence"] = "".join(seq_parts).upper()
    return out


def to_fasta(name: str, seq: str) -> str:
    return f">{name}\n" + "\n".join(seq[i : i + 70] for i in range(0, len(seq), 70)) + "\n"
