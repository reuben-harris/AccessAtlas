from __future__ import annotations

from .models import JobStatus

JOB_STATUS_COLORS = {
    JobStatus.UNASSIGNED: "#667382",
    JobStatus.ASSIGNED: "#206bc4",
    JobStatus.COMPLETED: "#2fb344",
    JobStatus.CANCELLED: "#d63939",
}
