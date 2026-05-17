# ADR-008: Context-Dependent UI Export

## Status
Accepted (2026-05-17)

## Context

BL-15 / issue #107 requires two export behaviours from the Streamlit KB UI:

1. **Анализ ТЗ** needs a spreadsheet report for analyst follow-up.
2. **Консультация** needs a readable Markdown transcript.

Writing intermediate files on the server would add cleanup and data-retention
risk. Reusing one format for both modes would also produce unreadable output:
tabular reports and chat transcripts have different consumers.

## Decision

Export is mode-dependent and generated in memory:

- `src/utils/export.py::export_to_excel(dataframe)` returns `io.BytesIO`
  containing an `.xlsx` workbook.
- `src/utils/export.py::export_chat_to_markdown(history)` returns `io.BytesIO`
  containing UTF-8-SIG Markdown.
- `configs/export_config.yaml` defines the strict Excel allow-list:
  `requirement_id`, `requirement_text`, `classification`, `reasoning`,
  `citations`.
- `src/ui/app.py` renders a disabled download button until mode-specific data
  exists:
  - «📥 Скачать отчет (.xlsx)» in «Анализ ТЗ».
  - «📥 Сохранить диалог (.md)» in «Консультация».

Both exporters apply `mask_text()` to every string value immediately before
serialization. Excel export reindexes the dataframe to the configured
allow-list, so service fields such as `raw`, `provider`, tokens, or prompt
payloads are not serialized even if they are present in memory.

## Consequences

### Positive
- No server-side export artifacts are created.
- Export format follows the active UI mode.
- Data minimization is enforced by column allow-listing for Excel and by using
  only persisted chat messages for Markdown.
- The masking boundary is close to serialization, which protects future callers
  that pass unmasked in-memory data by mistake.

### Negative
- The UI analysis mode currently exports the last interactive query/answer as
  one report row. Batch TZ export can reuse the same utility once the UI has a
  tabular result dataframe.
- `.xlsx` files are binary ZIP workbooks; UTF-8-SIG is therefore meaningful for
  the Markdown byte stream, while Excel text values are stored through the
  workbook writer.

## References
- Issue [#107](https://github.com/G-Ivan-A/clarify-engine-ai/issues/107).
- [`configs/export_config.yaml`](../../configs/export_config.yaml).
- [`src/utils/export.py`](../../src/utils/export.py).
- [`src/ui/app.py`](../../src/ui/app.py).
