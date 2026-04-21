from __future__ import annotations

import csv
from dataclasses import dataclass
from io import StringIO

from django.db import transaction

from access_atlas.sites.models import Site

from .models import Job, JobTemplate
from .services import create_job_from_template

REQUIRED_HEADERS = ["site_code", "template_title"]
SESSION_KEY = "job_import_rows"


@dataclass(frozen=True)
class JobImportRow:
    row_number: int
    site_code: str
    template_title: str
    site: Site | None = None
    template: JobTemplate | None = None
    error: str = ""

    @property
    def is_valid(self) -> bool:
        return not self.error and self.site is not None and self.template is not None

    def as_session_data(self) -> dict[str, object]:
        return {
            "row_number": self.row_number,
            "site_id": self.site.pk if self.site else None,
            "template_id": self.template.pk if self.template else None,
            "site_code": self.site_code,
            "template_title": self.template_title,
        }


def parse_job_import_csv(uploaded_file) -> list[JobImportRow]:
    content = uploaded_file.read()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return [
            JobImportRow(
                row_number=0,
                site_code="",
                template_title="",
                error="CSV file must be UTF-8 encoded.",
            )
        ]

    reader = csv.DictReader(StringIO(text))
    headers = reader.fieldnames or []
    if headers != REQUIRED_HEADERS:
        return [
            JobImportRow(
                row_number=0,
                site_code="",
                template_title="",
                error="CSV headers must be exactly: site_code,template_title.",
            )
        ]

    rows = list(reader)
    seen_rows: set[tuple[str, str]] = set()
    result = []
    for index, row in enumerate(rows, start=2):
        site_code = (row.get("site_code") or "").strip()
        template_title = (row.get("template_title") or "").strip()
        key = (site_code.lower(), template_title.lower())

        if not site_code:
            result.append(
                JobImportRow(
                    index, site_code, template_title, error="Missing site_code."
                )
            )
            continue
        if not template_title:
            result.append(
                JobImportRow(
                    index,
                    site_code,
                    template_title,
                    error="Missing template_title.",
                )
            )
            continue
        if key in seen_rows:
            result.append(
                JobImportRow(
                    index,
                    site_code,
                    template_title,
                    error="Duplicate site_code/template_title row in this file.",
                )
            )
            continue
        seen_rows.add(key)

        site = Site.objects.filter(code__iexact=site_code).first()
        if site is None:
            result.append(
                JobImportRow(
                    index,
                    site_code,
                    template_title,
                    error="Unknown site_code.",
                )
            )
            continue

        templates = JobTemplate.objects.filter(
            title__iexact=template_title,
            is_active=True,
        )
        template_count = templates.count()
        if template_count == 0:
            result.append(
                JobImportRow(
                    index,
                    site_code,
                    template_title,
                    error="Unknown active template_title.",
                )
            )
            continue
        if template_count > 1:
            result.append(
                JobImportRow(
                    index,
                    site_code,
                    template_title,
                    error="template_title matches more than one active job template.",
                )
            )
            continue

        result.append(
            JobImportRow(
                row_number=index,
                site_code=site_code,
                template_title=template_title,
                site=site,
                template=templates.get(),
            )
        )

    if not result:
        return [
            JobImportRow(
                row_number=0,
                site_code="",
                template_title="",
                error="CSV file does not contain any job rows.",
            )
        ]

    return result


def has_import_errors(rows: list[JobImportRow]) -> bool:
    return any(not row.is_valid for row in rows)


def rows_from_session(session_rows: list[dict[str, object]]) -> list[JobImportRow]:
    rows = []
    for row in session_rows:
        site = Site.objects.get(pk=row["site_id"])
        template = JobTemplate.objects.get(pk=row["template_id"])
        rows.append(
            JobImportRow(
                row_number=int(row["row_number"]),
                site_code=str(row["site_code"]),
                template_title=str(row["template_title"]),
                site=site,
                template=template,
            )
        )
    return rows


@transaction.atomic
def create_jobs_from_import_rows(rows: list[JobImportRow]) -> list[Job]:
    jobs = []
    for row in rows:
        if not row.is_valid:
            continue
        job = create_job_from_template(
            site=row.site,
            template=row.template,
            change_reason="Imported from CSV using job template",
        )
        jobs.append(job)
    return jobs
