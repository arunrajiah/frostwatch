# Quick Audit SQL (zero install)

Paste this into a Snowsight worksheet and click **Run All**. The final result lists findings sorted by estimated monthly savings, each with the SQL to fix it. Read-only.

It covers six core checks (auto-suspend, never-suspending warehouses, oversized warehouses, remote spilling, cloud services overage, missing resource monitors). The [`frostwatch audit`](savings-advisor.md) CLI adds repeated-query, Time Travel bloat, unused-table and clustering checks, plus a shareable report.

[Download the .sql file](https://raw.githubusercontent.com/arunrajiah/frostwatch/main/sql/frostwatch_quick_audit.sql){ .md-button }

```sql
--8<-- "sql/frostwatch_quick_audit.sql"
```
