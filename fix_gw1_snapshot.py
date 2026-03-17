"""
Fix: Force-push the correct GW1 squad snapshot to Firebase.

The local auction_data.json has the original, correct GW1 locked squads.
Firebase's copy got corrupted/overwritten with current squad data.
This script force-syncs the correct local data to Firebase.
"""
import json
import os
import sys

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    # Load local data (which has the correct GW1 snapshot)
    with open('auction_data.json', 'r') as f:
        data = json.load(f)
    
    room = data['rooms'].get('3ZZ5EE')
    if not room:
        print("Room 3ZZ5EE not found!")
        return
    
    # Verify GW1 snapshot exists locally
    gw1_snap = room.get('gameweek_squads', {}).get('1', {})
    if not gw1_snap:
        print("No GW1 snapshot found in local data!")
        return
    
    print("=== Local GW1 Snapshot (CORRECT) ===")
    for p_name, p_data in gw1_snap.items():
        if isinstance(p_data, dict):
            squad = p_data.get('squad', [])
        else:
            squad = p_data if isinstance(p_data, list) else []
        names = sorted([p['name'] for p in squad])
        print(f"  {p_name}: {len(squad)} players")
    
    print("\n=== Force-syncing to Firebase... ===")
    
    # Use StorageManager to force sync
    from backend.storage import StorageManager
    storage = StorageManager('auction_data.json')
    
    if not storage.use_remote:
        print("Firebase not configured! Cannot sync.")
        return
    
    success, msg = storage.force_sync_to_remote(data)
    print(f"Result: {msg}")
    
    if success:
        print("\n✅ Firebase now has the correct GW1 snapshot!")
        print("Restart Streamlit to see the fix.")
    else:
        print("\n❌ Sync failed. Try manually.")

if __name__ == '__main__':
    main()
