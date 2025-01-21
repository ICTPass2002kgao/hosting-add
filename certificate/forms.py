from django import forms
from .models import Certificate

class CertificateUploadForm(forms.ModelForm):
    class Meta:
        model = Certificate
        fields = [ 'document']
