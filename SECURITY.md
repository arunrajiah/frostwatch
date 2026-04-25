# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅ Yes    |

## Reporting a Vulnerability

**Please do not report security vulnerabilities via public GitHub issues.**

Email the maintainer directly at **arunrajiah@gmail.com** with:

1. A description of the vulnerability and its potential impact
2. Steps to reproduce or a proof-of-concept
3. Affected versions
4. Any suggested remediation (optional)

You will receive an acknowledgement within **48 hours** and a resolution timeline within **7 days**.

We ask that you:
- Give us reasonable time to fix the issue before public disclosure
- Avoid accessing or modifying data that does not belong to you during testing
- Not perform denial-of-service attacks

## Scope

In scope:
- The FrostWatch Python backend (`frostwatch/`)
- The React frontend (`frontend/`)
- The Docker deployment configuration
- Dependencies pulled in by `pyproject.toml` or `frontend/package.json`

Out of scope:
- Vulnerabilities in Snowflake itself
- Vulnerabilities in third-party LLM APIs (Anthropic, OpenAI, Gemini)
- Social engineering attacks

## Security Design Notes

FrostWatch is designed to run **inside your own infrastructure**. It makes outbound connections only to:
- Your Snowflake account (using credentials you supply)
- Your chosen LLM provider API (using a key you supply)
- Your Slack webhook or SMTP server (if configured)

FrostWatch does **not** phone home, collect telemetry, or transmit data to any service operated by the maintainer.

Credentials (Snowflake password, LLM API key) are stored in `~/.frostwatch/config.yaml` on the host filesystem. Protect that file with appropriate filesystem permissions (`chmod 600`).
