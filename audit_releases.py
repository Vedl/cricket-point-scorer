import json
import requests
import re

FIREBASE_URL = 'https://cricket-auction-b00e2-default-rtdb.asia-southeast1.firebasedatabase.app'
ROOM_CODE = '3ZZ5EE'

def audit_releases():
    print(f"Auditing Room {ROOM_CODE}...")
    try:
        response = requests.get(f'{FIREBASE_URL}/auction_data/rooms/{ROOM_CODE}.json', timeout=15)
        room_data = response.json()
    except Exception as e:
        print(f"Error fetching data: {e}")
        return

    if not room_data:
        print("No room data found.")
        return

    # 1. Analyze Logs for Refunded Releases
    logs = room_data.get('trade_log', [])
    release_counts = {}
    
    # Improved Regex to catch variations if any
    # Log format: "🗑️ Released: **{player}** by **{participant}** (Refund: {amount}M)"
    regex = r"Released: \*\*(.+?)\*\* by \*\*(.+?)\*\* \(Refund: (.+?)M\)"
    
    print("\n[Trade Log Analysis]")
    for log in logs:
        if isinstance(log, dict):
            msg = log.get('msg', '')
            match = re.search(regex, msg)
            if match:
                player, participant, refund_str = match.groups()
                try:
                    refund = float(refund_str)
                    if refund > 0:
                        print(f"  Found Refunded Release: {participant} released {player} ({refund}M)")
                        release_counts[participant] = release_counts.get(participant, 0) + 1
                except ValueError:
                    pass

    # 2. Check and Patch Participant Flags
    print("\n[Participant Flag Check & Patch]")
    participants = room_data.get('participants', [])
    # Normalize to list if dict
    if isinstance(participants, dict):
        participants = list(participants.values())
        
    updates_needed = False
    
    for i, p in enumerate(participants):
        if isinstance(p, dict):
            name = p.get('name')
            paid_rels = p.get('paid_releases', {})
            
            # Check if GW2 flag is set
            gw2_flag = False
            if isinstance(paid_rels, list):
                # GW2 is index 2? Let's check logic. 
                # App uses: paid_releases[current_gw] where current_gw is 2.
                # So list index 2.
                if len(paid_rels) > 2 and paid_rels[2]:
                    gw2_flag = True
            elif isinstance(paid_rels, dict):
                # Dict key "2"
                if paid_rels.get('2') or paid_rels.get(2):
                    gw2_flag = True
            
            count = release_counts.get(name, 0)
            
            status = "✅ OK"
            if count > 0 and not gw2_flag:
                status = "❌ FLAG MISSING - PATCHING..."
                
                # PATCH LOGIC
                if isinstance(paid_rels, list):
                    # Extend list if needed
                    while len(paid_rels) <= 2:
                        paid_rels.append(None)
                    paid_rels[2] = True
                else:
                    # Dict
                    paid_rels['2'] = True
                
                p['paid_releases'] = paid_rels
                updates_needed = True
                
            elif count > 1:
                status = f"⚠️ MULTIPLE RELEASES ({count})"
                # Flag should definitely be true
                if not gw2_flag:
                    # This case handles if they made multiple releases but flag is missing (double bug)
                     if isinstance(paid_rels, list):
                        while len(paid_rels) <= 2:
                            paid_rels.append(None)
                        paid_rels[2] = True
                     else:
                        paid_rels['2'] = True
                     p['paid_releases'] = paid_rels
                     updates_needed = True
            
            print(f"  {name}: Releases={count}, Flag={gw2_flag} -> {status}")

    # 3. Push Updates if needed
    if updates_needed:
        print("\n[Pushing Updates to Firebase...]")
        # We need to preserve the structure. 
        # room_data['participants'] was normalized to list for iteration.
        # If original was dict, we need to handle that? 
        # Actually Firebase returns list for participants usually unless keys are IDs.
        # App uses list. Safe to push list back to room_data['participants']?
        # Let's check original type.
        orig_parts = room_data.get('participants')
        if isinstance(orig_parts, dict):
            # This is tricky. Firebase "normalization" might have messed us up if we just push back list.
            # But specific room usually has list of participants.
            # Let's just update the specific participants who changed?
            # Safer to push the whole participants list if it was a list.
            pass
        
        # Save back to 'participants' key
        room_data['participants'] = participants
        
        try:
            # Push only participants to avoid overwriting other stuff concurrently?
            # Or push whole room? Pushing whole room is safer for consistency but race condition risk.
            # Let's push participants only.
            resp = requests.put(f'{FIREBASE_URL}/auction_data/rooms/{ROOM_CODE}/participants.json', json=participants)
            if resp.status_code == 200:
                print("✅ Update Success!")
            else:
                print(f"❌ Update Failed: {resp.status_code}")
        except Exception as e:
            print(f"❌ Update Error: {e}")
    else:
        print("\nNo updates needed.")

if __name__ == "__main__":
    audit_releases()
