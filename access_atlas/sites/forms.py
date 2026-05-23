from django import forms

MAX_PHOTO_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_PHOTO_UPLOAD_COUNT = 50


class MultipleImageInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    widget = MultipleImageInput

    def clean(self, data, initial=None):
        files = data if isinstance(data, list | tuple) else [data]
        if not files or files == [None]:
            raise forms.ValidationError("Choose at least one photo.")
        if len(files) > MAX_PHOTO_UPLOAD_COUNT:
            raise forms.ValidationError(
                f"Upload no more than {MAX_PHOTO_UPLOAD_COUNT} photos at once."
            )
        for file in files:
            if file.size > MAX_PHOTO_UPLOAD_BYTES:
                raise forms.ValidationError(f"{file.name} must be 20 MB or smaller.")
        clean_file = super().clean
        return [clean_file(file, initial) for file in files]


class SitePhotoUploadForm(forms.Form):
    photos = MultipleImageField(
        label="Photos",
        widget=MultipleImageInput(attrs={"multiple": True, "accept": "image/*"}),
        help_text=(
            "Upload one or more image files. Each photo must be 20 MB or smaller."
        ),
    )
