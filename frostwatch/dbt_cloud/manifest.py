"""Parse a dbt manifest.json to extract model metadata.

FrostWatch uses the manifest to enrich the dbt Models page with owner,
description, materialization type, and tags — information that isn't
available in Snowflake's QUERY_HISTORY.

Supported manifest schema versions: v7–v12 (dbt Core 1.4+).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def parse_manifest(source: str | bytes | Path) -> list[dict]:
    """Parse a dbt manifest.json and return a list of model metadata dicts.

    Args:
        source: Path to manifest.json, a JSON string, or raw bytes.

    Returns:
        List of dicts with keys:
            model_name, project_name, owner, description,
            materialization, tags, schema_name, database_name.
        Only ``model.*`` nodes are returned; seeds, tests, and snapshots
        are excluded.
    """
    if isinstance(source, Path):
        raw = source.read_text(encoding="utf-8")
    elif isinstance(source, bytes):
        raw = source.decode("utf-8")
    else:
        raw = source

    manifest: dict[str, Any] = json.loads(raw)
    nodes: dict[str, Any] = manifest.get("nodes") or {}
    sources: dict[str, Any] = manifest.get("sources") or {}  # noqa: F841 — reserved for future use
    metadata: dict[str, Any] = manifest.get("metadata") or {}
    project_name: str = metadata.get("project_id") or metadata.get("project_name") or ""

    results: list[dict] = []
    for node_id, node in nodes.items():
        if not node_id.startswith("model."):
            continue
        if not isinstance(node, dict):
            continue

        name: str = node.get("name") or node_id.rsplit(".", 1)[-1]
        config: dict = node.get("config") or {}
        meta: dict = node.get("meta") or {}

        # Owner — check meta.owner first, then config.meta.owner
        owner: str | None = meta.get("owner") or (config.get("meta") or {}).get("owner") or None

        # Materialization
        materialization: str | None = config.get("materialized") or None

        # Tags — merge node-level and config-level tags
        node_tags: list = node.get("tags") or []
        config_tags: list = config.get("tags") or []
        all_tags = sorted({str(t) for t in node_tags + config_tags})
        tags_json: str | None = json.dumps(all_tags) if all_tags else None

        results.append(
            {
                "model_name": name,
                "project_name": project_name or _infer_project(node_id),
                "owner": owner,
                "description": node.get("description") or None,
                "materialization": materialization,
                "tags": tags_json,
                "schema_name": node.get("schema") or None,
                "database_name": node.get("database") or None,
            }
        )

    return results


def _infer_project(node_id: str) -> str:
    """Extract project name from a node_id like 'model.<project>.<model>'."""
    parts = node_id.split(".")
    return parts[1] if len(parts) >= 3 else ""
