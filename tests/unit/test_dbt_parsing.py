"""Unit tests for dbt query tag parsing."""
from __future__ import annotations

import pytest

from frostwatch.api.routes.sync import _extract_dbt_model


@pytest.mark.parametrize(
    "query_tag, expected",
    [
        # Standard dbt flat format
        (
            '{"app": "dbt", "node_id": "model.my_project.my_model"}',
            "my_model",
        ),
        # dbt+snowflake variant
        (
            '{"app": "dbt+snowflake", "dbt_version": "1.5.0", "node_id": "model.analytics.orders"}',
            "orders",
        ),
        # Nested dbt_snowflake_query_tags format
        (
            '{"dbt_snowflake_query_tags": {"app": "dbt", "node_id": "model.proj.customers"}}',
            "customers",
        ),
        # Not a dbt query — no app key
        (
            '{"job": "etl_pipeline"}',
            None,
        ),
        # Not a dbt query — different app
        (
            '{"app": "airflow", "node_id": "model.proj.foo"}',
            None,
        ),
        # node_id is not a model (could be a seed or snapshot)
        (
            '{"app": "dbt", "node_id": "seed.proj.seed_table"}',
            None,
        ),
        # Empty string
        ("", None),
        # None
        (None, None),
        # Invalid JSON
        ("not-json", None),
        # Plain string tag (non-dbt user tag)
        ("etl_run_2024", None),
    ],
)
def test_extract_dbt_model(query_tag: str | None, expected: str | None) -> None:
    assert _extract_dbt_model(query_tag) == expected
