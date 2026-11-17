"""Pure decision logic: given probe results, which source should be used?"""

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from .probe import ProbeResult
from .registry import Ecosystem, Mirror, DEFAULT_TRUST_ALLOWED

# Upstream counts as "degraded" when slower than this AND a mirror is at least 2x faster.
DEFAULT_SLOW_MS = 3000.0


@dataclass
class Choice:
    mirror: Optional[Mirror]
    reason: str  # one of: upstream_ok, best_mirror, fastest, degraded, none
    only_community: Optional[Mirror] = None  # healthy community mirror that policy refused


def _healthy(results: Dict[str, ProbeResult], mirror: Mirror) -> Optional[ProbeResult]:
    r = results.get(mirror.id)
    return r if r is not None and r.ok else None


def _latency(r: ProbeResult) -> float:
    return r.latency_ms if r.latency_ms is not None else float("inf")


def healthy_mirrors(eco: Ecosystem, results: Dict[str, ProbeResult], allowed: Iterable[str]) -> List[Mirror]:
    allowed = set(allowed)
    pool = [m for m in eco.mirrors if m.trust in allowed and _healthy(results, m)]
    return sorted(pool, key=lambda m: _latency(results[m.id]))


def choose(
    eco: Ecosystem,
    results: Dict[str, ProbeResult],
    allowed_trust: Iterable[str] = DEFAULT_TRUST_ALLOWED,
    fastest: bool = False,
    slow_ms: float = DEFAULT_SLOW_MS,
) -> Choice:
    allowed = set(allowed_trust)
    up = eco.upstream
    up_res = _healthy(results, up)
    mirrors = healthy_mirrors(eco, results, allowed)

    if fastest:
        candidates = ([up] if up_res else []) + mirrors
        if not candidates:
            return Choice(None, "none", _first_refused_community(eco, results, allowed))
        best = min(candidates, key=lambda m: (_latency(results[m.id]), 0 if m.upstream else 1))
        return Choice(best, "fastest")

    if up_res:
        if mirrors and _latency(up_res) > slow_ms and _latency(results[mirrors[0].id]) * 2 < _latency(up_res):
            return Choice(mirrors[0], "degraded")
        return Choice(up, "upstream_ok")
    if mirrors:
        return Choice(mirrors[0], "best_mirror")
    return Choice(None, "none", _first_refused_community(eco, results, allowed))


def _first_refused_community(eco: Ecosystem, results: Dict[str, ProbeResult], allowed: set) -> Optional[Mirror]:
    refused = [m for m in eco.mirrors if m.trust not in allowed and _healthy(results, m)]
    refused.sort(key=lambda m: _latency(results[m.id]))
    return refused[0] if refused else None
