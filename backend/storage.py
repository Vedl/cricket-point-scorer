import json
import os
import requests
import streamlit as st

class StorageManager:
    def __init__(self, local_file_path):
        self.local_file_path = local_file_path
        self.api_key = st.secrets.get("JSONBIN_KEY")
        self.bin_id = st.secrets.get("JSONBIN_BIN_ID")
        self.use_remote = bool(self.api_key and self.bin_id)
        
        if self.use_remote:
            self.headers = {
                'X-Master-Key': self.api_key,
                'Content-Type': 'application/json'
            }
            self.url = f"https://api.jsonbin.io/v3/b/{self.bin_id}"

    def load_data(self):
        """Load data from Remote (JSONBin) if available, else local file."""
        if self.use_remote:
            try:
                response = requests.get(self.url + "/latest", headers=self.headers)
                if response.status_code == 200:
                    return response.json().get('record', {"users": {}, "rooms": {}})
                else:
                    # If bin is empty or error, fallback or return empty
                    print(f"Remote Load Error: {response.status_code} - {response.text}")
                    return {"users": {}, "rooms": {}}
            except Exception as e:
                print(f"Remote Load Exception: {e}")
                return {"users": {}, "rooms": {}}
        
        # Fallback to Local
        if os.path.exists(self.local_file_path):
            try:
                with open(self.local_file_path, 'r') as f:
                    data = json.load(f)
                    if 'users' not in data:
                        data = {"users": {}, "rooms": {}}
                    return data
            except:
                pass
        return {"users": {}, "rooms": {}}

    def save_data(self, data):
        """Save data to Remote (JSONBin) if available, AND local file."""
        # Always save local as backup/cache
        with open(self.local_file_path, 'w') as f:
            json.dump(data, f, indent=2)

        if self.use_remote:
            try:
                # JSONBin 'PUT' updates the bin
                response = requests.put(self.url, headers=self.headers, json=data)
                if response.status_code != 200:
                    print(f"Remote Save Error: {response.status_code} - {response.text}")
            except Exception as e:
                 print(f"Remote Save Exception: {e}")
