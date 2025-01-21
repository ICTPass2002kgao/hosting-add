from google.cloud import storage
from google.oauth2 import service_account

def download_file_from_gcs(bucket_name, file_name, local_path):
    """Downloads a file from GCS to a local temporary path."""
    
    # Load credentials from the JSON file directly
    credentials = service_account.Credentials.from_service_account_file(
        'C:/Users/Kgaogelo/Desktop/certificatesaqa/certificatesaqa/certificate-442017-a5a4246f2eca.json'
    )
    
    # Initialize the client with the credentials
    client = storage.Client(credentials=credentials, project='certificate-442017')
    
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(file_name)
    blob.download_to_filename(local_path)
    return local_path

from google.cloud import storage
from .models import Certificate
from django.conf import settings

def sync_files_to_database():
    # Initialize the GCS client
    client = storage.Client()
    bucket = client.get_bucket(settings.GS_BUCKET_NAME)

    # List all files in the bucket
    blobs = bucket.list_blobs()

    for blob in blobs:
        file_url = f"https://storage.googleapis.com/{settings.GS_BUCKET_NAME}/{blob.name}"

        # Check if the file already exists in the database
        if not Certificate.objects.filter(document=file_url).exists():
            # Extract metadata from the file name or path
            certificate_name = blob.name.split('/')[-1]
            
            # Create a new certificate entry
            Certificate.objects.create(
                customer_name="Recovered Certificate",
                document=file_url,
                qr_code="",  # Leave blank or regenerate if necessary
            )
            print(f"Added missing file to database: {file_url}")
        else:
            print(f"File already exists in database: {file_url}")
