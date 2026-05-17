# Retrieval Evaluation Metrics

Version: 1.0

This standard defines the offline retrieval metrics used by
`scripts/evaluate/evaluate_rag.py` for the BL-05 Golden Set Runner.

## Hit Rate@K

Hit Rate@K measures whether at least one expected source appears in the first
`K` retrieved chunks for a query.

For one query:

```text
hit@K = 1 if any top-K chunk source is in expected_sources, otherwise 0
```

For a dataset:

```text
Hit Rate@K = sum(hit@K for all queries) / number_of_queries
```

The default project value is `K=5`, matching `top_k` in
`configs/embedding_config.yaml`.

## Mean Reciprocal Rank

MRR rewards relevant sources that appear earlier in the ranked list. For one
query, find the first top-K result whose source is listed in `expected_sources`.
If it appears at 1-based rank `r`, the reciprocal rank is `1 / r`. If no
expected source appears in the top-K results, the reciprocal rank is `0`.

For a dataset:

```text
MRR = sum(reciprocal_rank for all queries) / number_of_queries
```

## Golden Set Format

The issue-level template lives in `data/golden_set_v1.jsonl`. Each line is an
independent JSON object:

```json
{"query": "настройка SIP транка", "expected_sources": ["SIP_trunk-1.23.43.pdf"], "expected_pages": [10]}
```

`expected_pages` is stored for future page-level analysis. The current BL-05
metrics use `expected_sources`.
