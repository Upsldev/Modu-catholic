import firebase_admin
from firebase_admin import credentials, firestore
import json
import os
import argparse

class FirebaseUploader:
    def __init__(self):
        self.collection_name = "catholic_churches"
        self.db = None
        self._initialize_firebase()

    def _initialize_firebase(self):
        """Initializes Firebase app looking for serviceAccountKey.json in current dir."""
        try:
            if not firebase_admin._apps:
                # Look for serviceAccountKey.json in the same directory as this script
                current_dir = os.path.dirname(os.path.abspath(__file__))
                key_path = os.path.join(current_dir, "serviceAccountKey.json")
                
                if os.path.exists(key_path):
                    cred = credentials.Certificate(key_path)
                    firebase_admin.initialize_app(cred)
                    print(f"Firebase initialized with key: {key_path}")
                else:
                    # Fallback to default (env var or Gcloud auth)
                    print("serviceAccountKey.json not found locally. Trying default credentials...")
                    firebase_admin.initialize_app()
            
            self.db = firestore.client()
        except Exception as e:
            print(f"Error initializing Firebase: {e}")
            raise e

    def load_data(self, filename="catholic_data.json"):
        """Loads data from JSON file using absolute path."""
        # Data is in crawler/data/
        current_dir = os.path.dirname(os.path.abspath(__file__))
        data_path = os.path.join(current_dir, "data", filename)
        
        if not os.path.exists(data_path):
            print(f"File not found: {data_path}")
            return []
        
        with open(data_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"Loaded {len(data)} records from {data_path}")
        return data

    def upload_single(self, data, target_name):
        """
        Hot-fix mode: Overwrites a single document.
        1. Deletes existing document.
        2. Sets new data.
        """
        target_item = next((item for item in data if item.get('name') == target_name), None)
        
        if not target_item:
            print(f"Error: Local data not found for '{target_name}'")
            return

        doc_ref = self.db.collection(self.collection_name).document(target_name)
        
        try:
            # 1. Delete existing
            doc_ref.delete()
            print(f"Deleted existing document: {target_name}")
            
            # 2. Set new data
            doc_ref.set(target_item)
            print(f"Successfully overwrote: {target_name}")
            
        except Exception as e:
            print(f"Failed to overwrite {target_name}: {e}")

    def upload_batch(self, data):
        """Uploads data to Firestore using Upsert (Merge=True)."""
        if not data:
            print("No data to upload.")
            return

        batch = self.db.batch()
        batch_count = 0
        total_uploaded = 0
        
        print(f"Starting batch upload to collection '{self.collection_name}'...")

        for item in data:
            # Use 'name' as Document ID to prevent duplicates
            doc_id = item.get('name')
            if not doc_id:
                print("Skipping item without name.")
                continue
                
            doc_ref = self.db.collection(self.collection_name).document(doc_id)
            
            # Upsert: Merge=True updates existing fields or creates new doc
            batch.set(doc_ref, item, merge=True)
            batch_count += 1

            # Firestore batch limit is 500
            if batch_count >= 400:
                batch.commit()
                total_uploaded += batch_count
                print(f"Committed batch of {batch_count} documents.")
                batch = self.db.batch() # New batch
                batch_count = 0

        # Commit remaining
        if batch_count > 0:
            batch.commit()
            total_uploaded += batch_count
            print(f"Committed final batch of {batch_count} documents.")

        print(f"Total {total_uploaded} documents processed (Upserted).")

def main():
    parser = argparse.ArgumentParser(description="Upload Modu-Catholic data to Firestore.")
    parser.add_argument("--name", help="Specific church name to hot-fix (overwrite).")
    args = parser.parse_args()

    try:
        uploader = FirebaseUploader()
        data = uploader.load_data()
        
        if args.name:
            # Hot-fix Mode
            print(f"--- Hot-fix Mode: {args.name} ---")
            uploader.upload_single(data, args.name)
        else:
            # Batch Mode
            print("--- Batch Upload Mode ---")
            uploader.upload_batch(data)
            
    except Exception as e:
        print(f"Upload failed: {e}")

if __name__ == "__main__":
    main()
