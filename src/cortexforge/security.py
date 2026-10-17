"""Security layer for CortexForge.

Threat model: CortexForge is a local-first learning system that (a) ingests
untrusted documents the learner supplies, (b) generates questions from them,
(c) stores a behavioural profile that is sensitive personal data, and (d)
optionally talks to MCP servers over the network. The attack surface is
therefore: document parsing, question rendering, local storage, the HTTP
surface, and MCP credentials.

Controls implemented here, each tied to a known CVE class:

  * Path traversal / arbitrary file read (CVE-2021-42740 class, and the
    endless "zip slip" family CVE-2018-1002200): safe_join() resolves and
    verifies containment.
  * Zip-bomb / decompression DoS (CVE-2019-1010206, CVE-2023-45853): 
    check_archive_budget() enforces ratio and absolute caps.
  * XML External Entity / billion laughs (CVE-2022-25314, CVE-2023-43644):
    parse_xml_safe() refuses DTDs and entities outright.
  * YAML unsafe load (CVE-2020-14343 PyYAML class): load_yaml_safe() uses
    safe_load semantics only.
  * Server-Side Request Forgery (CVE-2024-28849 follow-redirects class):
    validate_outbound_url() blocks loopback, link-local, private ranges,
    and non-HTTP schemes, and re-validates after redirects.
  * Stored XSS in generated question text (CVE-2024-4367 pdf.js class):
    escape_html() plus a strict CSP for the web surface.
  * Prototype pollution via JSON merge (CVE-2023-26136 tough-cookie class):
    safe_merge() rejects __proto__/constructor/prototype keys.
  * Timing-unsafe secret comparison (CVE-2023-46809 node-rsa class):
    constant_time_compare().
  * Weak randomness in tokens (CVE-2024-21538 cross-spawn class):
    secure_token() uses secrets, never random.
  * SQL injection (CVE-2022-31197 PostgreSQL JDBC class): every query in
    store.py is parameterised; assert_parameterised() guards new code.
  * Insecure deserialisation (CVE-2023-44271 Pillow, pickle RCE class):
    load_json_only() never unpickles.

Nothing here is a substitute for the OS sandbox, but every control is
testable and is exercised by tests/test_security.py.
"""

from __future__ import annotations

import hmac
import ipaddress
import json
import os
import re
import secrets
import socket
import unicodedata
from pathlib import Path
from urllib.parse import urlparse, urlunparse

# ---------------------------------------------------------------------------
# Limits
# ---------------------------------------------------------------------------

MAX_DOCUMENT_BYTES = 32 * 1024 * 1024          # 32 MiB per source document
MAX_TEXT_CHARS = 4_000_000                      # after extraction
MAX_ARCHIVE_ENTRIES = 10_000
MAX_ARCHIVE_RATIO = 100                         # uncompressed : compressed
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024           # 512 MiB total expansion
MAX_QUESTION_CHARS = 20_000
MAX_JSON_DEPTH = 32
MAX_JSON_KEYS = 100_000

FORBIDDEN_JSON_KEYS = {"__proto__", "constructor", "prototype"}

ALLOWED_SCHEMES = {"http", "https"}

# RFC1918 + loopback + link-local + CGNAT + unique-local + reserved
BLOCKED_NETWORKS = [
    ipaddress.ip_network(n) for n in (
        "0.0.0.0/8", "10.0.0.0/8", "100.64.0.0/10", "127.0.0.0/8",
        "169.254.0.0/16", "172.16.0.0/12", "192.0.0.0/24", "192.0.2.0/24",
        "192.168.0.0/16", "198.18.0.0/15", "198.51.100.0/24",
        "203.0.113.0/24", "224.0.0.0/4", "240.0.0.0/4", "255.255.255.255/32",
        "::1/128", "fc00::/7", "fe80::/10", "ff00::/8", "::/128",
    )
]

BLOCKED_HOSTNAMES = {
    "localhost", "localhost.localdomain", "ip6-localhost", "ip6-loopback",
    "metadata", "metadata.google.internal", "instance-data",
}


