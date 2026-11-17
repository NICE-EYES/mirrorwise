# Publishing on GitHub: step by step

Everything below is a checklist for the repository owner. Nothing here has been run on your GitHub account.

## 1. Name, description, topics

**Repository name:** `mirrorwise` (short, memorable; the keywords live in the description and topics). If the name is taken, alternatives that still carry keywords: `pip-mirror-failover`, `registry-mirror-switch`.

Before you commit to the name, check by hand (the author could not check PyPI automatically, and the web search on 2026-11-17 showed no obvious conflict):

- https://pypi.org/project/mirrorwise/
- https://github.com/search?q=mirrorwise&type=repositories

**Description** (limit 120 characters):

```
Probe pip/npm/Go/Cargo/Docker registries from your network, switch to a working mirror safely, and revert. Zero deps.
```

Length check: 117 characters.

**Topics** (GitHub allows up to 20):

```
mirror  registry  pypi  pip  npm  golang  cargo  docker  package-manager
failover  diagnostics  devtools  cli  python  ci  zero-dependencies
```

**Social preview / website:** none needed for v0.1.0. Optional: upload a screenshot of `mirrorwise doctor` as the social preview image (Settings, General).

## 2. Replace the `OWNER` placeholder

The files contain `OWNER` where your GitHub login belongs (`pyproject.toml`, READMEs, CONTRIBUTING, issue template config). From the repository root:

```bash
python3 - <<'PY'
import pathlib
login = "YOUR_LOGIN"          # <- edit
skip = {".git", "dist", "__pycache__", ".pytest_cache"}
for p in pathlib.Path(".").rglob("*"):
    if p.is_file() and not (set(p.parts) & skip) and p.name != "github-setup.md" and p.suffix in {".md", ".toml", ".yml", ".json", ".py", ".txt"}:
        s = p.read_text(encoding="utf-8")
        if "OWNER" in s:
            p.write_text(s.replace("OWNER", login), encoding="utf-8")
            print("updated", p)
PY
grep -rn OWNER . --exclude-dir=.git --exclude-dir=dist | head     # should print nothing
```

## 3. Create the repository and push

Use your private commit email so your real address is not published: GitHub, Settings, Emails, "Keep my email addresses private", then use the `ID+LOGIN@users.noreply.github.com` address it shows.

```bash
cd mirrorwise
git init -b main
git config user.name  "Your Name"
git config user.email "ID+LOGIN@users.noreply.github.com"
git add -A
git commit -m "Initial commit: mirrorwise 0.1.0"

# with the GitHub CLI
gh auth login
gh repo create mirrorwise --public --source . --remote origin \
  --description "Probe pip/npm/Go/Cargo/Docker registries from your network, switch to a working mirror safely, and revert. Zero deps." \
  --push

# topics
gh repo edit --add-topic mirror,registry,pypi,pip,npm,golang,cargo,docker,package-manager,failover,diagnostics,devtools,cli,python,ci,zero-dependencies
```

Without the CLI: create an empty public repository on github.com (no README, no license, no .gitignore), then

```bash
git remote add origin https://github.com/YOUR_LOGIN/mirrorwise.git
git push -u origin main
```

If GitHub itself is unreachable from your network, push through a network that can reach it. The repository can also be mirrored to another host (for example Codeberg or GitVerse; check their documentation for push mirrors) so the code stays reachable.

## 4. Repository settings

1. Settings, General, Features: enable **Issues** and **Discussions**.
2. Settings, Security: enable **Private vulnerability reporting** (SECURITY.md refers to it).
3. Labels: create `good first issue`, `help wanted`, `backend`, `data`, `dx`, `testing`, `docs`, `bug`, `enhancement` (the issue templates use `bug`, `data`, `enhancement`).
4. Issues: file the ten items from [docs/good-first-issues.md](../good-first-issues.md), one issue each. Pin two of them.
5. Branch protection on `main`: require the CI checks and a pull request.

## 5. First CI run (do this before the release)

Push to a branch, open a PR, and watch the matrix (Ubuntu, Windows, macOS; Python 3.9 to 3.13). The author ran the tests only on Linux with Python 3.11, 3.12 and 3.13 and syntax-checked 3.9. Failures on Windows or macOS are likely to be small (paths, file modes); fix them before tagging. If something cannot be fixed quickly, remove that OS from the matrix and say so in the README rather than shipping a red badge.

## 6. Release v0.1.0

Plan:

| Step | Command / action |
|---|---|
| 1 | CI is green on `main` |
| 2 | Move the CHANGELOG heading from `[0.1.0] - unreleased` to the release date |
| 3 | `git tag -a v0.1.0 -m "mirrorwise 0.1.0"` and `git push origin v0.1.0` |
| 4 | `python3 scripts/build_zipapp.py` and `cd dist && sha256sum mirrorwise.pyz > mirrorwise.pyz.sha256` |
| 5 | `gh release create v0.1.0 dist/mirrorwise.pyz dist/mirrorwise.pyz.sha256 --prerelease --title "mirrorwise 0.1.0" --notes-file docs/launch/release-v0.1.0.md` |
| 6 | Verify: download the asset on a clean machine, `python3 mirrorwise.pyz --version`, `python3 mirrorwise.pyz doctor` |

The release is marked **pre-release** on purpose: the catalog is unconfirmed (`confirmed: false`) and Windows/macOS are new. Release text: [release-v0.1.0.md](release-v0.1.0.md).

A PyPI upload is not part of v0.1.0. If you decide to publish there: `python3 -m build` and `twine upload` need the `build` and `twine` packages, and a PyPI account with a trusted publisher or API token; none of that was set up here.

## 7. After the release

1. Post the announcements from [posts.md](posts.md), one platform at a time, each with its own rules checked (see the notes in that file).
2. Answer issues within a day or two in the first weeks; first impressions decide whether contributors come back.
3. Ask people who try it to run `mirrorwise probe` and send the output through the **Mirror request** template: this is how entries move from `confirmed: false` to `true`.
