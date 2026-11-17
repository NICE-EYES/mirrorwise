# mirrorwise

[Русская версия](README.ru.md)

**Probe your package registries from your own network, pick a working mirror, switch to it safely, and switch back when the official registry recovers.**
Zero dependencies. One file if you need it (`mirrorwise.pyz`). Python 3.9+.

```console
$ mirrorwise doctor pip
pip - pip / uv / Poetry (PyPI)
  ID               TRUST      STATUS  LATENCY  DETAIL
  pypi             upstream   FAIL    100 ms   tls: connection dropped during TLS handshake
  yandex-pypi      vendor     ok      140 ms
  tuna-pypi        vendor     ok      420 ms
  ...
  DOWN: the official registry is unreachable (tls: connection dropped ...). Healthy mirror: yandex-pypi. Run: mirrorwise apply pip
```

> The transcript above is shortened from [docs/demo.txt](docs/demo.txt). In that file part 1 uses real probes against local test servers and part 2 uses **simulated** probe results (the planning and file handling are real). It is not a measurement of any real network.

## Why

Registries and mirrors fail in ways that are annoying to diagnose and tedious to work around:

- `pip install` hangs or dies with a TLS error while the site opens fine in a browser.
- The "fix" is a copy-pasted mirror URL from a blog post, edited by hand into four different config formats.
- A month later the official registry works again, but the mirror is still in your config, and nobody remembers why.
- In CI the failure shows up as a red build, not as a clear "this registry is unreachable from this runner".

Public reports of this pattern in 2026 (PyPI connections dropped during TLS from Russian networks on 1-2 June, GitHub access degradation in May and July, Docker Hub in 2024) are collected with links in [docs/research.md](docs/research.md). That document also says what the evidence does **not** show.

mirrorwise is a small, boring tool for that situation: **measure, decide, change one thing, keep a way back.**

## What it does

| Command | What it does |
|---|---|
| `mirrorwise list` | show the mirror catalog (bundled + your own) |
| `mirrorwise probe [eco...]` | test which sources answer from this machine, with the failing stage (`dns`, `connect`, `tls`, `http`, `content`, `timeout`, `proxy`) |
| `mirrorwise doctor [eco...]` | probe and give a verdict per ecosystem. Exit code `0` ok, `1` action needed, `2` broken. Good for CI |
| `mirrorwise status` | show what is configured right now and whether mirrorwise manages it |
| `mirrorwise apply <eco>` | switch to the best healthy source (backup first, `--dry-run` to preview) |
| `mirrorwise revert <eco>` | restore the exact previous bytes of the config |
| `mirrorwise env <eco>` | print env vars for CI (`sh`, `powershell`, `github`, `json`) without touching any file |
| `mirrorwise lint-data [--overlay] [file]` | validate a mirrors JSON file (`--overlay` for your own `--data` files) |

Supported ecosystems: **pip**, **npm**, **Go**, **Cargo**, **Docker**. The PyPI mirrors also work for uv and Poetry, but mirrorwise edits only pip's own config file. For uv, `env` emits `UV_INDEX_URL` as well; a `uv.toml` backend and Poetry support are open issues.

## Install

pip may be exactly the thing that is broken, so there are several ways:

```bash
# 1. Single file, no installation. Download mirrorwise.pyz from the Releases page, then:
python3 mirrorwise.pyz doctor

# 2. pipx / pip
pipx install git+https://github.com/NICE-EYES/mirrorwise
# or
pip install git+https://github.com/NICE-EYES/mirrorwise

# 3. From a checkout
git clone https://github.com/NICE-EYES/mirrorwise && cd mirrorwise
PYTHONPATH=src python3 -m mirrorwise --help
python3 scripts/build_zipapp.py        # builds dist/mirrorwise.pyz
```

mirrorwise has no runtime dependencies (standard library only), so a copied `.pyz` works on any machine with Python 3.9+. A PyPI release is on the roadmap.

## Quick start

```bash
mirrorwise doctor                     # what works from here?
mirrorwise apply pip --dry-run        # show the diff, write nothing
mirrorwise apply pip                  # asks for confirmation, makes a backup, writes the config
mirrorwise status                     # confirm what is configured
mirrorwise revert pip                 # undo; also happens automatically via `apply` once upstream is healthy again
```

