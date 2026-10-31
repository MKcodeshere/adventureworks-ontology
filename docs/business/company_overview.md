# Adventure Works Cycles — Company Overview

> Summarized from Microsoft sample documentation for tutorial use.
> Sources: [Analysis Services tutorial scenario](https://learn.microsoft.com/en-us/analysis-services/multidimensional-tutorial/analysis-services-tutorial-scenario),
> [AdventureWorks product scenario](https://learn.microsoft.com/en-us/previous-versions/sql/sql-server-2008/ms124670(v=sql.100)),
> [DAX sample model](https://learn.microsoft.com/en-us/dax/dax-sample-model).

## Who we are

Adventure Works Cycles is a fictional multinational bicycle manufacturer and seller.
The company sells bicycles, bicycle components, clothing, and accessories to
individual consumers (internet / online) and to reseller stores.

## Sales channels

- **Internet (online) sales**: orders placed by individual customers on the web.
  In the OLTP system these are orders where the online-order flag is true and
  there is usually no assigned salesperson.
- **Reseller sales**: orders placed by brick-and-mortar stores. These have a
  store on the customer record and an assigned salesperson.

## Fiscal calendar

Adventure Works uses a **fiscal year that starts on July 1**.
Fiscal year FY2014 runs from 2013-07-01 through 2014-06-30.
Calendar year and fiscal year therefore differ by six months.
When someone says "fiscal year sales", always filter on July 1 boundaries,
not January 1.

## Product lines (coded values)

Finished goods use a single-letter product line code:

| Code | Meaning |
|------|---------|
| R | Road |
| M | Mountain |
| T | Touring |
| S | Standard / Accessory (often clothing and accessories) |

Class codes: H = High, M = Medium, L = Low.
Style codes: W = Women's, M = Men's, U = Universal.

## Finished goods vs components

`FinishedGoodsFlag = true` (or the warehouse `fg_flg`) means the product is sold
to customers. Components and raw materials have the flag false and usually have
no product line.

## Key metrics used by the business

- **Revenue / Sales Amount**: sum of line-level (unit price × qty × (1 − discount)).
  Header `totaldue` / `net_amt` includes tax and freight; analysts usually prefer
  the line-level amount for product analysis, and header subtotal for order totals
  before tax.
- **Online vs reseller share**: percent of orders (or revenue) with online flag true.
- **Active product**: finished good with a sell start date in the past and
  (sell end date null OR sell end date in the future).
- **Top-rated product**: average review rating ≥ 4 on a 1–5 scale.

## Order status codes (sales)

In this OLTP snapshot nearly all sales orders are status **5 = Shipped**.
Historically the domain is: 1 In process, 2 Approved, 3 Backordered, 4 Rejected, 5 Shipped, 6 Cancelled.

## Purchase order status codes

1 = Pending, 2 = Approved, 3 = Rejected, 4 = Complete.

## Document status

1 = Pending approval, 2 = Approved / available.
