from django import forms

from access_atlas.jobs.models import Job, JobStatus

from .models import SiteVisit, Trip


class TripForm(forms.ModelForm):
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
        }


class SiteVisitForm(forms.ModelForm):
    class Meta:
        model = SiteVisit
        fields = ["site", "planned_order", "status", "notes"]


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
