"""
Script to swap Josh Hazlewood -> Steven Smith in auction_data.json.
Updates all squad entries, team lists, and gameweek snapshots.
"""
import json
import os

AUCTION_FILE = os.path.join(os.path.dirname(__file__), "auction_data.json")

OLD_NAME = "Josh Hazlewood"
NEW_NAME = "Steven Smith"
NEW_ROLE = "Batsman"

def swap_player_in_data(data, old_name, new_name, new_role):
    """Recursively find and replace player name in all data structures."""
    changes = 0
    
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, str) and value == old_name:
                data[key] = new_name
                changes += 1
                print(f"  Replaced string value: {key} = '{old_name}' -> '{new_name}'")
            elif isinstance(value, dict):
                # Check if this is a player object with 'name' field
                if value.get('name') == old_name:
                    value['name'] = new_name
                    value['role'] = new_role
                    changes += 1
                    print(f"  Replaced player object: {old_name} -> {new_name} (role: {new_role})")
                else:
                    changes += swap_player_in_data(value, old_name, new_name, new_role)
            elif isinstance(value, list):
                changes += swap_player_in_list(value, old_name, new_name, new_role)
    
    return changes

def swap_player_in_list(data, old_name, new_name, new_role):
    """Handle lists: could contain strings or dicts."""
    changes = 0
    for i, item in enumerate(data):
        if isinstance(item, str) and item == old_name:
            data[i] = new_name
            changes += 1
            print(f"  Replaced list item: '{old_name}' -> '{new_name}'")
        elif isinstance(item, dict):
            if item.get('name') == old_name:
                item['name'] = new_name
                item['role'] = new_role
                changes += 1
                print(f"  Replaced player dict: {old_name} -> {new_name} (role: {new_role})")
            else:
                changes += swap_player_in_data(item, old_name, new_name, new_role)
        elif isinstance(item, list):
            changes += swap_player_in_list(item, old_name, new_name, new_role)
    return changes

def main():
    print(f"Loading {AUCTION_FILE}...")
    with open(AUCTION_FILE, 'r') as f:
        data = json.load(f)
    
    print(f"\nSwapping '{OLD_NAME}' -> '{NEW_NAME}' ({NEW_ROLE})...")
    total_changes = swap_player_in_data(data, OLD_NAME, NEW_NAME, NEW_ROLE)
    
    print(f"\nTotal changes: {total_changes}")
    
    if total_changes > 0:
        with open(AUCTION_FILE, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"✅ Saved updated auction_data.json")
    else:
        print("⚠️ No changes made.")

if __name__ == "__main__":
    main()
