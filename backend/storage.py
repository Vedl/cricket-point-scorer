import json
import os
import requests
import streamlit as st
import threading

class StorageManager:
    """
    Firebase Realtime Database Storage Manager
    Uses REST API for compatibility with Streamlit Cloud
    """
    def __init__(self, local_file_path):
        self.local_file_path = local_file_path
        
        # Firebase Configuration
        self.firebase_url = st.secrets.get("FIREBASE_DATABASE_URL")
        self.firebase_api_key = st.secrets.get("FIREBASE_API_KEY")
        self.use_remote = bool(self.firebase_url)
        
        if self.use_remote:
            # Firebase REST API endpoint
            self.db_url = f"{self.firebase_url}/auction_data.json"
    
    def load_data(self):
        """Load data: Try Remote First (Source of Truth), Fallback to Local."""
        # 1. Try Firebase (Source of Truth for Cloud)
        if self.use_remote:
            try:
                response = requests.get(self.db_url, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if data is None:
                        data = {}
                    if 'users' not in data: data['users'] = {}
                    if 'rooms' not in data: data['rooms'] = {}
                    
                    # Cache locally
                    try:
                        with open(self.local_file_path, 'w') as f:
                            json.dump(data, f, indent=2)
                    except: pass
                    
                    return data
            except Exception as e:
                print(f"Firebase Load Error: {e}")
        
        # 2. Local Fallback
        if os.path.exists(self.local_file_path):
            try:
                with open(self.local_file_path, 'r') as f:
                    data = json.load(f)
                    if 'users' not in data: data['users'] = {}
                    if 'rooms' not in data: data['rooms'] = {}
                    return data
            except Exception as e:
                print(f"Local Load Error: {e}")
        
        return {"users": {}, "rooms": {}}
    
    def save_data(self, data):
        """Save data: Local + Firebase (Synchronous for reliability)."""
        try:
            json_str = json.dumps(data, indent=2)
            
            # 1. Save locally first (fast)
            tmp_file = self.local_file_path + ".tmp"
            with open(tmp_file, 'w') as f:
                f.write(json_str)
                f.flush()
                os.fsync(f.fileno())
            os.rename(tmp_file, self.local_file_path)
            
            # 2. Save to Firebase (synchronous - MUST succeed for cloud)
            if self.use_remote:
                try:
                    response = requests.put(
                        self.db_url,
                        data=json_str,
                        headers={'Content-Type': 'application/json'},
                        timeout=15
                    )
                    if response.status_code != 200:
                        print(f"Firebase Save Warning: {response.status_code}")
                except Exception as e:
                    print(f"Firebase Save Error: {e}")
                    st.warning(f"⚠️ Cloud save failed: {e}")
                    
        except Exception as e:
            st.error(f"SAVE FAILED: {str(e)}")
            print(f"Save Error: {e}")
    
    def force_sync_to_remote(self, data):
        """Manual sync to Firebase."""
        if not self.use_remote:
            return False, "Firebase not configured."
        
        try:
            json_str = json.dumps(data)
            response = requests.put(
                self.db_url,
                data=json_str,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            if response.status_code == 200:
                return True, "Successfully synced to Firebase!"
            else:
                return False, f"Firebase Error: {response.status_code}"
        except Exception as e:
            return False, f"Firebase Exception: {str(e)}"
    
    def force_fetch_from_remote(self):
        """Manual fetch from Firebase."""
        if not self.use_remote:
            return None, "Firebase not configured."
        
        try:
            response = requests.get(self.db_url, timeout=30)
            if response.status_code == 200:
                data = response.json() or {}
                
                # Save locally
                with open(self.local_file_path, 'w') as f:
                    json.dump(data, f, indent=2)
                
                return data, "Successfully restored from Firebase!"
            else:
                return None, f"Firebase Error: {response.status_code}"
        except Exception as e:
            return None, f"Firebase Exception: {str(e)}"
