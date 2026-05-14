# Security Policy

## Supported versions

This project is developed against the `main` branch. Only the latest commit on
`main` and the most recent published Docker image are receiving security fixes.

## Reporting a vulnerability

Please **do not** open a public GitHub issue for security-sensitive reports.

Use GitHub's private vulnerability reporting instead:

1. Go to <https://github.com/do2sz/localsend-paperless-docker/security/advisories/new>
2. Describe the issue, including reproduction steps and affected commit/image tag.

You can expect an initial response within a few business days. Coordinated
disclosure will be handled via a GitHub Security Advisory and an accompanying
patch release.

## Threat model

`localsend-paperless` is designed for **trusted LANs**. By default it accepts
every incoming transfer; the optional `LOCALSEND_PIN` only mitigates accidental
uploads, not a determined attacker on the same network segment. Do not expose
the receiver port (`53317`) to the public internet.

The container forwards files to Paperless-ngx using the API token configured
via `PAPERLESS_TOKEN`. Treat that token like a credential — store it in
`.env`, never commit it, and rotate it if exposed.
