# Knowledge Base Sources Manifest

| Filename | Size (MB) | Last Modified |
|----------|-----------|---------------|
| Click2call_Chrome_UserManual_1_0.pdf | 1.08 | 2026-05-16 |
| LK_manual_v-119_compressed.pdf | 13.94 | 2026-05-16 |
| MANGO_OFFICE_LK_VATS_Auth_SSO.pdf | 3.07 | 2026-05-16 |
| MangoOffice_VPBX_API_v1.9.pdf | 5.76 | 2026-05-16 |
| QM_manual_v-1.26.08_compressed.pdf | 2.98 | 2026-05-16 |
| RECHEVAYA-ANALITIKA_1.26.18.pdf | 8.52 | 2026-05-16 |
| RECHEVAYA-ANALITIKA_Skoring_Rukovodstvo-polzovatelya_v.1.26.15.pdf | 8.18 | 2026-05-16 |
| RECHEVAYA-ANALITIKA_VATS-_-Skoring-1.26.18.pdf | 9.34 | 2026-05-16 |
| RECHEVAYA-ANALITIKA_c-KATS_v.1.26.18.pdf | 9.18 | 2026-05-16 |
| Rolevaya-model-VATS_1_26_08.pdf | 2.09 | 2026-05-16 |
| SIP_trunk-1.23.43.pdf | 2.57 | 2026-05-16 |

**Summary:** 11 files, 66.72 MB total
*Metadata tracked via Git. Content updates require a new commit.*

---

## Pre-cloning Readiness Checks

### Repository rename
- Repository name: `clarify-engine-ai` (confirmed via `gh api repos/G-Ivan-A/clarify-engine-ai`).
- `README.md`: no legacy project names found.
- `docs/CONCEPT.md`: no legacy project names found (only a historical note in §change-log about YandexGPT exclusion per issue #64).
- `CHANGELOG.md` keeps the rename history `mango-tz-ai-analyzer` → `clarify-engine-ai` as a historical record (expected).

### `knowledge_base/sources/` directory
- Sentinel file `.gitkeep` is present (size 0 bytes), confirming directory tracking.
- All source files are PDFs; no `.docx` or `.xlsx` artefacts present.

### `configs/llm_config.yaml`
- Providers list contains **only** `deepseek` and `gigachat`.
- No `yandexgpt`, `qwen`, or `dashscope` references.
- `fallback_providers` chain: `deepseek` → `gigachat`.

### `.env.example`
- Contains placeholders for `DEEPSEEK_API_KEY` and `GIGACHAT_API_KEY` (value `"записать_ключ"` — placeholder only, not a secret).
- `YANDEXGPT_API_KEY` line is commented out with a reference to issue #64.
- No real secrets or API keys present.
