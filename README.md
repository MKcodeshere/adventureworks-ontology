# adventureworks-ontology

Build an ontology for Text-to-SQL from structured tables and unstructured docs,
using AdventureWorks on Postgres.

## Why I built this

I have used AdventureWorks for almost a decade. It shows up in data engineering
demos, analytics workshops, and sample warehouses. I could query the tables.
I still did not fully understand the business concepts behind them.

Product line codes. Fiscal year starting in July. Internet versus reseller.
Finished goods versus components. Store specialty buried in survey XML.

So I built an ontology layer for it. Cryptic warehouse names on one side.
Business language and docs on the other. Then I ask questions and generate SQL
with and without that ontology, and measure the difference.

## What you get

- AdventureWorks OLTP loaded into Postgres (68 tables)
- A scrambled schema `wh` with cryptic names (the warehouse the LLM sees)
- Company docs exported from Microsoft Learn + in-database text/XML
- A curated `ontology/ontology.yaml` (entities, joins, rules, metrics, value meanings)
- 30 eval questions (simple / medium / complex) tagged structured / needs-docs / both
- Scripts to profile the schema, draft an ontology via any LLM, ask questions, and evaluate
- Charts from real eval runs (baseline vs ontology)
- Streamlit guided UI (`app/app.py`) with provenance and live SQL

## Layout

```
adventureworks-ontology/
  sql/01_create_wh_views.sql   # scrambled wh layer
  data/scramble_map.yaml       # DEBUG only, do not feed to the LLM
  docs/                        # unstructured sources (see docs/SOURCES.md)
  artifacts/schema_profile.json
  ontology/ontology.yaml
  prompts/                     # LLM prompts
  scripts/                     # profile, draft, ask, evaluate
  eval/questions.yaml          # 30 questions + gold SQL
  eval/gold_results/           # verified result sets
  eval/charts/                 # produced by evaluate.py after a real run
  docker-compose.yml
```

## Docs policy

`docs/` uses business language, not the cryptic `wh` names. That matches real
company wikis. The ontology is what maps business terms onto `wh` columns.
`data/scramble_map.yaml` is only for humans debugging gold SQL.

## Quick start

### 1. Database

Docker (recommended for readers):

```bash
docker compose up -d
# then load AdventureWorks + wh views
export DATABASE_URL="host=127.0.0.1 port=5432 dbname=Adventureworks user=postgres password=postgres"
bash scripts/load_adventureworks.sh
```

Or point `DATABASE_URL` at any Postgres 16 instance that already has AdventureWorks,
then run `psql "$DATABASE_URL" -f sql/01_create_wh_views.sql`.

