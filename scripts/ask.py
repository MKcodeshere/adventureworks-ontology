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

def tokenize(text: str) -> set[str]:
    raw = re.findall(r"[a-z0-9_]+", (text or "").lower())
    out = set()
    for t in raw:
        out.add(t)
        out.add(stem_token(t))
    return out

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
    return _blob_tokens(
        r.get("name", ""),
        r.get("description", ""),
        r.get("sql_hint", ""),
        " ".join(r.get("synonyms") or []),
    )

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

def _overlap_score(a: set[str], b: set[str]) -> int:
    # ignore ultra-common glue tokens
    stop = {"a", "an", "the", "of", "and", "or", "to", "in", "for", "by", "on", "is", "are", "with", "from", "as"}
    return len((a - stop) & (b - stop))

def _expand_question_tokens(ont: dict, qtok: set[str]) -> set[str]:
    """Expand question tokens via ontology synonyms_index only (generic)."""
    expanded = set(qtok)
    syn = ont.get("synonyms_index") or {}
    for k, vals in syn.items():
        keys = tokenize(k)
        val_toks = set()
        for v in vals or []:
            val_toks |= tokenize(str(v))
        if (keys | val_toks) & qtok:
            expanded |= keys | val_toks
    return expanded

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
    """Generic ontology retrieval: token overlap + synonym expansion + multi-hop joins.

    No question-tuned keyword triggers. Matching uses only ontology content
    (names, descriptions, synonyms, synonyms_index, value_meanings text).
    """
    qtok = _expand_question_tokens(ont, tokenize(question))

    # --- score entities ---
    scored_ents = []
    for e in ont.get("entities") or []:
        score = _overlap_score(qtok, _entity_tokens(e))
        if score > 0:
            scored_ents.append((score, e))
    scored_ents.sort(key=lambda x: (-x[0], x[1].get("name", "")))

    if scored_ents:
        # keep every positive-overlap entity, ranked, capped
        ents = [e for s, e in scored_ents][:10]
    else:
        # light generic fallback: top-k by overlap even if 0... re-score raw name tokens only
        # If still empty, take top-3 entities whose name stem appears as substring of question
        soft = []
        ql = question.lower()
        for e in ont.get("entities") or []:
            name = e.get("name", "")
            st = stem_token(name.lower().replace(" ", ""))
            # token overlap on name alone
            sc = _overlap_score(qtok, tokenize(name))
            if sc == 0 and name and name.lower() in ql:
                sc = 1
            soft.append((sc, e))
        soft.sort(key=lambda x: (-x[0], x[1].get("name", "")))
        ents = [e for s, e in soft if s > 0][:5]
        if not ents:
            # last resort: top-3 entities by name length-agnostic token presence in synonyms_index hits only
            # If still nothing, pick 3 most central by relationship degree (generic, not question-tuned)
            adj, _ = _build_entity_graph(ont)
            degree = sorted(((len(adj.get(e.get("name"), [])), e) for e in ont.get("entities") or []), reverse=True)
            ents = [e for _, e in degree[:3]]

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

    # rules / metrics via ontology text overlap only
    rules = []
    for r in ont.get("rules") or []:
        if _overlap_score(qtok, _rule_tokens(r)) > 0:
            rules.append(r)

    metrics = []
    for m in ont.get("metrics") or []:
        if _overlap_score(qtok, _metric_tokens(m)) > 0:
            metrics.append(m)
    metrics = metrics[:8]

    # value meanings: attached to selected tables/columns OR text overlap
    vals = []
    for v in ont.get("value_meanings") or []:
        col = v.get("column") or ""
        attached = any(t and t in col for t in ent_tables if t)
        if attached or _overlap_score(qtok, _value_tokens(v)) > 0:
            vals.append(v)

    retrieval = {
        "question_tokens": sorted(qtok),
        "seed_entities": sorted(seed_names),
        "entities": [e["name"] for e in final_ents],
        "bridge_entities": sorted(expanded_names - seed_names),
        "rules": [r.get("name") for r in rules],
        "metrics": [m.get("name") for m in metrics],
        "value_meanings_columns": [v.get("column") for v in vals],
        "relationships": [r.get("name") for r in rels],
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

def run_sql(sql: str):
    conn = psycopg2.connect(DSN)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql)
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()

def ask(question: str, mode: str = "ontology") -> dict:
    ont = load_ontology()
    retrieval = None
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
    else:
        tmpl = (ROOT / "prompts" / "ask_sql_baseline.md").read_text()
        prompt = tmpl.replace("{{question}}", question).replace(
            "{{schema_hints}}", schema_hints(None, limit_tables=20)
        )
    raw = complete(prompt, system="You are a careful Postgres SQL generator.", temperature=0.0)
    sql = extract_sql(raw)
    try:
        rows = run_sql(sql)
        err = None
    except Exception as e:
        rows, err = [], str(e)
    return {
        "question": question,
        "mode": mode,
        "sql": sql,
        "rows": rows,
        "error": err,
        "raw": raw,
        "retrieval": retrieval,
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
