#!/usr/bin/env python3
"""
Quick script to reverse a wrongly-processed elimination.
Run this after the fix is deployed to Render.

Usage:
    python3 scratch/reverse_elimination.py <ROOM_CODE>
"""
import sys
import requests
import json

BASE_URL = "https://cricket-point-scorer.onrender.com"

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scratch/reverse_elimination.py <ROOM_CODE>")
        print("\nThis will reverse the most recent elimination in the room.")
        sys.exit(1)

    room_code = sys.argv[1]
    admin_name = "Ladda CC"

    print(f"🔄 Reversing elimination in room {room_code}...")
    print(f"   Admin: {admin_name}")
    print(f"   URL: {BASE_URL}/auction/reverse-elimination")
    print()

    try:
        resp = requests.post(
            f"{BASE_URL}/auction/reverse-elimination",
            json={"room_code": room_code, "admin_name": admin_name},
            timeout=60,
        )
        
        if resp.status_code == 200:
            result = resp.json()
            print("✅ SUCCESS!")
            print(f"   Message: {result.get('message')}")
            print(f"   Restored: {result.get('restored')}")
            print(f"   Squad source: {result.get('squad_source')}")
        else:
            print(f"❌ FAILED (HTTP {resp.status_code})")
            try:
                print(f"   Detail: {resp.json().get('detail', resp.text)}")
            except:
                print(f"   Response: {resp.text}")
    except requests.exceptions.ConnectionError:
        print("❌ Connection failed — Render may still be deploying. Try again in a minute.")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
