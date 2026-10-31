# Sources and attribution

All structured and unstructured material in this tutorial comes from public
Microsoft AdventureWorks samples and Microsoft Learn docs. Summaries in
`docs/business/` paraphrase those pages for tutorial use. Raw exports in
`docs/products/` and `docs/stores/` come from the loaded OLTP database.

## Structured data

| Source | Licence / note | Used for |
|--------|----------------|----------|
| [AdventureWorks OLTP install scripts (CSV zip)](https://github.com/Microsoft/sql-server-samples/releases/download/adventureworks/AdventureWorks-oltp-install-script.zip) | Microsoft sample data | Tables and rows |
| [AdventureWorks for Postgres](https://github.com/lorint/AdventureWorks-for-Postgres) (lorint) | MIT | Postgres load scripts (`install.sql`, `update_csvs.rb`, Docker bits) |

## Business / unstructured docs (Microsoft Learn)

| URL | What we took |
|-----|----------------|
| [Analysis Services tutorial scenario](https://learn.microsoft.com/en-us/analysis-services/multidimensional-tutorial/analysis-services-tutorial-scenario) | Company story, bike manufacturer selling globally |
| [Product scenario (SQL Server 2008 docs)](https://learn.microsoft.com/en-us/previous-versions/sql/sql-server-2008/ms124670(v=sql.100)) | Product lines, finished goods flag, BOM, categories |
| [DAX sample model](https://learn.microsoft.com/en-us/dax/dax-sample-model) | Fiscal year starts July 1, Internet vs Reseller channels |

## In-database unstructured exports

Exported at load time from the Postgres AdventureWorks database into this repo:

| File | Origin table / column |
|------|------------------------|
| `docs/products/catalog_descriptions.md` | `production.productdescription` (English) joined via model/culture |
| `docs/products/reviews.md` + `reviews_data.json` | `production.productreview` |
| `docs/products/model_catalog.md` | `production.productmodel.catalogdescription` and `instructions` (XML → text) |
| `docs/stores/store_survey.md` + `store_survey_sample.json` | `sales.store.demographics` StoreSurvey XML |
| `docs/business/data_dictionary.md` | Hand-written business glossary grounded in the docs above and table comments |

## Scrambled warehouse layer

`sql/01_create_wh_views.sql` creates schema `wh` with cryptic names. The reverse
map `data/scramble_map.yaml` is for debugging only. Do not feed it to the LLM.
Company docs use business terms on purpose, the way real wikis do.
