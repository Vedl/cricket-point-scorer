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
        
        # Firebase Configuration - try multiple ways to get secrets
        try:
            self.firebase_url = st.secrets.get("FIREBASE_DATABASE_URL", "")
        except:
            self.firebase_url = ""
        
        # Debug: Print Firebase config status
        if self.firebase_url:
            print(f"[StorageManager] Firebase URL configured: {self.firebase_url[:50]}...")
            self.use_remote = True
            self.db_url = f"{self.firebase_url}/auction_data.json"
        else:
            print("[StorageManager] WARNING: Firebase URL not found in secrets!")
            self.use_remote = False
            self.db_url = ""
    
    def _normalize_firebase_data(self, data):
        """
        Firebase converts dicts with numeric-looking keys (like '1', '2') to sparse arrays.
        Only convert back to dict if the array has None entries (sparse).
        """
        if data is None:
            return {}
        
        if isinstance(data, dict):
            # Recursively normalize nested dicts
            for key, value in data.items():
                data[key] = self._normalize_firebase_data(value)
            return data
        
        if isinstance(data, list):
            # Only convert sparse arrays (with None entries) back to dicts
            # This handles Firebase's conversion of {"1": x, "3": y} to [None, x, None, y]
            if any(item is None for item in data):
                result = {}
                for i, item in enumerate(data):
                    if item is not None:
                        result[str(i)] = self._normalize_firebase_data(item)
                return result
            # Keep normal lists as lists (participants, squad, members, etc.)
            return [self._normalize_firebase_data(item) if isinstance(item, (dict, list)) else item for item in data]
        
        return data
    
    def _ensure_schema(self, data):
        """Ensure data has required schema (squad lists, users/rooms dicts)."""
        if 'rooms' in data:
            for r_val in data['rooms'].values():
                if isinstance(r_val, dict) and 'participants' in r_val:
                    parts = r_val['participants']
                    if isinstance(parts, list):
                        for p in parts:
                            if isinstance(p, dict):
                                if 'squad' not in p or not isinstance(p['squad'], list):
                                    p['squad'] = []
        if 'users' not in data: data['users'] = {}
        if 'rooms' not in data: data['rooms'] = {}
        return data
    
    def load_data(self):
        """Load data: Local First (fast), then background sync from Firebase."""
        # 1. Try Local First (fast, <10ms)
        if os.path.exists(self.local_file_path):
            try:
                with open(self.local_file_path, 'r') as f:
                    data = json.load(f)
                    data = self._ensure_schema(data)
                    return data
            except Exception as e:
                print(f"Local Load Error: {e}")
        
        # 2. Fallback to Firebase if no local file (first run / cloud deploy)
        if self.use_remote:
            try:
                response = requests.get(self.db_url, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if data is None:
                        data = {}
                    
                    data = self._normalize_firebase_data(data)
                    data = self._ensure_schema(data)
                    
                    # Cache locally
                    try:
                        with open(self.local_file_path, 'w') as f:
                            json.dump(data, f, indent=2)
                    except: pass
                    
                    return data
            except Exception as e:
                print(f"Firebase Load Error: {e}")
        
        return {"users": {}, "rooms": {}}
    
    def load_data_from_remote(self):
        """Explicitly load fresh data from Firebase (for Refresh button)."""
        if not self.use_remote:
            return self.load_data()
        
        try:
            response = requests.get(self.db_url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data is None:
                    data = {}
                
                data = self._normalize_firebase_data(data)
                data = self._ensure_schema(data)
                
                # Update local cache
                try:
                    with open(self.local_file_path, 'w') as f:
                        json.dump(data, f, indent=2)
                except: pass
                
                return data
        except Exception as e:
            print(f"Firebase Remote Load Error: {e}")
        
        # Fallback to local
        return self.load_data()
    
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
                print(f"[StorageManager] Saving to Firebase: {self.db_url[:60]}...")
                try:
                    response = requests.put(
                        self.db_url,
                        data=json_str,
                        headers={'Content-Type': 'application/json'},
                        timeout=15
                    )
                    if response.status_code == 200:
                        print(f"[StorageManager] Firebase save SUCCESS")
                    else:
                        print(f"[StorageManager] Firebase save FAILED: {response.status_code} - {response.text[:200]}")
                        st.warning(f"⚠️ Cloud save failed: {response.status_code}")
                except Exception as e:
                    print(f"[StorageManager] Firebase Save Error: {e}")
                    st.warning(f"⚠️ Cloud save failed: {e}")
            else:
                print("[StorageManager] WARNING: use_remote is False, not saving to Firebase!")
                    
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
