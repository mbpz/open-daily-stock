# i18n Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate i18n (zh_CN/en_US) into GUI pages, TUI widgets, and add language switcher to Config page.

**Architecture:** Use existing `src.i18n._()` function to translate all hardcoded strings. Translation files already created at `locales/zh_CN.json` and `locales/en_US.json`.

**Tech Stack:** Python, Flet (GUI), Textual (TUI), src.i18n module

---

## Files Overview

**GUI pages to modify:**
- `gui/pages/markets.py` - Markets page (自选股行情, 代码, 名称, etc.)
- `gui/pages/analyze.py` - Analyze page (股票分析, etc.)
- `gui/pages/tasks.py` - Tasks page (历史任务, etc.)
- `gui/pages/config.py` - Config page (配置管理, etc.)
- `gui/pages/logs.py` - Logs page (运行日志, etc.)

**TUI widgets to modify:**
- `tui/widgets/markets.py` - MarketsView
- `tui/widgets/analyze.py` - AnalyzeView
- `tui/widgets/tasks.py` - TasksView
- `tui/widgets/config.py` - ConfigView
- `tui/widgets/logs.py` - LogsView
- `tui/widgets/wizard.py` - WizardView
- `tui/app.py` - TUIApp (footer, help panel)

**Config page enhancement:**
- Add language switcher (Dropdown with zh_CN/en_US options)
- Persist language preference in config

---

## Task 1: Integrate i18n into GUI pages

**Files:**
- Modify: `gui/pages/markets.py:1-98`
- Modify: `gui/pages/analyze.py`
- Modify: `gui/pages/tasks.py`
- Modify: `gui/pages/config.py`
- Modify: `gui/pages/logs.py`
- Test: `tests/test_gui_pages.py`

**Steps:**

- [ ] **Step 1: Add i18n import to markets.py**

```python
from src.i18n import _
```

- [ ] **Step 2: Replace hardcoded strings with _() calls**

Replace:
```python
ft.Text("自选股行情", size=24, weight=ft.FontWeight.BOLD)
```
With:
```python
ft.Text(_("自选股行情"), size=24, weight=ft.FontWeight.BOLD)
```

- [ ] **Step 3: Repeat for all GUI pages** - Same pattern for analyze, tasks, config, logs

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_gui_pages.py -v`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add gui/pages/*.py
git commit -m "feat: integrate i18n into GUI pages"
```

---

## Task 2: Integrate i18n into TUI widgets

**Files:**
- Modify: `tui/widgets/markets.py`
- Modify: `tui/widgets/analyze.py`
- Modify: `tui/widgets/tasks.py`
- Modify: `tui/widgets/config.py`
- Modify: `tui/widgets/logs.py`
- Modify: `tui/widgets/wizard.py`
- Modify: `tui/app.py`
- Test: `tests/test_tui*.py` (if exists)

**Steps:**

- [ ] **Step 1: Add i18n import to each widget**

```python
from src.i18n import _
```

- [ ] **Step 2: Replace hardcoded strings with _() calls** for all text content

- [ ] **Step 3: Update tui/app.py** - Footer and HelpPanel text

- [ ] **Step 4: Run tests**

Run: `pytest tests/ -v -k tui`
Expected: All TUI tests pass

- [ ] **Step 5: Commit**

```bash
git add tui/widgets/*.py tui/app.py
git commit -m "feat: integrate i18n into TUI widgets"
```

---

## Task 3: Add language switcher to Config page

**Files:**
- Modify: `gui/pages/config.py`
- Modify: `src/config.py` (add language preference)
- Modify: `src/i18n.py` (add set_language function)

**Steps:**

- [ ] **Step 1: Add set_language to src/i18n.py**

```python
def set_language(lang: str):
    """Set current language"""
    global _current_lang
    _current_lang = lang
```

- [ ] **Step 2: Add language config to src/config.py**

Add `language` field to Config class, default "zh_CN"

- [ ] **Step 3: Add language switcher to ConfigPage**

```python
language_dropdown = ft.Dropdown(
    label=_("语言"),
    value=config.language or "zh_CN",
    options=[
        ft.dropdown.Option("zh_CN", "简体中文"),
        ft.dropdown.Option("en_US", "English"),
    ],
    on_change=self._on_language_change,
)
```

- [ ] **Step 4: Implement _on_language_change handler**

```python
def _on_language_change(self, e):
    from src.i18n import set_language
    set_language(e.control.value)
    # Refresh UI
    self.app.page.show_snack_bar(ft.SnackBar(content=ft.Text(_("语言已切换")), open=True))
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_gui_pages.py -v`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add src/i18n.py src/config.py gui/pages/config.py
git commit -m "feat: add language switcher to Config"
```