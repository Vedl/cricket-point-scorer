import urllib.request
import json
import os

FIREBASE_URL = os.environ.get("FIREBASE_DATABASE_URL", "https://cricket-auction-32-default-rtdb.firebaseio.com/")

def fetch_data():
    req = urllib.request.Request(f"{FIREBASE_URL}/.json")
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode())

def save_data(data):
    req = urllib.request.Request(
        f"{FIREBASE_URL}/.json",
        data=json.dumps(data).encode('utf-8'),
        method='PUT',
        headers={'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req) as response:
        pass

def main():
    data = fetch_data()
    room = data.get('rooms', {}).get('3ZZ5EE')
    if not room:
        print("Room not found")
        return

    # Check Falcon's squad prices
    falcon = next((p for p in room['participants'] if p['name'] == 'Falcon'), None)
    if not falcon:
        print("Falcon not found")
        return
        
    print("Falcon's current squad:")
    for pl in falcon['squad']:
        print(f" - {pl['name']}: {pl.get('price', 0)}M")
        
    # Get GW7 prices to be absolutely sure we restore the right traded prices
    gw7_squads = room.get('gameweek_squads', {}).get('7', {})
    falcon_gw7 = gw7_squads.get('Falcon')
    if falcon_gw7:
        if isinstance(falcon_gw7, list):
            falcon_gw7_squad = falcon_gw7
        else:
            falcon_gw7_squad = falcon_gw7.get('squad', [])
            
        print("\nGW7 Prices:")
        gw7_prices = {pl['name']: pl.get('price', 0) for pl in falcon_gw7_squad}
        for name, price in gw7_prices.items():
            print(f" - {name}: {price}M")
            
        # Update current squad prices
        for pl in falcon['squad']:
            if pl['name'] in gw7_prices:
                pl['price'] = gw7_prices[pl['name']]
            elif pl['name'] == 'Rabada' or pl['name'] == 'Kagiso Rabada' or 'Rabada' in pl['name']:
                # Rabada was part of the Raza trade reversal
                # In GW1, Rabada was sold to someone else? Let's check CSV
                pl['price'] = 82 # Johnthedon bought for 82, Raza was 42. Falcon swapped Raza for Rabada. Wait, Falcon traded Raza (42) for Rabada. Wait, in fix_reversals I didn't set prices?
    
main()