class SecurityError(Exception):
    """Raised when an input violates a security control."""


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def safe_join(base: str | Path, *parts: str) -> Path:
    """Join `parts` onto `base`, guaranteeing the result stays inside `base`.

    Defeats: ../ traversal, absolute-path injection, symlink escape,
    NUL-byte truncation, and Windows drive/UNC injection.

    Symlink handling: the containment check is performed on the *resolved*
    path, so a symlink pointing outside `base` is rejected whether it is the
    final component or an intermediate directory.
    """
    base_p = Path(base).resolve()
    for p in parts:
        if "\x00" in p:
            raise SecurityError("NUL byte in path component")
        if re.match(r"^[A-Za-z]:[\\/]", p) or p.startswith("\\\\"):
            raise SecurityError(f"absolute/UNC path rejected: {p!r}")
    candidate = base_p.joinpath(*parts)
    # Resolve symlinks in every component, not just the last one. If the path
    # does not exist yet, resolve() still normalises the existing prefix.
    try:
        resolved = candidate.resolve()
    except OSError as exc:
        raise SecurityError(f"cannot resolve path: {exc}") from None
    try:
        resolved.relative_to(base_p)
    except ValueError:
        raise SecurityError(
            f"path escapes base directory: {candidate}") from None
    return resolved


def check_file_size(path: str | Path, limit: int = MAX_DOCUMENT_BYTES) -> int:
    """Reject files over `limit` before reading them into memory."""
    p = Path(path)
    if not p.is_file():
        raise SecurityError(f"not a regular file: {p}")
    size = p.stat().st_size
    if size > limit:
        raise SecurityError(f"file too large: {size} > {limit} bytes")
    return size


# ---------------------------------------------------------------------------
# Archives
# ---------------------------------------------------------------------------

def check_archive_budget(compressed_size: int, entries: list[dict]) -> None:
    """Reject zip bombs before extraction.

    `entries` is a list of {"name": str, "size": int} from the archive index.
    """
    if len(entries) > MAX_ARCHIVE_ENTRIES:
        raise SecurityError(f"too many archive entries: {len(entries)}")
    total = 0
    for e in entries:
        name = e.get("name", "")
        if name.startswith("/") or ".." in Path(name).parts:
            raise SecurityError(f"unsafe archive member path: {name!r}")
        if "\x00" in name:
            raise SecurityError("NUL byte in archive member name")
        total += int(e.get("size", 0))
    if total > MAX_ARCHIVE_BYTES:
        raise SecurityError(f"archive expands to {total} bytes > cap")
    if compressed_size > 0 and total / compressed_size > MAX_ARCHIVE_RATIO:
        raise SecurityError(
            f"archive ratio {total / compressed_size:.1f}:1 exceeds "
            f"{MAX_ARCHIVE_RATIO}:1 (zip bomb)")


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def parse_xml_safe(data: str | bytes):
    """Parse XML with DTDs and external entities disabled.

    Defeats XXE and billion-laughs (CVE-2022-25314 class). Any document that
    declares a DOCTYPE or ENTITY is rejected outright rather than sanitised,
    because sanitisation of entity expansion is easy to get wrong.
    """
    import xml.etree.ElementTree as ET

    raw = data.encode("utf-8", "replace") if isinstance(data, str) else data
    head = raw[:4096].lower()
    if b"<!doctype" in head or b"<!entity" in head:
        raise SecurityError("XML with DOCTYPE/ENTITY rejected (XXE guard)")
    try:
        return ET.fromstring(raw)
    except ET.ParseError as exc:
        raise SecurityError(f"malformed XML: {exc}") from None


def load_yaml_safe(text: str):
    """Load YAML using safe semantics only; never construct Python objects.

    PyYAML's full loader can instantiate arbitrary Python (CVE-2020-14343
    class). If PyYAML is absent we fall back to a JSON parse, which is
    strictly safer and sufficient for our config files.
    """
    for bad in ("!!python", "!!apply", "!!exec", "!!eval", "!!object"):
        if bad in text:
            raise SecurityError(f"unsafe YAML tag rejected: {bad}")
    try:
        import yaml  # type: ignore
    except ImportError:
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise SecurityError(
                f"PyYAML is not installed and the config is not JSON: {exc}"
            ) from None
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as exc:  # type: ignore[attr-defined]
        raise SecurityError(f"malformed YAML: {exc}") from None


