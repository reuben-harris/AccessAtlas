from __future__ import annotations

import csv
from dataclasses import dataclass
from io import StringIO

from django.db import transaction

from .models import JobTemplate, Priority

REQUIRED_HEADERS = ["title"]
OPTIONAL_HEADERS = [
    "description",
    "estimated_duration_minutes",
    "default_priority",
    "notes",
    "is_active",
]
SUPPORTED_HEADERS = REQUIRED_HEADERS + OPTIONAL_HEADERS
SESSION_KEY = "job_template_import_rows"
TRUTHY_VALUES = {"1", "true", "yes", "y", "on"}
FALSY_VALUES = {"0", "false", "no", "n", "off"}


@dataclass(frozen=True)
class JobTemplateImportRow:
    row_number: int
    title: str
    description: str = ""
    estimated_duration_minutes: int | None = None
    priority: str = Priority.NORMAL
    notes: str = ""
    is_active: bool = True
    error: str = ""

    @property
    def is_valid(self) -> bool:
        return not self.error

    def as_session_data(self) -> dict[str, object]:
        return {
            "row_number": self.row_number,
            "title": self.title,
            "description": self.description,
            "estimated_duration_minutes": self.estimated_duration_minutes,
            "priority": self.priority,
            "notes": self.notes,
            "is_active": self.is_active,
            "error": self.error,
        }

    @property
    def priority_label(self) -> str:
        try:
            return Priority(self.priority).label
        except ValueError:
            return self.priority or "-"

    @property
    def active_label(self) -> str:
        return "Yes" if self.is_active else "No"


def parse_optional_positive_int(value: str) -> tuple[int | None, str]:
    cleaned = value.strip()
    if not cleaned:
        return None, ""
    try:
        parsed = int(cleaned)
    except ValueError:
        return None, "estimated_duration_minutes must be a positive integer."
    if parsed <= 0:
        return None, "estimated_duration_minutes must be a positive integer."
    return parsed, ""


def parse_optional_bool(value: str) -> tuple[bool, str]:
    cleaned = value.strip().lower()
    if not cleaned:
        return True, ""
    if cleaned in TRUTHY_VALUES:
        return True, ""
    if cleaned in FALSY_VALUES:
        return False, ""
    return True, "is_active must be true or false."


def parse_job_template_import_csv(uploaded_file) -> list[JobTemplateImportRow]:
    content = uploaded_file.read()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return [
            JobTemplateImportRow(
                row_number=0,
                title="",
                error="CSV file must be UTF-8 encoded.",
            )
        ]

    reader = csv.DictReader(StringIO(text))
    headers = reader.fieldnames or []
    if any(header not in SUPPORTED_HEADERS for header in headers) or any(
        header not in headers for header in REQUIRED_HEADERS
    ):
        return [
            JobTemplateImportRow(
                row_number=0,
                title="",
                error=(
                    "CSV headers must include title and may also include "
                    "description,estimated_duration_minutes,default_priority,"
                    "notes,is_active."
                ),
            )
        ]

    rows = list(reader)
    existing_titles = {
        title.casefold()
        for title in JobTemplate.objects.values_list("title", flat=True)
    }
    seen_titles: set[str] = set()
    result = []
    for index, row in enumerate(rows, start=2):
        title = (row.get("title") or "").strip()
        description = (row.get("description") or "").strip()
        estimate, estimate_error = parse_optional_positive_int(
            row.get("estimated_duration_minutes") or ""
        )
        priority = (row.get("default_priority") or Priority.NORMAL).strip().lower()
        notes = (row.get("notes") or "").strip()
        is_active, active_error = parse_optional_bool(row.get("is_active") or "")
        folded_title = title.casefold()

        error = ""
        if not title:
            error = "Missing title."
        elif folded_title in existing_titles:
            error = "A job template with this title already exists."
        elif folded_title in seen_titles:
            error = "Duplicate title in this file."
        elif priority not in Priority.values:
            error = "Unknown default_priority."
        elif estimate_error:
            error = estimate_error
        elif active_error:
            error = active_error

        if folded_title:
            seen_titles.add(folded_title)

        result.append(
            JobTemplateImportRow(
                row_number=index,
                title=title,
                description=description,
                estimated_duration_minutes=estimate,
                priority=priority,
                notes=notes,
                is_active=is_active,
                error=error,
            )
        )

    if not result:
        return [
            JobTemplateImportRow(
                row_number=0,
                title="",
                error="CSV file does not contain any job template rows.",
            )
        ]

    return result


def has_template_import_errors(rows: list[JobTemplateImportRow]) -> bool:
    return any(not row.is_valid for row in rows)


def template_rows_from_session(
    session_rows: list[dict[str, object]],
) -> list[JobTemplateImportRow]:
    rows = []
    for row in session_rows:
        estimate = row.get("estimated_duration_minutes")
        rows.append(
            JobTemplateImportRow(
                row_number=int(row["row_number"]),
                title=str(row["title"]),
                description=str(row.get("description") or ""),
                estimated_duration_minutes=int(estimate)
                if estimate not in (None, "")
                else None,
                priority=str(row.get("priority") or Priority.NORMAL),
                notes=str(row.get("notes") or ""),
                is_active=bool(row.get("is_active", True)),
                error=str(row.get("error") or ""),
            )
        )
    return rows


@transaction.atomic
def create_job_templates_from_import_rows(
    rows: list[JobTemplateImportRow],
) -> list[JobTemplate]:
    templates = []
    for row in rows:
        if not row.is_valid:
            continue
        template = JobTemplate(
            title=row.title,
            description=row.description,
            estimated_duration_minutes=row.estimated_duration_minutes,
            priority=row.priority,
            notes=row.notes,
            is_active=row.is_active,
        )
        template._change_reason = "Imported job template from CSV"
        template.save()
        templates.append(template)
    return templates
