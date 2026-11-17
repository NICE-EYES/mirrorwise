# Security policy

## Supported versions

Only the latest release receives fixes.

## Reporting a vulnerability

Please **do not open a public issue** for security problems. Use GitHub's private vulnerability reporting (Security tab, "Report a vulnerability") on this repository. If that is not available, open an issue titled "security contact request" without details and a maintainer will reach out.

We aim to acknowledge reports within 7 days.

## What counts

Examples of in-scope problems:

- a way to make mirrorwise write outside the intended config file, or leave a config in a state that `revert` cannot restore;
- a way to make mirrorwise accept a downgrade from https to http, or a mirror entry that bypasses the trust-level policy;
- a crafted mirrors data file (`--data`, overlay) that executes code or reads unrelated files;
- shell/PowerShell injection through the `env` output formats.

## Out of scope

- A mirror serving altered packages. mirrorwise cannot verify what a mirror serves; use hash-pinned lockfiles. See "A mirror is a third party" in the README.
- Wrong or outdated entries in `mirrors.json`: please file a normal issue with `mirrorwise probe` output.