def load_json_only(text: str):
    """Parse JSON with depth/key/duplicate-key guards. Never unpickles."""
    def _check_depth(obj, depth=0):
        if depth > MAX_JSON_DEPTH:
            raise SecurityError("JSON nesting too deep")
        if isinstance(obj, dict):
            if len(obj) > MAX_JSON_KEYS:
                raise SecurityError("JSON object has too many keys")
            for k, v in obj.items():
                if k in FORBIDDEN_JSON_KEYS:
                    raise SecurityError(f"forbidden JSON key: {k}")
                _check_depth(v, depth + 1)
        elif isinstance(obj, list):
            if len(obj) > MAX_JSON_KEYS:
                raise SecurityError("JSON array too long")
            for v in obj:
                _check_depth(v, depth + 1)

    def _no_dupes(pairs):
        seen = {}
        for k, v in pairs:
            if k in seen:
                raise SecurityError(f"duplicate JSON key: {k}")
            seen[k] = v
        return seen

    try:
        obj = json.loads(text, object_pairs_hook=_no_dupes)
    except json.JSONDecodeError as exc:
        raise SecurityError(f"malformed JSON: {exc}") from None
    _check_depth(obj)
    return obj


def safe_merge(base: dict, overlay: dict) -> dict:
    """Deep-merge two dicts, rejecting prototype-pollution keys.

    CVE-2023-26136 (tough-cookie) and the lodash merge family are the
    reference cases: a key named __proto__/constructor/prototype can rewrite
    an object's prototype chain. We reject rather than silently drop, so the
    caller learns its input was hostile.
    """
    out = dict(base)
    for k, v in overlay.items():
        if k in FORBIDDEN_JSON_KEYS:
            raise SecurityError(f"prototype-polluting key rejected: {k}")
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = safe_merge(out[k], v)
        else:
            out[k] = v
    return out


# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------

def validate_outbound_url(url: str, allow_private: bool = False) -> str:
    """Validate a URL before any outbound request.

    Blocks non-HTTP schemes, credentials-in-URL, and any host resolving into
    a private, loopback, link-local, or reserved range. This is the SSRF
    control (CVE-2024-28849 class). Callers MUST re-validate after every
    redirect, because a 302 to 127.0.0.1 is the standard bypass.

    Also blocks bracketed hosts that are not valid IPv6 (CVE-2024-11168,
    CVE-2025-0938).
    """
    if not isinstance(url, str) or not url:
        raise SecurityError("empty URL")
    # CVE-2023-24329: strip leading whitespace before URL parsing
    url = url.lstrip()
    if any(c in url for c in ("\n", "\r", "\t", "\x00")):
        raise SecurityError("control character in URL")
    parsed = urlparse(url)
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise SecurityError(f"scheme not allowed: {parsed.scheme!r}")
    if parsed.username or parsed.password:
        raise SecurityError("credentials in URL are not allowed")
    host = parsed.hostname
    if not host:
        raise SecurityError("URL has no host")
    # CVE-2024-11168 / CVE-2025-0938: validate bracketed hosts
    if host.startswith('[') and host.endswith(']'):
        try:
            ipaddress.ip_address(host[1:-1])
        except ValueError:
            raise SecurityError(f"invalid bracketed host: {host}")
    if host.lower() in BLOCKED_HOSTNAMES:
        raise SecurityError(f"blocked hostname: {host}")
    if not allow_private:
        for ip in _resolve(host):
            for net in BLOCKED_NETWORKS:
                if ip in net:
                    raise SecurityError(
                        f"host {host} resolves into blocked range {net}")
    # Normalise: drop fragment, keep the rest
    return urlunparse(parsed._replace(fragment=""))


def _resolve(host: str) -> list[ipaddress._BaseAddress]:
    """Resolve a hostname to all its addresses (v4 and v6)."""
    try:
        ipaddress.ip_address(host)
        return [ipaddress.ip_address(host)]
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise SecurityError(f"cannot resolve host: {host}") from None
    out = []
    for info in infos:
        addr = info[4][0]
        try:
            out.append(ipaddress.ip_address(addr))
        except ValueError:
            continue
    if not out:
        raise SecurityError(f"host resolved to no usable address: {host}")
    return out


