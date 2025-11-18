from django import forms

class CertificateUploadForm(forms.Form):
    # We only need the file input; metadata is generated in the view
    document = forms.FileField(label="Upload Certificate")
    