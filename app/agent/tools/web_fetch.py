"""SSRF-safe web fetching for agent tools.

Rejects non-http(s) schemes, localhost, private/loopback/link-local/multicast
addresses, and unvalidated redirects. Each redirect target is re-validated.
DNS resolution is checked immediately before connecting to shrink the
rebind window; Host is pinned to the original hostname.
"""
import ipaddress
import socket
from typing import Optional
from urllib.parse import urlparse

import httpx

from app.config.settings import settings


class WebFetchError(Exception):
    pass


_BLOCKED_SCHEMES = {"file", "ftp", "gopher", "dict", "jar", "javascript"}


def _parse_ip(value: str):
    """Return an ip_address object, or None if value is not a literal IP."""
    try:
        return ipaddress.ip_address(value)
    except ValueError:
        return None


def _is_blocked_address(addr) -> bool:
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


def _validate_host(hostname: str) -> None:
    if not hostname:
        raise WebFetchError("missing hostname")
    lowered = hostname.lower()
    if lowered in ("localhost", "localhost.") or lowered.endswith(".localhost"):
        raise WebFetchError("localhost is not allowed")
    # Literal IP hosts are checked directly.
    addr = _parse_ip(hostname)
    if addr is not None:
        if _is_blocked_address(addr):
            raise WebFetchError(f"blocked address: {hostname}")
        return
    # Hostnames: resolve and validate every address.
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as e:
        raise WebFetchError(f"cannot resolve host: {e}")
    if not infos:
        raise WebFetchError(f"cannot resolve host: {hostname}")
    for info in infos:
        resolved = _parse_ip(info[4][0])
        if resolved is None or _is_blocked_address(resolved):
            raise WebFetchError(f"host resolves to a blocked address: {hostname} -> {info[4][0]}")


def _validate_url(url: str) -> str:
    if not url or not isinstance(url, str):
        raise WebFetchError("url is required")
    if len(url) > 2048:
        raise WebFetchError("url too long")
    parsed = urlparse(url)
    if parsed.scheme.lower() not in ("http", "https"):
        raise WebFetchError(f"blocked scheme: {parsed.scheme or '(none)'}")
    if not parsed.hostname:
        raise WebFetchError("missing hostname")
    _validate_host(parsed.hostname)
    return url


async def safe_fetch(
    url: str,
    timeout: Optional[float] = None,
    max_bytes: Optional[int] = None,
    max_redirects: int = 3,
) -> dict:
    import typing
    final_url = _validate_url(url)
    timeout = timeout or settings.WEB_FETCH_TIMEOUT_SECONDS
    max_bytes = max_bytes or settings.WEB_FETCH_MAX_BYTES
    redirect_count = 0
    seen_hosts = set()
    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=False,
        headers={"User-Agent": "agentic-crm-agent/1.0"},
    ) as client:
        while True:
            _validate_url(final_url)
            parsed = urlparse(final_url)
            seen_hosts.add(parsed.hostname.lower())
            if len(seen_hosts) > max_redirects + 1:
                raise WebFetchError("too many redirects")
            try:
                response = await client.get(final_url)
            except httpx.TimeoutException:
                raise WebFetchError("request timed out")
            except httpx.HTTPError as e:
                raise WebFetchError(f"request failed: {e}")
            if response.status_code in (301, 302, 303, 307, 308):
                redirect_count += 1
                if redirect_count > max_redirects:
                    raise WebFetchError("too many redirects")
                location = response.headers.get("location")
                if not location:
                    raise WebFetchError("redirect without location")
                final_url = response.url.join(location)
                continue
            content = response.content
            if len(content) > max_bytes:
                return {
                    "success": True,
                    "truncated": True,
                    "status_code": response.status_code,
                    "content_type": response.headers.get("content-type", ""),
                    "content": content[:max_bytes].decode("utf-8", errors="replace"),
                }
            return {
                "success": True,
                "truncated": False,
                "status_code": response.status_code,
                "content_type": response.headers.get("content-type", ""),
                "content": content.decode("utf-8", errors="replace"),
            }
