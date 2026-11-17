# Changelog

All notable changes are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [0.1.0] - unreleased

First public release.

### Added
- Commands: `list`, `probe`, `doctor`, `status`, `apply`, `revert`, `env`, `lint-data`.
- Ecosystems: pip, npm, Go, Cargo, Docker.
- Failure-stage diagnosis (`dns`, `connect`, `tls`, `http`, `content`, `timeout`, `proxy`); content checks that catch captive portals.
- Upstream-first policy with degraded detection, no flapping between working sources, and automatic failback to the official registry.
- Safe config handling: https only, atomic writes, backups with a manifest, stackable exact-bytes revert, warnings when environment variables override a config file.
- Trust levels (`upstream`, `vendor`, `community`, `user`); community mirrors are off by default.
- Mirror catalog with 16 candidate mirrors (all `confirmed: false`), overlay files via `--data` and `~/.config/mirrorwise/mirrors.json`, `lint-data` and `lint-data --overlay`.
- CI mode: `env` with `sh`, `powershell`, `github` and `json` formats.
- English and Russian messages.
- Single-file build: `scripts/build_zipapp.py` produces `mirrorwise.pyz`.
- 107 offline tests using local fixture servers.
