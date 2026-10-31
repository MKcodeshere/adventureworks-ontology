# Text-to-SQL prompt (with ontology slice)

You write PostgreSQL for schema `wh` only.

Question:
{{question}}

Relevant ontology slice:
{{ontology_slice}}

Schema hints (tables/columns touched by the slice):
{{schema_hints}}

Return ONLY a SQL query inside a ```sql fence. No explanation.
Use cryptic `wh` column names. Respect business rules in the ontology
(fiscal year, product line codes, online vs reseller, finished goods, etc).
