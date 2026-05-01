import json

from django import forms

from .access_records import AccessRecordGeoJSONError, parse_access_record_geojson
from .models import AccessRecord, AccessRecordUploadDraft, ArrivalMethod


class AccessRecordGeoJSONUploadMixin(forms.Form):
    geojson_file = forms.FileField(label="GeoJSON file", required=False)
    staged_upload_id = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user")
        self.staged_upload = None
        self.replaced_staged_upload = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        geojson_file = cleaned_data.get("geojson_file")
        staged_upload_id = cleaned_data.get("staged_upload_id")

        if geojson_file:
            if staged_upload_id:
                self.replaced_staged_upload = self._get_staged_upload(staged_upload_id)
            try:
                geojson = self._parse_geojson_file(geojson_file)
            except forms.ValidationError as exc:
                self.add_error("geojson_file", exc)
            else:
                cleaned_data["geojson"] = geojson
                cleaned_data["geojson_file_name"] = geojson_file.name
            return cleaned_data

        if staged_upload_id:
            staged_upload = self._get_staged_upload(staged_upload_id)
            if staged_upload is None:
                self.add_error(
                    "geojson_file",
                    "The retained GeoJSON file is no longer available. "
                    "Choose the file again.",
                )
            else:
                self.staged_upload = staged_upload
                cleaned_data["geojson"] = staged_upload.geojson
                cleaned_data["geojson_file_name"] = staged_upload.file_name
            return cleaned_data

        self.add_error("geojson_file", "Choose a GeoJSON file.")
        return cleaned_data

    def _parse_geojson_file(self, geojson_file):
        try:
            raw = geojson_file.read().decode("utf-8")
            geojson = json.loads(raw)
            parse_access_record_geojson(geojson)
        except UnicodeDecodeError as exc:
            raise forms.ValidationError("GeoJSON file must be UTF-8 encoded.") from exc
        except json.JSONDecodeError as exc:
            raise forms.ValidationError(
                "GeoJSON file must contain valid JSON."
            ) from exc
        except AccessRecordGeoJSONError as exc:
            raise forms.ValidationError(str(exc)) from exc
        return geojson

    def _get_staged_upload(self, staged_upload_id):
        try:
            staged_upload = AccessRecordUploadDraft.objects.get(
                pk=staged_upload_id,
                user=self.user,
            )
        except AccessRecordUploadDraft.DoesNotExist, ValueError:
            return None
        if not self._staged_upload_matches_context(staged_upload):
            return None
        return staged_upload

    def _staged_upload_matches_context(self, staged_upload):
        raise NotImplementedError


class AccessRecordUploadForm(AccessRecordGeoJSONUploadMixin):
    name = forms.CharField(max_length=255)
    arrival_method = forms.ChoiceField(choices=ArrivalMethod.choices)
    change_note = forms.CharField(widget=forms.Textarea(attrs={"rows": 4}))

    def __init__(self, *args, **kwargs):
        self.site = kwargs.pop("site")
        super().__init__(*args, **kwargs)

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if AccessRecord.objects.filter(site=self.site, name=name).exists():
            raise forms.ValidationError(
                "An access record with this name already exists for this site."
            )
        return name

    def clean_change_note(self):
        change_note = self.cleaned_data["change_note"].strip()
        if not change_note:
            raise forms.ValidationError("Enter a change note.")
        return change_note

    def _staged_upload_matches_context(self, staged_upload):
        return (
            staged_upload.site_id == self.site.pk
            and staged_upload.access_record_id is None
        )


class AccessRecordVersionUploadForm(AccessRecordGeoJSONUploadMixin):
    change_note = forms.CharField(widget=forms.Textarea(attrs={"rows": 4}))

    def __init__(self, *args, **kwargs):
        self.access_record = kwargs.pop("access_record")
        super().__init__(*args, **kwargs)

    def clean_change_note(self):
        change_note = self.cleaned_data["change_note"].strip()
        if not change_note:
            raise forms.ValidationError("Enter a change note.")
        return change_note

    def _staged_upload_matches_context(self, staged_upload):
        return staged_upload.access_record_id == self.access_record.pk


class AccessRecordForm(forms.ModelForm):
    class Meta:
        model = AccessRecord
        fields = ["name", "arrival_method", "status"]
