# localsend-paperless

[![License: MIT](https://img.shields.io/github/license/do2sz/localsend-paperless-docker)](./LICENSE)
[![Docker build](https://github.com/do2sz/localsend-paperless-docker/actions/workflows/docker-build.yml/badge.svg)](https://github.com/do2sz/localsend-paperless-docker/actions/workflows/docker-build.yml)
[![Latest release](https://img.shields.io/github/v/release/do2sz/localsend-paperless-docker?display_name=tag&sort=semver)](https://github.com/do2sz/localsend-paperless-docker/releases)

Headless [LocalSend](https://localsend.org) receiver in Docker that auto-accepts
every transfer and forwards each file to a [Paperless-ngx](https://docs.paperless-ngx.com/)
instance via the REST API.

> 📖 **Prefer the pretty docs?** A visual, illustrated walkthrough with
> architecture diagram, configuration tables and troubleshooting guide is
> published at **<https://do2sz.github.io/localsend-paperless-docker/>**.
> The same content is in [`docs/index.html`](./docs/index.html) if you want
> to read it offline.

```
phone/laptop → LocalSend (HTTPS :53317) → container → Paperless-ngx
                                        (auto-accept,    (POST /api/documents/post_document/)
                                         optional PIN)
```

## How it works

Two processes run inside the container:

1. **`localsend-cli recv`** — vendored Go binary from
   [`0w0mewo/localsend-cli`](https://github.com/0w0mewo/localsend-cli) (built
   from source in a multi-stage Dockerfile, pinned to a release tag). Listens on
   TCP/UDP `53317`, announces itself on the LocalSend multicast group
   `224.0.0.167`, generates a self-signed HTTPS cert, and writes received files
   to `/data/incoming`. It has no UI — every transfer is accepted, optionally
   gated by a PIN.

2. **`python -m forwarder`** — small Python service that watches
   `/data/incoming` with `watchdog`, debounces newly-arrived files, uploads
   them to Paperless using a token-authenticated multipart POST, and
   (optionally) polls `/api/tasks/` to confirm consumption succeeded. On success
   the local file is deleted; on failure it is moved to `/data/retry/<ts>/`
   and re-attempted every `RETRY_INTERVAL_SECONDS`.

## Requirements

- A Linux Docker host (host networking is required for UDP multicast discovery
  to work; Docker Desktop on macOS/Windows will not properly forward
  LocalSend's multicast packets).
- A Paperless-ngx instance reachable from the host, and an API token
  (Paperless → Profile → API Auth Token).

## Quick start

```sh
cp .env.example .env
# edit .env → at minimum set PAPERLESS_URL and PAPERLESS_TOKEN
docker compose up -d
docker compose logs -f
```

The bundled `docker-compose.yml` pulls the pre-built multi-arch image from
GHCR (`ghcr.io/do2sz/localsend-paperless-docker:latest`). To build the image
locally instead — e.g. when developing — use the dev override:

```sh
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
```

In the LocalSend app on your phone, the configured `LOCALSEND_ALIAS`
("Paperless Inbox" by default) should appear in the device list. Send any
PDF / image — it will land in Paperless without manual confirmation.

## Configuration

All configuration is through environment variables. See `.env.example` for the
full list with defaults. The most important ones:

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `PAPERLESS_URL` | yes | — | e.g. `https://paperless.lan` |
| `PAPERLESS_TOKEN` | yes | — | Paperless API token |
| `PAPERLESS_VERIFY_SSL` | no | `true` | set `false` for self-signed Paperless |
| `LOCALSEND_ALIAS` | no | `Paperless Inbox` | name shown in the LocalSend app |
| `LOCALSEND_PIN` | no | empty | optional 6-digit PIN gate |
| `PAPERLESS_DEFAULT_TAGS` | no | empty | comma-separated tag IDs |
| `PAPERLESS_DEFAULT_CORRESPONDENT` | no | empty | correspondent ID |
| `PAPERLESS_DEFAULT_DOCUMENT_TYPE` | no | empty | document type ID |
| `PAPERLESS_DEFAULT_STORAGE_PATH` | no | empty | storage path ID |
| `PAPERLESS_TITLE_PREFIX` | no | empty | prepended to the title |
| `PAPERLESS_POLL_TASK` | no | `true` | poll task status before deleting |
| `RETRY_INTERVAL_SECONDS` | no | `300` | how often `/data/retry` is rescanned |
| `LOG_LEVEL` | no | `INFO` | Python log level |

## Volumes

- `/data/incoming` — staging area for in-flight uploads (normally empty).
- `/data/retry`   — files whose Paperless upload failed; sidecar `.err` files
  contain the last error message. Files are retried automatically.

Both live under `/data`, mounted to `./data` by the bundled compose file.

## Operational notes

- **Multicast discovery only works with `network_mode: host`.** If you cannot
  use host networking (e.g. Docker Desktop, Synology), the container will
  still accept uploads but senders must enter its IP manually in the LocalSend
  app, since UDP multicast can't traverse Docker's bridge networks.
- **HTTPS certificate** is self-signed and managed entirely by `localsend-cli`.
  LocalSend clients pin by SHA-256 fingerprint, not by trust chain.
- **Port `53317`** must be free on the host (TCP and UDP).
- The container drops to UID `1000` for both processes; mount permissions on
  `./data` accordingly, or `chown` once after `docker compose up`.

## Troubleshooting

- Files stuck in `/data/incoming/` → check `docker compose logs` for
  `paperless` errors (auth, SSL, network).
- Container shows up in LocalSend but uploads fail → wrong PIN, or the
  receiver port is blocked by a firewall.
- Paperless rejects unknown formats → install the optional Tika integration
  in your Paperless deployment.

## Project layout

```
.
├── Dockerfile          # multi-stage: builds localsend-cli (Go), Python runtime
├── docker-compose.yml
├── entrypoint.sh       # supervises both processes, propagates SIGTERM
├── requirements.txt
├── .env.example
└── forwarder/
    ├── __main__.py     # python -m forwarder
    ├── config.py       # pydantic-settings
    ├── watcher.py      # watchdog → debounce → forward
    ├── paperless.py    # REST client (post_document + task polling)
    └── retry.py        # periodic rescan of /data/retry
```

## License

Released under the [MIT License](./LICENSE).

### Attribution

This image builds and bundles the following upstream components:

- [`0w0mewo/localsend-cli`](https://github.com/0w0mewo/localsend-cli) — MIT,
  compiled from source inside the Docker build.
- [LocalSend protocol](https://github.com/localsend/protocol) — the open
  protocol implemented by the receiver.
- Python runtime dependencies: [`watchdog`](https://github.com/gorakhargosh/watchdog)
  (Apache 2.0), [`httpx`](https://github.com/encode/httpx) (BSD-3-Clause),
  [`pydantic-settings`](https://github.com/pydantic/pydantic-settings) (MIT).

LocalSend and Paperless-ngx are independent projects; this wrapper is not
affiliated with either.

## Contributing

See [`CONTRIBUTING.md`](./CONTRIBUTING.md). For security-sensitive reports use
the private channel described in [`SECURITY.md`](./SECURITY.md).
