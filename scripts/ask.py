#!/usr/bin/env python3
"""Ask a question -> ontology slice (or schema-only) -> LLM SQL -> execute."""
from __future__ import annotations
import argparse, json, os, re, sys
from collections import defaultdict, deque
from pathlib import Path

import yaml
import psycopg2
from psycopg2.extras import RealDictCursor

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from llm import complete, LLMError  # noqa: E402

def load_dotenv():
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        # Overwrite DATABASE_URL always so an unquoted `source .env` can't leave a truncated DSN.
        if k == "DATABASE_URL" or not os.environ.get(k):
            os.environ[k] = v

load_dotenv()
DSN = os.environ.get(
    "DATABASE_URL",
    "host=127.0.0.1 port=5433 dbname=Adventureworks user=postgres",
)

def load_ontology():
    return yaml.safe_load((ROOT / "ontology" / "ontology.yaml").read_text())

def stem_token(tok: str) -> str:
    """Stemming-lite: lowercase already assumed; strip simple English plurals."""
    if len(tok) <= 4:
        return tok
    # keep irregular / ambiguous endings intact
    if tok in {"goods", "sales", "status", "address", "process", "series", "species"}:
        return tok
    if tok.endswith("ies") and len(tok) > 4:
        return tok[:-3] + "y"
    if tok.endswith(("sses", "xes", "zes", "ches", "shes")):
        return tok[:-2]
    if tok.endswith(("ss", "us", "is")):
        return tok
    if tok.endswith("s"):
        return tok[:-1]
    return tok

def _split_ident(text: str) -> list[str]:
    """Split CamelCase, snake_case, and dotted idents into lowercase pieces."""
    if not text:
        return []
    s = str(text).replace(".", " ").replace("-", " ").replace("_", " ")
    # CamelCase / acronyms
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", s)
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", s)
    return re.findall(r"[a-z0-9]+", s.lower())


def tokenize(text: str) -> set[str]:
    raw = _split_ident(text)
    # also keep whole lower tokens from non-ident prose
    raw += re.findall(r"[a-z0-9_]+", (text or "").lower())
    out = set()
    for t in raw:
        out.add(t)
        out.add(stem_token(t))
    return out


def phrase_in_text(phrase: str, text: str) -> bool:
    """Word-boundary phrase match (avoids 'us' hitting 'versus').

    Also tries a simple singular/plural variant of the final word so
    'sales order' matches 'sales orders'.
    """
    phrase = re.sub(r"\s+", " ", (phrase or "").lower().strip())
    if not phrase:
        return False
    tl = (text or "").lower()

    def _hit(p: str) -> bool:
        return re.search(rf"(?<![a-z0-9]){re.escape(p)}(?![a-z0-9])", tl) is not None

    if _hit(phrase):
        return True
    parts = phrase.split(" ")
    if len(parts) >= 2:
        last = parts[-1]
        alts = set()
        if last.endswith("s") and len(last) > 3:
            alts.add(last[:-1])
        else:
            alts.add(last + "s")
        if last.endswith("ies") and len(last) > 4:
            alts.add(last[:-3] + "y")
        for alt in alts:
            if _hit(" ".join(parts[:-1] + [alt])):
                return True
    return False

def _blob_tokens(*parts: str) -> set[str]:
    return tokenize(" ".join(p for p in parts if p))

def _entity_tokens(e: dict) -> set[str]:
    bits = [
        e.get("name", ""),
        e.get("description", ""),
        e.get("table", ""),
        " ".join(e.get("synonyms") or []),
    ]
    for a in e.get("attributes") or []:
        bits.append(a.get("name", ""))
        bits.append(a.get("column", ""))
        bits.append(" ".join(a.get("synonyms") or []))
    return _blob_tokens(*bits)

def _rule_tokens(r: dict) -> set[str]:
    # Intentionally skip description prose — it often mentions unrelated nouns
    # (e.g. "sold to customers") that false-trigger retrieval.
    toks = _blob_tokens(
        r.get("name", ""),
        r.get("sql_hint", ""),
        " ".join(r.get("synonyms") or []),
    )
    return toks - SQL_NOISE

def _metric_tokens(m: dict) -> set[str]:
    return _blob_tokens(
        m.get("name", ""),
        m.get("description", ""),
        m.get("sql", ""),
        " ".join(m.get("synonyms") or []),
    )

def _value_tokens(v: dict) -> set[str]:
    parts = [v.get("column", ""), json.dumps(v.get("values") or {}), " ".join(v.get("synonyms") or [])]
    return _blob_tokens(*parts)


