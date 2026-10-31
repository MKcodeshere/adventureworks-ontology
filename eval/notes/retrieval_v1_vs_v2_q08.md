# Retrieval before/after — Q08 internet orders

Question: `How many internet (online) sales orders are there?`

## v1 (any-overlap)
- seeds: Product, PurchaseOrder, PurchaseOrderLine, SalesOrder, SalesOrderLine, SalesTerritory, Salesperson, WorkOrder
- rules: internet_vs_reseller, finished_goods_only, active_product, sales_order_status_shipped, po_status

## v2 (IDF-weighted, current app)
- seeds: SalesOrder (score 106.092)
- rules: internet_vs_reseller
