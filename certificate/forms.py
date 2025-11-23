from django import forms

# 1. Custom widget to bypass Django 5+ strict checks
class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

class CertificateUploadForm(forms.Form):
    # 2. Apply the custom widget
    document = forms.FileField(
        widget=MultipleFileInput(attrs={'class': 'form-control', 'multiple': True}),
        label="Select Certificates (Select multiple files)"
    )