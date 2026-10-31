# Data Dictionary (Business Terms)

This is the glossary analysts keep in Confluence. It uses business names.
Warehouse table names in production are cryptic; this page does NOT list those.
Map business terms to physical columns via the ontology.

## Customer
A person or store that buys from us. Individual (internet) customers are people.
Reseller customers are linked to a store.

## Sales Order
A customer purchase. Has an order date, due date, ship date, status, and totals.
Online orders are placed on the website. Reseller orders go through a salesperson.

## Sales Order Line
One product line on a sales order. Quantity, unit price, and discount percent live here.
Line sales amount = unit price × quantity × (1 − discount).

## Product
Anything we sell or use to build what we sell. Finished goods are sold to customers.
Components are not sold alone. Product line codes: R Road, M Mountain, T Touring, S Standard.

## Product Category / Subcategory
Bikes, Components, Clothing, Accessories. Subcategories include Mountain Bikes,
Road Bikes, Touring Bikes, Helmets, Jerseys, etc.

## Store (Reseller)
A retail partner. Annual survey captures Specialty (Mountain/Road/Touring/Family),
BusinessType, AnnualSales, SquareFeet, NumberEmployees.

## Sales Territory
Geographic selling region. Grouped into North America, Europe, Pacific.
Country region code identifies the country.

## Salesperson / Employee
Employees who sell to resellers. Linked to a territory and optional quota.

## Vendor / Purchase Order
Suppliers we buy components and goods from. PO status: 1 Pending, 2 Approved,
3 Rejected, 4 Complete.

## Product Review
Customer rating 1–5 with free-text comments. Sparse; only a handful of products
have reviews in the sample system.

## Bill of Materials
Parent assembly product and component product with quantity per assembly.
