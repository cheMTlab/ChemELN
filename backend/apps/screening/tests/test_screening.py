import pytest

from apps.screening import analysis, design

pytestmark = pytest.mark.django_db

VARS = [
    {
        "id": "t",
        "name": "Temperature",
        "kind": "continuous",
        "unit": "°C",
        "low": 20,
        "high": 100,
        "levels": [],
    },
    {
        "id": "s",
        "name": "Solvent",
        "kind": "categorical",
        "unit": "",
        "low": None,
        "high": None,
        "levels": ["THF", "Toluene", "DMF"],
    },
]


def test_designs():
    assert len(design.full_factorial(VARS, 3)) == 9
    lhs = design.latin_hypercube(VARS, 10, seed=1)
    temps = sorted(r["t"] for r in lhs)
    # one point per stratum of width 8 °C
    assert all(20 + 8 * i <= t <= 20 + 8 * (i + 1) for i, t in enumerate(temps))
    assert design.assign_wells(13, 12)[-1] == (2, "A1")


def _truth(f):
    bonus = {"THF": 0, "Toluene": 10, "DMF": -5}[f["s"]]
    return 30 + 0.5 * f["t"] - 0.004 * (f["t"] - 20) ** 2 + bonus  # optimum ~ 82 °C


def test_analysis_recovers_effects():
    runs = [
        {"factors": f, "results": {"y": _truth(f)}, "status": "done"}
        for f in design.full_factorial(VARS, 5)
    ]
    out = analysis.analyse(
        VARS, {"id": "y", "name": "Yield", "unit": "%", "goal": "maximize"}, runs
    )
    assert out["model"]["metrics"]["r2"] > 0.99
    solvent = next(i for i in out["importance"] if i["variable"] == "s")
    assert solvent["best_at"] == "Toluene"
    temp = next(i for i in out["importance"] if i["variable"] == "t")
    assert 70 <= temp["best_at"] <= 95
    assert any("Toluene" in line for line in out["plain"])

    pred = analysis.predict(VARS, {"id": "y"}, runs, {"t": 150, "s": "THF"})
    assert pred["extrapolation"] is True and "outside the tested range" in pred["warnings"][0]

    sug = analysis.suggest(
        VARS, [{"id": "y", "name": "Yield", "goal": "maximize"}], runs, k=3, seed=0
    )["suggestions"]
    assert sug[0]["factors"]["s"] == "Toluene"
    assert sug[-1]["purpose"].startswith("explore")


def test_campaign_api(api, make_user, member_of, group):
    u = make_user()
    member_of(u)
    api.force_authenticate(u)
    c = api.post(
        "/api/campaigns/",
        {
            "group": str(group.id),
            "title": "Suzuki opt",
            "equipment": "hte_plate",
            "plate_format": 24,
        },
        format="json",
    ).json()
    t = api.post(
        "/api/campaign-variables/",
        {
            "campaign": c["id"],
            "name": "Temperature",
            "kind": "continuous",
            "unit": "°C",
            "low": 20,
            "high": 100,
        },
        format="json",
    ).json()
    s = api.post(
        "/api/campaign-variables/",
        {
            "campaign": c["id"],
            "name": "Solvent",
            "kind": "categorical",
            "levels": ["THF", "Toluene", "DMF"],
        },
        format="json",
    ).json()
    y = api.post(
        "/api/campaign-responses/",
        {"campaign": c["id"], "name": "Yield", "unit": "%", "goal": "maximize"},
        format="json",
    ).json()
    assert (
        api.post(
            "/api/campaign-variables/",
            {"campaign": c["id"], "name": "Bad", "kind": "continuous", "low": 5, "high": 1},
            format="json",
        ).status_code
        == 400
    )

    res = api.post(
        f"/api/campaigns/{c['id']}/generate/",
        {"design": "full_factorial", "levels": 4},
        format="json",
    )
    assert res.status_code == 201, res.json()
    runs = res.json()
    assert len(runs) == 12 and runs[0]["well"] and all(r["plate"] == 1 for r in runs)

    lines = ["run,Yield (%)"]
    for r in runs:
        f = {"t": r["factors"][t["id"]], "s": r["factors"][s["id"]]}
        lines.append(f"{r['index']},{_truth(f):.2f}")
    res = api.post(
        f"/api/campaigns/{c['id']}/import-results/", {"csv": "\n".join(lines)}, format="json"
    )
    assert res.json() == {"updated": 12, "errors": []}

    a = api.get(f"/api/campaigns/{c['id']}/analysis/").json()
    assert a["counts"]["done"] == 12
    assert a["responses"][0]["model"]["metrics"]["r2"] > 0.9

    res = api.post(f"/api/campaigns/{c['id']}/suggest/", {"k": 2, "add": True}, format="json")
    assert res.status_code == 200, res.json()
    assert len(api.get("/api/campaign-runs/", {"campaign": c["id"]}).json()) == 14
    csv = api.get(f"/api/campaigns/{c['id']}/export/").content.decode()
    assert csv.splitlines()[0].startswith("run,plate,well,status,Temperature (°C),Solvent,Yield")
    assert y["goal"] == "maximize"
