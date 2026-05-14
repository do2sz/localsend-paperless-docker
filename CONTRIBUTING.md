# Contributing

Thanks for your interest in this project. Issues and pull requests are welcome.

## Reporting bugs

Please include:

- Container logs (`docker compose logs --tail=200 localsend-paperless`).
- Your `.env` **with the token redacted**, or the relevant non-secret variables.
- Your platform (Linux distribution, kernel, Docker version).
- The LocalSend client/version that sent the file.

## Proposing changes

- Keep changes minimal and focused on a single concern.
- Avoid adding runtime dependencies unless they remove substantially more
  code than they add.
- Match the existing code style; the Python forwarder targets Python 3.13
  and is typed lightly.
- Verify locally with `docker compose up -d --build` before opening a PR.

## Security issues

Do **not** open a public issue for security-sensitive reports. See
[`SECURITY.md`](./SECURITY.md) for the private reporting channel.

## License

By contributing, you agree that your contributions will be licensed under the
[MIT License](./LICENSE).
