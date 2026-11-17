# Good first issues

Ten ready-to-file issues. Copy each block into a new issue, add the label `good first issue` (and the one in brackets), and link [CONTRIBUTING.md](../CONTRIBUTING.md).

Difficulty: **S** = a few hours, **M** = a weekend.

Where to look in the code: a backend is one small file in `src/mirrorwise/backends/` (start with `npm.py`, the smallest); tests for backends live in `tests/test_backends.py`; messages are in `src/mirrorwise/i18n.py`.

---

## 1. Backend for uv (`uv.toml`) [backend] - M

**Problem.** `mirrorwise apply pip` edits pip's config, which uv does not read. uv users only get `UV_INDEX_URL` through `mirrorwise env`.

**Task.** Add a `uv` backend that sets the default index in uv's user-level `uv.toml` (read uv's documentation for the current key names and the file location per OS; the key has changed between uv versions, so check before you write code).

**Acceptance.**
- `apply`, `status`, `revert` work like the other backends (backup, atomic write, exact-bytes revert).
- A user's other settings in `uv.toml` are preserved.
- A foreign index configuration that cannot be edited safely raises `ConflictError` instead of being overwritten.
- Tests: render, apply twice, revert.

---

## 2. Backend for Maven (`settings.xml` mirror) [backend] - M

**Problem.** Maven Central is a common single point of failure in Java builds, and mirrors are configured in `~/.m2/settings.xml`.

**Task.** Add a `maven` ecosystem: probe path (for example a well-known small artifact `maven-metadata.xml`), data entries with evidence URLs, and a backend that adds a clearly marked `<mirror>` element with `<mirrorOf>central</mirrorOf>` and removes it on revert.

**Acceptance.** An existing `settings.xml` with other mirrors, profiles and servers is preserved byte for byte outside the managed element. No XML library that rewrites the whole file (use text insertion between marker comments).

---

## 3. Backend for Composer (PHP) [backend] - S

**Task.** Add `composer`: the global config is JSON (`config.json` in Composer's home); the registry for packagist can be changed through the `repositories` key. Read the Composer documentation, implement `render` similar to the Docker backend (JSON merge), add a probe for `packages.json` or the metadata endpoint, and tests.

**Acceptance.** Existing `repositories` and `config` entries are kept; revert restores exact bytes.

---

## 4. Backend for RubyGems / Bundler [backend] - S

**Task.** Add `gem`: the `~/.gemrc` `:sources:` list or Bundler's mirror setting (`bundle config mirror.https://rubygems.org ...`). Pick one, document the choice, and keep the change reversible. Probe: a small `/api/v1/versions/<gem>.json` or `/specs.4.8.gz` request (check what mirrors actually serve).

---

## 5. Yarn Berry (`.yarnrc.yml`) [backend] - S

**Problem.** Yarn Berry ignores `.npmrc` and uses `npmRegistryServer` in `.yarnrc.yml`.

**Task.** Add a `yarn` backend (reuse the npm probe data) that edits only `npmRegistryServer` and preserves YAML comments. Do not add a YAML dependency: edit the line, like the pip backend does for INI.

---

## 6. NuGet (`NuGet.Config`) [backend] - M

**Task.** Add `nuget`: package sources live in `NuGet.Config` (XML). Add a marked `<add key=... value=.../>` under `<packageSources>` and a `<clear/>`-aware design, or document why you chose another approach. Probe the v3 service index.

---

## 7. Shell completions [dx] - S

**Task.** Add `mirrorwise completion {bash,zsh,fish}` that prints a completion script. Generate the list of commands and options from the `argparse` parser, so the script cannot go stale. No new dependency.

**Acceptance.** A test checks that every subcommand appears in the generated bash script.

---

## 8. Verify default paths on Windows and macOS [testing] - S

**Problem.** The maintainers developed on Linux. The CI matrix runs Windows and macOS, but nobody has looked at the real files the tool would touch there.

**Task.** On Windows or macOS, run `mirrorwise status` and `mirrorwise apply pip --dry-run` and check that the reported paths are the ones pip, npm, Cargo and Docker Desktop really use. Report mismatches, and fix the ones in `default_path()` with a test that sets the environment variables explicitly.

---

## 9. Respect `pip.conf` precedence [backend] - M

**Problem.** pip reads several config files (global, user, site) and environment variables, and later ones override earlier ones. `apply pip` edits one file and warns about `PIP_INDEX_URL`, but does not tell the user if another pip config file also sets `index-url`.

**Task.** Detect the other pip config locations (see `pip config debug`), and print a warning in `status` and `apply` when an effective value would come from a file other than the one being edited.

**Acceptance.** Tests with two temporary config files and `PIP_CONFIG_FILE` unset/set.

---

## 10. Translations and message review [docs] - S

**Task.** The tool speaks English and Russian (`i18n.py`). Add one more language, for example Chinese (many mirrors in the catalog are operated in China) or Turkish or Ukrainian. Keep technical tokens (`TLS`, `GOPROXY`, command names) untranslated.

**Acceptance.** `tests/test_i18n.py` (key and placeholder parity across all languages) passes with the new language included.

---

### Not "first" issues, but welcome

- Confirming mirrors from real networks and sending probe logs (see the **Mirror request** template).
- A signed community data feed so the catalog can be updated without a new release.
- git `insteadOf` rules for GitHub mirrors (a design discussion first: trust and TLS verification matter even more for source code).