STOPWORDS = {
    "a", "an", "the", "of", "and", "or", "to", "in", "for", "by", "on", "is", "are",
    "with", "from", "as", "at", "be", "we", "do", "does", "did", "how", "many",
    "much", "what", "which", "who", "when", "where", "there", "their", "this",
    "that", "these", "those", "have", "has", "had", "was", "were", "been", "being",
    "into", "over", "under", "than", "then", "also", "only", "just", "per",
}

# Ultra-generic tokens that appear across many warehouse concepts; never drive expansion alone.
SQL_NOISE = {
    "null", "true", "false", "and", "or", "not", "date", "interval", "select", "from",
    "where", "join", "left", "right", "inner", "outer", "on", "as", "case", "when",
    "then", "else", "end", "avg", "sum", "count", "min", "max", "coalesce", "cast",
    "current_date", "current_timestamp", "now", "extract", "year", "month", "day",
    "xpath", "text", "xml", "local", "name", "dt", "flg", "cd", "id",
    # Ambiguous crumbs from SQL / weak synonyms that false-trigger rules:
    "current", "currently", "top", "good", "well", "star", "stars",
}

GENERIC_TOKENS = {
    # Cross-cutting warehouse glue — must not alone unlock synonym entries or dominate scores.
    "order", "orders", "sale", "sales", "id", "ids", "name", "names", "code", "flag",
    "date", "amount", "total", "count", "number", "type", "status", "line", "lines",
    "active", "complete", "avg", "average", "sum", "qty", "quantity", "price", "cost",
    "key", "value", "row", "table", "item", "items", "detail", "details",
}


def _overlap_score(a: set[str], b: set[str]) -> int:
    """Legacy unweighted overlap (kept for callers); prefer _weighted_score."""
    return len((a - STOPWORDS) & (b - STOPWORDS))


def _entity_doc_tokens(e: dict) -> set[str]:
    """All tokens that describe an entity (for IDF document frequency)."""
    return _entity_tokens(e)


def build_idf(ont: dict) -> dict[str, float]:
    """IDF over ontology entities (+ light contribution from rules/metrics text).

    Tokens that appear in many entities (order, id, name, …) score near 0.
    """
    import math
    docs = []
    for e in ont.get("entities") or []:
        docs.append(_entity_doc_tokens(e))
    # fold rules/metrics as weak extra docs so rare business terms stay distinctive
    for r in ont.get("rules") or []:
        docs.append(_rule_tokens(r))
    for m in ont.get("metrics") or []:
        docs.append(_metric_tokens(m))
    n = max(1, len(docs))
    df: dict[str, int] = defaultdict(int)
    for doc in docs:
        for t in set(doc) - STOPWORDS:
            df[t] += 1
    idf = {}
    for t, c in df.items():
        # classic smooth IDF; clamp so ubiquitous tokens almost vanish
        idf[t] = math.log((n + 1) / (c + 1)) + 1.0
    return idf


def _is_strong_token(tok: str, idf: dict[str, float], median_idf: float) -> bool:
    if tok in STOPWORDS or tok in GENERIC_TOKENS:
        return False
    if len(tok) <= 2 and tok not in {"fy", "us", "po"}:
        return False
    return idf.get(tok, 0.0) >= max(1.15, median_idf * 0.85)


