from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.utils import timezone

HISTORY_FIELD_NAMES = {
    "history_id",
    "history_date",
    "history_change_reason",
    "history_type",
    "history_user",
    "history_user_id",
}


@dataclass(frozen=True)
class HistoryDiffRow:
    field_name: str
    label: str
    before_display: str
    after_display: str


@dataclass(frozen=True)
class HistoryJsonLine:
    text: str
    changed: bool


@dataclass(frozen=True)
class HistoryDiff:
    before_json: str
    after_json: str
    before_json_lines: list[HistoryJsonLine]
    after_json_lines: list[HistoryJsonLine]
    rows: list[HistoryDiffRow]
    previous_missing: bool


def _normalise_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, models.Model):
        try:
            return str(value)
        except ObjectDoesNotExist:
            object_type = value._meta.verbose_name.title()
            object_id = str(value.pk) if value.pk is not None else ""
            return f"{object_type} {object_id}".strip()
    if isinstance(value, tuple):
        return [_normalise_value(item) for item in value]
    if isinstance(value, list):
        return [_normalise_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _normalise_value(item) for key, item in value.items()}
    return value


def _display_value(value: Any) -> str:
    return json.dumps(
        _normalise_value(value),
        default=str,
        indent=2 if isinstance(value, (dict, list, tuple)) else None,
        sort_keys=True,
    )


def _json_block(data: dict[str, Any]) -> str:
    return json.dumps(
        {key: _normalise_value(value) for key, value in data.items()},
        default=str,
        indent=2,
        sort_keys=True,
    )


def _highlight_json_lines(
    before_json: str,
    after_json: str,
    changed_field_names: set[str],
) -> tuple[list[HistoryJsonLine], list[HistoryJsonLine]]:
    def line_changed(line: str) -> bool:
        stripped_line = line.strip()
        return any(
            stripped_line.startswith(f'"{field_name}":')
            for field_name in changed_field_names
        )

    return (
        [
            HistoryJsonLine(text=line, changed=line_changed(line))
            for line in before_json.splitlines()
        ],
        [
            HistoryJsonLine(text=line, changed=line_changed(line))
            for line in after_json.splitlines()
        ],
    )


def history_record_data(record) -> dict[str, Any]:
    """Return business fields from a simple-history record for diff rendering."""
    data = {}
    for field in record._meta.fields:
        if field.name in HISTORY_FIELD_NAMES or field.name == "id":
            continue
        # Historical FK rows may outlive their related live rows. Use the raw
        # stored key so diffs remain renderable and historically stable.
        value = (
            getattr(record, field.attname)
            if isinstance(field, models.ForeignKey)
            else getattr(record, field.name)
        )
        if isinstance(value, datetime):
            value = timezone.localtime(value) if timezone.is_aware(value) else value
        data[field.name] = value
    return data


def history_field_labels(record) -> dict[str, str]:
    return {
        field.name: str(field.verbose_name).title()
        for field in record._meta.fields
        if field.name not in HISTORY_FIELD_NAMES and field.name != "id"
    }


def build_history_diff(record, previous_record=None) -> HistoryDiff:
    """Build a NetBox-style before/after diff for a simple-history record."""
    current_data = history_record_data(record)
    previous_data = history_record_data(previous_record) if previous_record else {}
    previous_missing = record.history_type == "~" and previous_record is None

    if record.history_type == "+":
        before_data = {}
        after_data = current_data
    elif record.history_type == "-":
        before_data = current_data
        after_data = {}
    else:
        before_data = previous_data
        after_data = current_data

    labels = history_field_labels(record)
    field_names = list(after_data)
    field_names.extend(name for name in before_data if name not in after_data)
    rows = [
        HistoryDiffRow(
            field_name=field_name,
            label=labels.get(field_name, field_name.replace("_", " ").title()),
            before_display=_display_value(before_data.get(field_name)),
            after_display=_display_value(after_data.get(field_name)),
        )
        for field_name in field_names
        if before_data.get(field_name) != after_data.get(field_name)
    ]

    before_json = _json_block(before_data)
    after_json = _json_block(after_data)
    before_json_lines, after_json_lines = _highlight_json_lines(
        before_json,
        after_json,
        {row.field_name for row in rows},
    )

    return HistoryDiff(
        before_json=before_json,
        after_json=after_json,
        before_json_lines=before_json_lines,
        after_json_lines=after_json_lines,
        rows=rows,
        previous_missing=previous_missing,
    )
