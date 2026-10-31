# Evaluation report

Provider: `gemini`
Model: `gemini-2.5-flash`
Temperature: `0`

## Retrieval method

Ontology mode uses generic token overlap over ontology content only (entity/attribute names, descriptions, synonyms, `synonyms_index`, rule/metric names+descriptions+synonyms, value_meanings text). Stemming-lite strips simple plurals. After seed entities are chosen, relationships form a graph and shortest paths up to 3 hops between seed pairs add bridge entities and joins. There are no hardcoded question keyword triggers. Baseline mode gets schema profile only.

See `eval/runs/v0_keyword_triggers/` for the discarded first run that used keyword triggers. Headline numbers below are **v1** (generic retrieval). Result matching rules: `eval/COMPARISON.md`.

## Overall

| Mode | Accuracy | Correct | Total |
|------|----------|---------|-------|
| baseline | 53.3% | 16 | 30 |
| ontology | 86.7% | 26 | 30 |

## By difficulty

| Difficulty | Baseline | Ontology |
|------------|----------|----------|
| simple | 80.0% | 100.0% |
| medium | 58.3% | 91.7% |
| complex | 12.5% | 62.5% |

## By tag

| Tag | Baseline | Ontology |
|-----|----------|----------|
| structured | 86.7% | 93.3% |
| needs-docs | 28.6% | 85.7% |
| both | 12.5% | 75.0% |

## Charts

- `eval/charts/overall_accuracy.png`
- `eval/charts/accuracy_by_difficulty.png`
- `eval/charts/accuracy_by_tag.png`

## Per-question

| ID | Diff | Tag | Baseline | Ontology |
|----|------|-----|----------|----------|
| Q01 | simple | structured | Y | Y |
| Q02 | simple | structured | Y | Y |
| Q03 | simple | structured | Y | Y |
| Q04 | simple | structured | Y | Y |
| Q05 | simple | structured | Y | Y |
| Q06 | simple | structured | Y | Y |
| Q07 | simple | needs-docs | Y | Y |
| Q08 | simple | needs-docs | N | Y |
| Q09 | simple | structured | N | Y |
| Q10 | simple | structured | Y | Y |
| Q11 | medium | structured | Y | Y |
| Q12 | medium | needs-docs | N | Y |
| Q13 | medium | both | N | Y |
| Q14 | medium | structured | Y | Y |
| Q15 | medium | needs-docs | Y | Y |
| Q16 | medium | needs-docs | N | Y |
| Q17 | medium | structured | Y | Y |
| Q18 | medium | both | N | Y |
| Q19 | medium | structured | Y | Y |
| Q20 | medium | structured | Y | Y |
| Q21 | medium | both | N | Y |
| Q22 | medium | structured | Y | N |
| Q23 | complex | needs-docs | N | Y |
| Q24 | complex | both | N | Y |
| Q25 | complex | both | N | Y |
| Q26 | complex | needs-docs | N | N |
| Q27 | complex | both | N | N |
| Q28 | complex | structured | N | Y |
| Q29 | complex | both | Y | N |
| Q30 | complex | both | N | Y |

## Retrieval log (ontology mode)