Non-interactive use needs `--yes` or `--dry-run`. `apply` requires an explicit ecosystem or `--all`, so it never changes five tools by accident.

Your own mirror (for example a corporate Nexus or Artifactory):

```bash
mirrorwise probe pip --url https://nexus.example.com/repository/pypi/simple/
mirrorwise apply pip --url https://nexus.example.com/repository/pypi/simple/ --yes
```

### CI

```bash
# GitHub Actions: only emits variables when the official registry is unhealthy
- run: python3 mirrorwise.pyz env pip npm go --format github >> "$GITHUB_ENV"

# Any shell
eval "$(python3 mirrorwise.pyz env pip npm go --format sh)"
```

`env` prints nothing when the official registry is healthy (use `--always` to print anyway). Variables: `PIP_INDEX_URL` and `UV_INDEX_URL` for pip, `npm_config_registry` for npm, `GOPROXY` for Go. Cargo and Docker are configured through files and daemon settings, so `env` does not support them.

## How it decides

1. **Probe** every candidate with a small real request (for example `pip/` on PyPI, `left-pad` metadata on npm, `config.json` on a Cargo sparse index). Response content is checked, not only the status code, so a captive portal that answers `200 OK` with HTML is a failure.
2. When a request fails, mirrorwise **re-diagnoses stage by stage** with raw sockets to tell DNS, TCP connect, TLS, and HTTP failures apart.
3. **Policy** (`selection.choose`):
   - upstream healthy: keep upstream;
   - upstream healthy but slower than `--slow-ms` (default 3000) and a mirror is at least 2x faster: call it degraded and prefer the mirror;
   - upstream down: take the fastest healthy mirror you allow;
   - `--fastest`: the fastest of everything.
4. **Plan** (`apply`):
   - a source that works now is left alone (no flapping between mirrors);
   - a mirror that mirrorwise installed earlier is dropped (via revert) once upstream is healthy again;
   - a broken custom source is replaced;
   - an explicit `--mirror` or `--url` that fails its probe is refused unless `--force`.

### Trust levels

| Level | Meaning | Used by default |
|---|---|---|
| `upstream` | the official registry | yes |
| `vendor` | run by a company, university or cloud provider | yes |
| `user` | your own URL or overlay file | yes |
| `community` | run by individuals or unknown operators | **no**, needs `--allow-community` |

## Safety model

- https only. `http://` is refused unless `--allow-insecure` (meant for local tests).
- Redirects that downgrade `https` to `http` are refused.
- Config files are written atomically, with a backup and a manifest in the state directory (`MIRRORWISE_STATE_DIR` or `~/.local/state/mirrorwise`). `revert` restores the exact original bytes, or deletes a file that did not exist before. Reverts stack.
- A failed write leaves no phantom backup entry.
- Only the setting that matters is edited: `index-url` in pip's `[global]`, the `registry=` line in `.npmrc` (scoped registries are untouched), a marked block for Cargo, the `registry-mirrors` key in Docker's `daemon.json`, `GOPROXY` through `go env -w`.
- If an environment variable overrides the file (`PIP_INDEX_URL`, `npm_config_registry`, `GOPROXY`), mirrorwise warns you that the change will not take effect in that shell.
- Proxy variables from the environment are honored. `--no-proxy` ignores them.
- Cargo: a foreign `[source.crates-io]` section stops the change with an explicit conflict instead of being overwritten.

### A mirror is a third party

A mirror can serve altered files. mirrorwise cannot make that safe. What reduces the risk: use `vendor`-level mirrors (the default), keep hash-checked lockfiles (`pip install --require-hashes`, `package-lock.json` integrity, `go.sum`, `Cargo.lock`), and revert when the incident is over, which `apply` does for you.

## Mirror data

The catalog is a plain JSON file: [src/mirrorwise/data/mirrors.json](src/mirrorwise/data/mirrors.json). Important caveats:

- Every entry is a **candidate** taken from public articles and vendor documentation and carries its evidence URLs. All are currently marked `"confirmed": false`: the maintainer's environment could not verify them from an affected network. The probe is the source of truth at runtime, not the list.
- Anyone can add or disable entries locally with an overlay file (`--data FILE` or `~/.config/mirrorwise/mirrors.json`). See [examples/mirrors.corporate.json](examples/mirrors.corporate.json).
- `mirrorwise lint-data` validates the bundled file (https only, evidence required unless confirmed, unique ids, Cargo `sparse+` URLs). `mirrorwise lint-data --overlay FILE` checks your own overlay file and catches typos in ecosystem names and in `disable` ids.
- Adding a mirror to the bundled catalog: use the **Mirror request** issue template and paste your `mirrorwise probe` output.

## FAQ

**Does it need root?** Not for pip, npm, Go and Cargo: they are user-level files. On Linux, Docker's default file is `/etc/docker/daemon.json`, so you need `sudo` there (on macOS and Windows the default is `~/.docker/daemon.json`). A permission error is reported as an error, nothing is half-written. With `sudo`, the backup lives in root's state directory, so run `sudo mirrorwise revert docker` too. mirrorwise never restarts the daemon; it tells you to. `--config-path` lets you edit another file.

**Does it make my internet work when a site is blocked?** No. It is not a VPN or a proxy. It only helps when a legitimate mirror is reachable from your network.

**Why not just `pip config set global.index-url ...`?** You can. mirrorwise adds measuring, the decision, a backup, an automatic way back, and the same behavior across five tools.

**What about Go's checksum database?** mirrorwise only sets `GOPROXY` (as `<url>,direct`) and never touches `GOSUMDB`, `GONOSUMDB` or `GOFLAGS`. If the checksum database itself is unreachable you will see that error from `go`; do not "fix" it by disabling verification.

**Does it support uv / Poetry / pnpm / Yarn?** `apply` edits pip's config only. uv has its own configuration (`uv.toml`): use `mirrorwise env pip --format sh` to get `UV_INDEX_URL`, or help with the `uv.toml` backend (good first issue). Poetry keeps sources in `pyproject.toml` and is not supported. pnpm and Yarn classic read `.npmrc`, which the npm backend edits (not tested against them in v0.1). Yarn Berry has its own config and is not supported yet.

**Does it phone home?** No telemetry. The only network traffic is the probe requests to the URLs in the catalog (and your `--url`).

**The catalog is `confirmed: false`. Why should I trust it?** You should not trust it blindly. Use `probe` first, stay on `vendor` trust, and send corrections through the issue template.

## Limitations (v0.1)

- Git hosting (`git clone`, GitHub releases) is not covered. That is a different problem with different mitigations.
- The bundled mirror data is small and unconfirmed (see above). Regions beyond the ones in the catalog need contributions.
- apt/yum/Homebrew, Maven/Gradle, NuGet, Composer, RubyGems are not covered yet. See [docs/good-first-issues.md](docs/good-first-issues.md).
- Speed numbers come from a small sample and are only good for ranking, not for benchmarking.
- The probe checks the index endpoint. A PyPI mirror that does not rewrite file links can still depend on `files.pythonhosted.org` for the downloads themselves, so a green probe is necessary, not sufficient.

## Roadmap

`uv.toml` backend, Maven/Gradle, Composer, RubyGems, Yarn Berry, NuGet, git `insteadOf` for GitHub mirrors, shell completions, a signed community data feed, more languages. Details and good first issues: [docs/good-first-issues.md](docs/good-first-issues.md).

## Development

```bash
PYTHONPATH=src python3 -m pytest tests -q     # 107 tests, no network needed
PYTHONPATH=src python3 -m unittest discover -s tests -t .
python3 scripts/build_zipapp.py                # dist/mirrorwise.pyz
python3 scripts/demo.py en > docs/demo.txt     # regenerate the demo transcript
```

The tests use local fixture servers (healthy, TLS-dropping, captive portal, blackhole), so they run offline. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Prior art and credits

Similar tools exist and are worth a look: [chsrc](https://github.com/RubyMetric/chsrc) (C, GPL-3.0, many more targets), [nrm](https://github.com/Pana/nrm) (npm registries). mirrorwise was written independently, copies no code from them, and differs in focus: failure-stage diagnosis, an upstream-first policy with failback, backup/revert, and CI mode. A comparison is in [docs/research.md](docs/research.md).

## License

[MIT](LICENSE)
