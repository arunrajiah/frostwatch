# FrostWatch — Community Submission Checklist

## 1. GitHub Topics (do this first — 2 min)
Go to https://github.com/arunrajiah/frostwatch → gear icon next to "About"
Add these topics:
```
snowflake finops data-engineering dbt cost-optimization observability self-hosted open-source python fastapi
```

## 2. Screenshots (required before HN post)
Run `frostwatch demo`, open http://localhost:8000, and take screenshots of:
- Dashboard → save to `docs/screenshots/dashboard.png`
- Anomalies page → save to `docs/screenshots/anomalies.png`
- Queries page → save to `docs/screenshots/queries.png`

Then: `git add docs/screenshots/ && git commit -m "docs: add dashboard screenshots" && git push`

## 3. Hacker News — Show HN
Post at https://news.ycombinator.com/submit
Best time: Tuesday–Thursday, 8–10am ET

**Title:**
Show HN: FrostWatch – self-hosted Snowflake cost observability (MIT, BYO-LLM)

**URL:** https://github.com/arunrajiah/frostwatch

**Text:**
FrostWatch is an open-source tool I built after my team got hit by a surprise
Snowflake bill and the commercial options (Select.dev, Metronome) charge ~1–2%
of spend per month.

It runs entirely inside your infrastructure — the only outbound calls are to
Snowflake and your chosen LLM. No SaaS contract, no phone-home.

Try it in 30 seconds (no Snowflake account needed):

  pip install frostwatch && frostwatch demo

What it does:
- Cost breakdown by warehouse, user, role, and query tag
- Anomaly detection vs. a 21-day rolling baseline with LLM plain-English explanations
- Query fingerprinting — surface what SQL patterns are actually driving spend
- Week-over-week regression detection (catches dbt model changes that silently got expensive)
- AI query rewrites with estimated savings %
- dbt Cloud integration + GitHub Actions step that posts cost summaries as PR comments
- Resource monitor management — quota recommendations + generates CREATE RESOURCE MONITOR DDL
- Cost forecasting (1–30 day per-warehouse projections)
- Weekly digest to Slack or email
- BYO LLM: Anthropic, OpenAI, Google Gemini, or local Ollama

Stack: Python/FastAPI, React, SQLite, Docker.
Known gap: single-account today — multi-account is v0.5.

Happy to answer questions about the ACCOUNT_USAGE schema quirks I ran into.

---

## 4. dbt Slack (#tools-and-integrations)
Join at https://www.getdbt.com/community/join-the-community

Post in #tools-and-integrations:

Hey all — I've been building FrostWatch, an open-source Snowflake cost
observability tool with first-class dbt support:

- Parses query_tag to attribute Snowflake credits per dbt model
- dbt Cloud integration — syncs run metadata, shows cost by job/environment
- GitHub Actions step that posts a cost summary as a PR comment after every
  `dbt run` (catch expensive model changes before they merge)
- Threshold alerts when a model crosses a configurable daily credit limit
- manifest.json enrichment — links cost data back to model owner,
  materialization, and tags

MIT licensed, self-hosted. Try it without a Snowflake account:

    pip install frostwatch && frostwatch demo

GitHub: https://github.com/arunrajiah/frostwatch

Would love feedback on what cost attribution you wish you had that this doesn't cover yet.

---

## 5. Locally Optimistic Slack (#tools)
Join at https://locallyoptimistic.com/community/

Post in #tools — same message as dbt Slack above works fine here.

---

## 6. awesome-data-engineering PR
Repo: https://github.com/igorbarinov/awesome-data-engineering
File: README.md — find the "Monitoring" or "Observability" section and add:

* [FrostWatch](https://github.com/arunrajiah/frostwatch) - Self-hosted, AI-powered Snowflake cost and query observability. Anomaly detection, query fingerprinting, dbt attribution, resource monitor management.

---

## 7. awesome-snowflake PR
Repo: https://github.com/Snowflake-Labs/awesome-snowflake
Add under Cost Management / FinOps section:

* [FrostWatch](https://github.com/arunrajiah/frostwatch) - Open-source self-hosted cost observability tool. Anomaly detection, AI query rewrites, dbt model attribution, resource monitor management.

---

## Priority order
1. GitHub topics (2 min, immediate SEO impact)
2. Screenshots (needed for everything else to convert)
3. Show HN (highest reach, post after screenshots are live)
4. dbt Slack (most targeted audience, post same day as HN)
5. awesome-list PRs (passive ongoing discovery)
6. Locally Optimistic Slack
