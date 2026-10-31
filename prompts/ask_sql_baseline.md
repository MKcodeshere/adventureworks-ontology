# Text-to-SQL prompt (schema only baseline)

You write PostgreSQL for schema `wh` only.

Question:
{{question}}

Schema profile (abbreviated):
{{schema_hints}}

Return ONLY a SQL query inside a ```sql fence. No explanation.
Column names are cryptic. Guess carefully from names and samples.