def _expand_question_tokens(ont: dict, qtok: set[str], question: str = "",
                            idf: dict[str, float] | None = None) -> set[str]:
    """Expand via synonyms_index only on full-phrase or strong-token hits.

    Multi-word keys like 'complete purchase order' must match as a phrase (or
    enough content tokens); a single generic word must not fire the entry.
    Value-side matches must also be phrases or strong tokens — never a lone
    generic like 'sales' unlocking the whole 'revenue' entry.
    """
    if idf is None:
        idf = build_idf(ont)
    vals_idf = sorted(idf.values()) or [1.0]
    median_idf = vals_idf[len(vals_idf) // 2]
    ql = (question or "").lower()
    expanded = set(qtok)
    syn = ont.get("synonyms_index") or {}
    for k, vals in syn.items():
        keys = tokenize(k)
        content_keys = keys - STOPWORDS
        val_toks: set[str] = set()
        for v in vals or []:
            val_toks |= tokenize(str(v))

        key_phrase = re.sub(r"\s+", " ", str(k).lower().strip())
        phrase_hit = phrase_in_text(key_phrase, ql)
        for v in vals or []:
            vp = re.sub(r"\s+", " ", str(v).lower().strip())
            # value phrase only counts if multi-word OR non-generic single token
            vtoks = tokenize(vp) - STOPWORDS
            if not phrase_in_text(vp, ql):
                continue
            if len(vtoks) >= 2 or (vtoks and _is_strong_token(next(iter(vtoks)), idf, median_idf)):
                phrase_hit = True
                break

        strong_from_key = {
            t for t in content_keys & qtok if _is_strong_token(t, idf, median_idf)
        }
        # value tokens may reinforce only when strong (not generic)
        strong_from_val = {
            t for t in (val_toks - STOPWORDS) & qtok if _is_strong_token(t, idf, median_idf)
        }
        strong_hit = strong_from_key | strong_from_val

        if len(content_keys) >= 2:
            # Multi-word keys need a phrase hit or 2+ content tokens — a single
            # strong word like "employee" must not unlock "active employee".
            if phrase_hit or len(content_keys & qtok) >= 2:
                expanded |= keys | val_toks
            continue
        # single-token key: key itself strong in question, or a strong/non-generic phrase hit
        if phrase_hit or strong_hit:
            expanded |= keys | val_toks
    return expanded



def _weighted_score(qtok: set[str], field_toks: set[str], idf: dict[str, float],
                    weight: float) -> float:
    score = 0.0
    for t in (qtok & field_toks) - STOPWORDS:
        score += weight * idf.get(t, 1.0)
    return score


def _score_entity(e: dict, qtok: set[str], idf: dict[str, float], question: str = "", ont: dict | None = None) -> float:
    """Name/synonyms high, attributes medium, description low; IDF-weighted.

    Exact entity-name token hits always count (even if the token is common).
    Other generic tokens only count on name/synonym fields when paired with a
    strong token, or via multi-word phrase bonus.
    """
    ql = (question or "").lower()
    vals_idf = sorted(idf.values()) or [1.0]
    median_idf = vals_idf[len(vals_idf) // 2]

    name_toks = tokenize(e.get("name", ""))
    syn_list = list(e.get("synonyms") or [])
    syn_toks = tokenize(" ".join(syn_list))
    table_bits = tokenize((e.get("table") or "").replace(".", " "))
    attr_bits: set[str] = set()
    for a in e.get("attributes") or []:
        attr_bits |= tokenize(
            " ".join([a.get("name", ""), " ".join(a.get("synonyms") or [])])
        )
    desc_bits = tokenize(e.get("description") or "")

    def tok_w(t: str) -> float:
        return idf.get(t, 1.0)

    score = 0.0
    # Exact name identity (SalesOrder ↔ sales+order pieces, Customer ↔ customer)
    name_hits = (qtok & name_toks) - STOPWORDS
    for t in name_hits:
        score += 3.5 * tok_w(t)

    # Synonym tokens
    syn_hits = (qtok & syn_toks) - STOPWORDS - name_hits
    strong_syn = {t for t in syn_hits if _is_strong_token(t, idf, median_idf)}
    generic_syn = syn_hits - strong_syn
    for t in strong_syn:
        score += 3.0 * tok_w(t)
    if strong_syn or name_hits:
        for t in generic_syn:
            score += 0.6 * tok_w(t)

    # Attributes: any non-generic overlap (subtotal, territory, …)
    for t in (qtok & attr_bits) - STOPWORDS - GENERIC_TOKENS:
        score += 1.4 * tok_w(t)

    # Description: distinctive tokens only, low weight
    for t in (qtok & desc_bits) - STOPWORDS - GENERIC_TOKENS - name_hits:
        if _is_strong_token(t, idf, median_idf):
            score += 0.35 * tok_w(t)

    # Tiny table signal for distinctive tokens only
    for t in (qtok & table_bits) - STOPWORDS - GENERIC_TOKENS:
        if _is_strong_token(t, idf, median_idf):
            score += 0.2 * tok_w(t)

    # Value-meaning short labels on this entity's table (e.g. Road/Mountain).
    # Ignore long prose values like "finished good sold to customers".
    if ont is not None:
        et = e.get("table") or ""
        for v in ont.get("value_meanings") or []:
            col = v.get("column") or ""
            if not et or et not in col:
                continue
            parts = list(v.get("synonyms") or [])
            for k, val in (v.get("values") or {}).items():
                parts.append(str(k))
                vt = tokenize(str(val))
                if len(vt) <= 3:
                    parts.append(str(val))
            label_toks = tokenize(" ".join(parts))
            hits = (qtok & label_toks) - STOPWORDS - GENERIC_TOKENS
            if hits:
                score += 4.0 * sum(tok_w(t) for t in hits)

    # Bonus: multi-word synonym / spaced CamelCase name in the question
    phrases = [e.get("name", "")] + syn_list
    spaced = " ".join(_split_ident(e.get("name", "")))
    if spaced and " " in spaced:
        phrases.append(spaced)
    for ph in phrases:
        ph_norm = re.sub(r"\s+", " ", str(ph).lower().strip())
        if " " not in ph_norm:
            continue
        if phrase_in_text(ph_norm, ql):
            score += 10.0 * max(1.0, median_idf)
            break
    return score



def _score_text_item(qtok: set[str], item_toks: set[str], idf: dict[str, float]) -> float:
    """Strong match score for rules/metrics/value meanings.

    Ignores stopwords and generic glue tokens so 'order' alone cannot unlock
    every order-related rule.
    """
    vals_idf = sorted(idf.values()) or [1.0]
    median_idf = vals_idf[len(vals_idf) // 2]
    score = 0.0
    for t in (qtok & item_toks) - STOPWORDS - GENERIC_TOKENS:
        if _is_strong_token(t, idf, median_idf):
            score += 2.5 * idf.get(t, 1.0)
        else:
            score += 0.8 * idf.get(t, 1.0)
    return score


def _build_entity_graph(ont: dict) -> tuple[dict, list]:
    """Undirected graph: entity name -> neighbors; keep relationship objects."""
    entity_names = {e.get("name") for e in ont.get("entities") or []}
    adj = defaultdict(list)  # name -> list[(neighbor, rel)]
    rels = list(ont.get("relationships") or [])
    for rel in rels:
        a, b = rel.get("from"), rel.get("to")
        if not a or not b:
            continue
        # skip non-entity endpoints (raw table refs like wh.st_prov)
        if a not in entity_names or b not in entity_names:
            continue
        adj[a].append((b, rel))
        adj[b].append((a, rel))
    return adj, rels


def _shortest_path(adj: dict, src: str, dst: str, max_hops: int = 3) -> list[str] | None:
    if src == dst:
        return [src]
    q = deque([(src, [src])])
    seen = {src}
    while q:
        node, path = q.popleft()
        if len(path) - 1 >= max_hops:
            continue
        for nbr, _rel in adj.get(node, []):
            if nbr in seen:
                continue
            np = path + [nbr]
            if nbr == dst:
                return np
            seen.add(nbr)
            q.append((nbr, np))
    return None


def _multi_hop_expand(ont: dict, seed_names: set[str]) -> tuple[set[str], list]:
    """Add intermediate entities + relationships on shortest paths (<=3 hops)."""
    adj, _ = _build_entity_graph(ont)
    chosen = set(seed_names)
    path_rels = []
    seeds = sorted(seed_names)
    for i, a in enumerate(seeds):
        for b in seeds[i + 1 :]:
            path = _shortest_path(adj, a, b, max_hops=3)
            if not path:
                continue
            chosen.update(path)
            # collect edges along path
            for u, v in zip(path, path[1:]):
                for nbr, rel in adj.get(u, []):
                    if nbr == v:
                        path_rels.append(rel)
                        break
    return chosen, path_rels


def slice_ontology(ont: dict, question: str) -> dict:
    """Generic ontology retrieval: IDF-weighted scores + careful synonym expansion.

    No question-tuned keyword triggers. Matching uses only ontology content
    (names, descriptions, synonyms, synonyms_index, value_meanings text).
    """
    idf = build_idf(ont)
    vals_idf = sorted(idf.values()) or [1.0]
    median_idf = vals_idf[len(vals_idf) // 2]
    raw_qtok = tokenize(question)
    qtok = _expand_question_tokens(ont, raw_qtok, question=question, idf=idf)

    # --- score entities ---
    scored_ents: list[tuple[float, dict]] = []
    for e in ont.get("entities") or []:
        score = _score_entity(e, qtok, idf, question=question, ont=ont)
        if score > 0:
            scored_ents.append((score, e))
    scored_ents.sort(key=lambda x: (-x[0], x[1].get("name", "")))

    ents: list[dict] = []
    entity_scores: dict[str, float] = {}
    if scored_ents:
        best = scored_ents[0][0]
        thresh = best * 0.40
        for s, e in scored_ents:
            if s < thresh:
                break
            ents.append(e)
            entity_scores[e["name"]] = round(s, 3)
            if len(ents) >= 5:
                break
    else:
        # soft fallback: name/synonym substring or token hit without IDF gate
        soft = []
        ql = question.lower()
        for e in ont.get("entities") or []:
            name = e.get("name", "")
            sc = _score_entity(e, raw_qtok, idf, question=question, ont=ont)
            if sc == 0 and name and name.lower() in ql:
                sc = 0.5
            soft.append((sc, e))
        soft.sort(key=lambda x: (-x[0], x[1].get("name", "")))
        for s, e in soft:
            if s <= 0:
                continue
            ents.append(e)
            entity_scores[e["name"]] = round(s, 3)
            if len(ents) >= 5:
                break
        if not ents:
            adj, _ = _build_entity_graph(ont)
            degree = sorted(
                ((len(adj.get(e.get("name"), [])), e) for e in ont.get("entities") or []),
                reverse=True,
            )
            for _, e in degree[:3]:
                ents.append(e)
                entity_scores[e["name"]] = 0.0

    seed_names = {e["name"] for e in ents}
    expanded_names, path_rels = _multi_hop_expand(ont, seed_names)

    by_name = {e["name"]: e for e in ont.get("entities") or []}
    # preserve seed order then add bridges
    final_ents = list(ents)
    have = set(seed_names)
    for n in expanded_names:
        if n not in have and n in by_name:
            final_ents.append(by_name[n])
            have.add(n)
            entity_scores.setdefault(n, 0.0)

    ent_names = {e["name"] for e in final_ents}
    ent_tables = {e.get("table") for e in final_ents if e.get("table")}

    # relationships: any touching final entities, plus path rels
    rels = []
    seen_rel = set()
    for r in ont.get("relationships") or []:
        if r.get("from") in ent_names or r.get("to") in ent_names:
            key = (r.get("name"), r.get("from"), r.get("to"))
            if key not in seen_rel:
                rels.append(r)
                seen_rel.add(key)
    for r in path_rels:
        key = (r.get("name"), r.get("from"), r.get("to"))
        if key not in seen_rel:
            rels.append(r)
            seen_rel.add(key)

    # rules / metrics: strong score OR (weaker) overlap with selected entity tokens
    seed_toks: set[str] = set()
    for e in ents:
        seed_toks |= tokenize(e.get("name", ""))
        seed_toks |= tokenize(" ".join(e.get("synonyms") or []))

    def _strong_enough(sc: float) -> bool:
        # absolute floor scaled by median IDF so rare terms clear easily
        return sc >= max(2.0, median_idf * 1.2)

    rules = []
    for r in ont.get("rules") or []:
        rtoks = _rule_tokens(r)
        sc = _score_text_item(qtok, rtoks, idf)
        distinctive = (rtoks & qtok) - STOPWORDS - GENERIC_TOKENS - SQL_NOISE
        # Require at least one distinctive hit; score gate filters weak leftovers.
        if distinctive and (sc >= max(1.5, median_idf) or len(distinctive) >= 2):
            rules.append(r)

    metrics = []
    for m in ont.get("metrics") or []:
        mtoks = _metric_tokens(m)
        sc = _score_text_item(qtok, mtoks, idf)
        distinctive = (mtoks & qtok) - STOPWORDS - GENERIC_TOKENS
        if distinctive and (sc >= max(1.5, median_idf) or len(distinctive) >= 2):
            metrics.append(m)
    metrics = metrics[:8]

    # value meanings: attached to selected tables/columns OR strong text match
    vals = []
    for v in ont.get("value_meanings") or []:
        col = v.get("column") or ""
        attached = any(t and t in col for t in ent_tables if t)
        vtoks = _value_tokens(v)
        sc = _score_text_item(qtok, vtoks, idf)
        distinctive = (vtoks & qtok) - STOPWORDS - GENERIC_TOKENS
        strong_distinct = {t for t in distinctive if _is_strong_token(t, idf, median_idf)}
        # Attached value meanings only if the question also touches their labels,
        # or the match is strong on its own — avoids dumping every code table.
        if strong_distinct or _strong_enough(sc) or (attached and distinctive):
            vals.append(v)

    retrieval = {
        "question_tokens": sorted(raw_qtok),
        "expanded_tokens": sorted(qtok),
        "seed_entities": [e["name"] for e in ents],  # score order
        "entity_scores": entity_scores,
        "entities": [e["name"] for e in final_ents],
        "bridge_entities": sorted(expanded_names - seed_names),
        "rules": [r.get("name") for r in rules],
        "metrics": [m.get("name") for m in metrics],
        "value_meanings_columns": [v.get("column") for v in vals],
        "relationships": [r.get("name") for r in rels],
        "retrieval_version": "v2_idf",
    }

    return {
        "entities": final_ents,
        "relationships": rels,
        "rules": rules,
        "metrics": metrics,
        "value_meanings": vals,
        "_retrieval": retrieval,
    }


def schema_hints(tables: set[str] | None, limit_tables: int = 12) -> str:
    profile = json.loads((ROOT / "artifacts" / "schema_profile.json").read_text())
    lines = []
    if tables:
        names = [t.split(".")[-1] for t in tables]
    else:
        names = sorted(profile["tables"].keys())[:limit_tables]
    for t in names:
        bare = t.split(".")[-1]
        info = profile["tables"].get(bare)
        if not info:
            continue
        cols = ", ".join(
            f"{c['column_name']}:{c['data_type']}" for c in info["columns"][:20]
        )
        lines.append(f"wh.{bare} ({info['row_count']} rows): {cols}")
    bare_set = set(names)
    joins = profile.get("inferred_joins") or []
    jlines = [
        f"wh.{j['from_table']}.{j['from_col']} = wh.{j['to_table']}.{j['to_col']}"
        for j in joins
        if not tables
        or j["from_table"] in bare_set
        or j["to_table"] in bare_set
    ]
    return "\n".join(lines) + ("\nJOINS:\n" + "\n".join(jlines[:30]) if jlines else "")

def extract_sql(text: str) -> str:
    """Pull SQL from model output; strip thinking/reasoning scratchpads."""
    if not text:
        raise ValueError("Empty model output")
    cleaned = text
    cleaned = re.sub(r"<think>.*?</think>", " ", cleaned, flags=re.I | re.S)
    cleaned = re.sub(r"<thinking>.*?</thinking>", " ", cleaned, flags=re.I | re.S)
    cleaned = re.sub(r"<reasoning>.*?</reasoning>", " ", cleaned, flags=re.I | re.S)
    cleaned = re.sub(r"```thinking.*?```", " ", cleaned, flags=re.I | re.S)
    cleaned = re.sub(r"```reasoning.*?```", " ", cleaned, flags=re.I | re.S)

    m = re.search(r"```sql\s*(.*?)```", cleaned, re.I | re.S)
    if m:
        return m.group(1).strip().rstrip(";")
    m = re.search(r"```\s*(SELECT.*)```", cleaned, re.I | re.S)
    if m:
        return m.group(1).strip().rstrip(";")
    selects = list(re.finditer(r"(SELECT\b.*?)(?:;|\Z)", cleaned, re.I | re.S))
    if selects:
        return selects[-1].group(1).strip().rstrip(";")
    selects = list(re.finditer(r"(SELECT\b.*?)(?:;|\Z)", text, re.I | re.S))
    if selects:
        return selects[-1].group(1).strip().rstrip(";")
    raise ValueError("No SQL found in model output")

def assert_readonly_select(sql: str) -> str:
    """Allow a single SELECT / WITH…SELECT. Reject anything else."""
    cleaned = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
    cleaned = re.sub(r"--.*?$", " ", cleaned, flags=re.M)
    cleaned = cleaned.strip().rstrip(";").strip()
    if not cleaned:
        raise ValueError("Empty SQL")
    # reject multiple statements
    if ";" in cleaned:
        raise ValueError("Multiple SQL statements are not allowed")
    low = cleaned.lower()
    if not (low.startswith("select") or low.startswith("with")):
        raise ValueError("Only SELECT queries are allowed")
    banned = (
        r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|"
        r"copy|call|do|execute|refresh|reindex|vacuum|analyze|comment|"
        r"security\s+label|set\s+role|reset\s+role)\b"
    )
    if re.search(banned, low):
        raise ValueError("Only read-only SELECT queries are allowed")
    return cleaned

def run_sql(sql: str, row_limit: int | None = None):
    """Execute SQL read-only with a 15s statement_timeout.

    Behaviour for valid SELECTs is unchanged for evaluate.py (no row_limit).
    """
    safe = assert_readonly_select(sql)
    conn = psycopg2.connect(DSN)
    try:
        conn.set_session(readonly=True, autocommit=False)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SET LOCAL statement_timeout = '15s'")
            cur.execute(safe)
            rows = cur.fetchall()
            out = [dict(r) for r in rows]
            if row_limit is not None:
                return out[:row_limit]
            return out
    finally:
        try:
            conn.rollback()
        except Exception:
            pass
        conn.close()

def synonym_expansions(ont: dict, question: str) -> dict:
    """Detail which synonyms_index entries fired (same rules as v2 expansion)."""
    idf = build_idf(ont)
    vals_idf = sorted(idf.values()) or [1.0]
    median_idf = vals_idf[len(vals_idf) // 2]
    qtok = tokenize(question)
    expanded = _expand_question_tokens(ont, qtok, question=question, idf=idf)
    matches = []
    syn = ont.get("synonyms_index") or {}
    ql = question.lower()
    for k, vals in syn.items():
        keys = tokenize(k)
        content_keys = keys - STOPWORDS
        val_toks = set()
        for v in vals or []:
            val_toks |= tokenize(str(v))
        content_vals = val_toks - STOPWORDS
        key_phrase = re.sub(r"\s+", " ", str(k).lower().strip())
        phrase_hit = bool(key_phrase) and (
            phrase_in_text(key_phrase, ql)
            or any(phrase_in_text(re.sub(r"\s+", " ", str(v).lower().strip()), ql)
                   for v in (vals or []))
        )
        strong_hit_toks = {
            t for t in (content_keys | content_vals) & qtok
            if _is_strong_token(t, idf, median_idf)
        }
        fired = False
        reason = ""
        if len(content_keys) >= 2:
            if phrase_hit:
                fired, reason = True, "phrase"
            elif len(content_keys & qtok) >= 2:
                fired, reason = True, "multi-token"
            elif strong_hit_toks:
                fired, reason = True, "strong-token"
        else:
            if phrase_hit:
                fired, reason = True, "phrase"
            elif strong_hit_toks:
                fired, reason = True, "strong-token"
            elif content_keys and next(iter(content_keys)) in qtok and _is_strong_token(
                next(iter(content_keys)), idf, median_idf
            ):
                fired, reason = True, "strong-key"
        if fired:
            matches.append({
                "key": k,
                "values": list(vals or []),
                "matched_tokens": sorted(((keys | val_toks) & qtok) | strong_hit_toks),
                "reason": reason,
            })
    return {
        "question_tokens": sorted(qtok),
        "expanded_tokens": sorted(expanded),
        "added_tokens": sorted(expanded - qtok),
        "synonym_hits": matches,
    }



def multi_hop_paths(ont: dict, seed_names: set[str]) -> list[dict]:
    """Shortest paths (<=3 hops) between seed pairs, for UI display only."""
    adj, _ = _build_entity_graph(ont)
    paths = []
    seeds = sorted(seed_names)
    for i, a in enumerate(seeds):
        for b in seeds[i + 1 :]:
            path = _shortest_path(adj, a, b, max_hops=3)
            if not path or len(path) < 2:
                continue
            edges = []
            for u, v in zip(path, path[1:]):
                for nbr, rel in adj.get(u, []):
                    if nbr == v:
                        edges.append({
                            "from": u,
                            "to": v,
                            "name": rel.get("name"),
                            "join": rel.get("join") or rel.get("join_hint") or rel.get("via"),
                        })
                        break
            paths.append({"nodes": path, "edges": edges, "hops": len(path) - 1})
    return paths


def build_prompt(question: str, mode: str = "ontology") -> tuple[str, dict | None, dict]:
    """Build the exact prompt the LLM will see. Returns (prompt, slice_or_None, meta)."""
    ont = load_ontology()
    if mode == "ontology":
        sl = slice_ontology(ont, question)
        retrieval = sl.pop("_retrieval", None)
        tables = {e.get("table", "").split(".")[-1] for e in sl["entities"] if e.get("table")}
        tmpl = (ROOT / "prompts" / "ask_sql.md").read_text()
        prompt = (
            tmpl.replace("{{question}}", question)
            .replace("{{ontology_slice}}", yaml.dump(sl, sort_keys=False))
            .replace("{{schema_hints}}", schema_hints(tables))
        )
        meta = {
            "ontology_slice": sl,
            "tables": sorted(tables),
            "expansions": synonym_expansions(ont, question),
            "paths": multi_hop_paths(ont, set(retrieval.get("seed_entities") or [])),
        }
        return prompt, retrieval, meta
    tmpl = (ROOT / "prompts" / "ask_sql_baseline.md").read_text()
    profile = json.loads((ROOT / "artifacts" / "schema_profile.json").read_text())
    base_tables = sorted(profile["tables"].keys())[:20]
    prompt = tmpl.replace("{{question}}", question).replace(
        "{{schema_hints}}", schema_hints(None, limit_tables=20)
    )
    return prompt, None, {
        "ontology_slice": None,
        "tables": base_tables,
        "expansions": {"question_tokens": sorted(tokenize(question)),
                       "added_tokens": [], "synonym_hits": [],
                       "expanded_tokens": sorted(tokenize(question))},
        "paths": [],
        "schema_only": True,
    }


def ask_traced(question: str, mode: str = "ontology", row_limit: int | None = 200) -> dict:
    """Full ask pipeline with a rich UI trace. Retrieval/SQL identical to ask()."""
    import time
    t0 = time.perf_counter()
    prompt, retrieval, meta = build_prompt(question, mode=mode)
    t_prompt = time.perf_counter()
    system = "You are a careful Postgres SQL generator."
    raw = complete(prompt, system=system, temperature=0.0)
    t_llm = time.perf_counter()
    sql_error = None
    sql = None
    try:
        sql = extract_sql(raw)
    except Exception as e:
        sql_error = f"SQL extract failed: {e}"
        sql = None
    rows, err = [], sql_error
    if sql and not sql_error:
        try:
            rows = run_sql(sql, row_limit=row_limit)
            err = None
        except Exception as e:
            rows, err = [], str(e)
    t_end = time.perf_counter()
    sl = meta.get("ontology_slice") or {}
    return {
        "question": question,
        "mode": mode,
        "sql": sql,
        "rows": rows,
        "error": err,
        "raw": raw,
        "retrieval": retrieval,
        "prompt": prompt,
        "system": system,
        "prompt_chars": len(prompt),
        "prompt_approx_tokens": max(1, len(prompt) // 4),
        "expansions": meta.get("expansions"),
        "paths": meta.get("paths") or [],
        "entities": sl.get("entities") or [],
        "relationships": sl.get("relationships") or [],
        "rules": sl.get("rules") or [],
        "metrics": sl.get("metrics") or [],
        "value_meanings": sl.get("value_meanings") or [],
        "tables": meta.get("tables") or [],
        "latency_sec": {
            "prompt_build": round(t_prompt - t0, 3),
            "llm": round(t_llm - t_prompt, 3),
            "sql": round(t_end - t_llm, 3),
            "total": round(t_end - t0, 3),
        },
        "nuances": _nuances(mode, retrieval, err, meta),
    }


def _nuances(mode, retrieval, err, meta) -> list[str]:
    notes = [
        "Scrambled warehouse names (`wh.*`) are what the LLM sees; "
        "`data/scramble_map.yaml` is never sent.",
        f"Mode: {'ontology retrieval' if mode == 'ontology' else 'schema-only baseline'}.",
    ]
    if mode == "ontology" and retrieval:
        if not retrieval.get("seed_entities"):
            notes.append("Retrieval fell back to degree-based seed entities (weak token overlap).")
        if retrieval.get("bridge_entities"):
            notes.append(
                "Multi-hop bridges added: " + ", ".join(retrieval["bridge_entities"])
            )
        if not retrieval.get("rules") and not retrieval.get("metrics"):
            notes.append("No business rules/metrics matched this question.")
    if err:
        notes.append(f"SQL/execution error: {err}")
    return notes



def ask(question: str, mode: str = "ontology") -> dict:
    """CLI/eval entry point. Same keys as before; extras ignored by evaluate.py.

    Uses ask_traced with row_limit=None so eval still sees full result sets.
    """
    traced = ask_traced(question, mode=mode, row_limit=None)
    return {
        "question": traced["question"],
        "mode": traced["mode"],
        "sql": traced["sql"],
        "rows": traced["rows"],
        "error": traced["error"],
        "raw": traced["raw"],
        "retrieval": traced["retrieval"],
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question", nargs="?", help="Natural language question")
    ap.add_argument("--mode", choices=["ontology", "baseline"], default="ontology")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if not args.question:
        ap.error("question required")
    try:
        result = ask(args.question, mode=args.mode)
    except LLMError as e:
        print(f"LLM error: {e}", file=sys.stderr)
        sys.exit(1)
    if args.json:
        out = {k: result[k] for k in ("question", "mode", "sql", "error", "retrieval")}
        out["n_rows"] = len(result["rows"])
        out["rows_preview"] = result["rows"][:5]
        print(json.dumps(out, indent=2, default=str))
    else:
        if result.get("retrieval"):
            print("RETRIEVAL:", json.dumps(result["retrieval"], indent=2))
        print("SQL:\n", result["sql"])
        if result["error"]:
            print("ERROR:", result["error"])
        else:
            print(f"ROWS ({len(result['rows'])}):")
            for r in result["rows"][:10]:
                print(" ", r)

if __name__ == "__main__":
    main()
