import requests
from bs4 import BeautifulSoup
import re
import json
import os

class CricbuzzScraper:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'
        }
        # Load player roles from local database for fast lookup
        self.player_roles = {}
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'players_database.json')
        if os.path.exists(db_path):
            try:
                with open(db_path, 'r') as f:
                    data = json.load(f)
                    for p in data.get('players', []):
                        self.player_roles[p['name']] = p['role']
            except:
                pass

    def get_player_role(self, profile_url):
        """
        Fetches the player's role from their Cricbuzz profile page.
        """
        if not profile_url:
            return 'Unknown'
            
        full_url = f"https://www.cricbuzz.com{profile_url}"
        try:
            response = requests.get(full_url, headers=self.headers)
            if response.status_code != 200: return 'Unknown'
            
            soup = BeautifulSoup(response.content, 'html.parser')
            role_label = soup.find(string="Role")
            if role_label:
                parent = role_label.parent
                role_value_div = parent.find_next_sibling('div')
                if role_value_div:
                    return role_value_div.get_text().strip()
            
            return 'Unknown'
        except Exception:
            return 'Unknown'

    def fetch_match_data(self, url):
        """
        Fetches match data from a Cricbuzz scorecard URL.
        Returns a list of player stats dictionaries.
        """
        # Ensure we are requesting the scorecard page
        if '/live-cricket-scores/' in url:
             url = url.replace('/live-cricket-scores/', '/live-cricket-scorecard/')
        elif '/cricket-scores/' in url:
             url = url.replace('/cricket-scores/', '/live-cricket-scorecard/')

        print(f"DEBUG: Fetching {url}")
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
        except Exception as e:
            print(f"Error fetching URL: {e}")
            return []

        soup = BeautifulSoup(response.content, 'html.parser')
        
        # === PHASE 1: Build Canonical Player List from Batting+Bowling Grids ===
        # These grids contain full player names with profile links
        canonical_players = {}  # name -> {profile_url, role, ...}
        
        def normalize(n): 
            return n.lower().replace('.', ' ').replace('-', ' ').strip()
        
        def add_canonical(name, profile_url=None):
            name_clean = re.sub(r'\s*\(.*?\)', '', name).strip()
            if name_clean and name_clean not in canonical_players:
                canonical_players[name_clean] = {
                    'name': name_clean,
                    'profile_url': profile_url,
                    'role': 'Unknown',
                    'is_batter_or_allrounder': False
                }
            elif profile_url and name_clean in canonical_players and not canonical_players[name_clean].get('profile_url'):
                canonical_players[name_clean]['profile_url'] = profile_url
            return canonical_players.get(name_clean)
        
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
                        return pdata
            
            # Strategy 2: Fragment is contained in canonical name (Be careful!)
            # ONLY if fragment is long enough or contains spaces
            if len(frag_norm) > 4 or ' ' in frag_norm:
                for pname, pdata in canonical_players.items():
                    pname_norm = normalize(pname)
                    if frag_norm in pname_norm:
                        return pdata
            
            # Strategy 3: Canonical name starts/ends with fragment
            for pname, pdata in canonical_players.items():
                p_norm = normalize(pname)
                if p_norm.endswith(frag_norm) or p_norm.startswith(frag_norm):
                    return pdata
            
            return None
        
        def get_or_create_player(name, profile_url=None):
            """
            Get a canonical player if match found, otherwise create new entry.
            """
            # Try to find canonical match first
            match = find_canonical_match(name)
            if match:
                if profile_url and not match.get('profile_url'):
                    match['profile_url'] = profile_url
                return match
            
            # No match - add as new canonical player
            return add_canonical(name, profile_url)
        
        # --- PHASE 1a: Pre-scan batting grid for canonical names ---
        bat_rows = soup.find_all(lambda tag: tag.name == 'div' and tag.get('class') and 'wb:scorecard-bat-grid-web' in tag.get('class'))
        for row in bat_rows:
            name_tag = row.find('a', href=re.compile(r'^/profiles/'))
            if name_tag:
                name = name_tag.get_text().strip()
                url = name_tag.get('href')
                add_canonical(name, url)
        
        # --- PHASE 1b: Pre-scan bowling grid for canonical names ---
        bowl_rows = soup.find_all(lambda tag: tag.name == 'div' and tag.get('class') and 'wb:scorecard-bowl-grid-web' in tag.get('class'))
        for row in bowl_rows:
            cols = row.find_all(recursive=False)
            if cols and cols[0].name == 'a':
                name = cols[0].get_text().strip()
                url = cols[0].get('href')
                add_canonical(name, url)
        
        print(f"DEBUG: Found {len(canonical_players)} canonical players from scorecard")
        
        # === PHASE 2: Parse Batting Stats (assign to canonical players) ===
        for row in bat_rows:
            cols = row.find_all(recursive=False)
            if len(cols) < 5: continue 
            
            if 'Batter' in row.get_text(): continue
            if 'Extras' in row.get_text(): continue
            if 'Total' in row.get_text(): continue

            name_col = cols[0]
            player_name_tag = name_col.find('a')
            if not player_name_tag: continue

            player_name = player_name_tag.get_text().strip()
            player_name_clean = re.sub(r'\s*\(.*?\)', '', player_name).strip()
            profile_url = player_name_tag.get('href')
            
            dismissal_div = name_col.find('div', class_='text-cbTxtSec') 
            dismissal_text = ""
            if dismissal_div:
                dismissal_text = dismissal_div.get_text().strip()
            else:
                full_text = name_col.get_text(" ", strip=True)
                dismissal_text = full_text.replace(player_name, "").strip()

            try:
                runs = int(cols[1].get_text().strip())
                balls = int(cols[2].get_text().strip())
                fours = int(cols[3].get_text().strip())
                sixes = int(cols[4].get_text().strip())
                
                p = get_or_create_player(player_name_clean, profile_url)
                p['runs'] = runs
                p['balls_faced'] = balls
                p['fours'] = fours
                p['sixes'] = sixes
                p['is_batter_or_allrounder'] = True
                
                # Check if player is "not out"
                is_not_out = 'not out' in dismissal_text.lower()
                p['is_not_out'] = is_not_out
                
                # Dismissal Processing (Fielding credits)
                if 'b ' in dismissal_text: 
                    parts = dismissal_text.split(' b ')
                    if len(parts) > 1:
                        bowler_name = parts[1].strip()
                        bp = get_or_create_player(bowler_name)
                        if dismissal_text.strip().startswith('b ') or 'lbw ' in dismissal_text:
                            if 'c & b' not in dismissal_text:
                                bp['lbw_bowled_bonus'] = bp.get('lbw_bowled_bonus', 0) + 1

                if 'c ' in dismissal_text:
                     if 'c & b' in dismissal_text:
                         bowler_name = dismissal_text.split('c & b')[1].strip()
                         cp = get_or_create_player(bowler_name) 
                         cp['catches'] = cp.get('catches', 0) + 1
                     else:
                         if ' b ' in dismissal_text:
                             catcher_part = dismissal_text.split(' b ')[0]
                             catcher_name = catcher_part.replace('c ', '', 1).strip()
                             catcher_name = re.sub(r'\(.*?\)', '', catcher_name).strip()
                             
                             # DEBUG: Check if we are matching "Mitchell" to "Daryl Mitchell" when it should be "Mitchell Santner"
                             # Logic: If catcher_name is a single word (Last Name), prefer finding a player whose last name matches EXACTLY
                             # and avoid partial matches if possible.
                             # Actually `get_or_create_player` has the matching logic. 
                             # The issue is `find_canonical_match` might be too aggressive with containment.
                             # Let's clean the name better first?
                             
                             cp = get_or_create_player(catcher_name)
                             cp['catches'] = cp.get('catches', 0) + 1

                if 'st ' in dismissal_text and 'b ' in dismissal_text:
                     stumper_part = dismissal_text.split(' b ')[0]
                     stumper_name = stumper_part.replace('st ', '', 1).strip()
                     sp = get_or_create_player(stumper_name)
                     sp['stumpings'] = sp.get('stumpings', 0) + 1

                if 'run out' in dismissal_text:
                     match = re.search(r'run out \((.*?)\)', dismissal_text)
                     if match:
                         fielders = match.group(1).split('/')
                         for f in fielders:
                             f_clean = re.sub(r'\(.*?\)', '', f).strip()
                             fp = get_or_create_player(f_clean)
                             if len(fielders) == 1:
                                 fp['run_outs_direct'] = fp.get('run_outs_direct', 0) + 1
                             else:
                                 fp['run_outs_throw'] = fp.get('run_outs_throw', 0) + 1
                                 
            except (ValueError, IndexError):
                pass
                
        # === PHASE 3: Parse Bowling Stats ===
        for row in bowl_rows:
            cols = row.find_all(recursive=False)
            if len(cols) < 8: continue
            
            if 'Bowler' in row.get_text(): continue
            
            name_tag = cols[0]
            if name_tag.name != 'a': continue
            
            bowler_name = name_tag.get_text().strip()
            bowler_name_clean = re.sub(r'\s*\(.*?\)', '', bowler_name).strip()
            profile_url = name_tag.get('href')
            
            try:
                overs = float(cols[1].get_text().strip())
                maidens = int(cols[2].get_text().strip())
                runs = int(cols[3].get_text().strip())
                wickets = int(cols[4].get_text().strip())
                
                p = get_or_create_player(bowler_name_clean, profile_url)
                p['wickets'] = wickets
                p['overs_bowled'] = overs
                p['maidens'] = maidens
                p['runs_conceded'] = runs
                
            except (ValueError, IndexError):
                pass

        # === PHASE 4: Final Merge Pass ===
        # Merge any remaining duplicates where one name is a substring of another
        # e.g., 'Holder' stats should merge into 'Jason Holder'
        
        names_to_remove = set()
        names_list = list(canonical_players.keys())
        
        for i, name1 in enumerate(names_list):
            if name1 in names_to_remove:
                continue
            for j in range(i + 1, len(names_list)):  # Only compare with later names to avoid double processing
                name2 = names_list[j]
                if name2 in names_to_remove:
                    continue
                
                n1_norm = normalize(name1)
                n2_norm = normalize(name2)
                
                words1 = set(n1_norm.split())
                words2 = set(n2_norm.split())
                
                # SAFEGUARD: Don't merge if either name has only 1 word
                # Single-word names are too risky for substring matching
                # (e.g., "Siraj" shouldn't auto-merge with "Mohammed Siraj")
                if len(words1) <= 1 or len(words2) <= 1:
                    continue
                
                # Check if names are likely the same person
                # Method 1: Simple substring (for multi-word names only)
                is_substring = n1_norm in n2_norm or n2_norm in n1_norm
                
                # Method 2: Word-based (all words from shorter appear in longer)
                is_word_match = words1.issubset(words2) or words2.issubset(words1)
                
                if is_substring or is_word_match:
                    data1 = canonical_players[name1]
                    data2 = canonical_players[name2]
                    
                    # Check which entry has more stats (batting/bowling stats indicate primary entry)
                    def has_stats(d):
                        return d.get('runs') is not None or d.get('wickets') is not None or d.get('overs_bowled') is not None
                    
                    stats1 = has_stats(data1)
                    stats2 = has_stats(data2)
                    
                    # Prefer entry with stats; if equal, prefer longer name
                    if stats1 and not stats2:
                        keep, discard = name1, name2
                    elif stats2 and not stats1:
                        keep, discard = name2, name1
                    elif len(name2) > len(name1):
                        keep, discard = name2, name1
                    else:
                        keep, discard = name1, name2
                    
                    keep_data = canonical_players[keep]
                    discard_data = canonical_players[discard]
                    
                    # Merge cumulative stats
                    for key in ['catches', 'stumpings', 'run_outs_direct', 'run_outs_throw', 'lbw_bowled_bonus']:
                        if discard_data.get(key):
                            keep_data[key] = keep_data.get(key, 0) + discard_data[key]
                    
                    # Copy over unique stats if missing in keep
                    for key in ['runs', 'balls_faced', 'fours', 'sixes', 'wickets', 'overs_bowled', 'maidens', 'runs_conceded']:
                        if discard_data.get(key) is not None and keep_data.get(key) is None:
                            keep_data[key] = discard_data[key]
                    
                    if discard_data.get('profile_url') and not keep_data.get('profile_url'):
                        keep_data['profile_url'] = discard_data['profile_url']
                    
                    if discard_data.get('is_batter_or_allrounder'):
                        keep_data['is_batter_or_allrounder'] = True
                    
                    names_to_remove.add(discard)
        
        for name in names_to_remove:
            del canonical_players[name]
        
        print(f"DEBUG: After merge pass: {len(canonical_players)} players")

        # === PHASE 5: Assign Roles ===
        print("Assigning player roles...")
        for p in canonical_players.values():
            name = p['name']
            if name in self.player_roles:
                p['role'] = self.player_roles[name]
            else:
                if p.get('profile_url'):
                    p['role'] = self.get_player_role(p['profile_url'])
                else:
                    p['role'] = 'Unknown'
                
        return list(canonical_players.values())
