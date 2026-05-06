from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from access_atlas.core.imports import has_import_row_errors, read_uploaded_csv_rows
from access_atlas.sites.models import Site

from .models import Job, JobStatus, JobTemplate, WorkProgramme
from .services import create_job_from_template

REQUIRED_HEADERS = ["site_code", "template_title"]
OPTIONAL_HEADERS = ["status", "closeout_note", "work_programme"]
IMPORTABLE_STATUSES = {
    JobStatus.UNASSIGNED,
    JobStatus.COMPLETED,
    JobStatus.CANCELLED,
}
SESSION_KEY = "job_import_rows"


@dataclass(frozen=True)
class JobImportRow:
    row_number: int
    site_code: str
    template_title: str
    status: str = JobStatus.UNASSIGNED
    closeout_note: str = ""
    work_programme_name: str = ""
    site: Site | None = None
    template: JobTemplate | None = None
    work_programme: WorkProgramme | None = None
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
            "status": self.status,
            "closeout_note": self.closeout_note,
            "work_programme_id": self.work_programme.pk
            if self.work_programme
            else None,
            "work_programme_name": self.work_programme_name,
            "error": self.error,
        }

    @property
    def status_label(self) -> str:
        try:
            return JobStatus(self.status).label
        except ValueError:
            return self.status or "-"


def normalize_import_status(value: str) -> str:
    normalized = value.strip().lower().replace(" ", "_")
    return normalized or JobStatus.UNASSIGNED


def parse_job_import_csv(uploaded_file) -> list[JobImportRow]:
    rows, error = read_uploaded_csv_rows(
        uploaded_file,
        required_headers=REQUIRED_HEADERS,
        optional_headers=OPTIONAL_HEADERS,
    )
    if error:
        return [
            JobImportRow(
                row_number=0,
                site_code="",
                template_title="",
                error=error,
            )
        ]

    result = []
    for index, row in enumerate(rows, start=2):
        site_code = (row.get("site_code") or "").strip()
        template_title = (row.get("template_title") or "").strip()
        status = normalize_import_status(row.get("status") or "")
        closeout_note = (row.get("closeout_note") or "").strip()
        work_programme_name = (row.get("work_programme") or "").strip()

        if not site_code:
            result.append(
                JobImportRow(
                    index,
                    site_code,
                    template_title,
                    status=status,
                    closeout_note=closeout_note,
                    work_programme_name=work_programme_name,
                    error="Missing site_code.",
                )
            )
            continue
        if not template_title:
            result.append(
                JobImportRow(
                    index,
                    site_code,
                    template_title,
                    status=status,
                    closeout_note=closeout_note,
                    work_programme_name=work_programme_name,
                    error="Missing template_title.",
                )
            )
            continue
        if status == JobStatus.ASSIGNED:
            result.append(
                JobImportRow(
                    index,
                    site_code,
                    template_title,
                    status=status,
                    closeout_note=closeout_note,
                    work_programme_name=work_programme_name,
                    error="Assigned jobs must be planned through a site visit.",
                )
            )
            continue
        if status not in IMPORTABLE_STATUSES:
            result.append(
                JobImportRow(
                    index,
                    site_code,
                    template_title,
                    status=status,
                    closeout_note=closeout_note,
                    work_programme_name=work_programme_name,
                    error="Unknown status.",
                )
            )
            continue
        if status in {JobStatus.COMPLETED, JobStatus.CANCELLED} and not closeout_note:
            result.append(
                JobImportRow(
                    index,
                    site_code,
                    template_title,
                    status=status,
                    closeout_note=closeout_note,
                    work_programme_name=work_programme_name,
                    error="closeout_note is required for completed or cancelled jobs.",
                )
            )
            continue
        site = Site.objects.filter(code__iexact=site_code).first()
        if site is None:
            result.append(
                JobImportRow(
                    index,
                    site_code,
                    template_title,
                    status=status,
                    closeout_note=closeout_note,
                    work_programme_name=work_programme_name,
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
                    status=status,
                    closeout_note=closeout_note,
                    work_programme_name=work_programme_name,
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
                    status=status,
                    closeout_note=closeout_note,
                    work_programme_name=work_programme_name,
                    error="template_title matches more than one active job template.",
                )
            )
            continue

        work_programme = None
        if work_programme_name:
            work_programme = WorkProgramme.objects.filter(
                name__iexact=work_programme_name
            ).first()
            if work_programme is None:
                result.append(
                    JobImportRow(
                        index,
                        site_code,
                        template_title,
                        status=status,
                        closeout_note=closeout_note,
                        work_programme_name=work_programme_name,
                        error="Unknown work_programme.",
                    )
                )
                continue

        result.append(
            JobImportRow(
                row_number=index,
                site_code=site_code,
                template_title=template_title,
                status=status,
                closeout_note=closeout_note,
                work_programme_name=work_programme_name,
                site=site,
                template=templates.get(),
                work_programme=work_programme,
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
    return has_import_row_errors(rows)


def rows_from_session(session_rows: list[dict[str, object]]) -> list[JobImportRow]:
    rows = []
    for row in session_rows:
        site_id = row.get("site_id")
        template_id = row.get("template_id")
        work_programme_id = row.get("work_programme_id")
        site = Site.objects.filter(pk=site_id).first() if site_id else None
        template = (
            JobTemplate.objects.filter(pk=template_id).first() if template_id else None
        )
        work_programme = (
            WorkProgramme.objects.filter(pk=work_programme_id).first()
            if work_programme_id
            else None
        )
        rows.append(
            JobImportRow(
                row_number=int(row["row_number"]),
                site_code=str(row["site_code"]),
                template_title=str(row["template_title"]),
                status=str(row.get("status") or JobStatus.UNASSIGNED),
                closeout_note=str(row.get("closeout_note") or ""),
                work_programme_name=str(row.get("work_programme_name") or ""),
                site=site,
                template=template,
                work_programme=work_programme,
                error=str(row.get("error") or ""),
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
            work_programme=row.work_programme,
        )
        if row.status != JobStatus.UNASSIGNED or row.closeout_note:
            job.status = row.status
            job.closeout_note = row.closeout_note
            job._change_reason = "Imported from CSV using job template"
            job.save(update_fields=["status", "closeout_note", "updated_at"])
        jobs.append(job)
    return jobs
