# Evaluation report — `gpt-oss:120b`

Provider: `ollama`
Model: `gpt-oss:120b`
Temperature: `0`

## Retrieval method

Ontology mode uses **v2 IDF-weighted** retrieval: entity scores weight name/synonym hits highest, attribute names medium, description lowest; corpus IDF down-weights generic tokens; synonym expansion only on full phrases or strong tokens. Top seeds by relative score (≥40% of best, max 5), then multi-hop paths ≤3 hops for bridges. No question-tuned keyword triggers. Baseline mode gets schema profile only.

Result matching rules: `eval/COMPARISON.md`.

## Overall

| Mode | Accuracy | Correct | Total |
|------|----------|---------|-------|
| baseline | 33.3% | 10 | 30 |
| ontology | 73.3% | 22 | 30 |

## By difficulty

| Difficulty | Baseline | Ontology |
|------------|----------|----------|
| simple | 60.0% | 90.0% |
| medium | 25.0% | 66.7% |
| complex | 12.5% | 62.5% |

## By tag

| Tag | Baseline | Ontology |
|-----|----------|----------|
| structured | 53.3% | 73.3% |
| needs-docs | 14.3% | 85.7% |
| both | 12.5% | 62.5% |

## Charts

- `eval/charts/overall_accuracy.png` (latest run)
- `eval/charts/accuracy_by_difficulty.png`
- `eval/charts/accuracy_by_tag.png`
- `eval/charts/model_comparison.png`
- `eval/charts/model_comparison_by_tag.png`

## Per-question

| ID | Diff | Tag | Baseline | Ontology |
|----|------|-----|----------|----------|
| Q01 | simple | structured | Y | Y |
| Q02 | simple | structured | N | N |
| Q03 | simple | structured | Y | Y |
| Q04 | simple | structured | Y | Y |
| Q05 | simple | structured | Y | Y |
| Q06 | simple | structured | Y | Y |
| Q07 | simple | needs-docs | N | Y |
| Q08 | simple | needs-docs | N | Y |
| Q09 | simple | structured | N | Y |
| Q10 | simple | structured | Y | Y |
| Q11 | medium | structured | Y | Y |
| Q12 | medium | needs-docs | N | Y |
| Q13 | medium | both | N | Y |
| Q14 | medium | structured | N | N |
| Q15 | medium | needs-docs | Y | Y |
| Q16 | medium | needs-docs | N | Y |
| Q17 | medium | structured | Y | Y |
| Q18 | medium | both | N | Y |
| Q19 | medium | structured | N | Y |
| Q20 | medium | structured | N | N |
| Q21 | medium | both | N | N |
| Q22 | medium | structured | N | N |
| Q23 | complex | needs-docs | N | Y |
| Q24 | complex | both | N | Y |
| Q25 | complex | both | N | Y |
| Q26 | complex | needs-docs | N | N |
| Q27 | complex | both | N | N |
| Q28 | complex | structured | N | Y |
| Q29 | complex | both | Y | Y |
| Q30 | complex | both | N | N |

## Retrieval log (ontology mode)

| ID | Seed entities | Bridge | Rules | Metrics |
|----|---------------|--------|-------|---------|
| Q01 | SalesOrder | - | - | - |
| Q02 | Product | - | finished_goods_only, active_product | - |
| Q03 | Customer | - | - | - |
| Q04 | ProductCategory, Product | ProductSubcategory | - | - |
| Q05 | Employee | - | - | - |
| Q06 | SalesOrderLine, SalesOrder | - | - | - |
| Q07 | Product | - | finished_goods_only, active_product, store_specialty | - |
| Q08 | SalesOrder | - | internet_vs_reseller | - |
| Q09 | Vendor | - | - | - |
| Q10 | ProductReview | - | highly_rated | - |
| Q11 | Product, ProductCategory | ProductSubcategory | finished_goods_only, active_product | - |
| Q12 | SalesOrder, Store | Customer | internet_vs_reseller | - |
| Q13 | Product, SalesOrderLine, Store | Customer, SalesOrder | store_specialty | line_sales_amount |
| Q14 | SalesOrder | - | - | - |
| Q15 | Product, ProductReview, PurchaseOrder, SalesOrder | SalesOrderLine | highly_rated | average_review_score |
| Q16 | Store, Product | - | internet_vs_reseller, store_specialty | - |
| Q17 | Salesperson, SalesOrder, SalesOrderLine | - | - | - |
| Q18 | Product | - | finished_goods_only, active_product, store_specialty | - |
| Q19 | PurchaseOrder, Product, PurchaseOrderLine | - | finished_goods_only, po_status | - |
| Q20 | Store, SalesOrder | Customer | internet_vs_reseller | - |
| Q21 | Product | - | highly_rated, store_specialty | - |
| Q22 | Employee, Department | - | - | - |
| Q23 | SalesOrder, PurchaseOrder | - | fiscal_year_start | - |
| Q24 | SalesOrder, Store | Customer | fiscal_year_start, internet_vs_reseller | line_sales_amount |
| Q25 | Product, SalesOrder, SalesOrderLine, Store | Customer | store_specialty | line_sales_amount |
| Q26 | Product, Store | - | store_specialty | - |
| Q27 | Product | - | finished_goods_only, active_product | - |
| Q28 | Salesperson, Person | Customer, SalesOrder | - | - |
| Q29 | Product, PurchaseOrder, SalesOrder, ProductReview | SalesOrderLine | highly_rated | average_order_value |
| Q30 | CountryRegion | - | fiscal_year_start, sales_order_status_shipped | - |
