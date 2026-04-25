from django import forms

from access_atlas.jobs.models import Job, JobStatus

from .models import SiteVisit, SiteVisitStatus, Trip, TripStatus
from .services import (
    JOB_OUTCOME_CANCELLED,
    JOB_OUTCOME_COMPLETED,
    JOB_OUTCOME_RETURN,
    get_trip_assignments,
)


class TripCloseoutJobOutcome:
    COMPLETED = JOB_OUTCOME_COMPLETED
    RETURN = JOB_OUTCOME_RETURN
    CANCELLED = JOB_OUTCOME_CANCELLED

    CHOICES = [
        (COMPLETED, "Completed"),
        (RETURN, "Return to unassigned"),
        (CANCELLED, "Cancelled"),
    ]


class TripForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["status"].choices = [
            (TripStatus.DRAFT, TripStatus.DRAFT.label),
            (TripStatus.PLANNED, TripStatus.PLANNED.label),
        ]

    class Meta:
        model = Trip
        fields = [
            "name",
            "start_date",
            "end_date",
            "trip_leader",
            "team_members",
            "status",
            "notes",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "team_members": forms.CheckboxSelectMultiple(
                attrs={"class": "form-selectgroup-input"}
            ),
        }


class SiteVisitForm(forms.ModelForm):
    planned_start = forms.SplitDateTimeField(
        required=False,
        label="Planned start",
        input_date_formats=["%Y-%m-%d"],
        input_time_formats=["%H:%M"],
        widget=forms.SplitDateTimeWidget(
            date_attrs={"type": "date"},
            time_attrs={"type": "time"},
            date_format="%Y-%m-%d",
            time_format="%H:%M",
        ),
    )
    planned_end = forms.SplitDateTimeField(
        required=False,
        label="Planned end",
        input_date_formats=["%Y-%m-%d"],
        input_time_formats=["%H:%M"],
        widget=forms.SplitDateTimeWidget(
            date_attrs={"type": "date"},
            time_attrs={"type": "time"},
            date_format="%Y-%m-%d",
            time_format="%H:%M",
        ),
    )

    def __init__(self, *args, **kwargs):
        trip = kwargs.pop("trip", None)
        super().__init__(*args, **kwargs)
        self.fields["site"].widget.attrs.update(
            {
                "data-searchable-select": "true",
                "data-search-placeholder": "Search sites",
            }
        )
        if trip is not None:
            self.instance.trip = trip

    def clean(self):
        cleaned_data = super().clean()
        planned_start = cleaned_data.get("planned_start")
        planned_end = cleaned_data.get("planned_end")
        trip = self.instance.trip

        if planned_end and not planned_start:
            self.add_error("planned_start", "A planned end requires a planned start.")
        if planned_start and planned_end and planned_end <= planned_start:
            self.add_error("planned_end", "Planned end must be after planned start.")
        if not trip:
            return cleaned_data

        trip_date_message = f"Must be between {trip.start_date} and {trip.end_date}."
        if planned_start:
            planned_start_date = SiteVisit.planned_date(planned_start)
            if (
                planned_start_date < trip.start_date
                or planned_start_date > trip.end_date
            ):
                self.add_error("planned_start", trip_date_message)
        if planned_end:
            planned_end_date = SiteVisit.planned_date(planned_end)
            if planned_end_date < trip.start_date or planned_end_date > trip.end_date:
                self.add_error("planned_end", trip_date_message)
        return cleaned_data

    class Meta:
        model = SiteVisit
        fields = [
            "site",
            "planned_start",
            "planned_end",
            "status",
            "notes",
        ]


class AssignJobForm(forms.Form):
    job = forms.ModelChoiceField(queryset=Job.objects.none())

    def __init__(self, *args, **kwargs):
        site = kwargs.pop("site")
        super().__init__(*args, **kwargs)
        self.fields["job"].queryset = Job.objects.filter(
            site=site,
            status=JobStatus.UNASSIGNED,
            site_visit_assignment__isnull=True,
        )
        self.fields["job"].widget.attrs.update(
            {
                "class": "form-select",
                "data-searchable-select": "true",
                "data-search-placeholder": "Search jobs",
            }
        )


class TripCloseoutForm(forms.Form):
    def __init__(self, *args, **kwargs):
        self.trip = kwargs.pop("trip")
        super().__init__(*args, **kwargs)
        for site_visit in self.trip.site_visits.select_related("site").all():
            initial_status = (
                site_visit.status
                if site_visit.status != SiteVisitStatus.PLANNED
                else SiteVisitStatus.COMPLETED
            )
            self.fields[self.site_visit_field(site_visit)] = forms.ChoiceField(
                label=str(site_visit.site),
                choices=[
                    (SiteVisitStatus.COMPLETED, SiteVisitStatus.COMPLETED.label),
                    (SiteVisitStatus.SKIPPED, SiteVisitStatus.SKIPPED.label),
                ],
                initial=initial_status,
                widget=forms.Select(attrs={"class": "form-select"}),
            )

        assignments = self.closeout_assignments()

        for assignment in assignments:
            self.fields[self.job_outcome_field(assignment)] = forms.ChoiceField(
                label=str(assignment.job),
                choices=TripCloseoutJobOutcome.CHOICES,
                initial=TripCloseoutJobOutcome.COMPLETED,
                widget=forms.Select(attrs={"class": "form-select"}),
            )
            self.fields[self.job_reason_field(assignment)] = forms.CharField(
                label=f"{assignment.job} cancellation reason",
                required=False,
                widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            )

    @staticmethod
    def site_visit_field(site_visit: SiteVisit) -> str:
        return f"site_visit_{site_visit.pk}"

    @staticmethod
    def job_outcome_field(assignment) -> str:
        return f"job_{assignment.pk}_outcome"

    @staticmethod
    def job_reason_field(assignment) -> str:
        return f"job_{assignment.pk}_cancelled_reason"

    def clean(self):
        cleaned_data = super().clean()
        assignments = self.closeout_assignments()
        site_visit_outcomes = {
            site_visit.pk: cleaned_data.get(self.site_visit_field(site_visit))
            for site_visit in self.trip.site_visits.all()
        }

        for assignment in assignments:
            outcome = cleaned_data.get(self.job_outcome_field(assignment))
            reason = cleaned_data.get(self.job_reason_field(assignment), "").strip()
            if outcome == TripCloseoutJobOutcome.CANCELLED and not reason:
                self.add_error(
                    self.job_reason_field(assignment),
                    "A cancelled job requires a reason.",
                )
            if (
                site_visit_outcomes.get(assignment.site_visit_id)
                == SiteVisitStatus.SKIPPED
                and outcome == TripCloseoutJobOutcome.COMPLETED
            ):
                self.add_error(
                    self.job_outcome_field(assignment),
                    "A job cannot be completed when its site visit is skipped.",
                )
        return cleaned_data

    def closeout_assignments(self):
        return get_trip_assignments(self.trip).filter(
            job__status__in=[JobStatus.PLANNED, JobStatus.UNASSIGNED]
        )

    def site_visit_fields(self):
        return [
            self[self.site_visit_field(site_visit)]
            for site_visit in self.trip.site_visits.select_related("site").all()
        ]

    def job_decision_fields(self):
        return [
            {
                "assignment": assignment,
                "outcome": self[self.job_outcome_field(assignment)],
                "reason": self[self.job_reason_field(assignment)],
            }
            for assignment in self.closeout_assignments()
        ]
