from django.db import models
import uuid
import os

def certificate_upload_to(instance, filename): 
    ext = filename.split('.')[-1]   
    new_filename = f"{uuid.uuid4()}.{ext}" 
    return os.path.join('', new_filename)

class Certificate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(unique=True, max_length=255, blank=False, default=uuid.uuid4, )
    document = models.FileField(upload_to=certificate_upload_to,max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    qr_code = models.ImageField(upload_to='qr_codes/', blank=True, null=True)

    class Meta:
            # This will ensure that the certificates are ordered by created_at in descending order by default
            ordering = ['-created_at']
    def __str__(self):
        return self.name
