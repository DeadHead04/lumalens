# Security and private data

## Protect sessions and exports

Luma cookies and registered ticket links grant access to an account or event. Treat them as credentials. Never post them in issues, pull requests, logs, screenshots, or public repositories.

Use `.sessions/` for session files and `exports/` for results; both are ignored by Git and excluded from release artifacts. If you use another location, check it yourself before committing. History may contain ticket keys; guest exports may contain personal profile information.

New files use mode `0600` on POSIX systems. On Windows, permissions follow directory ACLs. Keep sessions on a private device or server directory. The login flow saves only Luma cookies and does not upload credentials to the project maintainer.

## Reporting a vulnerability

Use GitHub's **Security → Advisories → Report a vulnerability** for this repository when private reporting is enabled. If unavailable, open an issue containing only a request for a private reporting channel; do not disclose credentials or exploit details publicly.

Include the affected version, impact, and a minimal reproduction using synthetic data. Never include your actual Luma session.

The latest release is the recommended target for fixes. Older releases have no guaranteed backports. This project has no security response-time SLA.

## Scope

Use accounts and event data you are authorized to access. The tool respects HTTP access denials and does not circumvent hidden guest-list permissions. Report upstream Luma security issues to Luma, not as public project issues.