| ID | Seed entities | Bridge | Rules | Metrics |
|----|---------------|--------|-------|---------|
| Q01 | Product, PurchaseOrder, PurchaseOrderLine, SalesOrder, SalesOrderLine, SalesTerritory, Salesperson, WorkOrder | - | internet_vs_reseller, finished_goods_only, active_product, sales_order_status_shipped, po_status | line_sales_amount, order_subtotal, average_order_value |
| Q02 | Product, ProductCategory, ProductReview, ProductSubcategory, PurchaseOrder, PurchaseOrderLine, SalesOrder, SalesOrderLine, WorkOrder | - | internet_vs_reseller, finished_goods_only, active_product, store_specialty, sales_order_status_shipped, po_status | line_sales_amount, order_subtotal, average_order_value, average_review_score |
| Q03 | Customer, Product, ProductReview, SalesOrder | SalesOrderLine | finished_goods_only | - |
| Q04 | BillOfMaterials, CountryRegion, Department, Person, Product, ProductCategory, ProductModel, ProductReview, ProductSubcategory, SalesOrderLine | Customer, SalesOrder | finished_goods_only, active_product, store_specialty | line_sales_amount, average_review_score |
| Q05 | Employee | - | active_product | - |
| Q06 | Product, ProductCategory, ProductReview, ProductSubcategory, PurchaseOrder, PurchaseOrderLine, SalesOrder, SalesOrderLine, SalesTerritory, Salesperson | - | internet_vs_reseller, finished_goods_only, active_product, store_specialty, sales_order_status_shipped, po_status | line_sales_amount, order_subtotal, average_order_value, average_review_score |
| Q07 | Product, ProductCategory, ProductReview, ProductSubcategory, PurchaseOrder, PurchaseOrderLine, SalesOrder, SalesOrderLine, SalesTerritory, Salesperson | - | internet_vs_reseller, finished_goods_only, active_product, store_specialty, sales_order_status_shipped, po_status | line_sales_amount, order_subtotal, average_order_value, average_review_score |
| Q08 | Product, PurchaseOrder, PurchaseOrderLine, SalesOrder, SalesOrderLine, SalesTerritory, Salesperson, WorkOrder | - | internet_vs_reseller, finished_goods_only, active_product, sales_order_status_shipped, po_status | line_sales_amount, order_subtotal, average_order_value |
| Q09 | Employee, Vendor | - | active_product | - |
| Q10 | Product, ProductCategory, ProductReview, ProductSubcategory, PurchaseOrderLine, SalesOrderLine | - | finished_goods_only, active_product, highly_rated, store_specialty | line_sales_amount, average_review_score |
| Q11 | BillOfMaterials, Product, ProductCategory, ProductReview, ProductSubcategory, PurchaseOrder, PurchaseOrderLine, SalesOrder, SalesOrderLine, SpecialOffer | - | internet_vs_reseller, finished_goods_only, active_product, highly_rated, store_specialty, sales_order_status_shipped, po_status | line_sales_amount, order_subtotal, average_order_value, average_review_score |
| Q12 | Customer, Product, PurchaseOrder, PurchaseOrderLine, SalesOrder, SalesOrderLine, Store, Vendor, WorkOrder | - | internet_vs_reseller, finished_goods_only, active_product, store_specialty, sales_order_status_shipped, po_status | order_subtotal, average_order_value |
| Q13 | Product, ProductCategory, ProductReview, ProductSubcategory, PurchaseOrder, PurchaseOrderLine, SalesOrder, SalesOrderLine, SalesTerritory, Salesperson | - | finished_goods_only, active_product, store_specialty | line_sales_amount, order_subtotal, average_review_score |
| Q14 | Product, ProductReview, PurchaseOrder, PurchaseOrderLine, SalesOrder, SalesOrderLine, SalesTerritory, Salesperson, WorkOrder | - | internet_vs_reseller, finished_goods_only, active_product, highly_rated, sales_order_status_shipped, po_status | line_sales_amount, order_subtotal, average_order_value, average_review_score |
| Q15 | Product, ProductCategory, ProductReview, ProductSubcategory, PurchaseOrderLine, SalesOrderLine | - | finished_goods_only, active_product, highly_rated, store_specialty, po_status | line_sales_amount, average_order_value, average_review_score |
| Q16 | Customer, Product, ProductCategory, ProductReview, ProductSubcategory, PurchaseOrderLine, SalesOrder, SalesOrderLine, Store, Vendor | PurchaseOrder | internet_vs_reseller, finished_goods_only, active_product, store_specialty | line_sales_amount |
| Q17 | Product, ProductReview, PurchaseOrder, PurchaseOrderLine, SalesOrder, SalesOrderLine, SalesTerritory, Salesperson, WorkOrder | - | internet_vs_reseller, finished_goods_only, active_product, highly_rated, sales_order_status_shipped, po_status | line_sales_amount, order_subtotal, average_order_value, average_review_score |
| Q18 | Employee, Product, ProductCategory, ProductReview, ProductSubcategory, PurchaseOrder, PurchaseOrderLine, SalesOrder, SalesOrderLine, SalesTerritory | Salesperson | fiscal_year_start, internet_vs_reseller, finished_goods_only, active_product, store_specialty, sales_order_status_shipped, po_status | line_sales_amount, order_subtotal, average_order_value, average_review_score |
| Q19 | Product, PurchaseOrder, PurchaseOrderLine, SalesOrder, SalesOrderLine, WorkOrder | - | internet_vs_reseller, finished_goods_only, active_product, sales_order_status_shipped, po_status | order_subtotal, average_order_value |
| Q20 | Customer, Product, ProductReview, SalesOrder, Store, Vendor | SalesOrderLine | internet_vs_reseller, finished_goods_only, store_specialty | - |
| Q21 | Product, ProductCategory, ProductReview, ProductSubcategory, PurchaseOrder, PurchaseOrderLine, SalesOrder, SalesOrderLine, SalesTerritory, Salesperson | - | finished_goods_only, active_product, highly_rated, store_specialty, po_status | line_sales_amount, order_subtotal, average_order_value, average_review_score |
| Q22 | Department, Employee | - | active_product | - |
| Q23 | Product, PurchaseOrder, PurchaseOrderLine, SalesOrder, SalesOrderLine, WorkOrder | - | fiscal_year_start, internet_vs_reseller, finished_goods_only, active_product, store_specialty, sales_order_status_shipped, po_status | line_sales_amount, order_subtotal, average_order_value |
| Q24 | Customer, Product, ProductCategory, ProductReview, ProductSubcategory, PurchaseOrder, SalesOrder, SalesOrderLine, Salesperson, Store | - | fiscal_year_start, internet_vs_reseller, finished_goods_only, active_product, store_specialty, sales_order_status_shipped, po_status | line_sales_amount, order_subtotal, average_order_value, average_review_score |
| Q25 | Product, ProductCategory, ProductReview, ProductSubcategory, PurchaseOrderLine, SalesOrder, SalesOrderLine, SalesTerritory, Salesperson | - | finished_goods_only, active_product, highly_rated, store_specialty, sales_order_status_shipped, po_status | line_sales_amount, average_order_value, average_review_score |
| Q26 | Customer, Product, ProductCategory, ProductReview, ProductSubcategory, PurchaseOrderLine, SalesOrder, SalesOrderLine, Salesperson, Store | - | internet_vs_reseller, finished_goods_only, active_product, highly_rated, store_specialty, po_status | line_sales_amount, average_order_value, average_review_score |
| Q27 | BillOfMaterials, Customer, Product, ProductCategory, ProductReview, PurchaseOrder, PurchaseOrderLine, SalesOrder, SalesOrderLine, Store | ProductSubcategory | internet_vs_reseller, finished_goods_only, active_product, highly_rated, store_specialty, sales_order_status_shipped, po_status | line_sales_amount, order_subtotal, average_order_value, average_review_score |
| Q28 | CountryRegion, Customer, Department, Person, SalesOrder, SalesOrderLine, SalesTerritory, Salesperson, Store, Vendor | Employee | internet_vs_reseller, highly_rated, store_specialty, po_status | line_sales_amount, average_order_value, average_review_score |
| Q29 | Product, ProductCategory, ProductReview, ProductSubcategory, PurchaseOrder, PurchaseOrderLine, SalesOrder, SalesOrderLine, WorkOrder | - | internet_vs_reseller, finished_goods_only, active_product, highly_rated, store_specialty, sales_order_status_shipped, po_status | line_sales_amount, order_subtotal, average_order_value, average_review_score |
| Q30 | Address, CountryRegion, Product, PurchaseOrder, PurchaseOrderLine, SalesOrder, SalesOrderLine, WorkOrder | - | fiscal_year_start, internet_vs_reseller, finished_goods_only, active_product, sales_order_status_shipped, po_status | order_subtotal, average_order_value |

## v0 comparison (discarded)

v0 used hardcoded keyword triggers in retrieval. Archived at
`eval/runs/v0_keyword_triggers/`. With denotation rescoring, v0 was about
**baseline 40.0% / ontology 76.7%**. Headline numbers above are **v1**
(generic ontology retrieval + multi-hop joins).
