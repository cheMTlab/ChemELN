# Installing CheMTlab on an institution server

This guide is for the IT team (or a technically confident lab member). It takes about 15 minutes.

## 1. What you need
| | Minimum | Recommended (≈ 50–200 users) |
|---|---|---|
| OS | Any 64-bit Linux with Docker (Ubuntu 22.04/24.04, Debian 12, RHEL/Rocky 9) | Ubuntu 24.04 LTS |
| CPU / RAM | 2 vCPU / 4 GB | 4 vCPU / 8 GB |
| Disk | 40 GB | 100 GB+ SSD (attachments and spectra grow over time) |
| Network | A DNS name, e.g. `chemtlab.chem.example.ac.uk`; ports 80 and 443 open to your users | |
| Backups | A folder on separate storage (NAS mount) or an S3-compatible bucket | Off-site copy |

Install Docker Engine and the Compose plugin: <https://docs.docker.com/engine/install/>.

## 2. Install
```bash
git clone https://github.com/chemtlab/chemtlab.git /opt/chemtlab
cd /opt/chemtlab
./install.sh
```
The installer:

1. Asks for the domain name, an administrator email and the backup folder.
2. Generates strong random secrets into `.env` (readable only by root).
3. Shows the **backup encryption password**. Store it in your password manager, *off* the server.
4. Builds and starts the services, then asks you to create the first administrator account.

Open `https://<your-domain>` and sign in. Then go to `https://<your-domain>/admin/` and create your institution, departments and research groups.

### HTTPS certificates
- **Server reachable from the internet:** Caddy gets a free Let's Encrypt certificate automatically.
- **Internal-only server:** edit `docker/Caddyfile` and add `tls internal`, or use your institution's certificate (`tls /certs/cert.pem /certs/key.pem`, mounted into the `web` service).

## 3. Institutional single sign-on (optional, recommended)
CheMTlab supports any OpenID Connect provider: Microsoft Entra ID (Azure AD), Keycloak, Google Workspace, Shibboleth/SAML through an OIDC proxy such as SATOSA, and eduGAIN.

1. Register an application with your identity provider. Use the redirect URI
   `https://<your-domain>/_allauth/browser/v1/auth/provider/callback/institution`
   (if login fails, the error page from your identity provider shows the exact URI it expected).
2. Fill in `.env`:
   ```
   OIDC_PROVIDER_NAME=University login
   OIDC_SERVER_URL=https://login.microsoftonline.com/<tenant-id>/v2.0
   OIDC_CLIENT_ID=...
   OIDC_CLIENT_SECRET=...
   ```
3. Apply the change: `docker compose up -d`

## 4. Day-to-day administration
```bash
./chemtlab status          # are services running?
./chemtlab doctor          # health and configuration checks
./chemtlab backup --verify # backup now and check repository integrity
./chemtlab snapshots       # list backups
./chemtlab restore         # restore latest backup (asks for confirmation)
./chemtlab upgrade         # safety backup → update → migrate → health check
./chemtlab logs backend
```

## 5. Where the data is
| Data | Location on the server |
|---|---|
| Database (all records, audit trail) | Docker volume `chemtlab_pgdata` |
| Files (attachments, SDS, spectra) | Docker volume `chemtlab_media` |
| Configuration and secrets | `/opt/chemtlab/.env` |
| Backups (encrypted) | `CHEMTLAB_BACKUP_DIR` (NAS) or S3 bucket |

Backups run daily at `BACKUP_HOUR` (UTC). Restore-test them regularly: run `./chemtlab restore` on a *test* VM.
