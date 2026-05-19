from pathlib import Path


DOC = Path("docs/backlog/2026-05-17_backlog_rag-optimization_v1.3.md")


def main() -> int:
    text = DOC.read_text(encoding="utf-8")
    required = [
        "**Версия:** v1.3",
        "**Дата:** 2026-05-19",
        "Предыдущая версия:",
        "**Статус:** Draft → Review",
        "### 0.6. Актуальный статус задач",
        "## 14. Отложенные задачи (Backlog / Thinking)",
        "BL-27 (export-markup) ──► BL-28 (ExportRouter) ──► BL-29 (UI selectors)",
        "| **v1.3** | **2026-05-19** |",
    ]
    missing = [item for item in required if item not in text]
    if missing:
        raise AssertionError("Missing required fragments:\n" + "\n".join(missing))

    for old, new in [("BL-19", "BL-27"), ("BL-20", "BL-28"), ("BL-21", "BL-29")]:
        if f"**{old}**" in text:
            raise AssertionError(f"Found old task row ID {old}; expected {new}")
        if f"**{new}**" not in text:
            raise AssertionError(f"Missing new task row ID {new}")

    for issue in ["#91", "#105", "#92", "#93", "#94", "#106", "#107", "#132", "#101", "#103", "#120", "#121", "#122", "#142"]:
        if f"/issues/{issue[1:]}" not in text:
            raise AssertionError(f"Missing GitHub issue link for {issue}")

    for task_id in ["BL-30", "BL-31", "BL-32"]:
        if task_id not in text:
            raise AssertionError(f"Missing deferred task {task_id}")

    print(f"{DOC} passes v1.3 backlog checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
