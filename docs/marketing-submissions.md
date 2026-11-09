# FrostWatch launch kit (v0.5, Savings Advisor)

The hook for every post is the same: **"Run one command, see how much your Snowflake account is wasting, with the SQL to fix it."** Lead with the audit, not the dashboard. People try a 60-second command; they do not try a self-hosted server from a cold post.

Always link the sample report so people can see the output without installing anything:
https://arunrajiah.github.io/frostwatch/sample-audit.html

Order that works: 1) ship release to PyPI, 2) Reddit + LinkedIn on the same day, 3) Show HN 2 to 3 days later once the README has a few stars, 4) awesome-list PRs, 5) the checklist article.

---

## 0. Before posting (10 min)

- [ ] Tag `v0.5.0` so the release workflow publishes to PyPI. Verify `uvx frostwatch audit --demo` works on a clean machine.
- [ ] GitHub repo "About": add topics `snowflake-cost`, `cost-management`, `data-warehouse`, `sql`, `devtools` (keep the existing ones). Set the website to the docs site.
- [ ] Pin a GitHub Discussion "Share your audit result (anonymized)" so visitors see social proof.
- [ ] Run `frostwatch audit` on a real account you have access to, anonymize, and keep one real number ready ("found $X/month on a $Y/month account"). Real numbers beat demo numbers every time.

---

## 1. r/snowflake and r/dataengineering

**Title:** I built a free CLI that audits your Snowflake account for wasted spend in about a minute (open source, read-only)

**Body:**

> After cleaning up the same handful of Snowflake cost problems at a few teams (auto-suspend left at 10 minutes, a Medium warehouse running 2 second queries, dashboards missing the result cache, Time Travel bigger than the table itself), I turned the checks into a tool.
>
> `pip install frostwatch && frostwatch audit -c <your connection>`
>
> It reads ACCOUNT_USAGE (read-only), runs 11 checks, and writes an HTML report with a dollar estimate and the exact SQL fix for each finding. Works with SSO, key-pair and connections.toml. No server, no LLM key, nothing leaves your machine.
>
> Sample report: https://arunrajiah.github.io/frostwatch/sample-audit.html
> No Python? There is a single SQL script you can paste into Snowsight: https://github.com/arunrajiah/frostwatch/blob/main/sql/frostwatch_quick_audit.sql
>
> It is MIT licensed. If you want continuous monitoring there is also a self-hosted dashboard (anomalies, cost per dbt model, query regressions, weekly Slack digest), but the audit stands on its own.
>
> I would love feedback on the estimates: which checks are wrong for your setup, and what checks you would add.

Rules: r/dataengineering allows self-promo if you engage in comments. Reply to every comment for the first 3 hours.

---

## 2. LinkedIn (personal post, no link in body; put the link in the first comment)

> Most Snowflake accounts I have looked at waste 15 to 40 percent of their bill in the same few places.
>
> Auto-suspend set to 10 minutes. A warehouse that never suspends. A Medium warehouse running queries that finish in 2 seconds. Dashboards re-running the same query 8,000 times a month and missing the free result cache. Tables whose Time Travel is 3x the table.
>
> So I made a free, open source command that finds them for you in about a minute:
>
> pip install frostwatch
> frostwatch audit
>
> Read-only. Runs on your laptop. Gives you a report with a dollar estimate and the SQL fix for each issue. You can forward it straight to your data lead or your CFO.
>
> Sample report and code in the first comment. If you run it, tell me what it found.
>
> #Snowflake #DataEngineering #FinOps #dbt

Tag Snowflake Data Superheroes you know personally and ask them to try it, not to share it.

---

## 3. Show HN

**Title:** Show HN: FrostWatch, find wasted Snowflake spend with one command (open source)

**URL:** https://github.com/arunrajiah/frostwatch

**Text:**

> FrostWatch is an open source Snowflake cost tool. The new part is `frostwatch audit`: point it at an account (SSO, key-pair, or your Snowflake CLI connection) and in about a minute it writes a report of what is wasting money, with a dollar estimate and the SQL fix for each item. Read-only, runs locally, no LLM needed.
>
> Checks: auto-suspend, never-suspending and oversized warehouses, remote spilling, queuing, identical queries missing the result cache, cloud services above the free 10 percent, Time Travel and Fail-safe bloat, tables unread for 90 days, missing resource monitors, auto-clustering spend.
>
> Sample report: https://arunrajiah.github.io/frostwatch/sample-audit.html
>
> The estimates are deliberately conservative heuristics (for example, downsizing assumes a 30 percent saving, not 50). I would like to hear where they are wrong.
>
> Beyond the audit there is a self-hosted dashboard: anomaly detection, cost per dbt model, week-over-week query regressions, AI query rewrites with your own LLM (Ollama works), weekly Slack digest. Python/FastAPI/React/SQLite, MIT.

Best time: Tuesday to Thursday, 8 to 10am US Eastern. Be in the comments for 2 hours.

---

## 4. dbt Community Slack (#tools-and-integrations) and Locally Optimistic Slack

> Sharing a free tool for Snowflake + dbt teams: `frostwatch audit` gives you a savings report in about a minute (read-only, local). The full app also attributes Snowflake credits to dbt models via query_tag, flags models crossing a cost threshold, and can post a cost summary on PRs from GitHub Actions. Sample report: https://arunrajiah.github.io/frostwatch/sample-audit.html. Feedback welcome.

---

## 5. Snowflake Community and Snowflake Builders forum

Post the checklist article (below) as a how-to, with FrostWatch as the "automate this" footer. How-tos get more reach there than tool announcements.

---

## 6. Evergreen article (dev.to, Medium, Hashnode, your blog)

Repost https://arunrajiah.github.io/frostwatch/snowflake-cost-optimization/ with a canonical link back to the docs page. Title options:

- "11 places your Snowflake bill is leaking money (and the SQL to find each one)"
- "A Snowflake cost optimization checklist you can run in 60 seconds"

This is the long-term SEO play: people search "snowflake cost optimization", "snowflake auto suspend best practice", "reduce snowflake costs".

---

## 7. Awesome lists (one PR each, one-line entry)

Entry text: `[FrostWatch](https://github.com/arunrajiah/frostwatch) - Open source Snowflake cost audit and observability: savings report in 60 seconds, anomaly alerts, dbt model costs.`

- awesome-snowflake lists on GitHub (search "awesome snowflake")
- awesome-dbt
- awesome-data-engineering
- awesome-finops / awesome-cloud-cost lists
- awesome-selfhosted (needs a demo or screenshots, and a stable release)

---

## 8. Product directories

- Product Hunt (launch the audit as the product: "Snowflake Savings Audit")
- AlternativeTo: list as an alternative to SELECT, Chaos Genius, Keebo, Sundeck
- PyPI: already published; the new description and keywords help search

---

## Follow-up content ideas (one per week keeps the repo alive)

- "We ran frostwatch audit on N accounts: here is what it found" (aggregate, anonymized, only with permission)
- Short screen recording (30s GIF) of `frostwatch audit --demo` for README and social
- A post per check, each answering one search query ("Snowflake auto suspend 60 seconds or 5 minutes?")
