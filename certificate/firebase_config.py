import firebase_admin
from firebase_admin import credentials, storage, firestore
import os
import json

# 1. Get the JSON string from Railway Variables
firebase_creds_json = os.environ.get("FIREBASE_CREDENTIALS")

if not firebase_creds_json:
    # Fallback for local testing if you still have the file locally
    # This allows the code to work both on Railway AND your computer
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    local_key_path = os.path.join(base_dir, "firebase_key.json")
    
    if os.path.exists(local_key_path):
        cred = credentials.Certificate(local_key_path)
    else:
        raise ValueError("FIREBASE_CREDENTIALS env var not set, and firebase_key.json not found.")
else:
    # 2. Parse the string into a Python Dictionary
    # valid_json_string = firebase_creds_json.replace("'", "\"") # Sometimes needed if quotes get messed up
    cred_dict = json.loads(firebase_creds_json)
    cred = credentials.Certificate(cred_dict)

# 3. Initialize App
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred, {
        "storageBucket": "certiificate-saqa.appspot.com"
    })

db = firestore.client()
bucket = storage.bucket()