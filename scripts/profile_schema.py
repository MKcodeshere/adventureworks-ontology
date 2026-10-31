#!/usr/bin/env python3
"""Profile the scrambled wh schema into artifacts/schema_profile.json."""
from __future__ import annotations
import json, os, sys
from pathlib import Path

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("pip install psycopg2-binary", file=sys.stderr)
    raise

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "schema_profile.json"

DSN = os.environ.get(
    "DATABASE_URL",
    "host=127.0.0.1 port=5433 dbname=Adventureworks user=postgres",
)

def main():
    conn = psycopg2.connect(DSN)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT table_name FROM information_schema.views
        WHERE table_schema='wh' ORDER BY table_name
    """)
    tables = [r["table_name"] for r in cur.fetchall()]
    profile = {"schema": "wh", "tables": {}}

    for t in tables:
        cur.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema='wh' AND table_name=%s
            ORDER BY ordinal_position
        """, (t,))
        cols = list(cur.fetchall())
        cur.execute(f'SELECT COUNT(*) AS n FROM wh."{t}"')
        nrows = cur.fetchone()["n"]
        col_stats = []
        for c in cols:
            name = c["column_name"]
            # skip xml/heavy text for sampling
            if c["data_type"] in ("xml", "bytea"):
                col_stats.append({**c, "distinct": None, "samples": None, "note": "skipped heavy type"})
                continue
            try:
                cur.execute(
                    f'SELECT COUNT(DISTINCT "{name}") AS d FROM wh."{t}"'
                )
                distinct = cur.fetchone()["d"]
                cur.execute(
                    f'SELECT DISTINCT "{name}" AS v FROM wh."{t}" '
                    f'WHERE "{name}" IS NOT NULL LIMIT 5'
                )
                samples = [str(r["v"])[:120] for r in cur.fetchall()]
            except Exception as e:
                conn.rollback()
                distinct, samples = None, [f"error:{e}"]
            col_stats.append({**dict(c), "distinct": distinct, "samples": samples})
        # crude FK inference: columns ending with _id that match other table prefixes
        profile["tables"][t] = {
            "row_count": nrows,
            "columns": col_stats,
        }

    # inferred joins from naming conventions
    joins = []
    id_owners = {}
    for t, info in profile["tables"].items():
        for c in info["columns"]:
            n = c["column_name"]
            if n.endswith("_id") or n.endswith("_cd"):
                id_owners.setdefault(n, []).append(t)
    # known join hints from cryptic names
    known = [
        ("sls_ord_dtl", "ord_id", "sls_ord_hdr", "ord_id"),
        ("sls_ord_hdr", "cst_id", "cst_mstr", "cst_id"),
        ("sls_ord_hdr", "terr_id", "terr_dim", "terr_id"),
        ("sls_ord_hdr", "rep_id", "sls_rep", "rep_id"),
        ("sls_ord_dtl", "prd_id", "prd_mstr", "prd_id"),
        ("sls_ord_dtl", "ofr_id", "spec_ofr", "ofr_id"),
        ("cst_mstr", "str_id", "str_mstr", "str_id"),
        ("cst_mstr", "pers_id", "pers_mstr", "pers_id"),
        ("prd_mstr", "subcat_id", "prd_subcat", "subcat_id"),
        ("prd_subcat", "cat_id", "prd_cat", "cat_id"),
        ("prd_mstr", "mdl_id", "prd_mdl", "mdl_id"),
        ("prd_rev", "prd_id", "prd_mstr", "prd_id"),
        ("prd_mdl_desc_cult", "mdl_id", "prd_mdl", "mdl_id"),
        ("prd_mdl_desc_cult", "desc_id", "prd_desc", "desc_id"),
        ("emp_dept_hist", "emp_id", "emp_mstr", "emp_id"),
        ("emp_dept_hist", "dept_id", "dept_mstr", "dept_id"),
        ("sls_rep", "rep_id", "emp_mstr", "emp_id"),
        ("po_hdr", "vnd_id", "vnd_mstr", "vnd_id"),
        ("po_dtl", "po_id", "po_hdr", "po_id"),
        ("po_dtl", "prd_id", "prd_mstr", "prd_id"),
        ("be_addr", "addr_id", "addr_mstr", "addr_id"),
        ("addr_mstr", "st_id", "st_prov", "st_id"),
        ("st_prov", "ctry_cd", "ctry_rgn", "ctry_cd"),
        ("sls_ord_rsn", "ord_id", "sls_ord_hdr", "ord_id"),
        ("sls_ord_rsn", "rsn_id", "sls_rsn", "rsn_id"),
        ("bom", "asm_prd_id", "prd_mstr", "prd_id"),
        ("bom", "cmp_prd_id", "prd_mstr", "prd_id"),
        ("wrk_ord", "prd_id", "prd_mstr", "prd_id"),
        ("str_mstr", "rep_id", "sls_rep", "rep_id"),
    ]
    profile["inferred_joins"] = [
        {"from_table": a, "from_col": b, "to_table": c, "to_col": d} for a,b,c,d in known
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(profile, indent=2, default=str))
    print(f"Wrote {OUT} ({len(tables)} tables)")

if __name__ == "__main__":
    main()
