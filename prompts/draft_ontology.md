# Draft ontology prompt

You are building a business ontology for Text-to-SQL over a cryptic warehouse schema `wh`.

You receive:
1. A JSON schema profile of `wh` (tables, columns, samples, inferred joins).
2. A folder of company docs (markdown / json) that use business language.

Produce a YAML ontology with entities, relationships, rules, metrics, value_meanings.
Map only to `wh.*` tables/columns from the profile. Cite provenance. Valid YAML only.
