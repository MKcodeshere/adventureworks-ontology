# KPI Definitions (Finance & Sales)

Adapted from the Contoso / AdventureWorks DAX sample model guidance and internal
finance playbooks. Fiscal year starts **July 1**.

## Sales Amount (line)

```
Sales Amount = SUM( unit_price * qty * (1 - discount_pct) )
```

Prefer this over header totals when slicing by product, category, or territory.

## Internet Sales vs Reseller Sales

- Internet Sales: orders where online flag is true.
- Reseller Sales: orders where online flag is false (store customers).

## YTD / Fiscal YTD

Fiscal YTD for a given date D runs from the most recent July 1 on or before D,
through D. Do not use calendar January 1.

## Average Order Value (AOV)

```
AOV = SUM(header subtotal) / COUNT(DISTINCT order id)
```

## Review Score

Mean of product review ratings (1–5). A product is "highly rated" when mean ≥ 4
and it has at least one review.
