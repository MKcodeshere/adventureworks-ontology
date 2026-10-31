#!/usr/bin/env python3
"""Run all eval questions in baseline vs ontology modes. Write report + charts.

Charts are only produced from a real run. Never writes placeholder numbers.
"""
from __future__ import annotations
from decimal import Decimal, ROUND_HALF_UP
import argparse, json, os, sys, re
from collections import defaultdict
from pathlib import Path

import yaml
import psycopg2
from psycopg2.extras import RealDictCursor

ROOT = Path(__file__).resolve().parents[1]

# Preferred chart/report order. Size labels only when verified.
MODEL_ORDER = ["gemini-2.5-flash", "gpt-oss:120b", "nemotron-3-super"]
MODEL_DISPLAY = {
    # gpt-oss size is in the model id; nemotron-3-super = 120B MoE / 12B active
    # per https://ollama.com/library/nemotron-3-super. Gemini: no public size.
    "nemotron-3-super": "nemotron-3-super (120B)",
}
sys.path.insert(0, str(ROOT / "scripts"))
from ask import ask, extract_sql, run_sql, DSN  # noqa: E402
from llm import LLMError  # noqa: E402

def norm_val(v):
    """Normalize a cell for denotation comparison."""
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)) or isinstance(v, Decimal):
        d = Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return float(d)
    if hasattr(v, "isoformat"):
        return v.isoformat()
    s = str(v).strip()
    try:
        d = Decimal(s).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return float(d)
    except Exception:
        return s.lower()

def _cell_sort_key(v):
    """Total order over mixed None/num/str cells for order-insensitive row compare."""
    if v is None:
        return (0, "")
    if isinstance(v, bool):
        return (1, int(v))
    if isinstance(v, (int, float)):
        return (2, float(v))
    return (3, str(v))

def norm_rows(rows):
    """Bag of rows as sorted value-tuples, ignoring column names and column order.

    Text-to-SQL denotation accuracy (Spider/BIRD style): two results match when
    they contain the same multiset of rows under value equality. Column aliases
    and select-list order must not affect the score. Within each row, values are
    sorted so that SELECT a,b and SELECT b,a still match when values align.
    Numerics are rounded to 2 decimals; strings are stripped/lowercased.
    Mixed-type rows use a typed sort key (None < bool < number < string).
    """
    out = []
    for r in rows:
        vals = tuple(sorted((norm_val(v) for v in dict(r).values()), key=_cell_sort_key))
        out.append(vals)
    return sorted(out, key=lambda row: tuple(_cell_sort_key(c) for c in row))

def _row_value_counter(row):
    from collections import Counter
    return Counter(norm_val(v) for v in dict(row).values())

def _projection_match(pred, gold) -> bool:
    """Each pred row values are a multiset-subset of a unique gold row."""
    if len(pred) != len(gold):
        return False
    gold_rows = [_row_value_counter(r) for r in gold]
    used = [False] * len(gold_rows)
    for pr in pred:
        pc = _row_value_counter(pr)
        found = False
        for i, gc in enumerate(gold_rows):
            if used[i]:
                continue
            if all(pc[k] <= gc[k] for k in pc):
                used[i] = True
                found = True
                break
        if not found:
            return False
    return True

def _numeric_bag_match(pred, gold) -> bool:
    """Same row count and numeric multiset; ignores string labels."""
    if len(pred) != len(gold):
        return False
    def nums(rows):
        out = []
        for r in rows:
            for v in dict(r).values():
                nv = norm_val(v)
                if isinstance(nv, (int, float)) and not isinstance(nv, bool):
                    out.append(nv)
        return sorted(out)
    return nums(pred) == nums(gold)

def results_match(pred, gold) -> bool:
    if norm_rows(pred) == norm_rows(gold):
        return True
    if _projection_match(pred, gold):
        return True
    if _numeric_bag_match(pred, gold):
        return True
    return False

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
            rec["retrieval"] = out.get("retrieval")
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

def current_model_label() -> str:
    provider = os.environ.get("LLM_PROVIDER", "ollama").lower()
    if provider == "gemini":
        return os.environ.get("GEMINI_MODEL", "gemini")
    if provider == "openai":
        return os.environ.get("OPENAI_MODEL", "openai")
    if provider == "anthropic":
        return os.environ.get("ANTHROPIC_MODEL", "anthropic")
    return os.environ.get("OLLAMA_MODEL", "ollama")

def model_slug(label: str) -> str:
    return label.replace("/", "-").replace(":", "-").replace(" ", "-")

