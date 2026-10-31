# Result comparison rules

`scripts/evaluate.py` scores **denotation accuracy**: predicted SQL is correct
when its result set matches the gold result set as data, not as text.

## Match tiers (any one passes)

1. **Full bag match** — same multiset of rows after normalizing cells. Ignores
   column names/aliases and column order within a row. Ignores row order.
2. **Projection match** — same number of rows; each predicted row's values are
   a multiset-subset of a unique gold row. Lets the model omit extra columns
   (e.g. return product name only when gold also has id and average rating).
3. **Numeric bag match** — same number of rows and the same multiset of numeric
   cells, ignoring string labels. Lets channel labels differ
   (`internet` vs `Internet Orders`) when the counts are identical.

## Normalization
- Numerics rounded to 2 decimal places
- Strings stripped and lowercased
- Timestamps compared via ISO string form
- Mixed-type within-row sorts use a typed key (None < bool < number < string)

## Still wrong
- Wrong filters, joins, grain, or metrics
- Extra/missing rows that change the answer
- Execution errors
