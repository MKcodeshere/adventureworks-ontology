#!/usr/bin/env python3
"""Run all eval questions in baseline vs ontology modes. Write report + charts.

Charts are only produced from a real run. Never writes placeholder numbers.
"""
from __future__ import annotations
import argparse, json, os, sys, re
from collections import defaultdict
from pathlib import Path

import yaml
import psycopg2
from psycopg2.extras import RealDictCursor

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from ask import ask, extract_sql, run_sql, DSN  # noqa: E402
from llm import LLMError  # noqa: E402

def norm_val(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return round(float(v), 2)
    if hasattr(v, "isoformat"):
        return v.isoformat()
    s = str(v).strip()
    try:
        return round(float(s), 2)
    except Exception:
        return s.lower()

def norm_rows(rows):
    out = []
    for r in rows:
        items = tuple(sorted((k.lower(), norm_val(v)) for k, v in dict(r).items()))
        out.append(items)
    return sorted(out)

def results_match(pred, gold) -> bool:
    return norm_rows(pred) == norm_rows(gold)

def load_gold(qid: str):
    p = ROOT / "eval" / "gold_results" / f"{qid}.json"
    data = json.loads(p.read_text())
    return data["rows"]

def run_mode(questions, mode: str):
    results = []
    for q in questions:
        rec = {
            "id": q["id"],
            "difficulty": q["difficulty"],
            "tag": q["tag"],
            "question": q["question"],
            "mode": mode,
            "correct": False,
            "exec_ok": False,
            "sql": None,
            "error": None,
        }
        try:
            out = ask(q["question"], mode=mode)
            rec["sql"] = out["sql"]
            rec["error"] = out["error"]
            rec["exec_ok"] = out["error"] is None
            if out["error"] is None:
                gold = load_gold(q["id"])
                rec["correct"] = results_match(out["rows"], gold)
        except Exception as e:
            rec["error"] = str(e)
        results.append(rec)
        mark = "OK" if rec["correct"] else "MISS"
        print(f"[{mode}] {q['id']} {mark} exec={rec['exec_ok']} {rec['error'] or ''}")
    return results

def accuracy(rows):
    if not rows:
        return 0.0
    return sum(1 for r in rows if r["correct"]) / len(rows)

def write_charts(all_rows, out_dir: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_dir.mkdir(parents=True, exist_ok=True)
    by_mode = defaultdict(list)
    for r in all_rows:
        by_mode[r["mode"]].append(r)

    # 1) overall
    modes = ["baseline", "ontology"]
    vals = [accuracy(by_mode[m]) * 100 for m in modes]
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.bar(modes, vals, color=["#c0392b", "#27ae60"])
    ax.set_ylim(0, 100)
    ax.set_ylabel("Accuracy %")
    ax.set_title("Overall accuracy: baseline vs ontology")
    for i, v in enumerate(vals):
        ax.text(i, v + 1, f"{v:.1f}%", ha="center")
    fig.tight_layout()
    fig.savefig(out_dir / "overall_accuracy.png", dpi=120)
    plt.close(fig)

    # 2) by difficulty
    diffs = ["simple", "medium", "complex"]
    fig, ax = plt.subplots(figsize=(7, 4))
    import numpy as np
    x = np.arange(len(diffs))
    w = 0.35
    bvals = [accuracy([r for r in by_mode["baseline"] if r["difficulty"] == d]) * 100 for d in diffs]
    ovals = [accuracy([r for r in by_mode["ontology"] if r["difficulty"] == d]) * 100 for d in diffs]
    ax.bar(x - w / 2, bvals, w, label="baseline", color="#c0392b")
    ax.bar(x + w / 2, ovals, w, label="ontology", color="#27ae60")
    ax.set_xticks(x)
    ax.set_xticklabels(diffs)
    ax.set_ylim(0, 100)
    ax.set_ylabel("Accuracy %")
    ax.set_title("Accuracy by difficulty")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "accuracy_by_difficulty.png", dpi=120)
    plt.close(fig)

    # 3) by tag
    tags = ["structured", "needs-docs", "both"]
    fig, ax = plt.subplots(figsize=(7, 4))
    x = np.arange(len(tags))
    bvals = [accuracy([r for r in by_mode["baseline"] if r["tag"] == t]) * 100 for t in tags]
    ovals = [accuracy([r for r in by_mode["ontology"] if r["tag"] == t]) * 100 for t in tags]
    ax.bar(x - w / 2, bvals, w, label="baseline", color="#c0392b")
    ax.bar(x + w / 2, ovals, w, label="ontology", color="#27ae60")
    ax.set_xticks(x)
    ax.set_xticklabels(tags)
    ax.set_ylim(0, 100)
    ax.set_ylabel("Accuracy %")
    ax.set_title("Accuracy by question tag")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "accuracy_by_tag.png", dpi=120)
    plt.close(fig)
    print(f"Charts written to {out_dir}")

