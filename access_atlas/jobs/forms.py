from django import forms
from django_tomselect.app_settings import TomSelectConfig
from django_tomselect.forms import TomSelectModelChoiceField

from .models import Job, JobStatus, JobTemplate, Requirement, TemplateRequirement


def _site_tomselect_config() -> TomSelectConfig:
    return TomSelectConfig(
        url="autocomplete_sites",
        css_framework="bootstrap5",
        label_field="label",
        placeholder="Search sites",
        minimum_query_length=0,
        preload="focus",
    )


def _template_tomselect_config() -> TomSelectConfig:
    return TomSelectConfig(
        url="autocomplete_job_templates",
        css_framework="bootstrap5",
        label_field="title",
        placeholder="Search templates",
        minimum_query_length=0,
        preload="focus",
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


class TemplateRequirementForm(forms.ModelForm):
    class Meta:
        model = TemplateRequirement
        fields = ["requirement_type", "name", "quantity", "notes", "is_required"]


class JobForm(forms.ModelForm):
    site = TomSelectModelChoiceField(config=_site_tomselect_config())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.is_assigned:
            return
        choices = [
            (value, label)
            for value, label in self.fields["status"].choices
            if value != JobStatus.PLANNED
        ]
        self.fields["status"].choices = choices

    class Meta:
        model = Job
        fields = [
            "site",
            "title",
            "description",
            "estimated_duration_minutes",
            "priority",
            "status",
            "cancelled_reason",
            "notes",
        ]


class JobFromTemplateForm(forms.Form):
    site = TomSelectModelChoiceField(config=_site_tomselect_config())
    template = TomSelectModelChoiceField(config=_template_tomselect_config())

    def __init__(self, *args, **kwargs):
        kwargs.pop("site_queryset")
        super().__init__(*args, **kwargs)


class JobImportUploadForm(forms.Form):
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
