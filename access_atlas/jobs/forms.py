from django import forms
from django_tomselect.forms import (
    TomSelectModelChoiceField,
    TomSelectModelMultipleChoiceField,
)

from access_atlas.core.tomselect import (
    job_template_tomselect_config,
    site_tomselect_config,
    unprogrammed_jobs_tomselect_config,
    work_programme_tomselect_config,
)
from access_atlas.core.widgets import DatePicker

from .models import (
    Job,
    JobStatus,
    JobTemplate,
    Requirement,
    TemplateRequirement,
    WorkProgramme,
)

ASSIGNED_JOB_CLOSEOUT_FIELD_DISABLED_REASON = (
    "This field is managed by trip closeout while the job is assigned to a trip."
)
ASSIGNED_JOB_SITE_DISABLED_REASON = (
    "Site cannot be changed while this job is assigned to a trip."
)


class JobTemplateForm(forms.ModelForm):
    class Meta:
        model = JobTemplate
        fields = [
            "title",
            "description",
            "estimated_duration_minutes",
            "priority",
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
            "start_date": DatePicker(),
            "end_date": DatePicker(),
        }


class AssignWorkProgrammeJobForm(forms.Form):
    jobs = TomSelectModelMultipleChoiceField(
        label="Jobs",
        config=unprogrammed_jobs_tomselect_config(),
    )


class JobForm(forms.ModelForm):
    site = TomSelectModelChoiceField(config=site_tomselect_config())
    work_programme = TomSelectModelChoiceField(
        config=work_programme_tomselect_config(),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.is_assigned:
            self.fields["site"].disabled = True
            self.fields["site"].help_text = ASSIGNED_JOB_SITE_DISABLED_REASON
            for field_name in ("status", "completed_date", "closeout_note"):
                field = self.fields[field_name]
                field.disabled = True
                field.help_text = ASSIGNED_JOB_CLOSEOUT_FIELD_DISABLED_REASON
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
            "completed_date",
            "closeout_note",
        ]
        labels = {
            "completed_date": "Completed date",
            "closeout_note": "Closeout note",
        }
        widgets = {
            "completed_date": DatePicker(),
        }


class JobFromTemplateForm(forms.Form):
    site = TomSelectModelChoiceField(config=site_tomselect_config())
    template = TomSelectModelChoiceField(config=job_template_tomselect_config())
    work_programme = TomSelectModelChoiceField(
        config=work_programme_tomselect_config(),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        kwargs.pop("site_queryset")
        super().__init__(*args, **kwargs)


class JobImportUploadForm(forms.Form):
    csv_file = forms.FileField(label="CSV file")


class JobTemplateImportUploadForm(forms.Form):
    csv_file = forms.FileField(label="CSV file")


class RequirementForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        fixed_job = kwargs.pop("fixed_job", None)
        job_queryset = kwargs.pop("job_queryset", None)
        super().__init__(*args, **kwargs)

        if fixed_job is not None or job_queryset is None:
            self.fields.pop("job", None)
            return

        self.fields["job"].queryset = job_queryset
        self.fields["job"].label_from_instance = lambda job: (
            f"{job.site.display_code} - {job.title}"
        )

    class Meta:
        model = Requirement
        fields = [
            "job",
            "requirement_type",
            "name",
            "quantity",
            "notes",
            "is_required",
            "is_checked",
        ]
