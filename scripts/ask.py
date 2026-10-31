#!/usr/bin/env python3
"""Ask a question -> ontology slice (or schema-only) -> LLM SQL -> execute."""
from __future__ import annotations
import argparse, json, os, re, sys
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
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

load_dotenv()
DSN = os.environ.get("DATABASE_URL", "host=127.0.0.1 port=5433 dbname=Adventureworks user=postgres")

def load_ontology():
    return yaml.safe_load((ROOT / "ontology" / "ontology.yaml").read_text())

def tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9_]+", text.lower()))

def slice_ontology(ont: dict, question: str) -> dict:
    qtok = tokenize(question)
    # expand with synonym index
    syn = ont.get("synonyms_index") or {}
    for k, vals in syn.items():
        if tokenize(k) & qtok or any(tokenize(v) & qtok for v in vals):
            qtok |= tokenize(k)
            for v in vals:
                qtok |= tokenize(v)

    ents, rels, rules, metrics, vals = [], [], [], [], []
    for e in ont.get("entities") or []:
        blob = " ".join([
            e.get("name", ""), e.get("description", ""), e.get("table", ""),
            " ".join(e.get("synonyms") or []),
            " ".join(a.get("name", "") for a in e.get("attributes") or []),
        ]).lower()
        if tokenize(blob) & qtok or e.get("name", "").lower() in question.lower():
            ents.append(e)

    ent_names = {e["name"] for e in ents}
    ent_tables = {e.get("table") for e in ents}

    for r in ont.get("relationships") or []:
        if r.get("from") in ent_names or r.get("to") in ent_names:
            rels.append(r)

    for r in ont.get("rules") or []:
        blob = (r.get("name", "") + " " + r.get("description", "")).lower()
        if tokenize(blob) & qtok:
            rules.append(r)
    # always include fiscal/online/finished if keywords present
    for r in ont.get("rules") or []:
        if r in rules:
            continue
        n = r.get("name", "")
        if "fiscal" in qtok and "fiscal" in n:
            rules.append(r)
        if ({"internet", "online", "reseller", "channel"} & qtok) and "internet" in n:
            rules.append(r)
        if ({"mountain", "road", "touring", "finished"} & qtok) and n in {
            "finished_goods_only", "store_specialty"
        }:
            rules.append(r)
        if ({"rated", "review", "rating"} & qtok) and "rated" in n:
            rules.append(r)

    for m in ont.get("metrics") or []:
        blob = (m.get("name", "") + " " + m.get("description", "")).lower()
        if tokenize(blob) & qtok or {"sales", "revenue", "amount", "aov"} & qtok:
            if {"sales", "revenue", "amount", "aov", "subtotal"} & qtok:
                metrics.append(m)
            elif tokenize(blob) & qtok:
                metrics.append(m)

    for v in ont.get("value_meanings") or []:
        col = v.get("column", "")
        if any(t and t in col for t in ent_tables if t):
            vals.append(v)
        else:
            blob = json.dumps(v).lower()
            if tokenize(blob) & qtok:
                vals.append(v)

    # fallback: if nothing matched, include core sales entities
    if not ents:
        for e in ont.get("entities") or []:
            if e["name"] in {"SalesOrder", "SalesOrderLine", "Product", "Customer"}:
                ents.append(e)

    return {
        "entities": ents,
        "relationships": rels,
        "rules": rules,
        "metrics": metrics[:5],
        "value_meanings": vals,
    }

def schema_hints(tables: set[str] | None, limit_tables: int = 12) -> str:
    profile = json.loads((ROOT / "artifacts" / "schema_profile.json").read_text())
    lines = []
    names = list(tables) if tables else list(profile["tables"].keys())[:limit_tables]
    if not tables:
        names = sorted(profile["tables"].keys())[:limit_tables]
    for t in names:
        info = profile["tables"].get(t) or profile["tables"].get(t.split(".")[-1])
        if not info:
            # try bare name
            bare = t.split(".")[-1]
            info = profile["tables"].get(bare)
        if not info:
            continue
        cols = ", ".join(
            f"{c['column_name']}:{c['data_type']}" for c in info["columns"][:20]
        )
        lines.append(f"wh.{t.split('.')[-1]} ({info['row_count']} rows): {cols}")
    joins = profile.get("inferred_joins") or []
    jlines = [
        f"wh.{j['from_table']}.{j['from_col']} = wh.{j['to_table']}.{j['to_col']}"
        for j in joins
        if not tables or j["from_table"] in {x.split('.')[-1] for x in tables}
        or j["to_table"] in {x.split('.')[-1] for x in tables}
    ]
    return "\n".join(lines) + ("\nJOINS:\n" + "\n".join(jlines[:20]) if jlines else "")

def extract_sql(text: str) -> str:
    m = re.search(r"```sql\s*(.*?)```", text, re.I | re.S)
    if m:
        return m.group(1).strip().rstrip(";")
    m = re.search(r"```\s*(SELECT.*)```", text, re.I | re.S)
    if m:
        return m.group(1).strip().rstrip(";")
    # raw select
    m = re.search(r"(SELECT\b.*)", text, re.I | re.S)
    if m:
        return m.group(1).strip().rstrip(";")
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
    if mode == "ontology":
        sl = slice_ontology(ont, question)
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
    raw = complete(prompt, system="You are a careful Postgres SQL generator.")
    sql = extract_sql(raw)
    try:
        rows = run_sql(sql)
        err = None
    except Exception as e:
        rows, err = [], str(e)
    return {"question": question, "mode": mode, "sql": sql, "rows": rows, "error": err, "raw": raw}

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
        # compact
        out = {k: result[k] for k in ("question", "mode", "sql", "error")}
        out["n_rows"] = len(result["rows"])
        out["rows_preview"] = result["rows"][:5]
        print(json.dumps(out, indent=2, default=str))
    else:
        print("SQL:\n", result["sql"])
        if result["error"]:
            print("ERROR:", result["error"])
        else:
            print(f"ROWS ({len(result['rows'])}):")
            for r in result["rows"][:10]:
                print(" ", r)

if __name__ == "__main__":
    main()
