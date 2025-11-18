import firebase_admin
from firebase_admin import credentials, storage, firestore
import os

# Load Firebase service account
# Ensure firebase_key.json is in your project root
cred = credentials.Certificate(os.path.join("firebase_key.json")) 

if not firebase_admin._apps:
    firebase_admin.initialize_app(cred, {
        "storageBucket": "certiificate-saqa.appspot.com" # Ensure this is correct
    })


# Initialize Firestore Database
db = firestore.client()

# Initialize Storage Bucket
bucket = storage.bucket()