def write_report(all_rows, path: Path):
    by_mode = defaultdict(list)
    for r in all_rows:
        by_mode[r["mode"]].append(r)
    lines = ["# Evaluation report\n"]
    lines.append(f"Provider: `{os.environ.get('LLM_PROVIDER', 'ollama')}`\n")
    lines.append("## Overall\n")
    lines.append("| Mode | Accuracy | Correct | Total |")
    lines.append("|------|----------|---------|-------|")
    for m in ("baseline", "ontology"):
        rows = by_mode[m]
        lines.append(
            f"| {m} | {accuracy(rows)*100:.1f}% | {sum(1 for r in rows if r['correct'])} | {len(rows)} |"
        )
    lines.append("\n## By difficulty\n")
    lines.append("| Difficulty | Baseline | Ontology |")
    lines.append("|------------|----------|----------|")
    for d in ("simple", "medium", "complex"):
        b = accuracy([r for r in by_mode["baseline"] if r["difficulty"] == d]) * 100
        o = accuracy([r for r in by_mode["ontology"] if r["difficulty"] == d]) * 100
        lines.append(f"| {d} | {b:.1f}% | {o:.1f}% |")
    lines.append("\n## By tag\n")
    lines.append("| Tag | Baseline | Ontology |")
    lines.append("|-----|----------|----------|")
    for t in ("structured", "needs-docs", "both"):
        b = accuracy([r for r in by_mode["baseline"] if r["tag"] == t]) * 100
        o = accuracy([r for r in by_mode["ontology"] if r["tag"] == t]) * 100
        lines.append(f"| {t} | {b:.1f}% | {o:.1f}% |")
    lines.append("\n## Charts\n")
    lines.append("- `eval/charts/overall_accuracy.png`")
    lines.append("- `eval/charts/accuracy_by_difficulty.png`")
    lines.append("- `eval/charts/accuracy_by_tag.png`")
    lines.append("\n## Per-question\n")
    lines.append("| ID | Diff | Tag | Baseline | Ontology |")
    lines.append("|----|------|-----|----------|----------|")
    ids = [r["id"] for r in by_mode["ontology"]]
    bmap = {r["id"]: r for r in by_mode["baseline"]}
    omap = {r["id"]: r for r in by_mode["ontology"]}
    for qid in ids:
        b, o = bmap[qid], omap[qid]
        lines.append(
            f"| {qid} | {o['difficulty']} | {o['tag']} | "
            f"{'Y' if b['correct'] else 'N'} | {'Y' if o['correct'] else 'N'} |"
        )
    path.write_text("\n".join(lines) + "\n")
    print(f"Wrote {path}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="Optional cap for smoke tests")
    ap.add_argument("--mode", choices=["both", "baseline", "ontology"], default="both")
    args = ap.parse_args()
    qs = yaml.safe_load((ROOT / "eval" / "questions.yaml").read_text())["questions"]
    if args.limit:
        qs = qs[: args.limit]
    all_rows = []
    modes = ["baseline", "ontology"] if args.mode == "both" else [args.mode]
    for m in modes:
        all_rows.extend(run_mode(qs, m))
    (ROOT / "eval" / "last_run.json").write_text(json.dumps(all_rows, indent=2, default=str))
    if args.mode == "both" or len(modes) == 2:
        write_report(all_rows, ROOT / "eval" / "report.md")
        write_charts(all_rows, ROOT / "eval" / "charts")
    else:
        print("Single-mode run: report/charts need both modes. Saved eval/last_run.json only.")

if __name__ == "__main__":
    main()
