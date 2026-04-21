from django import forms

from .models import Job, JobStatus, JobTemplate, Requirement, TemplateRequirement


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
            "notes",
        ]


class JobFromTemplateForm(forms.Form):
    site = forms.ModelChoiceField(queryset=None)
    template = forms.ModelChoiceField(
        queryset=JobTemplate.objects.filter(is_active=True)
    )

    def __init__(self, *args, **kwargs):
        site_queryset = kwargs.pop("site_queryset")
        super().__init__(*args, **kwargs)
        self.fields["site"].queryset = site_queryset


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
