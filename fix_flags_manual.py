import json
import requests

FIREBASE_URL = 'https://cricket-auction-b00e2-default-rtdb.asia-southeast1.firebasedatabase.app'
ROOM_CODE = '3ZZ5EE'

def fix_flags():
    print(f"Manually Fixing Flags for Room {ROOM_CODE}...")
    try:
        response = requests.get(f'{FIREBASE_URL}/auction_data/rooms/{ROOM_CODE}.json', timeout=15)
        room_data = response.json()
    except Exception as e:
        print(f"Error fetching data: {e}")
        return

    if not room_data:
        print("No room data found.")
        return

    participants = room_data.get('participants', [])
    if isinstance(participants, dict):
        participants = list(participants.values())
        
    updates_to_push = {}
    
    # User Instructions:
    # Arrow -> USED (True)
    # Everyone else -> NOT USED (False/None)
    
    print("\n[Applying Manual Fixes]")
    for i, p in enumerate(participants):
        if isinstance(p, dict):
            name = p.get('name')
            paid_rels = p.get('paid_releases', {})
            
            # Helper to set GW2 flag
            def set_gw2_flag(val):
                nonlocal paid_rels
                if isinstance(paid_rels, list):
                    while len(paid_rels) <= 2:
                        paid_rels.append(None)
                    paid_rels[2] = val
                else:
                    paid_rels['2'] = val
                return paid_rels

            if name == 'Arrow':
                print(f"  Arrow: Ensuring GW2 Flag is TRUE")
                p['paid_releases'] = set_gw2_flag(True)
            else:
                 # Reset everyone else to allowed
                 print(f"  {name}: Resetting GW2 Flag to FALSE (Allowed)")
                 p['paid_releases'] = set_gw2_flag(False)
    
    # Push Updates
    print("\n[Pushing Updates to Firebase...]")
    # We update the whole participants list to be safe
    room_data['participants'] = participants
    
    try:
        resp = requests.put(f'{FIREBASE_URL}/auction_data/rooms/{ROOM_CODE}/participants.json', json=participants)
        if resp.status_code == 200:
             print("✅ Manual Fix Applied Successfully!")
        else:
             print(f"❌ Update Failed: {resp.status_code}")
    except Exception as e:
        print(f"❌ Update Error: {e}")

if __name__ == "__main__":
    fix_flags()
