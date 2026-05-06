from django import forms
from django_tomselect.forms import TomSelectModelChoiceField

from access_atlas.core.tomselect import (
    job_template_tomselect_config,
    site_tomselect_config,
    work_programme_tomselect_config,
)

from .models import (
    Job,
    JobStatus,
    JobTemplate,
    Requirement,
    TemplateRequirement,
    WorkProgramme,
)


class JobTemplateForm(forms.ModelForm):
    class Meta:
        model = JobTemplate
        fields = [
            "title",
            "description",
            "estimated_duration_minutes",
            "priority",
            "notes",
            "is_active",
        ]
        labels = {
            "priority": "Default Priority",
        }


class TemplateRequirementForm(forms.ModelForm):
    class Meta:
        model = TemplateRequirement
        fields = ["requirement_type", "name", "quantity", "notes", "is_required"]


class WorkProgrammeForm(forms.ModelForm):
    class Meta:
        model = WorkProgramme
        fields = ["name", "start_date", "end_date", "description"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }


class JobForm(forms.ModelForm):
    site = TomSelectModelChoiceField(config=site_tomselect_config())
    work_programme = TomSelectModelChoiceField(
        config=work_programme_tomselect_config(),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.is_assigned:
            return
        choices = [
            (value, label)
            for value, label in self.fields["status"].choices
            if value != JobStatus.ASSIGNED
        ]
        self.fields["status"].choices = choices

    class Meta:
        model = Job
        fields = [
            "site",
            "work_programme",
            "title",
            "description",
            "estimated_duration_minutes",
            "priority",
            "status",
            "closeout_note",
            "notes",
        ]
        labels = {
            "closeout_note": "Closeout note",
        }


class JobFromTemplateForm(forms.Form):
    site = TomSelectModelChoiceField(config=site_tomselect_config())
    template = TomSelectModelChoiceField(config=job_template_tomselect_config())

    def __init__(self, *args, **kwargs):
        kwargs.pop("site_queryset")
        super().__init__(*args, **kwargs)


class JobImportUploadForm(forms.Form):
    csv_file = forms.FileField(label="CSV file")


class JobTemplateImportUploadForm(forms.Form):
    csv_file = forms.FileField(label="CSV file")


class RequirementForm(forms.ModelForm):
    class Meta:
        model = Requirement
        fields = [
            "requirement_type",
            "name",
            "quantity",
            "notes",
            "is_required",
            "is_checked",
        ]
