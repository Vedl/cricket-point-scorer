#!/usr/bin/env python3
"""
Robust Backup & Restore Tool for Cricket Auction
Run: python3 backup_restore.py [backup|restore|list]
"""

import json
import os
import sys
import shutil
from datetime import datetime

DATA_FILE = "auction_data.json"
BACKUP_DIR = "backups"

def create_backup(name_suffix=""):
    """Create a timestamped backup with optional name suffix."""
    if not os.path.exists(DATA_FILE):
        print("❌ No auction_data.json found!")
        return None
    
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if name_suffix:
        backup_name = f"auction_{timestamp}_{name_suffix}.json"
    else:
        backup_name = f"auction_{timestamp}.json"
    
    backup_path = os.path.join(BACKUP_DIR, backup_name)
    shutil.copy2(DATA_FILE, backup_path)
    
    # Verify backup
    with open(backup_path, 'r') as f:
        data = json.load(f)
    
    room_count = len(data.get('rooms', {}))
    user_count = len(data.get('users', {}))
    
    print(f"✅ Backup created: {backup_name}")
    print(f"   Rooms: {room_count}, Users: {user_count}")
    print(f"   Size: {os.path.getsize(backup_path) / 1024:.1f} KB")
    
    return backup_path

def list_backups():
    """List all available backups sorted by date."""
    if not os.path.exists(BACKUP_DIR):
        print("No backups directory found.")
        return []
    
    backups = [f for f in os.listdir(BACKUP_DIR) if f.endswith('.json')]
    backups.sort(reverse=True)  # Newest first
    
    print(f"\n📁 Available Backups ({len(backups)} total):\n")
    print(f"{'#':<4} {'Filename':<40} {'Size':<10} {'Rooms':<8}")
    print("-" * 65)
    
    for i, backup in enumerate(backups[:20], 1):  # Show last 20
        path = os.path.join(BACKUP_DIR, backup)
        size = os.path.getsize(path) / 1024
        
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            room_count = len(data.get('rooms', {}))
        except:
            room_count = "?"
        
        print(f"{i:<4} {backup:<40} {size:.1f} KB     {room_count}")
    
    return backups

def restore_backup(backup_name=None, backup_number=None):
    """Restore from a backup file."""
    if not os.path.exists(BACKUP_DIR):
        print("❌ No backups directory found!")
        return False
    
    backups = sorted([f for f in os.listdir(BACKUP_DIR) if f.endswith('.json')], reverse=True)
    
    if not backups:
        print("❌ No backups available!")
        return False
    
    # Select backup
    if backup_number is not None:
        if 1 <= backup_number <= len(backups):
            backup_name = backups[backup_number - 1]
        else:
            print(f"❌ Invalid backup number. Choose 1-{len(backups)}")
            return False
    elif backup_name is None:
        print("Available backups:")
        list_backups()
        print("\nUsage: python3 backup_restore.py restore <number>")
        return False
    
    backup_path = os.path.join(BACKUP_DIR, backup_name)
    if not os.path.exists(backup_path):
        print(f"❌ Backup not found: {backup_name}")
        return False
    
    # Create safety backup of current state before restoring
    if os.path.exists(DATA_FILE):
        safety_backup = create_backup("pre_restore")
        print(f"   (Safety backup created: {safety_backup})")
    
    # Restore
    shutil.copy2(backup_path, DATA_FILE)
    
    # Verify
    with open(DATA_FILE, 'r') as f:
        data = json.load(f)
    
    room_count = len(data.get('rooms', {}))
    user_count = len(data.get('users', {}))
    
    print(f"\n✅ Restored from: {backup_name}")
    print(f"   Rooms: {room_count}, Users: {user_count}")
    
    return True

def show_room_summary(room_code=None):
    """Show summary of a specific room or all rooms."""
    with open(DATA_FILE, 'r') as f:
        data = json.load(f)
    
    rooms = data.get('rooms', {})
    
    if room_code:
        if room_code not in rooms:
            print(f"❌ Room {room_code} not found!")
            return
        rooms = {room_code: rooms[room_code]}
    
    print(f"\n🏏 Room Summary:\n")
    print(f"{'Code':<10} {'Name':<25} {'Members':<8} {'GW':<4} {'Phase':<12}")
    print("-" * 70)
    
    for code, room in rooms.items():
        name = room.get('name', 'Unknown')[:24]
        members = len(room.get('members', []))
        gw = room.get('current_gameweek', 1)
        phase = room.get('game_phase', 'N/A')
        print(f"{code:<10} {name:<25} {members:<8} {gw:<4} {phase:<12}")

def main():
    if len(sys.argv) < 2:
        print("""
Cricket Auction Backup & Restore Tool
======================================

Commands:
  python3 backup_restore.py backup [name]     Create a backup (optional name suffix)
  python3 backup_restore.py list              List all backups
  python3 backup_restore.py restore <number>  Restore backup by number
  python3 backup_restore.py rooms [CODE]      Show room summary
  python3 backup_restore.py verify            Verify current data integrity

Examples:
  python3 backup_restore.py backup pre_gw2_lock
  python3 backup_restore.py restore 1
  python3 backup_restore.py rooms YMMO07
        """)
        return
    
    cmd = sys.argv[1].lower()
    
    if cmd == "backup":
        suffix = sys.argv[2] if len(sys.argv) > 2 else ""
        create_backup(suffix)
    
    elif cmd == "list":
        list_backups()
    
    elif cmd == "restore":
        if len(sys.argv) > 2:
            try:
                num = int(sys.argv[2])
                restore_backup(backup_number=num)
            except ValueError:
                restore_backup(backup_name=sys.argv[2])
        else:
            restore_backup()
    
    elif cmd == "rooms":
        room_code = sys.argv[2] if len(sys.argv) > 2 else None
        show_room_summary(room_code)
    
    elif cmd == "verify":
        try:
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
            print("✅ auction_data.json is valid JSON")
            print(f"   Rooms: {len(data.get('rooms', {}))}")
            print(f"   Users: {len(data.get('users', {}))}")
        except Exception as e:
            print(f"❌ Data verification failed: {e}")
    
    else:
        print(f"Unknown command: {cmd}")
        print("Use: backup, list, restore, rooms, verify")

if __name__ == "__main__":
    main()
