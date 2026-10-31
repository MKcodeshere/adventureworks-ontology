# Evaluation report (multi-model)

Temperature: `0`. Retrieval: v1 generic ontology retrieval. Comparator: `eval/COMPARISON.md`.

## Models

Parameter sizes labelled only when verified: `gpt-oss:120b` (120B); `nemotron-3-super` is 120B total / 12B active MoE per [ollama.com/library/nemotron-3-super](https://ollama.com/library/nemotron-3-super). Gemini has no public parameter count.

| Model | Baseline | Ontology | Delta |
|-------|----------|----------|-------|
| `gemini-2.5-flash` | 53.3% | 86.7% | +33.3 pp |
| `gpt-oss:120b` | 33.3% | 70.0% | +36.7 pp |
| `nemotron-3-super (120B)` | 53.3% | 76.7% | +23.3 pp |

## `gemini-2.5-flash`

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

## `gpt-oss:120b`

### Overall

| Mode | Accuracy | Correct | Total |
|------|----------|---------|-------|
| baseline | 33.3% | 10 | 30 |
| ontology | 70.0% | 21 | 30 |

### By difficulty

| Difficulty | Baseline | Ontology |
|------------|----------|----------|
| simple | 60.0% | 90.0% |
| medium | 25.0% | 58.3% |
| complex | 12.5% | 62.5% |

### By tag

| Tag | Baseline | Ontology |
|-----|----------|----------|
| structured | 53.3% | 80.0% |
| needs-docs | 14.3% | 71.4% |
| both | 12.5% | 50.0% |

## `nemotron-3-super (120B)`

### Overall

| Mode | Accuracy | Correct | Total |
|------|----------|---------|-------|
| baseline | 53.3% | 16 | 30 |
| ontology | 76.7% | 23 | 30 |

### By difficulty

| Difficulty | Baseline | Ontology |
|------------|----------|----------|
| simple | 80.0% | 90.0% |
| medium | 58.3% | 91.7% |
| complex | 12.5% | 37.5% |

### By tag

| Tag | Baseline | Ontology |
|-----|----------|----------|
| structured | 86.7% | 93.3% |
| needs-docs | 28.6% | 57.1% |
| both | 12.5% | 62.5% |

## Charts

- `eval/charts/model_comparison.png`
- `eval/charts/model_comparison_by_tag.png`
- Default single-model charts (`overall_accuracy.png`, `accuracy_by_difficulty.png`, `accuracy_by_tag.png`) are from `gemini-2.5-flash` (kept as the primary reference).
- Per-model charts under `eval/runs/v1_<model>/charts/`

## Run archives

- `eval/runs/v1_gemini-2.5-flash/`
- `eval/runs/v1_gpt-oss-120b/`
- `eval/runs/v1_nemotron-3-super-(120B)/`
