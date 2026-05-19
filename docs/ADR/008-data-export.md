# ADR-008: Context-Dependent UI Export

## Status
Accepted (2026-05-17; reaffirmed 2026-05-19 by BL-40 ADR-sync — see §History v1.1)

> 🔀 **Channel separation (BL-40, v2.5 alignment).** ADR-008 covers the
> **UI-side** export channel only (Streamlit download buttons, in-memory
> `io.BytesIO`, mode-dependent format). The **pipeline-side** export contract
> (CSV / JSON Lines for batch TZ runs, `EXPORT_SCHEMA_VERSION = "1.0"`, 7 base
> fields) lives in [`ADR-002 (Export Schema Extension)`](002-export-schema-extension.md).
> The two channels intentionally share masking rules (`mask_text()`) and the
> allow-listed column set declared in [`configs/export_config.yaml`](../../configs/export_config.yaml),
> but use disjoint code paths: `src/utils/export.py` for the UI and
> `src/exporters/contract.py` for the pipeline. Cross-channel changes require
> updating **both** ADRs.

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
- Issue [#107](https://github.com/G-Ivan-A/clarify-engine-ai/issues/107),
  Issue [#166](https://github.com/G-Ivan-A/clarify-engine-ai/issues/166) (BL-40 ADR-sync).
- [`configs/export_config.yaml`](../../configs/export_config.yaml) — Excel
  allow-list (`requirement_id`, `requirement_text`, `classification`,
  `reasoning`, `citations`).
- [`src/utils/export.py`](../../src/utils/export.py) — `export_to_excel()`,
  `export_chat_to_markdown()`, in-memory `io.BytesIO` outputs.
- [`src/ui/app.py`](../../src/ui/app.py) — mode-dependent download buttons.
- [`src/llm/masking.py`](../../src/llm/masking.py) — `mask_text()` applied
  before serialization (shared with ADR-002 / ADR-005).
- [`ADR-002 (Export Schema Extension)`](002-export-schema-extension.md) —
  pipeline-side export channel and `EXPORT_SCHEMA_VERSION = "1.0"`.
- [BL-34 audit §CHK-05 «Цитаты & экспорт из UI»](../audit/2026-05-19_bl-34_architecture-consistency-audit_v1.md).

## History

| Version | Date | Change |
|---------|------|--------|
| 1.0 | 2026-05-17 | First Accepted version: in-memory `io.BytesIO` UI export, mode-dependent format (Excel for Анализ ТЗ, Markdown for Консультация), `configs/export_config.yaml` Excel allow-list, `mask_text()` applied at the serialization boundary. |
| 1.1 | 2026-05-19 | BL-40 (issue [#166](https://github.com/G-Ivan-A/clarify-engine-ai/issues/166)): ADR-sync. Added explicit **Channel separation** blockquote that distinguishes ADR-008 (UI export) from [`ADR-002`](002-export-schema-extension.md) (pipeline export, `EXPORT_SCHEMA_VERSION = "1.0"`) and pins the shared masking rules. References extended to `src/llm/masking.py`, `configs/export_config.yaml` allow-list, and BL-34 §CHK-05. Code and config defaults unchanged. |
