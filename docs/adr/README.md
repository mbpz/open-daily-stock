# Architecture Decision Records

This directory contains the ADRs for open-daily-stock. Each ADR
captures a significant design decision: the context, the choice we
made, and the consequences.

## Index

| # | Title | Status |
|---|-------|--------|
| [ADR-001](ADR-001-SQLite-主存储.md) | SQLite as the primary data store | Accepted |
| [ADR-002](ADR-002-stdio-JSON-IPC.md) | stdio JSON for IPC | Accepted |
| [ADR-003](ADR-003-Gemini-OpenAI-Fallback.md) | Gemini + OpenAI fallback | Accepted |
| [ADR-004](ADR-004-DataFetcherManager-策略模式.md) | DataFetcherManager strategy pattern | Accepted |
| [ADR-005](ADR-005-mplfinance-图表渲染.md) | mplfinance for K-line charts | Accepted |
| [ADR-006](ADR-006-notification-migration.md) | Notification module migration (P7-4) | In progress |
| [ADR-007](ADR-007-async-task-mixin.md) | AsyncTaskMixin for Flet pages (P7-3) | Accepted |

## Conventions

- One ADR per significant design decision
- Filename format: `ADR-NNN-kebab-case-title.md`
- Required sections: Status, Context, Decision, Consequences
- Update an ADR (don't write a new one) when the decision evolves;
  add a note at the bottom recording the change
