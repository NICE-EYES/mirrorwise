"""Reachability probe: what actually works from THIS machine's network.

For every candidate we fetch a small, well-known resource and check the answer.
When it fails we locate the failing stage (dns / connect / tls / http / content)
by repeating the connection step by step with plain sockets.
"""

import http.client
import json
import re
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, asdict
from typing import List, Optional, Tuple

from . import __version__
from .registry import Mirror, ProbeSpec

STAGES = ("dns", "connect", "tls", "http", "content", "timeout", "proxy", "error")


@dataclass
class ProbeResult:
    mirror_id: str
    eco: str
    url: str
    ok: bool
    stage: str = "ok"
    detail: str = ""
    status: Optional[int] = None
    latency_ms: Optional[float] = None
    size: int = 0
    kb_per_s: Optional[float] = None

    def to_dict(self):
        return asdict(self)


class _NoDowngradeRedirect(urllib.request.HTTPRedirectHandler):
    """Follow redirects, but never from https to http."""

    max_redirections = 5

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if req.full_url.startswith("https://") and newurl.lower().startswith("http://"):
            raise urllib.error.HTTPError(req.full_url, code, "refusing https->http redirect", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def build_probe_url(base: str, path: str) -> str:
    base = base if base.endswith("/") else base + "/"
    return base + path.lstrip("/")


def _build_opener(use_proxy: bool):
    handlers = [_NoDowngradeRedirect()]
    if not use_proxy:
        handlers.insert(0, urllib.request.ProxyHandler({}))
    return urllib.request.build_opener(*handlers)


def _uses_proxy(url: str, use_proxy: bool) -> bool:
    if not use_proxy:
        return False
    parts = urllib.parse.urlsplit(url)
    proxies = urllib.request.getproxies()
    if parts.scheme not in proxies:
        return False
    try:
        return not urllib.request.proxy_bypass(parts.hostname or "")
    except Exception:
        return True


def diagnose(url: str, timeout: float) -> Tuple[str, str]:
    """Walk dns -> connect -> tls with raw sockets and report the first broken stage."""
    parts = urllib.parse.urlsplit(url)
    host = parts.hostname or ""
    tls = parts.scheme == "https"
    port = parts.port or (443 if tls else 80)
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        return "dns", "name resolution failed: %s" % (exc.strerror or exc)
    except UnicodeError as exc:
        return "dns", "bad host name: %s" % exc
    last_exc = None
    sock = None
    for family, socktype, proto, _canon, sockaddr in infos:
        try:
            sock = socket.socket(family, socktype, proto)
            sock.settimeout(timeout)
            sock.connect(sockaddr)
            last_exc = None
            break
        except socket.timeout:
            last_exc = "connect timed out after %.0fs" % timeout
        except OSError as exc:
            last_exc = "connect failed: %s" % (exc.strerror or exc)
        if sock is not None:
            sock.close()
            sock = None
    if sock is None:
        return "connect", last_exc or "connect failed"
    try:
        if tls:
            ctx = ssl.create_default_context()
            try:
                with ctx.wrap_socket(sock, server_hostname=host):
                    pass
            except ssl.SSLCertVerificationError as exc:
                return "tls", "certificate verification failed: %s" % (exc.verify_message or exc)
            except socket.timeout:
                return "tls", "TLS handshake timed out after %.0fs" % timeout
            except (ConnectionResetError, ssl.SSLEOFError, BrokenPipeError) as exc:
                return "tls", "connection dropped during TLS handshake (%s)" % type(exc).__name__
            except ssl.SSLError as exc:
                return "tls", "TLS error: %s" % (getattr(exc, "reason", None) or exc)
            except OSError as exc:
                return "tls", "TLS handshake failed: %s" % (exc.strerror or exc)
    finally:
        try:
            sock.close()
        except OSError:
            pass
    return "http", "TCP and TLS are fine; the HTTP exchange failed"


def _check_content(spec: ProbeSpec, body: bytes, truncated: bool) -> Optional[str]:
    """Return None if the body looks right, otherwise a short reason."""
    kind = spec.expect_type
    if kind == "any":
        return None
    text = body.decode("utf-8", errors="replace")
    if kind == "contains":
        return None if spec.expect_value in text else "response does not contain %r" % spec.expect_value
    if kind == "regex":
        return None if re.search(spec.expect_value, text) else "response does not match /%s/" % spec.expect_value
    if kind == "json_key":
        if truncated:
            return "response too large to parse as JSON"
        try:
            data = json.loads(text)
        except ValueError:
            return "response is not valid JSON"
        if isinstance(data, dict) and spec.expect_value in data:
            return None
        return "JSON has no key %r" % spec.expect_value
    return "unknown expect type %r" % kind


def probe_url(url: str, spec: ProbeSpec, timeout: float = 6.0, use_proxy: bool = True) -> ProbeResult:
    """Probe one fully built URL. Never raises for network problems."""
    result = ProbeResult(mirror_id="", eco="", url=url, ok=False)
    headers = {
        "User-Agent": "mirrorwise/%s (+reachability probe)" % __version__,
        "Accept-Encoding": "identity",
    }
    if spec.accept:
        headers["Accept"] = spec.accept
    request = urllib.request.Request(url, headers=headers)
    opener = _build_opener(use_proxy)
    started = time.monotonic()
    try:
        try:
            resp = opener.open(request, timeout=timeout)
        except urllib.error.HTTPError as exc:
            resp = exc  # HTTPError is also a response object
            if exc.code not in spec.ok_status:
                result.status = exc.code
                result.stage = "http"
                result.detail = "HTTP %d %s" % (exc.code, exc.reason)
                result.latency_ms = (time.monotonic() - started) * 1000
                return result
        status = getattr(resp, "status", None) or getattr(resp, "code", None)
        result.status = status
        body = resp.read(spec.max_bytes + 1)
        elapsed = time.monotonic() - started
        truncated = len(body) > spec.max_bytes
        body = body[: spec.max_bytes]
        result.latency_ms = elapsed * 1000
        result.size = len(body)
        if elapsed > 0 and body:
            result.kb_per_s = len(body) / 1024.0 / elapsed
        if status not in spec.ok_status:
            result.stage = "http"
            result.detail = "HTTP %s" % status
            return result
        problem = _check_content(spec, body, truncated)
        if problem:
            result.stage = "content"
            result.detail = problem
            return result
        result.ok = True
        result.stage = "ok"
        return result
    except Exception as exc:  # noqa: BLE001 - classify everything, never crash the run
        result.latency_ms = (time.monotonic() - started) * 1000
        return _classify_failure(result, exc, url, timeout, use_proxy)


def _classify_failure(result: ProbeResult, exc: BaseException, url: str, timeout: float, use_proxy: bool) -> ProbeResult:
    reason = exc.reason if isinstance(exc, urllib.error.URLError) else exc
    if _uses_proxy(url, use_proxy):
        result.stage = "proxy"
        result.detail = "via proxy: %s" % _short(reason)
        return result
    if isinstance(reason, (socket.timeout, TimeoutError)) or "timed out" in str(reason).lower():
        stage, detail = diagnose(url, timeout)
        if stage == "http":
            result.stage = "timeout"
            result.detail = "no answer within %.0fs after connecting" % timeout
        else:
            result.stage, result.detail = stage, detail
        return result
    if isinstance(reason, socket.gaierror):
        result.stage = "dns"
        result.detail = "name resolution failed: %s" % (reason.strerror or reason)
        return result
    if isinstance(reason, ssl.SSLCertVerificationError):
        result.stage = "tls"
        result.detail = "certificate verification failed: %s" % (reason.verify_message or reason)
        return result
    stage, detail = diagnose(url, timeout)
    if stage != "http":
        result.stage, result.detail = stage, detail
        return result
    if isinstance(reason, (http.client.HTTPException, ConnectionError, ssl.SSLError, OSError)):
        result.stage = "http"
        result.detail = _short(reason)
        return result
    result.stage = "error"
    result.detail = _short(reason)
    return result


def _short(reason) -> str:
    text = str(reason) or type(reason).__name__
    return text if len(text) <= 120 else text[:117] + "..."


def probe_mirror(mirror: Mirror, spec: ProbeSpec, timeout: float = 6.0, use_proxy: bool = True) -> ProbeResult:
    url = build_probe_url(mirror.probe_base, spec.path)
    res = probe_url(url, spec, timeout=timeout, use_proxy=use_proxy)
    res.mirror_id = mirror.id
    res.eco = mirror.eco
    return res


def probe_many(items, timeout: float = 6.0, use_proxy: bool = True, workers: int = 12) -> List[ProbeResult]:
    """``items`` is a list of ``(Mirror, ProbeSpec)``; results keep the same order."""
    if not items:
        return []
    with ThreadPoolExecutor(max_workers=min(workers, len(items))) as pool:
        futures = [pool.submit(probe_mirror, m, s, timeout, use_proxy) for m, s in items]
        return [f.result() for f in futures]
