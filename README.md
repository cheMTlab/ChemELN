# CheMTlab

**An open-source electronic lab notebook (ELN) with an interactive chemical inventory, built to be installed by any institution, anywhere.**

CheMTlab is in early development. M0 (foundations) is done; M1 (inventory core) is in progress.

## Why
Chemistry groups need to know what they have, where it is, how dangerous it is, and what they did with it. Existing tools are either closed source or hard to install and maintain. CheMTlab aims to be:

- **Open**: AGPL-3.0. Free to use, study, modify, and host.
- **Easy to install**: one server, one command (`install.sh`), Docker under the hood.
- **Safe for your data**: everything lives on *your* institution's server. You get encrypted backups, a full audit trail, signed notebook entries, and institutional single sign-on (SSO).
- **Useful**: inventory with structure search, barcode/QR scanning from phones, ELN with reaction stoichiometry linked to stock, instrument data capture, and FAIR data export.

## How it is deployed
```
            ┌──────────── Institution server / VM (run by university IT) ───────────┐
 Browser ──►│ Caddy (HTTPS) ─► Django API ─► PostgreSQL + RDKit   (all data here)    │
 Phone PWA ─►│              └─► React app   └─► File store, Redis/Celery worker      │
 Instrument ►│                                                                        │
  agent     └──────────────────────────── encrypted backups ─► NAS / S3 you own ────┘
```
- **Computers:** nothing to install. Open `https://chemtlab.<your-institution>` in a browser.
- **Phones/tablets:** open the same URL and choose "Add to Home Screen" (a PWA). Barcode scanning uses the camera.
- **Data:** stored only on the institution's server. It is never sent to a central service. External lookups (e.g. PubChem) and AI features are off until an admin turns them on.

## Roadmap
| Milestone | Scope |
|---|---|
| M0 Foundations ✓ | Repo, Docker stack, accounts, institutions/groups/roles, API, CI |
| **M1 Inventory core** | Compounds (RDKit), containers, locations, PubChem autofill, GHS, structure search, labels, import |
| M2 Mobile PWA | Camera scanning, stock-taking, offline queue |
| M3 ELN | Experiments, reaction schemes, stoichiometry linked to inventory, signing/witnessing |
| M4 Screening & optimization | Reaction optimization campaigns: variables, design of experiments, HTE plates, live monitoring graphs, models that suggest and extrapolate relations |
| M5 Smart assist | Storage incompatibility checks, hazard warnings, reminders, optional LLM features |
| M6 Instruments | Drop-folder agent, JCAMP-DX/Bruker/mzML, spectra viewer |
| M7 Federation & FAIR | RO-Crate, Zenodo/Chemotion publishing, cross-institution sharing |

## Structure editor
The default is **Ketcher** (Apache-2.0). Institutions that hold a ChemAxon licence can switch to **Marvin JS** (the editor Reaxys uses) by setting `STRUCTURE_EDITOR=marvinjs` and supplying the licensed files. CheMTlab cannot ship Marvin JS itself because it is proprietary.

## Quick start (development)
Requirements: Docker (Desktop on Windows/macOS), Node 22, [uv](https://docs.astral.sh/uv/).

```bash
cp .env.example .env
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
# API:       http://localhost:8000/api/health
# API docs:  http://localhost:8000/api/docs
# Frontend:  http://localhost:5173
docker compose exec backend python manage.py createsuperuser
```

## Production install
See [docs/install.md](docs/install.md).

## License
CheMTlab is licensed under the GNU Affero General Public License v3.0 or later (`AGPL-3.0-or-later`). See [LICENSE](LICENSE).
