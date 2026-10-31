"""Resolve ontology provenance to structured vs document sources + snippets/URLs."""
from __future__ import annotations
import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@lru_cache(maxsize=1)
def load_source_urls() -> dict[str, str]:
    """Map doc path / topic keywords → original URLs from docs/SOURCES.md."""
    text = (ROOT / "docs" / "SOURCES.md").read_text(encoding="utf-8")
    urls: dict[str, str] = {}
    for m in re.finditer(r"\[([^\]]+)\]\((https?://[^)]+)\)", text):
        label, url = m.group(1), m.group(2)
        urls[label.lower()] = url
        urls[url] = url
    # Explicit path → URL hints from the sources table
    path_hints = {
        "docs/business/company_overview.md": "https://learn.microsoft.com/en-us/analysis-services/multidimensional-tutorial/analysis-services-tutorial-scenario",
        "docs/business/product_codes.md": "https://learn.microsoft.com/en-us/previous-versions/sql/sql-server-2008/ms124670(v=sql.100)",
        "docs/business/kpi_definitions.md": "https://learn.microsoft.com/en-us/dax/dax-sample-model",
        "docs/business/data_dictionary.md": "https://learn.microsoft.com/en-us/analysis-services/multidimensional-tutorial/analysis-services-tutorial-scenario",
        "docs/products/catalog_descriptions.md": None,  # in-DB export
        "docs/products/reviews.md": None,
        "docs/products/model_catalog.md": None,
        "docs/stores/store_survey.md": None,
    }
    for p, u in path_hints.items():
        if u:
            urls[p] = u
    return urls


def classify_provenance(prov: str | None) -> str:
    """Return 'structured' | 'document' | 'both' | 'unknown'."""
    if not prov:
        return "unknown"
    p = str(prov).strip().lower()
    if p in {"schema", "profile", "schema_profile", "table", "column"}:
        return "structured"
    if p.startswith("docs/") or p.endswith(".md") or "http" in p:
        return "document"
    if "schema" in p and ("doc" in p or "docs/" in p):
        return "both"
    if "schema" in p or "profile" in p or "comment" in p:
        return "structured"
    return "document" if "/" in p else "unknown"


def badge_for(kind: str) -> str:
    return {
        "structured": "From tables",
        "document": "From docs",
        "both": "Both",
        "unknown": "Unknown",
    }.get(kind, "Unknown")


def resolve_doc_path(prov: str) -> Path | None:
    if not prov:
        return None
    p = str(prov).strip()
    if p.startswith("http"):
        return None
    # normalize
    if p in {"schema", "profile", "schema_profile"}:
        return None
    cand = ROOT / p
    if cand.exists():
        return cand
    cand = ROOT / "docs" / p
    if cand.exists():
        return cand
    return None


def snippet_from_doc(path: Path, needle: str | None = None, max_chars: int = 420) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    if not needle:
        # first non-empty, non-heading-ish paragraph
        paras = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.startswith("#")]
        body = " ".join(paras[:4])
        return (body[:max_chars] + ("…" if len(body) > max_chars else ""))
    low = text.lower()
    n = needle.lower()
    idx = low.find(n)
    if idx < 0:
        # try individual tokens
        for tok in re.findall(r"[a-z0-9_]{4,}", n):
            idx = low.find(tok)
            if idx >= 0:
                break
    if idx < 0:
        return snippet_from_doc(path, None, max_chars)
    start = max(0, idx - 80)
    end = min(len(text), idx + max_chars)
    snip = text[start:end].strip().replace("\n", " ")
    if start > 0:
        snip = "…" + snip
    if end < len(text):
        snip = snip + "…"
    return snip


def enrich_provenance(item: dict, needle: str | None = None) -> dict:
    """Attach kind/badge/path/url/snippet to an ontology item with `provenance`."""
    prov = item.get("provenance")
    kind = classify_provenance(prov)
    path = resolve_doc_path(str(prov)) if prov else None
    urls = load_source_urls()
    url = None
    if prov:
        url = urls.get(str(prov)) or urls.get(str(prov).lower())
    snippet = None
    if path and path.exists():
        snippet = snippet_from_doc(path, needle or item.get("name") or item.get("description"))
    return {
        **item,
        "source_kind": kind,
        "source_badge": badge_for(kind),
        "source_path": str(path.relative_to(ROOT)) if path else (None if kind == "structured" else str(prov) if prov else None),
        "source_url": url,
        "source_snippet": snippet,
        "source_label": (
            "schema / profile" if kind == "structured"
            else (str(path.relative_to(ROOT)) if path else str(prov or ""))
        ),
    }
