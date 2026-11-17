## What and why

<!-- One or two sentences. Link the issue if there is one. -->

## How I checked it

- [ ] `PYTHONPATH=src python3 -m pytest tests -q` passes
- [ ] New or changed behavior has a test that runs offline
- [ ] For config-file changes: I pasted the `--dry-run` output below and checked that `revert` restores the original
- [ ] For mirror data changes: `mirrorwise lint-data` passes and the entry has an evidence URL; `confirmed` is `false` unless I probed it from a network that can reach it

```
<!-- paste output here -->
```

## Checklist

- [ ] No new runtime dependencies
- [ ] No personal data (usernames, private URLs, other people's IPs) in the diff
- [ ] I did not copy code or text from other projects (or I credited and checked the license)
