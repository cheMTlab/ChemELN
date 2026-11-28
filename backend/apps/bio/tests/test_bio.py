import numpy as np
import pytest

from apps.bio import plates, sequence

pytestmark = pytest.mark.django_db

GENBANK = """LOCUS       pTEST                 60 bp    DNA     circular SYN 01-JAN-2026
DEFINITION  test plasmid.
FEATURES             Location/Qualifiers
     source          1..60
     promoter        1..20
                     /label="T7 promoter"
     CDS             complement(25..55)
                     /gene="bla"
ORIGIN
        1 taatacgact cactataggg agaccacaac ggtttccctc tagaaataat tttgtttaac
//
"""


def test_sequence_tools():
    assert sequence.clean("acg t\n12u") == "ACGTT"
    with pytest.raises(ValueError):
        sequence.clean("ACGZ")
    assert sequence.reverse_complement("ATGC") == "GCAT"
    assert sequence.gc_content("GGCC") == 100.0
    tm = sequence.melting_temperature("AGCGGATAACAATTTCACACAGGA")  # M13 rev, ~58-62 °C
    assert 55 < tm < 66
    gb = sequence.parse_genbank(GENBANK)
    assert gb["circular"] and len(gb["sequence"]) == 60
    assert gb["features"][0] == {
        "type": "promoter",
        "name": "T7 promoter",
        "start": 1,
        "end": 20,
        "strand": 1,
    }
    assert gb["features"][1]["strand"] == -1 and gb["features"][1]["name"] == "bla"


def test_4pl_fit_recovers_ic50():
    conc = [100 / 3**i for i in range(10)]
    resp = [0 + 100 / (1 + (c / 1.5) ** -1.2) for c in conc]  # rising curve, EC50 1.5
    fit = plates.fit_4pl(conc, resp)
    assert fit["ec50"] == pytest.approx(1.5, rel=0.02)
    assert fit["r2"] > 0.999 and fit["ec50_in_tested_range"]


@pytest.fixture
def biologist(api, make_user, member_of):
    u = make_user("bio@example.org")
    member_of(u)
    api.force_authenticate(u)
    return u


def test_registry(api, biologist, group, make_user):
    p = api.post(
        "/api/plasmids/",
        {
            "group": str(group.id),
            "name": "pET-28a-GFP",
            "resistance": ["Kanamycin"],
            "sequence": "atgc" * 50,
        },
        format="json",
    ).json()
    assert p["code"] == "pCT0001" and p["size_bp"] == 200 and p["gc_content"] == 50.0
    s = api.post(
        "/api/strains/",
        {
            "group": str(group.id),
            "name": "BL21(DE3) pET-GFP",
            "kind": "bacterium",
            "organism": "E. coli",
            "plasmids": [p["id"]],
            "biosafety_level": 1,
        },
        format="json",
    ).json()
    assert s["code"] == "ST0001" and s["plasmid_codes"] == ["pCT0001"]
    o = api.post(
        "/api/oligos/",
        {"group": str(group.id), "name": "T7 fwd", "sequence": "TAATACGACTCACTATAGGG"},
        format="json",
    ).json()
    assert o["code"] == "OL0001" and o["tm"] > 45
    assert api.get("/api/plasmids/", {"sequence": "GCAT"}).json()["count"] == 1
    assert api.get("/api/plasmids/", {"resistance": "kan"}).json()["count"] == 1
    sample = api.post(
        "/api/bio-samples/",
        {"group": str(group.id), "kind": "glycerol", "name": "GFP glycerol", "strain": s["id"]},
        format="json",
    ).json()
    assert sample["barcode"].startswith("BCT")
    # Outsiders see nothing; biosafety officers see all strains
    api.force_authenticate(make_user("x@example.org"))
    assert api.get("/api/strains/").json()["count"] == 0
    api.force_authenticate(make_user("bso@example.org", capabilities=["biosafety_officer"]))
    assert api.get("/api/strains/").json()["count"] == 1


def test_plate_workflow(api, biologist, group):
    plate = api.post(
        "/api/plates/", {"group": str(group.id), "name": "IC50 run 1", "format": 96}, format="json"
    ).json()
    wells = api.get(f"/api/plates/{plate['id']}/wells/").json()
    assert len(wells) == 96 and wells[0]["name"] == "A1" and wells[-1]["name"] == "H12"

    api.post(
        f"/api/plates/{plate['id']}/layout/",
        {"wells": [f"{r}1" for r in "ABCDEFGH"], "values": {"role": "negative"}},
        format="json",
    )
    api.post(
        f"/api/plates/{plate['id']}/layout/",
        {"wells": [f"{r}12" for r in "ABCDEFGH"], "values": {"role": "positive"}},
        format="json",
    )
    res = api.post(
        f"/api/plates/{plate['id']}/dilution/",
        {
            "start_well": "A2",
            "direction": "row",
            "steps": 10,
            "top": 100,
            "factor": 3,
            "label": "Cmpd-7",
            "replicates": 2,
        },
        format="json",
    )
    assert res.json() == {"updated": 20}

    # Simulated reader grid: neg ≈ 1000, pos ≈ 100, compound inhibits with IC50 2 µM
    rng = np.random.default_rng(0)
    lines = ["," + ",".join(str(c) for c in range(1, 13))]
    for r, letter in enumerate("ABCDEFGH"):
        vals = []
        for c in range(12):
            if c == 0:
                v = 1000 + rng.normal(0, 20)
            elif c == 11:
                v = 100 + rng.normal(0, 10)
            elif r < 2:
                conc = 100 / 3 ** (c - 1)
                v = 100 + 900 / (1 + (conc / 2.0) ** 1.0)
            else:
                v = 1000 + rng.normal(0, 20)
            vals.append(f"{v:.1f}")
        lines.append(letter + "," + ",".join(vals))
    res = api.post(
        f"/api/plates/{plate['id']}/import-readings/", {"text": "\n".join(lines)}, format="json"
    )
    assert res.status_code == 201, res.json()
    assert res.json()["imported"] == 96

    a = api.get(f"/api/plates/{plate['id']}/analysis/").json()
    assert a["z_prime"] > 0.7
    assert a["grid"][0][0] == pytest.approx(1000, abs=80)
    curve = a["curves"][0]
    assert curve["label"] == "Cmpd-7" and len(curve["points"]) == 20
    assert curve["fit"]["ec50"] == pytest.approx(2.0, rel=0.1)
    assert any("Z′" in p for p in a["plain"])

    # long format import, kinetic channel
    long = "well,time,value\nA1,0,0.05\nA1,30,0.1\nA1,60,0.2\nA1,90,0.4"
    res = api.post(
        f"/api/plates/{plate['id']}/import-readings/",
        {"text": long, "channel": "OD600"},
        format="json",
    )
    assert res.status_code == 201, res.json()
    k = api.get(f"/api/plates/{plate['id']}/kinetics/", {"channel": "OD600"}).json()
    assert k["max_specific_rate_per_min"]["A1"] == pytest.approx(0.0231, rel=0.05)
    assert "A1" in api.get(f"/api/plates/{plate['id']}/export/").content.decode()

    copy = api.post(
        "/api/plates/",
        {"group": str(group.id), "name": "IC50 run 2", "format": 96, "template": plate["id"]},
        format="json",
    ).json()
    w = api.get(f"/api/plates/{copy['id']}/wells/").json()
    assert w[0]["role"] == "negative" and w[1]["group_label"] == "Cmpd-7"
