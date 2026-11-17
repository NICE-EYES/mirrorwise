"""Command line interface."""

import argparse
import json
import subprocess
import sys
from typing import Dict, List, Optional, Tuple

from . import __version__, fsutil
from .backends import BACKENDS, ConflictError, GoMissing
from .i18n import set_lang, t
from .probe import ProbeResult, probe_many
from .registry import (
    DEFAULT_TRUST_ALLOWED,
    Catalog,
    DataError,
    Ecosystem,
    Mirror,
    custom_mirror,
    lint_file,
    load_catalog,
)
from .selection import DEFAULT_SLOW_MS, Choice, choose, healthy_mirrors

EXIT_OK = 0
EXIT_ACTION = 1
EXIT_ERROR = 2


# --------------------------------------------------------------------------- output helpers
def out(text: str = "") -> None:
    print(text)


def err(text: str) -> None:
    print(text, file=sys.stderr)


def fmt_table(headers: List[str], rows: List[List[str]]) -> List[str]:
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    lines = ["  ".join(h.ljust(widths[i]) for i, h in enumerate(headers)).rstrip()]
    for row in rows:
        lines.append("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)).rstrip())
    return lines


def fmt_latency(r: ProbeResult) -> str:
    return "-" if r.latency_ms is None else "%d ms" % round(r.latency_ms)


def fmt_speed(r: ProbeResult) -> str:
    return "-" if r.kb_per_s is None or not r.ok else "%d KB/s" % round(r.kb_per_s)


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass


# --------------------------------------------------------------------------- shared logic
def resolve_ecos(args, catalog: Catalog) -> List[str]:
    names = list(getattr(args, "ecosystems", []) or [])
    if getattr(args, "all", False) or not names:
        if not getattr(args, "all", False) and getattr(args, "require_eco", False):
            err(t("err_no_eco", known=", ".join(catalog.keys())))
            raise SystemExit(EXIT_ERROR)
        return catalog.keys()
    for name in names:
        if name not in catalog.ecosystems:
            err(t("err_unknown_eco", eco=name, known=", ".join(catalog.keys())))
            raise SystemExit(EXIT_ERROR)
    return names


def allowed_trust(args) -> frozenset:
    allowed = set(DEFAULT_TRUST_ALLOWED)
    if getattr(args, "allow_community", False):
        allowed.add("community")
    return frozenset(allowed)


def current_setting(catalog: Catalog, eco: str, path_override: Optional[str] = None):
    """Return ``(url_or_None, source, identified Mirror or None)``."""
    url, source = BACKENDS[eco].read_current(path_override)
    return url, source, catalog.identify(eco, url)


def build_items(catalog: Catalog, ecos: List[str], extra: Optional[Dict[str, Mirror]] = None):
    """Collect (Mirror, ProbeSpec) pairs for the requested ecosystems, plus a custom 'current' source."""
    items = []
    for eco in ecos:
        spec = catalog.get(eco)
        sources = list(spec.all_sources())
        if extra and eco in extra:
            sources.append(extra[eco])
        for m in sources:
            items.append((m, spec.probe))
    return items


def run_probes(args, items) -> Dict[Tuple[str, str], ProbeResult]:
    if items:
        err(t("probing", n=len(items)))
    results = probe_many(items, timeout=args.timeout, use_proxy=not args.no_proxy)
    return {(r.eco, r.mirror_id): r for r in results}


def per_eco(results: Dict[Tuple[str, str], ProbeResult], eco: str) -> Dict[str, ProbeResult]:
    return {mid: r for (e, mid), r in results.items() if e == eco}


def current_extra(catalog: Catalog, ecos: List[str]) -> Dict[str, Mirror]:
    extra: Dict[str, Mirror] = {}
    for eco in ecos:
        url, _src, ident = current_setting(catalog, eco)
        if url and ident is None:
            extra[eco] = custom_mirror(eco, url, "current")
    return extra


def print_probe_table(eco: Ecosystem, sources: List[Mirror], results: Dict[str, ProbeResult]) -> None:
    out(t("eco_header", eco=eco.key, title=eco.title))
    rows = []
    for m in sources:
        r = results.get(m.id)
        if r is None:
            continue
        status = t("status_ok") if r.ok else t("status_fail")
        detail = "" if r.ok else "%s: %s" % (r.stage, r.detail)
        rows.append([m.id, m.trust, status, fmt_latency(r), fmt_speed(r), detail])
    headers = [t("col_id"), t("col_trust"), t("col_status"), t("col_latency"), t("col_speed"), t("col_detail")]
    for line in fmt_table(headers, rows):
        out("  " + line)
    out()


def print_tips(results: Dict[str, ProbeResult]) -> None:
    if any(r.stage == "tls" and "TLS" in r.detail.upper() and not r.ok for r in results.values()):
        err(t("tip_tls"))
    if any(r.stage == "proxy" for r in results.values()):
        err(t("proxy_note"))


# --------------------------------------------------------------------------- commands
def cmd_list(args, catalog: Catalog) -> int:
    ecos = resolve_ecos(args, catalog)
    if args.json:
        data = {}
        for eco in ecos:
            spec = catalog.get(eco)
            data[eco] = [dict(m.__dict__, evidence=list(m.evidence)) for m in spec.all_sources()]
        out(json.dumps(data, indent=2, ensure_ascii=False))
        return EXIT_OK
    for eco in ecos:
        spec = catalog.get(eco)
        out(t("eco_header", eco=eco, title=spec.title))
        rows = [[m.id, m.trust, m.region or "-", "yes" if m.confirmed else "no", m.url] for m in spec.all_sources()]
        headers = [t("col_id"), t("col_trust"), t("col_region"), t("col_confirmed"), "URL"]
        for line in fmt_table(headers, rows):
            out("  " + line)
        out()
    return EXIT_OK


def cmd_probe(args, catalog: Catalog) -> int:
    ecos = resolve_ecos(args, catalog)
    if args.url:
        # Test one URL of your own (a corporate Nexus, a new mirror before a PR to the catalog).
        if len(ecos) != 1 or len(getattr(args, "ecosystems", [])) != 1:
            err(t("err_no_eco", known=", ".join(catalog.keys())))
            return EXIT_ERROR
        custom = custom_mirror(ecos[0], args.url, "custom")
        results = run_probes(args, [(custom, catalog.get(ecos[0]).probe)])
        if args.json:
            out(json.dumps([r.to_dict() for r in results.values()], indent=2, ensure_ascii=False))
            return EXIT_OK
        print_probe_table(catalog.get(ecos[0]), [custom], per_eco(results, ecos[0]))
        print_tips(per_eco(results, ecos[0]))
        return EXIT_OK
    extra = current_extra(catalog, ecos)
    results = run_probes(args, build_items(catalog, ecos, extra))
    if args.json:
        out(json.dumps([r.to_dict() for r in results.values()], indent=2, ensure_ascii=False))
        return EXIT_OK
    for eco in ecos:
        spec = catalog.get(eco)
        sources = spec.all_sources() + ([extra[eco]] if eco in extra else [])
        res = per_eco(results, eco)
        print_probe_table(spec, sources, res)
        print_tips(res)
    return EXIT_OK


def verdict_for(args, catalog: Catalog, eco: str, results: Dict[str, ProbeResult]):
    """Return (exit_level, message, data) for one ecosystem."""
    spec = catalog.get(eco)
    url, source, ident = current_setting(catalog, eco)
    effective = ident if ident is not None else (custom_mirror(eco, url, "current") if url else spec.upstream)
    eff_res = results.get(effective.id)
    allowed = allowed_trust(args)
    what = t("what_upstream") if effective.upstream else t("what_current")
    choice = choose(spec, results, allowed, slow_ms=args.slow_ms)
    data = {
        "eco": eco,
        "configured": url,
        "source": source,
        "effective": effective.id,
        "ok": bool(eff_res and eff_res.ok),
        "suggested": choice.mirror.id if choice.mirror else None,
    }
    if eff_res is not None and eff_res.ok:
        up_res = results.get(spec.upstream.id)
        if (
            effective.upstream
            and eff_res.latency_ms is not None
            and eff_res.latency_ms > args.slow_ms
            and choice.reason == "degraded"
        ):
            msg = t("verdict_degraded", what=what, ms=round(eff_res.latency_ms), mirror=choice.mirror.id)
            return EXIT_ACTION, msg, data
        return EXIT_OK, t("verdict_ok", what=what), data
    detail = "%s: %s" % (eff_res.stage, eff_res.detail) if eff_res else "no probe result"
    if choice.mirror is not None and not choice.mirror.upstream:
        return EXIT_ACTION, t("verdict_down_fix", what=what, detail=detail, mirror=choice.mirror.id, eco=eco), data
    if choice.mirror is not None and choice.mirror.upstream and effective.id != spec.upstream.id:
        return EXIT_ACTION, t("verdict_down_fix", what=what, detail=detail, mirror=choice.mirror.id, eco=eco), data
    if choice.only_community is not None:
        return EXIT_ERROR, t("verdict_down_community", what=what, mirror=choice.only_community.id), data
    return EXIT_ERROR, t("verdict_down_nofix", what=what, detail=detail), data


def cmd_doctor(args, catalog: Catalog) -> int:
    ecos = resolve_ecos(args, catalog)
    extra = current_extra(catalog, ecos)
    results = run_probes(args, build_items(catalog, ecos, extra))
    worst = EXIT_OK
    payload = []
    for eco in ecos:
        spec = catalog.get(eco)
        res = per_eco(results, eco)
        level, msg, data = verdict_for(args, catalog, eco, res)
        data["message"] = msg
        payload.append(data)
        worst = max(worst, level)
        if not args.json:
            sources = spec.all_sources() + ([extra[eco]] if eco in extra else [])
            print_probe_table(spec, sources, res)
            out("  " + msg)
            out()
            print_tips(res)
    if args.json:
        out(json.dumps(payload, indent=2, ensure_ascii=False))
    return worst


def cmd_status(args, catalog: Catalog) -> int:
    ecos = resolve_ecos(args, catalog)
    rows = []
    payload = []
    for eco in ecos:
        url, source, ident = current_setting(catalog, eco)
        managed = fsutil.is_managed(eco)
        label = ident.id if ident else ("custom" if url else t("status_unset"))
        rows.append([eco, label, url or "-", source + (" (%s)" % t("status_managed") if managed else "")])
        payload.append({"eco": eco, "url": url, "source": source, "mirror_id": ident.id if ident else None, "managed": managed})
    if args.json:
        out(json.dumps(payload, indent=2, ensure_ascii=False))
        return EXIT_OK
    out(t("status_header"))
    for line in fmt_table(["ECO", "SOURCE", "URL", "FROM"], rows):
        out("  " + line)
    return EXIT_OK


def _explicit_mirror(args, catalog: Catalog, eco: str) -> Optional[Mirror]:
    if args.url:
        if not args.url.startswith("https://") and not args.url.startswith("sparse+https://") and not args.allow_insecure:
            err(t("err_insecure", url=args.url))
            raise SystemExit(EXIT_ERROR)
        return custom_mirror(eco, args.url, "custom")
    if args.mirror:
        found = catalog.get(eco).find(args.mirror)
        if found is None:
            err(t("err_unknown_mirror", id=args.mirror, eco=eco))
            raise SystemExit(EXIT_ERROR)
        return found
    return None


def _confirm(args) -> bool:
    if args.yes:
        return True
    if not sys.stdin.isatty():
        err("non-interactive session: pass --yes to apply or --dry-run to preview")
        raise SystemExit(EXIT_ERROR)
    try:
        answer = input(t("confirm"))
    except EOFError:
        return False
    return answer.strip().lower() in ("y", "yes", "д", "да")


def _plan_for(args, catalog: Catalog, eco: str, results: Dict[str, ProbeResult]):
    """Return (mirror_or_None, reason_key, action) where action is apply|revert|none|fail."""
    spec = catalog.get(eco)
    explicit = _explicit_mirror(args, catalog, eco)
    url, _src, ident = current_setting(catalog, eco, args.config_path)
    if explicit is not None:
        r = results.get(explicit.id)
        if (r is None or not r.ok) and not args.force:
            detail = "%s: %s" % (r.stage, r.detail) if r else "no probe result"
            err(t("err_unhealthy_explicit", id=explicit.id, detail=detail))
            return None, "none", "fail"
        return explicit, "reason_explicit", "apply"

    managed = fsutil.is_managed(eco)
    up_res = results.get(spec.upstream.id)
    up_ok = bool(up_res and up_res.ok)
    cur = ident if ident is not None else (custom_mirror(eco, url, "current") if url else None)
    cur_res = results.get(cur.id) if cur is not None else None

    # The source that is configured right now still works: leave it alone (no flapping),
    # except that a mirror we installed is dropped as soon as the official registry is back.
    if cur is not None and cur_res is not None and cur_res.ok and not args.fastest:
        if managed and up_ok and not cur.upstream:
            return spec.upstream, "reason_failback", "revert"
        return cur, "reason_current_ok", "none"

    choice = choose(spec, results, allowed_trust(args), fastest=args.fastest, slow_ms=args.slow_ms)
    if choice.mirror is None:
        return None, "none", "fail"
    if choice.reason == "upstream_ok":
        if managed:
            return choice.mirror, "reason_failback", "revert"
        if cur is not None and not cur.upstream:
            return choice.mirror, "reason_current_broken", "apply"
        return choice.mirror, "reason_upstream_ok", "none"
    if cur is not None and cur.id == choice.mirror.id:
        return choice.mirror, "reason_current_ok", "none"
    key = {"best_mirror": "reason_best_mirror", "fastest": "reason_fastest", "degraded": "reason_degraded"}[choice.reason]
    return choice.mirror, key, "apply"


def cmd_apply(args, catalog: Catalog) -> int:
    args.require_eco = True
    ecos = resolve_ecos(args, catalog)
    if (args.url or args.mirror or args.config_path) and len(ecos) != 1:
        err(t("err_no_eco", known=", ".join(catalog.keys())))
        return EXIT_ERROR
    if args.url or args.mirror:
        # Explicit choice: probe only that one source, not the whole catalog.
        target = _explicit_mirror(args, catalog, ecos[0])
        items = [(target, catalog.get(ecos[0]).probe)]
    else:
        extra = {}
        for eco in ecos:
            url, _src, ident = current_setting(catalog, eco, args.config_path if len(ecos) == 1 else None)
            if url and ident is None:
                extra[eco] = custom_mirror(eco, url, "current")
        items = build_items(catalog, ecos, extra)
    results_all = run_probes(args, items)
    pending = []
    status = EXIT_OK
    for eco in ecos:
        res = per_eco(results_all, eco)
        out(t("plan_title", eco=eco))
        mirror, reason_key, action = _plan_for(args, catalog, eco, res)
        if action == "fail":
            if mirror is None and not (args.url or args.mirror):
                out(t("no_healthy", eco=eco))
            status = max(status, EXIT_ACTION)
            continue
        reason = t(reason_key)
        if action == "none":
            out(t("plan_nochange", reason=reason))
            continue
        if action == "revert":
            out(t("plan_choice", id=mirror.id, url=mirror.url, reason=reason))
            pending.append((eco, mirror, "revert"))
            continue
        out(t("plan_choice", id=mirror.id, url=mirror.url, reason=reason))
        pending.append((eco, mirror, "apply"))
        backend = BACKENDS[eco]
        _cur_url, cur_source = backend.read_current(args.config_path)
        if cur_source.startswith("env "):
            err(t("warn_env_override", source=cur_source[4:]))
        try:
            preview = backend.apply(mirror, args.config_path, dry_run=True)
        except (ConflictError, GoMissing) as exc:
            _report_backend_error(eco, exc)
            pending.pop()
            status = max(status, EXIT_ERROR)
            continue
        if preview.path:
            out(t("plan_file", path=preview.path))
        if args.dry_run:
            if preview.command:
                out("  $ " + preview.command)
            elif preview.diff:
                for line in preview.diff.splitlines():
                    out("    " + line)
    if args.dry_run:
        if pending:
            out(t("dry_run"))
        return status
    if not pending:
        return status
    if not _confirm(args):
        out(t("aborted"))
        return EXIT_ERROR
    for eco, mirror, action in pending:
        backend = BACKENDS[eco]
        try:
            if action == "revert":
                results = fsutil.revert_all(eco)
                for kind, path in results:
                    out("  " + t("reverted" if kind == "restored" else "revert_deleted", eco=eco, path=path))
                continue
            outcome = backend.apply(mirror, args.config_path, dry_run=False)
        except PermissionError as exc:
            err(t("err_permission", eco=eco, path=getattr(exc, "filename", None) or backend.path(args.config_path)))
            status = max(status, EXIT_ERROR)
            continue
        except (ConflictError, GoMissing, subprocess.SubprocessError, OSError) as exc:
            _report_backend_error(eco, exc)
            status = max(status, EXIT_ERROR)
            continue
        if not outcome.wrote:
            out(t("plan_nochange", reason="already configured"))
            continue
        out(t("applied_go" if outcome.command else "applied", path=outcome.path))
        if outcome.note_key:
            out(t(outcome.note_key))
        out(t("revert_hint", eco=eco))
    return status


def _report_backend_error(eco: str, exc: BaseException) -> None:
    if isinstance(exc, GoMissing):
        err(t("err_go_missing"))
    else:
        err(t("err_conflict", eco=eco, detail=str(exc)))


def cmd_revert(args, catalog: Catalog) -> int:
    args.require_eco = True
    ecos = resolve_ecos(args, catalog)
    status = EXIT_OK
    for eco in ecos:
        try:
            results = fsutil.revert_all(eco)
        except (OSError, FileNotFoundError) as exc:
            err("%s: %s" % (eco, exc))
            status = EXIT_ERROR
            continue
        if not results:
            out(t("revert_nothing", eco=eco))
            continue
        for kind, path in results:
            out(t("reverted" if kind == "restored" else "revert_deleted", eco=eco, path=path))
    return status


def _quote_sh(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def cmd_env(args, catalog: Catalog) -> int:
    args.require_eco = True
    ecos = resolve_ecos(args, catalog)
    for eco in ecos:
        if not BACKENDS[eco].env_vars("https://x/"):
            err(t("err_env_unsupported", eco=eco))
            return EXIT_ERROR
    results_all = run_probes(args, build_items(catalog, ecos))
    allowed = allowed_trust(args)
    env: Dict[str, str] = {}
    status = EXIT_OK
    for eco in ecos:
        spec = catalog.get(eco)
        choice = choose(spec, per_eco(results_all, eco), allowed, fastest=args.fastest, slow_ms=args.slow_ms)
        if choice.mirror is None:
            err(t("no_healthy", eco=eco))
            status = EXIT_ACTION
            continue
        if choice.mirror.upstream and not args.always:
            err("%s: %s" % (eco, t("reason_upstream_ok")))
            continue
        env.update(BACKENDS[eco].env_vars(choice.mirror.url.rstrip("/") if eco == "go" else choice.mirror.url))
    fmt = args.format
    if fmt == "json":
        out(json.dumps(env, indent=2))
    else:
        for key, value in env.items():
            if fmt == "sh":
                out("export %s=%s" % (key, _quote_sh(value)))
            elif fmt == "powershell":
                out("$env:%s = '%s'" % (key, value.replace("'", "''")))
            else:  # github
                out("%s=%s" % (key, value))
    return status


def cmd_lint(args, catalog: Optional[Catalog]) -> int:
    files = args.files or [None]
    total_problems = 0
    for path in files:
        problems, cat = lint_file(path, overlay=args.overlay)
        if problems:
            total_problems += len(problems)
            out(t("lint_fail", n=len(problems)))
            for p in problems:
                out("  - " + p)
        else:
            n = sum(len(e.mirrors) for e in cat.ecosystems.values())
            out("%s: %s" % (path or "bundled mirrors.json", t("lint_ok", n=n, e=len(cat.ecosystems))))
    return EXIT_OK if total_problems == 0 else EXIT_ERROR


# --------------------------------------------------------------------------- parser
def _common_probe_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--timeout", type=float, default=6.0, help="per-request timeout in seconds (default 6)")
    p.add_argument("--no-proxy", action="store_true", help="ignore HTTP(S)_PROXY from the environment")
    p.add_argument("--slow-ms", type=float, default=DEFAULT_SLOW_MS, help="official registry slower than this counts as degraded")
    p.add_argument("--allow-community", action="store_true", help="also consider mirrors run by individuals/unknown operators")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mirrorwise",
        description="Probe package registries from your own network, pick a working mirror and switch to it safely.",
    )
    parser.add_argument("--version", action="version", version="mirrorwise " + __version__)
    parser.add_argument("--lang", choices=["en", "ru"], help="output language (default: from MIRRORWISE_LANG / LANG)")
    parser.add_argument("--data", action="append", default=[], metavar="FILE", help="extra mirrors JSON file (repeatable)")
    parser.add_argument("--no-user-data", action="store_true", help="ignore ~/.config/mirrorwise/mirrors.json")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    def eco_arg(p, required=False):
        p.add_argument("ecosystems", nargs="*", metavar="ECO", help="pip npm go cargo docker (default: all)")
        p.add_argument("--all", action="store_true", help="all ecosystems")

    p = sub.add_parser("list", help="show the mirror catalog")
    eco_arg(p)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("probe", help="test which sources answer from this machine")
    eco_arg(p)
    _common_probe_args(p)
    p.add_argument("--url", metavar="URL", help="probe only this URL for the given ecosystem (e.g. your own mirror)")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_probe)

    p = sub.add_parser("doctor", help="probe and give a verdict per ecosystem (exit code 0 ok, 1 action needed, 2 broken)")
    eco_arg(p)
    _common_probe_args(p)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("status", help="show what is configured right now")
    eco_arg(p)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("apply", help="switch to the best healthy source (with backup)")
    eco_arg(p)
    _common_probe_args(p)
    p.add_argument("--mirror", metavar="ID", help="use this catalog entry")
    p.add_argument("--url", metavar="URL", help="use your own mirror URL (e.g. a corporate Nexus)")
    p.add_argument("--fastest", action="store_true", help="pick the fastest source even if the official one works")
    p.add_argument("--config-path", metavar="PATH", help="edit this config file instead of the default")
    p.add_argument("--dry-run", action="store_true", help="show what would change, write nothing")
    p.add_argument("--yes", "-y", action="store_true", help="do not ask for confirmation")
    p.add_argument("--force", action="store_true", help="apply even if the probe failed")
    p.add_argument("--allow-insecure", action="store_true", help="allow http:// URLs (local tests only)")
    p.set_defaults(func=cmd_apply)

    p = sub.add_parser("revert", help="undo changes made by mirrorwise")
    eco_arg(p)
    p.set_defaults(func=cmd_revert)

    p = sub.add_parser("env", help="print environment variables for CI (pip, npm, go)")
    eco_arg(p)
    _common_probe_args(p)
    p.add_argument("--format", choices=["sh", "powershell", "github", "json"], default="sh")
    p.add_argument("--fastest", action="store_true")
    p.add_argument("--always", action="store_true", help="print variables even when the official registry is healthy")
    p.set_defaults(func=cmd_env)

    p = sub.add_parser("lint-data", help="validate a mirrors JSON file (default: the bundled one)")
    p.add_argument("files", nargs="*")
    p.add_argument("--overlay", action="store_true", help="check FILE as an overlay (--data) file: it may add mirrors and disable bundled ones")
    p.set_defaults(func=cmd_lint)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    _configure_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.lang:
        set_lang(args.lang)
    if not getattr(args, "func", None):
        parser.print_help()
        return EXIT_ERROR
    try:
        if args.command == "lint-data":
            return args.func(args, None)
        catalog = load_catalog(args.data, use_user_file=not args.no_user_data)
    except DataError as exc:
        err("data error: %s" % exc)
        return EXIT_ERROR
    try:
        return args.func(args, catalog)
    except KeyboardInterrupt:
        err("interrupted")
        return 130
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
