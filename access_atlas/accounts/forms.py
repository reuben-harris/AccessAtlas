from django import forms


class EmailLoginForm(forms.Form):
    email = forms.EmailField()
    display_name = forms.CharField(required=False, max_length=255)
