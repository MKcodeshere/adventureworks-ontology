#!/usr/bin/env python3
"""Call an LLM to draft ontology YAML from schema profile + docs.

The repo already ships a curated ontology/ontology.yaml. Use this script
to regenerate with your own provider (see .env.example).
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from llm import complete, LLMError  # noqa: E402

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "ontology" / "ontology.draft.yaml"))
    ap.add_argument("--max-docs-chars", type=int, default=40000)
    args = ap.parse_args()

    profile = (ROOT / "artifacts" / "schema_profile.json").read_text()
    # keep profile smaller for tokens
    if len(profile) > 60000:
        profile = profile[:60000] + "\n... truncated ..."

    docs_bits = []
    for p in sorted((ROOT / "docs").rglob("*")):
        if p.suffix.lower() not in {".md", ".json"}:
            continue
        if p.name == "SOURCES.md":
            continue
        text = p.read_text(errors="replace")
        docs_bits.append(f"### FILE {p.relative_to(ROOT)}\n{text}")
    docs = "\n\n".join(docs_bits)
    if len(docs) > args.max_docs_chars:
        docs = docs[: args.max_docs_chars] + "\n... truncated ..."

    prompt_template = (ROOT / "prompts" / "draft_ontology.md").read_text()
    prompt = (
        f"{prompt_template}\n\n"
        f"## Schema profile JSON\n```json\n{profile}\n```\n\n"
        f"## Company docs\n{docs}\n"
    )
    try:
        out = complete(prompt, system="Return valid YAML ontology only.")
    except LLMError as e:
        print(f"LLM error: {e}", file=sys.stderr)
        sys.exit(1)
    # strip fences if any
    text = out.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
    Path(args.out).write_text(text.strip() + "\n")
    print(f"Wrote {args.out}")

if __name__ == "__main__":
    main()
