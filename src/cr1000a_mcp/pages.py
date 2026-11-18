"""Read-only access to a small allowlist of router data pages.

The web UI loads page data from ``GET /cgi/cgi_<name>.js``. Those scripts call
``addROD("key", value)`` and ``addCfg("key", "enc", "value")``. Only pages that
are read-only by nature are allowed here; anything that can change or wipe the
device (upload, restore, clear-log, diagnostics, engineering pages) is not.
"""

from __future__ import annotations

from typing import Any, Literal, get_args

PageName = Literal["arp", "net_connections", "log", "upnp", "firmware"]
SAFE_PAGES: tuple[str, ...] = get_args(PageName)

DEFAULT_ITEM_LIMIT = 100
MAX_STRING = 2000


def cap(value: Any, limit: int = DEFAULT_ITEM_LIMIT, max_str: int = MAX_STRING) -> Any:
    """Recursively truncate long lists and strings so output stays small."""
    if isinstance(value, str):
        return value if len(value) <= max_str else value[:max_str] + "...[truncated]"
    if isinstance(value, list):
        items = [cap(v, limit, max_str) for v in value[:limit]]
        if len(value) > limit:
            items.append(f"...[{len(value) - limit} more items truncated]")
        return items
    if isinstance(value, dict):
        return {k: cap(v, limit, max_str) for k, v in value.items()}
    return value


def fetch_page(client: Any, page: str, *, limit: int = DEFAULT_ITEM_LIMIT) -> dict[str, Any]:
    """Fetch and parse one allowlisted data page.

    Uses the client's internal GET and parsers (there is no public generic
    fetch), so ``verizon-router-client`` is pinned to a compatible range.
    """
    if page not in SAFE_PAGES:
        raise ValueError(f"page must be one of {', '.join(SAFE_PAGES)}; got {page!r}")
    if limit < 1:
        raise ValueError("limit must be at least 1")
    text = client._get(f"/cgi/cgi_{page}.js").text
    rod = client._parse_addrod(text)
    cfg = client._parse_addcfg(text)
    if not rod and not cfg:
        raise RuntimeError(f"No addROD/addCfg entries found in /cgi/cgi_{page}.js")
    return {
        "page": page,
        "data": cap(rod, limit),
        "settings": cap({key: entry.val for key, entry in cfg.items()}, limit),
    }
