# Metadata Coverage Fix — Section Propagation (issue #109)

## Метаданные
- **Дата:** 2026-05-17
- **Версия:** v1
- **Автор:** konard (AI issue solver)
- **Статус:** Draft
- **Issue:** [#109](https://github.com/G-Ivan-A/clarify-engine-ai/issues/109)
- **PR:** [#110](https://github.com/G-Ivan-A/clarify-engine-ai/pull/110)

## 1. Контекст
Baseline из issue #109: после переиндексации корпуса покрытие
`section_title` / `section_number` составляло **0.1356 (13.56%)**. Основная
причина — индексатор извлекал раздел только из текста текущего чанка. В
длинных PDF-разделах заголовок встречался в первом чанке, а последующие чанки
теряли привязку к разделу.

Цель MVP hardening: поднять `metadata_coverage_min` до реалистичного порога
**0.65** без онлайн-сервисов и без LLM-enrichment.

## 2. Выбранный подход
Реализован per-document `SectionPropagationState` в
`knowledge_base/indexing/build_index.py`:

1. Каждый документ получает отдельное состояние, поэтому метаданные не
   перетекают между PDF-файлами.
2. При найденном заголовке `extract_section()` вычисляет `depth`
   (`4.2` → 2). Заголовок того же или более высокого уровня сбрасывает нижний
   контекст; дочерний заголовок добавляется в стек.
3. Чанк без локального заголовка наследует верхний активный раздел и получает
   `section_inherited=true`.
4. Если после последнего заголовка прошло больше
   `section_propagation.max_pages_without_heading` (по умолчанию 6 страниц),
   контекст сбрасывается для защиты от ghost inheritance.
5. Если активного контекста нет, используется безопасный fallback по имени
   документа: `section_number=document`, `section_fallback=source_filename`.

Отклонения от базового предложения: layout-aware парсеры и offline
LLM-enrichment не добавлялись. Regex + stateful propagation закрывают целевой
порог на текущем корпусе дешевле и без новых runtime-зависимостей.

## 3. Метрики
Полная переиндексация корпуса выполнена командой:

```bash
python knowledge_base/indexing/build_index.py > logs/metadata-coverage-reindex.log 2>&1
```

Run ID: `b5693bd8-5318-4ee3-ae10-52281b0c762d`

| Метрика | Baseline | После fix | Целевое | Статус |
|:---|---:|---:|---:|:---:|
| Searchable metadata coverage | 0.1356 | **1.0000** | ≥ 0.65 | ✅ |
| `source` | н/д | 1.0000 | 1.00 | ✅ |
| `chunk_idx` | н/д | 1.0000 | 1.00 | ✅ |
| `page_number` | н/д | 1.0000 | 1.00 | ✅ |
| `section_title` | ~0.1356 | 1.0000 | ≥ 0.65 | ✅ |
| `section_number` | ~0.1356 | 1.0000 | ≥ 0.65 | ✅ |
| `product` | н/д | 1.0000 | 1.00 | ✅ |

Итог по persisted ChromaDB collection `clarify_engine_kb`:

| Показатель | Значение |
|:---|---:|
| Chunks indexed | 6,934 |
| Source PDFs indexed | 11 |
| `section_inherited=true` | 3,570 chunks |
| `section_fallback=source_filename` | 37 chunks |
| `section_fallback=none` | 6,897 chunks |
| ChromaDB size (`./chroma_data`) | 62 MB |

Примечание: reindex-log был снят до финальной корректировки schema-check,
которая признаёт `chunk_idx=0` валидным значением первого чанка. Поэтому
логовая строка показывает `0.9984`, а пересчёт persisted metadata финальной
версией helper-а показывает `1.0000`.

## 4. Edge Cases
- **Sibling reset:** `4.2` заменяет активный `4.1`, последующие чанки
  наследуют только `4.2`.
- **Child section:** `4.2.1` становится верхним активным разделом, но стек
  сохраняет родительский контекст для корректного reset-а на следующем sibling.
- **Long gap:** после `max_pages_without_heading + 1` страниц без заголовка
  стек очищается.
- **Preamble / title pages:** до первого заголовка используется fallback по
  имени документа, а не пустые `section_*`.
- **Hidden placeholders:** `.gitkeep` больше не попадает в список source files.
- **Coverage check:** `chunk_idx=0` считается заполненным полем; `page_number`
  должен быть положительным.

## 5. Примеры Metadata
Direct heading:

```json
{
  "source": "Click2call_Chrome_UserManual_1_0.pdf",
  "chunk_idx": 2,
  "page_number": 2,
  "section_number": "2",
  "section_title": "Оглавление",
  "product": "Click2Call",
  "section_inherited": false,
  "section_fallback": "none"
}
```

Inherited section:

```json
{
  "source": "SIP_trunk-1.23.43.pdf",
  "chunk_idx": 1,
  "page_number": 4,
  "section_number": "4.2",
  "section_title": "Настройка транка",
  "product": "SIP Trunk",
  "section_inherited": true,
  "section_fallback": "none"
}
```

Document fallback:

```json
{
  "source": "Click2call_Chrome_UserManual_1_0.pdf",
  "chunk_idx": 0,
  "page_number": 1,
  "section_number": "document",
  "section_title": "Click2call Chrome UserManual 1 0",
  "product": "Click2Call",
  "section_inherited": false,
  "section_fallback": "source_filename"
}
```

## 6. Verification
- `tests/test_metadata_extraction.py` covers direct extraction, inheritance,
  sibling reset, stale reset, fallback, and `chunk_idx=0` coverage.
- `tests/test_citation_links.py` covers UI citation labels with fallback
  section signatures.
- Full reindex completed and persisted `6,934` chunks to ChromaDB.
- `python -m pytest tests/ -q` → `221 passed`.
- `python scripts/evaluate/evaluate_rag.py --retriever stub --subset smoke` →
  Hit Rate@5 `1.000`, MRR `1.000`, Context Recall `1.000` on 5 smoke items.

## 7. Follow-up Risks
- `extract_section()` still relies on regex and can over-detect table-of-content
  lines as headings. The page-distance guard and fallback make this acceptable
  for MVP, but layout-aware parsing remains a Pilot-level improvement.
- The ChromaDB vector store is generated under ignored `./chroma_data`; reviewers
  should rebuild locally rather than expect the binary index in Git.