### 2. Python

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# set LLM_PROVIDER and the matching key / Ollama host
```

### 3. Profile (optional refresh)

```bash
python scripts/profile_schema.py
```

### 4. Ontology

A curated ontology already lives at `ontology/ontology.yaml`.
To regenerate with your LLM:

```bash
python scripts/draft_ontology.py
# review ontology/ontology.draft.yaml then replace ontology.yaml
```

### 5. Ask one question

```bash
python scripts/ask.py "How many Mountain line finished goods do we have?"
python scripts/ask.py --mode baseline "How many Mountain line finished goods do we have?"
```

### 6. Evaluate (writes report + charts)

```bash
python scripts/evaluate.py
# -> eval/report.md
# -> eval/charts/overall_accuracy.png
# -> eval/charts/accuracy_by_difficulty.png
# -> eval/charts/accuracy_by_tag.png
```

Charts are generated only from a real run. No placeholder numbers.

## LLM providers

Set in `.env` (never commit keys):

| LLM_PROVIDER | What you need |
|--------------|---------------|
| `ollama` | Local Ollama **or** [Ollama Cloud](https://ollama.com) |
| `gemini` | `GEMINI_API_KEY` + `GEMINI_MODEL` (e.g. `gemini-2.5-flash`) |
| `openai` | `OPENAI_API_KEY` |
| `anthropic` | `ANTHROPIC_API_KEY` |

### Ollama local

```bash
LLM_PROVIDER=ollama
OLLAMA_HOST=http://127.0.0.1:11434
OLLAMA_MODEL=qwen2.5-coder:3b
```

### Ollama Cloud

```bash
LLM_PROVIDER=ollama
OLLAMA_HOST=https://ollama.com
OLLAMA_API_KEY=...          # Bearer token; keep out of git
OLLAMA_MODEL=gpt-oss:120b   # cloud API name (CLI may show gpt-oss:120b-cloud)
```

The code path is the same for every provider. Swap the key, keep the ontology.

Eval archives live under `eval/runs/v1_<model>/`. After each full run,
`eval/report.md` aggregates all v1 models and writes comparison charts.


## The 30 questions (summary)

| ID | Diff | Tag | Question (short) |
|----|------|-----|------------------|
| Q01 | simple | structured | Count sales orders |
| Q02 | simple | structured | Count finished goods |
| Q03 | simple | structured | Count customers |
| Q04 | simple | structured | List product categories |
| Q05 | simple | structured | Count active employees |
| Q06 | simple | structured | Count order lines |
| Q07 | simple | needs-docs | Count Mountain finished goods |
| Q08 | simple | needs-docs | Count internet orders |
| Q09 | simple | structured | Count active vendors |
| Q10 | simple | structured | Count product reviews |
| Q11 | medium | structured | Avg list price by category |
| Q12 | medium | needs-docs | Reseller vs internet order counts |
| Q13 | medium | both | Line sales for Road products |
| Q14 | medium | structured | Top 5 territories by orders |
| Q15 | medium | needs-docs | Highly rated products (avg >= 4) |
| Q16 | medium | needs-docs | Stores with Mountain specialty |
| Q17 | medium | structured | Avg subtotal with salesperson |
| Q18 | medium | both | Active Touring finished goods |
| Q19 | medium | structured | Complete purchase orders |
| Q20 | medium | structured | Reseller customers (with store) |
| Q21 | medium | both | Line sales High-class Mountain |
| Q22 | medium | structured | Employees per department |
| Q23 | complex | needs-docs | FY2024 order subtotal |
| Q24 | complex | both | FY2025 internet vs reseller sales |
| Q25 | complex | both | Top 5 Road products by sales |
| Q26 | complex | needs-docs | Avg AnnualSales for Road stores |
| Q27 | complex | both | Finished goods by product line |
| Q28 | complex | structured | Top 10 salespeople by YTD |
| Q29 | complex | both | Orders that include highly rated products |
| Q30 | complex | both | FY2024 US ship-to subtotal |


## Try it in the browser

A Streamlit guide walks through one question step by step: tokens and synonym
hits, ontology entities and multi-hop joins, business rules with **From tables**
vs **From docs** provenance (snippet + original URL), the exact prompt, generated
SQL, live Postgres rows, and an eval check against gold when you pick a sample
question.

```bash
pip install -r requirements.txt
# Postgres with AdventureWorks + wh views must be up (see Quick start)
streamlit run app/app.py
```

Open the URL Streamlit prints (default `http://localhost:8501`). Use the sidebar
to pick Gemini / Ollama Cloud / OpenAI / Anthropic, toggle Ontology vs Schema-only
vs Compare both, and choose a sample from the 30 eval questions.

Tabs:

- **Ask (guided)** — the step-by-step trace
- **Ontology explorer** — browse entities / relationships / rules + interactive graph
- **Benchmark** — `eval/report.md` and accuracy charts

Screenshots from a local run live under `docs/images/app-*.png`.

## Licence

MIT for this repo. AdventureWorks sample data is Microsoft sample data.
Postgres port by [lorint/AdventureWorks-for-Postgres](https://github.com/lorint/AdventureWorks-for-Postgres) (MIT).
See `docs/SOURCES.md` for full attribution.
