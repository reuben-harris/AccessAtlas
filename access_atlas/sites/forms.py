import json

from django import forms

from .access_records import AccessRecordGeoJSONError, parse_access_record_geojson
from .models import AccessRecord, ArrivalMethod


class AccessRecordUploadForm(forms.Form):
    name = forms.CharField(max_length=255)
    arrival_method = forms.ChoiceField(choices=ArrivalMethod.choices)
    geojson_file = forms.FileField(label="GeoJSON file")
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

    def clean_geojson_file(self):
        geojson_file = self.cleaned_data["geojson_file"]
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
        self.cleaned_data["geojson"] = geojson
        return geojson_file


class AccessRecordVersionUploadForm(forms.Form):
    geojson_file = forms.FileField(label="GeoJSON file")
    change_note = forms.CharField(widget=forms.Textarea(attrs={"rows": 4}))

    def clean_change_note(self):
        change_note = self.cleaned_data["change_note"].strip()
        if not change_note:
            raise forms.ValidationError("Enter a change note.")
        return change_note

    def clean_geojson_file(self):
        geojson_file = self.cleaned_data["geojson_file"]
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
        self.cleaned_data["geojson"] = geojson
        return geojson_file


class AccessRecordForm(forms.ModelForm):
    class Meta:
        model = AccessRecord
        fields = ["name", "arrival_method", "status"]
