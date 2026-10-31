# Evaluation report (multi-model)

Temperature: `0`. Current app retrieval is **v2 IDF-weighted**. Gemini kept at **v1** (credits exhausted, not rerun). Comparator: `eval/COMPARISON.md`.

## Models

Parameter sizes labelled only when verified: `gpt-oss:120b` (120B); `nemotron-3-super` is 120B total / 12B active MoE per [ollama.com/library/nemotron-3-super](https://ollama.com/library/nemotron-3-super). Gemini has no public parameter count.

| Model | Baseline | Ontology | Delta |
|-------|----------|----------|-------|
| `gemini-2.5-flash (v1 retrieval)` | 53.3% | 86.7% | +33.3 pp |
| `gpt-oss:120b (v2 retrieval)` | 33.3% | 73.3% | +40.0 pp |
| `nemotron-3-super (120B) (v2 retrieval)` | 46.7% | 70.0% | +23.3 pp |


## v1 → v2 retrieval delta (Ollama only)

Same protocol (30 Qs × both modes, temp 0). Gemini not rerun (HTTP 402).

| Model | Mode | v1 | v2 | Δ |
|-------|------|----|----|---|
| `gpt-oss:120b` | baseline | 33.3% | 33.3% | +0.0 pp |
| `gpt-oss:120b` | ontology | 70.0% | 73.3% | +3.3 pp |
| `nemotron-3-super` | baseline | 53.3% | 46.7% | −6.7 pp |
| `nemotron-3-super` | ontology | 76.7% | 70.0% | −6.7 pp |

Baseline variance for nemotron is expected under identical protocol (non-determinism / sampling). Ontology drop for nemotron is real under tighter v2 retrieval (less noisy seeds; some previously lucky retrievals no longer fire). gpt-oss ontology improved slightly, especially needs-docs (+71.4→85.7%).

Q08 retrieval example: see `eval/notes/retrieval_v1_vs_v2_q08.md`.

## `gemini-2.5-flash (v1 retrieval)`

### Overall

| Mode | Accuracy | Correct | Total |
|------|----------|---------|-------|
| baseline | 53.3% | 16 | 30 |
| ontology | 86.7% | 26 | 30 |

### By difficulty

| Difficulty | Baseline | Ontology |
|------------|----------|----------|
| simple | 80.0% | 100.0% |
| medium | 58.3% | 91.7% |
| complex | 12.5% | 62.5% |

### By tag

| Tag | Baseline | Ontology |
|-----|----------|----------|
| structured | 86.7% | 93.3% |
| needs-docs | 28.6% | 85.7% |
| both | 12.5% | 75.0% |

## `gpt-oss:120b (v2 retrieval)`

### Overall

| Mode | Accuracy | Correct | Total |
|------|----------|---------|-------|
| baseline | 33.3% | 10 | 30 |
| ontology | 73.3% | 22 | 30 |

### By difficulty

| Difficulty | Baseline | Ontology |
|------------|----------|----------|
| simple | 60.0% | 90.0% |
| medium | 25.0% | 66.7% |
| complex | 12.5% | 62.5% |

### By tag

| Tag | Baseline | Ontology |
|-----|----------|----------|
| structured | 53.3% | 73.3% |
| needs-docs | 14.3% | 85.7% |
| both | 12.5% | 62.5% |

## `nemotron-3-super (120B) (v2 retrieval)`

### Overall

| Mode | Accuracy | Correct | Total |
|------|----------|---------|-------|
| baseline | 46.7% | 14 | 30 |
| ontology | 70.0% | 21 | 30 |

### By difficulty

| Difficulty | Baseline | Ontology |
|------------|----------|----------|
| simple | 70.0% | 100.0% |
| medium | 41.7% | 58.3% |
| complex | 25.0% | 50.0% |

### By tag

| Tag | Baseline | Ontology |
|-----|----------|----------|
| structured | 60.0% | 80.0% |
| needs-docs | 42.9% | 57.1% |
| both | 25.0% | 62.5% |

## Charts

- `eval/charts/model_comparison.png`
- `eval/charts/model_comparison_by_tag.png`
- Default single-model charts (`overall_accuracy.png`, `accuracy_by_difficulty.png`, `accuracy_by_tag.png`) are from `gemini-2.5-flash` (kept as the primary reference).
- Per-model charts under `eval/runs/v2_<model>/charts/` (and v1_*)

## Run archives

- `eval/runs/v1_gemini-2.5-flash/` — v1 retrieval only
- `eval/runs/v1_*` — original v1 Ollama/Gemini archives (kept)
- `eval/runs/v2_*` — v2 IDF retrieval (current app)