def write_report(all_rows, path: Path, model: str | None = None):
    """Single-model detailed report (also used per run folder)."""
    model = model or current_model_label()
    by_mode = defaultdict(list)
    for r in all_rows:
        by_mode[r["mode"]].append(r)
    lines = [f"# Evaluation report — `{model}`\n"]
    lines.append(f"Provider: `{os.environ.get('LLM_PROVIDER', 'ollama')}`")
    lines.append(f"Model: `{model}`")
    lines.append("Temperature: `0`\n")
    lines.append("## Retrieval method\n")
    lines.append(
        "Ontology mode uses **v2 IDF-weighted** retrieval: entity scores weight "
        "name/synonym hits highest, attribute names medium, description lowest; "
        "corpus IDF down-weights generic tokens; synonym expansion only on full "
        "phrases or strong tokens. Top seeds by relative score (≥40% of best, "
        "max 5), then multi-hop paths ≤3 hops for bridges. No question-tuned "
        "keyword triggers. Baseline mode gets schema profile only.\n"
    )
    lines.append("Result matching rules: `eval/COMPARISON.md`.\n")
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
    lines.append("- `eval/charts/overall_accuracy.png` (latest run)")
    lines.append("- `eval/charts/accuracy_by_difficulty.png`")
    lines.append("- `eval/charts/accuracy_by_tag.png`")
    lines.append("- `eval/charts/model_comparison.png`")
    lines.append("- `eval/charts/model_comparison_by_tag.png`")
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
    lines.append("\n## Retrieval log (ontology mode)\n")
    lines.append("| ID | Seed entities | Bridge | Rules | Metrics |")
    lines.append("|----|---------------|--------|-------|---------|")
    for qid in ids:
        o = omap[qid]
        ret = o.get("retrieval") or {}
        seeds = ", ".join(ret.get("seed_entities") or []) or "-"
        bridge = ", ".join(ret.get("bridge_entities") or []) or "-"
        rules = ", ".join(ret.get("rules") or []) or "-"
        metrics = ", ".join(ret.get("metrics") or []) or "-"
        lines.append(f"| {qid} | {seeds} | {bridge} | {rules} | {metrics} |")
    path.write_text("\n".join(lines) + "\n")
    print(f"Wrote {path}")

def _load_run_dir(d: Path) -> tuple[str, list, dict] | None:
    lr = d / "last_run.json"
    if not lr.exists():
        return None
    rows = json.loads(lr.read_text())
    meta = {}
    if (d / "meta.json").exists():
        meta = json.loads((d / "meta.json").read_text())
    label = meta.get("model") or d.name.split("_", 1)[-1]
    return label, rows, meta


def load_v1_model_runs() -> dict[str, list]:
    """Backward-compatible: v1 archives only."""
    return load_report_runs(prefer_v2=False)


def load_report_runs(prefer_v2: bool = True) -> dict[str, list]:
    """Load runs for the aggregate report.

    When prefer_v2=True (default): use v2_* for models that have it (current
    retrieval), keep gemini from v1 and label it as v1-only.
    """
    runs_dir = ROOT / "eval" / "runs"
    if not runs_dir.exists():
        return {}
    v1, v2 = {}, {}
    for d in sorted(runs_dir.iterdir()):
        if not d.is_dir():
            continue
        if d.name.startswith("v1_"):
            got = _load_run_dir(d)
            if got:
                v1[got[0]] = (got[1], got[2], d.name)
        elif d.name.startswith("v2_"):
            got = _load_run_dir(d)
            if got:
                v2[got[0]] = (got[1], got[2], d.name)

    ordered = {}
    # Gemini: always v1 when present (credits exhausted — not rerun on v2)
    if "gemini-2.5-flash" in v1:
        ordered["gemini-2.5-flash (v1 retrieval)"] = v1["gemini-2.5-flash"][0]
    for key in MODEL_ORDER:
        if key == "gemini-2.5-flash":
            continue
        if prefer_v2 and key in v2:
            disp = MODEL_DISPLAY.get(key, key) + " (v2 retrieval)"
            ordered[disp] = v2[key][0]
        elif key in v1:
            disp = MODEL_DISPLAY.get(key, key) + " (v1 retrieval)"
            ordered[disp] = v1[key][0]
    return ordered

