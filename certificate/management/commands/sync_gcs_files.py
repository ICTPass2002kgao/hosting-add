from django.core.management.base import BaseCommand
from google.cloud import storage
from certificate.models import Certificate  # Replace 'certificate' with your app name
from django.conf import settings

class Command(BaseCommand):
    help = "Sync files from Google Cloud Storage to the database"

    def handle(self, *args, **kwargs):
        client = storage.Client()
        bucket = client.get_bucket(settings.GS_BUCKET_NAME)
        blobs = bucket.list_blobs()

        for blob in blobs:
            file_url = f"https://storage.googleapis.com/{settings.GS_BUCKET_NAME}/{blob.name}"

            if not Certificate.objects.filter(document=file_url).exists():
                Certificate.objects.create(
                    name=blob.name.split('/')[-1],  # Replace 'name' with an actual field from your model
                    document=file_url,
                    qr_code="",  # Remove or adjust based on your model definition
                )
                self.stdout.write(self.style.SUCCESS(f"Added file to database: {file_url}"))
            else:
                self.stdout.write(self.style.WARNING(f"File already exists in database: {file_url}"))
