"""
lib/cf_fetch.py

Thin wrapper around Cloudflare Workers' built-in fetch() API.
Replaces httpx — no external packages needed, works natively in Pyodide.
"""
import json as _json
from workers import fetch


async def cf_get(url: str, headers: dict = None, params: dict = None) -> dict:
    """GET request, returns parsed JSON."""
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{qs}"
    resp = await fetch(url, method="GET", headers=headers or {})
    text = await resp.text()
    return _json.loads(text) if text else {}


async def cf_post(url: str, headers: dict = None, data: dict = None) -> dict:
    """POST request with JSON body, returns parsed JSON."""
    h = {**(headers or {}), "Content-Type": "application/json"}
    resp = await fetch(url, method="POST", headers=h, body=_json.dumps(data or {}))
    text = await resp.text()
    return _json.loads(text) if text else {}


async def cf_patch(url: str, headers: dict = None, params: dict = None, data: dict = None) -> dict:
    """PATCH request with JSON body, returns parsed JSON."""
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{qs}"
    h = {**(headers or {}), "Content-Type": "application/json"}
    resp = await fetch(url, method="PATCH", headers=h, body=_json.dumps(data or {}))
    text = await resp.text()
    return _json.loads(text) if text else {}


async def cf_delete(url: str, headers: dict = None, params: dict = None) -> bool:
    """DELETE request, returns True on success."""
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{qs}"
    resp = await fetch(url, method="DELETE", headers=headers or {})
    return resp.status < 300
