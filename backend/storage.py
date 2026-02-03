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

    import threading
    
    def load_data(self):
        """Load data: Prefer Local File (Speed), Fallback to Remote (Backup)."""
        # 1. Try Local File (Fast Cache)
        if os.path.exists(self.local_file_path):
            try:
                with open(self.local_file_path, 'r') as f:
                    data = json.load(f)
                    # Basic Validation
                    if 'users' not in data: data['users'] = {}
                    if 'rooms' not in data: data['rooms'] = {}
                    return data
            except Exception as e:
                print(f"Local Load Error: {e}")
        
        # 2. Remote Fallback (Cold Start)
        if self.use_remote:
            try:
                # print("Fetching from Remote Storage...")
                response = requests.get(self.url + "/latest", headers=self.headers, timeout=5)
                if response.status_code == 200:
                    data = response.json().get('record', {})
                    if 'users' not in data: data['users'] = {}
                    if 'rooms' not in data: data['rooms'] = {}
                    
                    # Cache it locally immediately
                    try:
                        with open(self.local_file_path, 'w') as f:
                            json.dump(data, f, indent=2)
                    except: pass
                    
                    return data
            except Exception as e:
                print(f"Remote Load Exception: {e}")
        
        return {"users": {}, "rooms": {}}

    def save_data(self, data):
        """Save data: Sync Local (Fast) + Async Remote (Background)."""
        try:
            # 1. Serialize ONCE (Thread-Safety)
            json_str = json.dumps(data, indent=2)
            
            # 2. Local Save (Synchronous/Immediate)
            with open(self.local_file_path, 'w') as f:
                f.write(json_str)
            
            # 3. Remote Save (Asynchronous/Fire-and-Forget)
            if self.use_remote:
                def _push_remote(payload):
                    try:
                        requests.put(self.url, headers=self.headers, data=payload, timeout=5)
                    except Exception as e:
                        print(f"Async Upload Failed: {e}")
                
                # Start background thread
                t = threading.Thread(target=_push_remote, args=(json_str,))
                t.start()
                
        except Exception as e:
            print(f"Save Data Error: {e}")
