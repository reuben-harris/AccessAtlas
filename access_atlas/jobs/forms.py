from django import forms
from django_tomselect.forms import (
    TomSelectModelChoiceField,
    TomSelectModelMultipleChoiceField,
)

from access_atlas.core.bulk_edit import NullableBulkEditFormMixin
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
    Priority,
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


class DurationMinutesField(forms.CharField):
    """Parse duration minutes as text so invalid input reaches server validation."""

    def __init__(self, *args, **kwargs):
        attrs = {"inputmode": "numeric", **kwargs.pop("attrs", {})}
        kwargs["widget"] = forms.TextInput(attrs=attrs)
        super().__init__(*args, **kwargs)

    def clean(self, value):
        value = super().clean(value)
        if value in self.empty_values:
            return None

        try:
            duration_minutes = int(value)
        except (TypeError, ValueError) as exc:
            raise forms.ValidationError(
                "Enter duration as a whole number of minutes."
            ) from exc

        if duration_minutes <= 0:
            raise forms.ValidationError("Enter a duration greater than 0 minutes.")

        return duration_minutes


class JobTemplateForm(forms.ModelForm):
    estimated_duration_minutes = DurationMinutesField(
        required=False,
        label="Estimated duration minutes",
    )

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
    estimated_duration_minutes = DurationMinutesField(
        required=False,
        label="Estimated duration minutes",
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


class JobBulkEditForm(NullableBulkEditFormMixin, forms.Form):
    nullable_fields = ("work_programme", "completed_date")
    nullable_field_labels = {
        "work_programme": "Set work programme to null",
        "completed_date": "Set completed date to null",
    }

    priority = forms.ChoiceField(
        choices=[("", "No change"), *Priority.choices],
        required=False,
    )
    work_programme = forms.ModelChoiceField(
        queryset=WorkProgramme.objects.order_by("start_date", "name"),
        required=False,
        empty_label="No change",
    )
    status = forms.ChoiceField(
        choices=[
            ("", "No change"),
            (JobStatus.UNASSIGNED, JobStatus.UNASSIGNED.label),
            (JobStatus.COMPLETED, JobStatus.COMPLETED.label),
            (JobStatus.CANCELLED, JobStatus.CANCELLED.label),
        ],
        required=False,
        help_text=(
            "Assigned jobs cannot have status changed because trip closeout "
            "manages them."
        ),
    )
    completed_date = forms.DateField(
        required=False,
        widget=DatePicker(),
        label="Completed date",
        help_text="Required when bulk setting jobs to completed.",
    )
    closeout_note = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Required when bulk setting jobs to cancelled.",
    )

    def clean(self):
        cleaned_data = super().clean()
        work_programme = cleaned_data.get("work_programme")
        status = cleaned_data.get("status")
        completed_date = cleaned_data.get("completed_date")
        closeout_note = (cleaned_data.get("closeout_note") or "").strip()
        nullified_fields = self.nullified_fields()
        clear_work_programme = "work_programme" in nullified_fields
        clear_completed_date = "completed_date" in nullified_fields

        has_change = any(
            [
                cleaned_data.get("priority"),
                work_programme is not None,
                clear_work_programme,
                status,
                completed_date,
                clear_completed_date,
            ]
        )
        if not has_change:
            raise forms.ValidationError("Choose at least one field to bulk edit.")
        if clear_work_programme and work_programme is not None:
            self.add_error(
                "work_programme",
                "Choose a work programme or set it to null, not both.",
            )
        if clear_completed_date and completed_date is not None:
            self.add_error(
                "completed_date",
                "Choose a completed date or set it to null, not both.",
            )
        if status == JobStatus.CANCELLED and not closeout_note:
            self.add_error("closeout_note", "Enter a closeout note for cancelled jobs.")
        if status == JobStatus.COMPLETED:
            if clear_completed_date:
                self.add_error(
                    "completed_date",
                    "Completed date cannot be set to null when status is completed.",
                )
            elif completed_date is None:
                self.add_error(
                    "completed_date",
                    "Enter a completed date for completed jobs.",
                )
        elif completed_date is not None:
            self.add_error(
                "completed_date",
                "Completed date can only be set when status is completed.",
            )
        return cleaned_data


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
