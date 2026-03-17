
import re

# Mock canonical players database
canonical_players = {
    'Daryl Mitchell': {'name': 'Daryl Mitchell', 'role': 'bat_ar'},
    'Mitchell Santner': {'name': 'Mitchell Santner', 'role': 'bowl_ar'},
    'Lockie Ferguson': {'name': 'Lockie Ferguson', 'role': 'bowler'},
    'Glenn Phillips': {'name': 'Glenn Phillips', 'role': 'batsman'},
}

def normalize(name):
    return name.lower().strip()

def find_canonical_match(name_fragment):
    """
    Find the best matching canonical player for a name fragment.
    Returns the canonical player dict, or None if no match.
    """
    if name_fragment in canonical_players:
        return canonical_players[name_fragment]
    
    frag_norm = normalize(name_fragment)
    
    # Strategy 1: Exact last name match (Strict)
    # If fragment is single word, match against LAST name only.
    if ' ' not in name_fragment:
         for pname, pdata in canonical_players.items():
            parts = pname.split()
            if len(parts) > 1 and normalize(parts[-1]) == frag_norm:
                print(f"DEBUG: Matched '{name_fragment}' to '{pname}' via Last Name Strict")
                return pdata
    
    # Strategy 2: Fragment is contained in canonical name (Be careful!)
    # ONLY if fragment is long enough or contains spaces
    if len(frag_norm) > 4 or ' ' in frag_norm:
        for pname, pdata in canonical_players.items():
            pname_norm = normalize(pname)
            if frag_norm in pname_norm:
                print(f"DEBUG: Matched '{name_fragment}' to '{pname}' via Containment")
                return pdata
    
    # Strategy 3: Canonical name starts/ends with fragment
    for pname, pdata in canonical_players.items():
        p_norm = normalize(pname)
        if p_norm.endswith(frag_norm) or p_norm.startswith(frag_norm):
            print(f"DEBUG: Matched '{name_fragment}' to '{pname}' via Start/End")
            return pdata
    
    return None

def get_or_create_player(name):
    match = find_canonical_match(name)
    if match:
        return match
    print(f"DEBUG: Creating new player '{name}'")
    p = {'name': name, 'catches': 0}
    canonical_players[name] = p
    return p

# Test Cases based on screenshot
dismissals = [
    "c Daryl Mitchell b Mitchell Santner",  # Should be Catch: DM, Bowl: MS
    "c Mitchell Santner b Lockie Ferguson", # Should be Catch: MS, Bowl: LF
    "c Mitchell b Santner", # Should be Catch: DM
    "c Santner b Mitchell", # Should be Catch: MS
    "c & b Mitchell", # Should be Catch: DM
    "c & b Santner"   # Should be Catch: MS
]

print("=== STARTING TESTS ===")

for dismissal_text in dismissals:
    print(f"\nProcessing: '{dismissal_text}'")
    
    if 'c ' in dismissal_text:
         if 'c & b' in dismissal_text:
             bowler_name = dismissal_text.split('c & b')[1].strip()
             cp = get_or_create_player(bowler_name) 
             cp['catches'] = cp.get('catches', 0) + 1
             print(f" -> Catch credited to: {cp['name']}")
         else:
             if ' b ' in dismissal_text:
                 catcher_part = dismissal_text.split(' b ')[0]
                 catcher_name = catcher_part.replace('c ', '', 1).strip()
                 catcher_name = re.sub(r'\(.*?\)', '', catcher_name).strip()
                 
                 print(f" -> Catcher Name Parsed: '{catcher_name}'")
                 cp = get_or_create_player(catcher_name)
                 cp['catches'] = cp.get('catches', 0) + 1
                 print(f" -> Catch credited to: {cp['name']}")

print("\n=== FINAL COUNTS ===")
for name, p in canonical_players.items():
    if p.get('catches', 0) > 0:
        print(f"{name}: {p['catches']} catches")
