# Changelog

Notation: new entries go under **Unreleased**; when preparing a release, fold
them into the next semver version below and bump the `VERSION` file in the
repository root together with this changelog.

## Unreleased

- Deployment: Traefik serves TLS with a Cloudflare Origin Certificate (no ACME)
  from `/etc/ssl` (host config, kept out of the `/data` backup tree) and trusts
  `X-Forwarded-*` only from Cloudflare's ranges, preserving the visitor IP for
  `ProxyFix` (Traefik bumped to v3.7).
- Docs: add the Cloudflare WAF / DNS / TLS setup and the origin firewall rules.

## 0.1.0 - First public release (Alpha)

- First release
