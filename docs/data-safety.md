# Data safety

## Where data lives
All data stays on the institution's own server: the database and file store run as Docker volumes there. CheMTlab has **no telemetry** and no central service. Desktop browsers keep only a login session. Phones (PWA) will keep a small encrypted offline cache, added in M2, which is wiped on logout.

## Nothing leaves without consent
Features that contact outside services are **off by default** and switched on per instance by an administrator:

| Setting | What it enables |
|---|---|
| `CHEMTLAB_ALLOW_EXTERNAL_LOOKUPS` | Look up compound data in PubChem by CAS number, name or structure |
| `CHEMTLAB_AI_PROVIDER` | Optional AI features. A local model (Ollama) keeps data on-site |

## Access control
- Email + password (minimum 10 characters, common passwords rejected), optional TOTP two-factor, or institutional SSO.
- Self sign-up is **closed** by default (`CHEMTLAB_OPEN_SIGNUP=false`). Users arrive via SSO or are created by an admin.
- Roles per research group: **admin › PI › member › viewer**. Users only see groups they belong to. Only group admins can grant the admin role.

## Backups
- Daily encrypted, deduplicated backups with [restic](https://restic.net) of the database and all files.
- Retention: 14 daily, 8 weekly, 12 monthly (configurable).
- The encryption password is shown once at install time. Keep it off the server.
- `./chemtlab backup --verify` checks repository integrity. Do a full restore test on a spare VM regularly.

## Audit trail
Every change to compounds, locations and containers is stored as a historical version with the user and time (django-simple-history). Containers also keep a readable activity log (created, moved, used, status changes). Non-admins cannot delete containers; they mark them "disposed", so nothing disappears silently.

## Coming in later milestones
- **M3:** signed ELN entries become immutable, hash-chained, with witness countersigning.
