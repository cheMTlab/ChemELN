# Security policy

CheMTlab stores research records and chemical safety data, so we take security seriously.

## Reporting a vulnerability
**Do not open a public issue.** Use GitHub's "Report a vulnerability" (private security advisory) on this repository. Please include steps to reproduce, the affected version, and the impact.

We aim to acknowledge reports within 5 working days and to release a fix for critical issues within 30 days.

## Supported versions
Until 1.0, only the latest release gets security fixes.

## Design principles
- All data stays on the institution's own server. There is no telemetry.
- Features that contact external services are off by default.
- Audit trail on records; signed ELN entries are immutable.
- Encrypted backups (restic); secrets live only in `.env`, generated at install time.
