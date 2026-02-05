import json
import os
import requests
import streamlit as st
import threading
import fcntl

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
        """Load data: Prefer Local File (Speed), Fallback to Remote (Backup). Uses File Locking."""
        # 1. Try Local File (Fast Cache) with LOCK_SH (Shared Lock) for Reading
        if os.path.exists(self.local_file_path):
            try:
                with open(self.local_file_path, 'r') as f:
                    # Acquire Shared Lock (wait if writing)
                    fcntl.flock(f, fcntl.LOCK_SH)
                    try:
                        data = json.load(f)
                    finally:
                        fcntl.flock(f, fcntl.LOCK_UN)
                    
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
                    
                    # Cache it locally immediately (Atomic-ish)
                    try:
                        fd = os.open(self.local_file_path, os.O_RDWR | os.O_CREAT)
                        with os.fdopen(fd, 'r+') as f:
                            fcntl.flock(f, fcntl.LOCK_EX)
                            try:
                                f.truncate(0)
                                f.seek(0)
                                json.dump(data, f, indent=2)
                                f.flush()
                                os.fsync(f.fileno())
                            finally:
                                fcntl.flock(f, fcntl.LOCK_UN)
                    except: pass
                    
                    return data
            except Exception as e:
                print(f"Remote Load Exception: {e}")
        
        return {"users": {}, "rooms": {}}

    def save_data(self, data):
        """Save data: Atomic Rename Pattern (Tmp -> Rename) + Async Remote."""
        try:
            # 1. Serialize
            json_str = json.dumps(data, indent=2)
            
            # 2. Atomic Local Save
            # Write to a temp file first
            tmp_file = self.local_file_path + ".tmp"
            
            # Use 'w' mode for temp file - we don't care about its previous content
            with open(tmp_file, 'w') as f:
                f.write(json_str)
                f.flush()
                os.fsync(f.fileno())
            
            # Atomic Rename: Overwrites target instantly
            os.rename(tmp_file, self.local_file_path)
            
            # 3. Remote Save (Asynchronous)
            if self.use_remote:
                def _push_remote(payload):
                    try:
                        requests.put(self.url, headers=self.headers, data=payload, timeout=5)
                    except Exception as e:
                        print(f"Async Upload Failed: {e}")
                
                t = threading.Thread(target=_push_remote, args=(json_str,))
                t.start()
                
        except Exception as e:
            st.error(f"SAVE FAILED: {str(e)}")
            print(f"Save Data Error: {e}")

    def force_sync_to_remote(self, data):
        """Manual Trigger: Force Synchronous Upload to Remote (Blocking)."""
        if not self.use_remote:
            return False, "Remote storage not configured."
        
        try:
            # === COMPRESSION LOGIC ===
            # Deep copy to avoid mutating active state
            import copy
            compressed = copy.deepcopy(data)
            
            # Minimize 'gameweek_squads' history (High Impact)
            rooms = compressed.get('rooms', {})
            if isinstance(rooms, dict):
                for room_key, room_data in rooms.items():
                    if not isinstance(room_data, dict): continue
                    
                    gw_squads = room_data.get('gameweek_squads', {})
                    if isinstance(gw_squads, dict):
                        for gw, participants in gw_squads.items():
                            if not isinstance(participants, dict): continue
                            
                            for p_name, p_data in participants.items():
                                if not isinstance(p_data, dict): continue
                                
                                # Strip squad list to essentials
                                minimized_squad = []
                                squad_list = p_data.get('squad', [])
                                if isinstance(squad_list, list):
                                    for pl in squad_list:
                                        if isinstance(pl, dict):
                                            minimized_squad.append({
                                                'name': pl.get('name', 'Unknown'),
                                                'buy_price': pl.get('buy_price', 0)
                                            })
                                        else:
                                            # Handle edge case where pl might be just a string name?
                                            pass
                                    p_data['squad'] = minimized_squad
            
            json_str = json.dumps(compressed, separators=(',', ':')) # Removing whitespace saves ~20%
            
            if len(json_str) > 100000:
                print(f"⚠️ Warning: Payload size {len(json_str)} bytes approaches 100KB limit.")
            
            response = requests.put(self.url, headers=self.headers, data=json_str, timeout=10)
            if response.status_code == 200:
                return True, "Successfully synced to Cloud! (Compressed)"
            else:
                return False, f"Cloud Upload Failed: {response.status_code} - {response.text}"
        except Exception as e:
            return False, f"Cloud Exception: {str(e)}"

    def force_fetch_from_remote(self):
        """Manual Trigger: Force Download from Remote and Overwrite Local (Blocking)."""
        if not self.use_remote:
            return None, "Remote storage not configured."
            
        try:
            response = requests.get(self.url + "/latest", headers=self.headers, timeout=10)
            if response.status_code == 200:
                data = response.json().get('record', {})
                
                # Overwrite Local File Immediately
                fd = os.open(self.local_file_path, os.O_RDWR | os.O_CREAT)
                with os.fdopen(fd, 'r+') as f:
                    fcntl.flock(f, fcntl.LOCK_EX)
                    try:
                        f.truncate(0)
                        f.seek(0)
                        json.dump(data, f, indent=2)
                        f.flush()
                        os.fsync(f.fileno())
                    finally:
                        fcntl.flock(f, fcntl.LOCK_UN)
                
                return data, "Successfully restored from Cloud!"
            else:
                return None, f"Cloud Download Failed: {response.status_code}"
        except Exception as e:
            return None, f"Cloud Exception: {str(e)}"
