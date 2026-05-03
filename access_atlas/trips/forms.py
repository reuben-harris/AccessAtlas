from datetime import datetime, timedelta

from django import forms
from django.forms.models import construct_instance
from django.utils import timezone

from access_atlas.jobs.models import Job, JobStatus

from .models import SiteVisit, SiteVisitStatus, Trip
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
    class Meta:
        model = Trip
        fields = [
            "name",
            "start_date",
            "end_date",
            "trip_leader",
            "team_members",
            "notes",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "team_members": forms.CheckboxSelectMultiple(
                attrs={"class": "form-selectgroup-input"}
            ),
        }


class TripDayChoiceField(forms.ChoiceField):
    def validate(self, value):
        forms.Field.validate(self, value)


class SiteVisitForm(forms.ModelForm):
    planned_day = TripDayChoiceField(
        label="Visit day",
        widget=forms.RadioSelect,
    )
    planned_start_time = forms.TimeField(
        required=False,
        label="Start time",
        input_formats=["%H:%M"],
        widget=forms.TimeInput(attrs={"type": "time"}),
    )
    planned_end_time = forms.TimeField(
        required=False,
        label="End time",
        input_formats=["%H:%M"],
        widget=forms.TimeInput(attrs={"type": "time"}),
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
        trip = getattr(self.instance, "trip", None) if self.instance.trip_id else trip
        if trip and trip.start_date and trip.end_date:
            self.fields["planned_day"].choices = list(self.trip_day_choices(trip))
        else:
            self.fields["planned_day"].choices = []
        self.order_fields(
            [
                "site",
                "planned_day",
                "planned_start_time",
                "planned_end_time",
                "status",
                "notes",
            ]
        )

        initial_day = self.instance.planned_day
        if initial_day is None and self.instance.planned_start:
            initial_day = SiteVisit.planned_date(self.instance.planned_start)
        if initial_day is not None:
            self.initial["planned_day"] = initial_day.isoformat()
        if self.instance.planned_start:
            self.initial["planned_start_time"] = timezone.localtime(
                self.instance.planned_start
            ).strftime("%H:%M")
        if self.instance.planned_end:
            self.initial["planned_end_time"] = timezone.localtime(
                self.instance.planned_end
            ).strftime("%H:%M")

    @staticmethod
    def trip_day_choices(trip: Trip):
        current_day = trip.start_date
        while current_day <= trip.end_date:
            label = current_day.strftime("%a %d %b %Y")
            yield (current_day.isoformat(), label)
            current_day += timedelta(days=1)

    @staticmethod
    def combine_day_and_time(planned_day, planned_time):
        naive_value = datetime.combine(planned_day, planned_time)
        return timezone.make_aware(naive_value, timezone.get_current_timezone())

    def clean(self):
        cleaned_data = super().clean()
        trip = self.instance.trip
        planned_day_value = cleaned_data.get("planned_day")
        planned_start_time = cleaned_data.get("planned_start_time")
        planned_end_time = cleaned_data.get("planned_end_time")

        planned_day = None
        if planned_day_value:
            try:
                planned_day = datetime.strptime(planned_day_value, "%Y-%m-%d").date()
            except ValueError:
                self.add_error("planned_day", "Choose a valid trip day.")
        else:
            self.add_error("planned_day", "Choose a trip day.")

        if not trip:
            return cleaned_data

        trip_date_message = f"Must be between {trip.start_date} and {trip.end_date}."
        if planned_day and (
            planned_day < trip.start_date or planned_day > trip.end_date
        ):
            self.add_error("planned_day", trip_date_message)

        if planned_end_time and not planned_start_time:
            self.add_error("planned_start_time", "An end time requires a start time.")
        if (
            planned_start_time
            and planned_end_time
            and planned_end_time <= planned_start_time
        ):
            self.add_error("planned_end_time", "End time must be after start time.")

        planned_start = None
        planned_end = None
        if planned_day and planned_start_time:
            planned_start = self.combine_day_and_time(planned_day, planned_start_time)
        if planned_day and planned_end_time:
            planned_end = self.combine_day_and_time(planned_day, planned_end_time)

        cleaned_data["planned_day"] = planned_day
        cleaned_data["planned_start"] = planned_start
        cleaned_data["planned_end"] = planned_end
        self.instance.planned_day = planned_day
        self.instance.planned_start = planned_start
        self.instance.planned_end = planned_end

        try:
            self.instance.clean()
        except forms.ValidationError as exc:
            if hasattr(exc, "message_dict"):
                field_map = {
                    "planned_start": "planned_start_time",
                    "planned_end": "planned_end_time",
                }
                for field_name, errors in exc.message_dict.items():
                    target_field = field_map.get(field_name, field_name)
                    for error in errors:
                        self.add_error(target_field, error)
            else:
                self.add_error(None, exc)

        return cleaned_data

    def _post_clean(self):
        opts = self._meta
        self.instance = construct_instance(
            self,
            self.instance,
            opts.fields,
            opts.exclude,
        )
        if self._validate_unique:
            self.validate_unique()

    def save(self, commit=True):
        self.instance.planned_day = self.cleaned_data.get("planned_day")
        self.instance.planned_start = self.cleaned_data.get("planned_start")
        self.instance.planned_end = self.cleaned_data.get("planned_end")
        return super().save(commit=commit)

    class Meta:
        model = SiteVisit
        fields = [
            "site",
            "planned_day",
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