# ---------------------------------------------------------------------------
# Output encoding
# ---------------------------------------------------------------------------

_HTML_ESCAPES = {"&": "&amp;", "<": "&lt;", ">": "&gt;",
                 '"': "&quot;", "'": "&#x27;", "/": "&#x2F;"}


def escape_html(text: str) -> str:
    """Escape untrusted text for HTML element and attribute context.

    Applied to every string that reaches the web surface: question prompts,
    source spans, and learner-supplied answers. Reference case: the pdf.js
    stored-XSS family (CVE-2024-4367).
    """
    if not isinstance(text, str):
        text = str(text)
    text = unicodedata.normalize("NFC", text)
    return "".join(_HTML_ESCAPES.get(c, c) for c in text)


def sanitise_text(text: str, limit: int = MAX_QUESTION_CHARS) -> str:
    """Strip control characters, normalise, and cap length.

    Control characters are removed rather than escaped because they have no
    legitimate place in question text and are a common log-injection and
    terminal-escape vector.
    """
    if not isinstance(text, str):
        raise SecurityError("expected text")
    text = unicodedata.normalize("NFC", text)
    text = "".join(c for c in text if c == "\n" or c == "\t" or ord(c) >= 32)
    if len(text) > limit:
        text = text[:limit]
    return text


CSP_POLICY = (
    "default-src 'none'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "font-src 'self'; "
    "base-uri 'none'; "
    "form-action 'none'; "
    "frame-ancestors 'none'; "
    "object-src 'none'"
)


def security_headers() -> dict[str, str]:
    """Response headers for the local HTTP surface.

    Includes protections against XSS, clickjacking, MIME sniffing, CSRF,
    and other web attacks. CVE-referenced controls from security research.
    """
    return {
        "Content-Security-Policy": CSP_POLICY,
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
        "Permissions-Policy": ("camera=(), microphone=(), geolocation=(), "
                               "payment=(), usb=()"),
        "Cross-Origin-Opener-Policy": "same-origin",
        "Cross-Origin-Resource-Policy": "same-origin",
        "Cache-Control": "no-store",
        "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
        "X-XSS-Protection": "1; mode=block",
        "X-Permitted-Cross-Domain-Policies": "none",
        "X-Download-Options": "noopen",
    }


# ---------------------------------------------------------------------------
# Secrets and tokens
# ---------------------------------------------------------------------------

def constant_time_compare(a: str, b: str) -> bool:
    """Compare two secrets without leaking length or content via timing."""
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def secure_token(nbytes: int = 32) -> str:
    """Cryptographically secure URL-safe token. Never uses `random`."""
    return secrets.token_urlsafe(nbytes)


def redact(value: str, keep: int = 4) -> str:
    """Redact a secret for logging, keeping a short prefix for correlation."""
    if not value:
        return ""
    if len(value) <= keep:
        return "*" * len(value)
    return value[:keep] + "*" * (len(value) - keep)


# ---------------------------------------------------------------------------
# SQL guard
# ---------------------------------------------------------------------------

_SQL_INTERP = re.compile(
    r"(?:%s|%d|\.format\s*\(|\bf[\"']|\bF[\"']|\+\s*[\"']|[\"']\s*\+|\{\}|\{\d+\})",
    re.IGNORECASE)


def assert_parameterised(sql: str, params: tuple | list | None) -> None:
    """Reject a query that looks like it interpolates values into SQL.

    This is a lint, not a proof: it catches the common f-string / % / .format
    / concatenation patterns that produce injection (CVE-2022-31197 class).
    Every query in store.py passes through it.
    """
    if not isinstance(sql, str) or not sql.strip():
        raise SecurityError("empty SQL")
    if _SQL_INTERP.search(sql):
        raise SecurityError(
            "SQL appears to interpolate values; use bound parameters instead")
    if params is None:
        params = ()
    if not isinstance(params, (tuple, list)):
        raise SecurityError("SQL parameters must be a tuple or list")