def write_model_comparison_charts(model_runs: dict[str, list], out_dir: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    out_dir.mkdir(parents=True, exist_ok=True)
    models = list(model_runs.keys())
    if not models:
        return

    # Overall baseline vs ontology per model
    x = np.arange(len(models))
    w = 0.35
    bvals, ovals = [], []
    for m in models:
        by = defaultdict(list)
        for r in model_runs[m]:
            by[r["mode"]].append(r)
        bvals.append(accuracy(by["baseline"]) * 100)
        ovals.append(accuracy(by["ontology"]) * 100)
    fig, ax = plt.subplots(figsize=(max(6, 2.2 * len(models)), 4.5))
    ax.bar(x - w / 2, bvals, w, label="baseline", color="#c0392b")
    ax.bar(x + w / 2, ovals, w, label="ontology", color="#27ae60")
    ax.set_xticks(x)
    ax.set_xticklabels(models, rotation=15, ha="right")
    ax.set_ylim(0, 100)
    ax.set_ylabel("Accuracy %")
    ax.set_title("Model comparison — overall accuracy")
    ax.legend()
    for i, (b, o) in enumerate(zip(bvals, ovals)):
        ax.text(i - w / 2, b + 1, f"{b:.0f}", ha="center", fontsize=8)
        ax.text(i + w / 2, o + 1, f"{o:.0f}", ha="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "model_comparison.png", dpi=120)
    plt.close(fig)

    # By tag: for each tag, grouped bars per model (baseline+ontology)
    tags = ["structured", "needs-docs", "both"]
    # layout: x positions for each (model, tag) cluster — simpler: one subplot per tag
    fig, axes = plt.subplots(1, 3, figsize=(12, 4), sharey=True)
    for ax, tag in zip(axes, tags):
        bb, oo = [], []
        for m in models:
            by = defaultdict(list)
            for r in model_runs[m]:
                by[r["mode"]].append(r)
            bb.append(accuracy([r for r in by["baseline"] if r["tag"] == tag]) * 100)
            oo.append(accuracy([r for r in by["ontology"] if r["tag"] == tag]) * 100)
        x = np.arange(len(models))
        ax.bar(x - w / 2, bb, w, label="baseline", color="#c0392b")
        ax.bar(x + w / 2, oo, w, label="ontology", color="#27ae60")
        ax.set_xticks(x)
        ax.set_xticklabels(models, rotation=20, ha="right", fontsize=8)
        ax.set_ylim(0, 100)
        ax.set_title(tag)
        if tag == "structured":
            ax.set_ylabel("Accuracy %")
            ax.legend(fontsize=8)
    fig.suptitle("Model comparison — accuracy by tag")
    fig.tight_layout()
    fig.savefig(out_dir / "model_comparison_by_tag.png", dpi=120)
    plt.close(fig)
    print(f"Model comparison charts written to {out_dir}")

def write_aggregate_report(model_runs: dict[str, list], path: Path):
    lines = ["# Evaluation report (multi-model)\n"]
    lines.append("Temperature: `0`. Current app retrieval is **v2 IDF-weighted**. "
                 "Gemini kept at **v1** (credits exhausted, not rerun). "
                 "Comparator: `eval/COMPARISON.md`.\n")
    lines.append("## Models\n")
    lines.append(
        "Parameter sizes labelled only when verified: `gpt-oss:120b` (120B); "
        "`nemotron-3-super` is 120B total / 12B active MoE per "
        "[ollama.com/library/nemotron-3-super]"
        "(https://ollama.com/library/nemotron-3-super). "
        "Gemini has no public parameter count.\n"
    )
    lines.append("| Model | Baseline | Ontology | Delta |")
    lines.append("|-------|----------|----------|-------|")
    for model, rows in model_runs.items():
        by = defaultdict(list)
        for r in rows:
            by[r["mode"]].append(r)
        b = accuracy(by["baseline"]) * 100
        o = accuracy(by["ontology"]) * 100
        lines.append(f"| `{model}` | {b:.1f}% | {o:.1f}% | {o-b:+.1f} pp |")

    for model, rows in model_runs.items():
        by = defaultdict(list)
        for r in rows:
            by[r["mode"]].append(r)
        lines.append(f"\n## `{model}`\n")
        lines.append("### Overall\n")
        lines.append("| Mode | Accuracy | Correct | Total |")
        lines.append("|------|----------|---------|-------|")
        for m in ("baseline", "ontology"):
            rs = by[m]
            lines.append(
                f"| {m} | {accuracy(rs)*100:.1f}% | {sum(1 for r in rs if r['correct'])} | {len(rs)} |"
            )
        lines.append("\n### By difficulty\n")
        lines.append("| Difficulty | Baseline | Ontology |")
        lines.append("|------------|----------|----------|")
        for d in ("simple", "medium", "complex"):
            b = accuracy([r for r in by["baseline"] if r["difficulty"] == d]) * 100
            o = accuracy([r for r in by["ontology"] if r["difficulty"] == d]) * 100
            lines.append(f"| {d} | {b:.1f}% | {o:.1f}% |")
        lines.append("\n### By tag\n")
        lines.append("| Tag | Baseline | Ontology |")
        lines.append("|-----|----------|----------|")
        for t in ("structured", "needs-docs", "both"):
            b = accuracy([r for r in by["baseline"] if r["tag"] == t]) * 100
            o = accuracy([r for r in by["ontology"] if r["tag"] == t]) * 100
            lines.append(f"| {t} | {b:.1f}% | {o:.1f}% |")

    lines.append("\n## Charts\n")
    lines.append("- `eval/charts/model_comparison.png`")
    lines.append("- `eval/charts/model_comparison_by_tag.png`")
    lines.append(
        "- Default single-model charts (`overall_accuracy.png`, "
        "`accuracy_by_difficulty.png`, `accuracy_by_tag.png`) are from "
        "`gemini-2.5-flash` (kept as the primary reference)."
    )
    lines.append("- Per-model charts under `eval/runs/v2_<model>/charts/` (and v1_*)")
    lines.append("\n## Run archives\n")
    lines.append("- `eval/runs/v1_gemini-2.5-flash/` — v1 retrieval only")
    lines.append("- `eval/runs/v1_*` — original v1 Ollama/Gemini archives (kept)")
    lines.append("- `eval/runs/v2_*` — v2 IDF retrieval (current app)")
    path.write_text("\n".join(lines) + "\n")
    print(f"Wrote aggregate {path}")

def archive_run(all_rows, model: str, version: str = "v2"):
    slug = model_slug(model)
    run_dir = ROOT / "eval" / "runs" / f"{version}_{slug}"
    charts = run_dir / "charts"
    charts.mkdir(parents=True, exist_ok=True)
    retrieval_tag = "v2_idf" if version == "v2" else "v1_generic"
    (run_dir / "last_run.json").write_text(json.dumps(all_rows, indent=2, default=str))
    (run_dir / "meta.json").write_text(json.dumps({
        "model": model,
        "provider": os.environ.get("LLM_PROVIDER"),
        "temperature": 0,
        "retrieval": retrieval_tag,
        "version": version,
    }, indent=2))
    write_report(all_rows, run_dir / "report.md", model=model)
    write_charts(all_rows, charts)
    (run_dir / "README.md").write_text(
        f"# {version} run — {model}\n\nTemperature 0. Retrieval={retrieval_tag}. "
        f"See report.md and charts/.\n"
    )
    return run_dir

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="Optional cap for smoke tests")
    ap.add_argument("--mode", choices=["both", "baseline", "ontology"], default="both")
    ap.add_argument("--rebuild-aggregate", action="store_true",
                    help="Only rebuild multi-model report/charts from archived runs")
    ap.add_argument("--version", choices=["v1", "v2"], default="v2",
                    help="Archive folder prefix (default v2)")
    args = ap.parse_args()

    if args.rebuild_aggregate:
        model_runs = load_report_runs(prefer_v2=True)
        write_aggregate_report(model_runs, ROOT / "eval" / "report.md")
        write_model_comparison_charts(model_runs, ROOT / "eval" / "charts")
        gem_charts = ROOT / "eval" / "runs" / "v1_gemini-2.5-flash" / "charts"
        if gem_charts.exists():
            import shutil
            for name in ("overall_accuracy.png", "accuracy_by_difficulty.png",
                         "accuracy_by_tag.png"):
                src = gem_charts / name
                if src.exists():
                    shutil.copy2(src, ROOT / "eval" / "charts" / name)
        return

    qs = yaml.safe_load((ROOT / "eval" / "questions.yaml").read_text())["questions"]
    if args.limit:
        qs = qs[: args.limit]
    all_rows = []
    modes = ["baseline", "ontology"] if args.mode == "both" else [args.mode]
    for m in modes:
        all_rows.extend(run_mode(qs, m))
    (ROOT / "eval" / "last_run.json").write_text(json.dumps(all_rows, indent=2, default=str))
    model = current_model_label()
    if args.mode == "both" or len(modes) == 2:
        write_report(all_rows, ROOT / "eval" / "report.md", model=model)
        write_charts(all_rows, ROOT / "eval" / "charts")
        archive_run(all_rows, model, version=args.version)
        model_runs = load_report_runs(prefer_v2=True)
        write_aggregate_report(model_runs, ROOT / "eval" / "report.md")
        write_model_comparison_charts(model_runs, ROOT / "eval" / "charts")
        # Keep default single-model charts as Gemini reference when present.
        gem_charts = ROOT / "eval" / "runs" / "v1_gemini-2.5-flash" / "charts"
        if gem_charts.exists():
            import shutil
            for name in ("overall_accuracy.png", "accuracy_by_difficulty.png",
                         "accuracy_by_tag.png"):
                src = gem_charts / name
                if src.exists():
                    shutil.copy2(src, ROOT / "eval" / "charts" / name)
    else:
        print("Single-mode run: report/charts need both modes. Saved eval/last_run.json only.")

if __name__ == "__main__":
    main()
