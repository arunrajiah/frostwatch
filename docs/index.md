# FrostWatch

**AI-powered cost and query observability for Snowflake — open source and self-hostable.**

FrostWatch connects to your Snowflake account, pulls from `SNOWFLAKE.ACCOUNT_USAGE`, and gives you a dark-themed web dashboard with:

- 📊 **Cost breakdown** by warehouse, user, and query tag
- 🚨 **Anomaly detection** — spend spikes vs. a 21-day rolling baseline per warehouse
- 🤖 **AI explanations** — plain-English summaries for each anomaly (BYO LLM: Claude, GPT-4o, Gemini, or local Ollama)
- 📦 **dbt model costs** — per-model credit and performance breakdown parsed from `query_tag`
- 📬 **Weekly digest** delivered to Slack or email
- 🔌 **REST API** for integration with your own tooling

## Quick start

=== "pip"

    ```bash
    pip install frostwatch
    frostwatch config init    # creates ~/.frostwatch/config.yaml
    frostwatch serve          # starts on http://localhost:8000
    ```

=== "Docker"

    ```bash
    docker run -p 8000:8000 \
      -e FROSTWATCH_SNOWFLAKE_ACCOUNT=xy12345.us-east-1 \
      -e FROSTWATCH_SNOWFLAKE_USER=myuser \
      -e FROSTWATCH_SNOWFLAKE_PASSWORD=mypass \
      -e FROSTWATCH_LLM_API_KEY=sk-ant-... \
      ghcr.io/arunrajiah/frostwatch
    ```

=== "docker compose"

    ```bash
    curl -O https://raw.githubusercontent.com/arunrajiah/frostwatch/main/docker-compose.yml
    # Edit docker-compose.yml to set your env vars
    docker compose up
    ```

Then open [http://localhost:8000](http://localhost:8000).

## Links

- [GitHub](https://github.com/arunrajiah/frostwatch)
- [PyPI](https://pypi.org/project/frostwatch/)
- [Docker Image](https://ghcr.io/arunrajiah/frostwatch)
