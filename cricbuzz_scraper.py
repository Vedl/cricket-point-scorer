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
            # print(f"DEBUG: Fetching Role from {full_url}")
            response = requests.get(full_url, headers=self.headers)
            if response.status_code != 200: return 'Unknown'
            
            soup = BeautifulSoup(response.content, 'html.parser')
            # Look for div containing "Role"
            # Based on debug: <div ...>Role</div> sibling is the value
            role_label = soup.find(string="Role")
            if role_label:
                parent = role_label.parent
                # The structure is usually label div -> value div in a flex container
                # sibling
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
        
        players = {} 

        def get_best_match_player(name_fragment):
            """
            Attempts to find an existing player whose name contains the fragment.
            Useful for linking 'Conway' (catch) to 'Devon Conway' (batter).
            """
            if name_fragment in players:
                return players[name_fragment]
            
            # Helper to normalize names for comparison
            def normalize(n): return n.lower().replace('.', ' ').strip()
            
            fragment_norm = normalize(name_fragment)
            
            # 1. Try exact last name match first (most common)
            # e.g. 'Conway' -> 'Devon Conway'
            for pname in players:
                parts = pname.split()
                if len(parts) > 1 and normalize(parts[-1]) == fragment_norm:
                    return players[pname]
                    
            # 2. Try strict substring (word boundary preferred)
            # e.g. 'J Bairstow' -> 'Jonny Bairstow' matches 'Bairstow'
            for pname in players:
                pname_norm = normalize(pname)
                # Check if fragment is a distinct part of the name
                if f" {fragment_norm} " in f" {pname_norm} ":
                    return players[pname]
            
            # 3. Fallback: Loose substring (risky for short names like 'Wade' in 'Wadekar' but rare in match content)
            for pname in players:
                if fragment_norm in normalize(pname):
                    return players[pname]
                    
            # No match found, create new (likely sub fielder or unmatched)
            return get_player(name_fragment)

        def get_player(name, profile_url=None):
            if name not in players:
                players[name] = {
                    'name': name,
                    'is_batter_or_allrounder': False,
                    'role': 'Unknown',
                    'profile_url': profile_url
                }
            # Update url if missing
            if profile_url and not players[name]['profile_url']:
                players[name]['profile_url'] = profile_url
            return players[name]

        # --- Pre-Scan Players from Scorecard Sections Only ---
        # Only scan within scorecard containers to avoid picking up coaches, commentators, etc.
        # We look for profile links within batting AND bowling grids specifically.
        scorecard_containers = soup.find_all(lambda tag: tag.name == 'div' and tag.get('class') and 
            any('scorecard' in c.lower() for c in tag.get('class', [])))
        
        for container in scorecard_containers:
            profile_links = container.find_all('a', href=re.compile(r'^/profiles/'))
            for link in profile_links:
                name = link.get_text().strip()
                url = link.get('href')
                # Valid player names don't have commas (unlike "Lastname, Firstname" format)
                # and are reasonably short
                if name and len(name) < 50 and ',' not in name:
                     name_clean = re.sub(r'\s*\(.*?\)', '', name).strip()
                     get_player(name_clean, url)
        
        # --- Batting Parsing ---
        # --- Batting Parsing ---
        # Strictly look for 'wb:scorecard-bat-grid-web' to target desktop view and avoid duplicates
        bat_rows = soup.find_all(lambda tag: tag.name == 'div' and tag.get('class') and 'wb:scorecard-bat-grid-web' in tag.get('class'))
        
        for row in bat_rows:
            cols = row.find_all(recursive=False)
            if len(cols) < 5: continue 
            
            # Header check
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
                # Use assignment = instead of += to be safe against accidental row duplication
                # T20/ODI logic: 1 innings per player usually. 
                runs = int(cols[1].get_text().strip())
                balls = int(cols[2].get_text().strip())
                fours = int(cols[3].get_text().strip())
                sixes = int(cols[4].get_text().strip())
                
                p = get_player(player_name_clean, profile_url)
                p['runs'] = runs
                p['balls_faced'] = balls
                p['fours'] = fours
                p['sixes'] = sixes
                p['is_batter_or_allrounder'] = True
                
                # Dismissal Processing (Fielding)
                # Note: Fielding stats accumulate because a player can catch multiple times.
                # However, since we process each unique row once now, += is correct for fielding attribution.
                
                if 'b ' in dismissal_text: 
                    parts = dismissal_text.split(' b ')
                    if len(parts) > 1:
                        bowler_name = parts[1].strip()
                        # Can't easily get profile URL here without lookup, assume scraped later in bowling
                        bp = get_player(bowler_name)
                        if dismissal_text.strip().startswith('b ') or 'lbw ' in dismissal_text:
                            if 'c & b' not in dismissal_text:
                                bp['lbw_bowled_bonus'] = bp.get('lbw_bowled_bonus', 0) + 1

                if 'c ' in dismissal_text:
                     if 'c & b' in dismissal_text:
                         bowler_name = dismissal_text.split('c & b')[1].strip()
                         # Bowler is usually already in players/processed, but might not be if parsing order varies
                         # Use simple get for bowler as name is usually more complete here? 
                         # Actually c & b usually has 'c & b BowlerName'.
                         cp = get_best_match_player(bowler_name) 
                         cp['catches'] = cp.get('catches', 0) + 1
                     else:
                         if ' b ' in dismissal_text:
                             catcher_part = dismissal_text.split(' b ')[0]
                             ifcatcher_name = catcher_part.replace('c ', '', 1).strip()
                             ifcatcher_name = re.sub(r'\(.*?\)', '', ifcatcher_name).strip()
                             
                             # Use Fuzzy Match
                             cp = get_best_match_player(ifcatcher_name)
                             cp['catches'] = cp.get('catches', 0) + 1

                if 'st ' in dismissal_text and 'b ' in dismissal_text:
                     stumper_part = dismissal_text.split(' b ')[0]
                     stumper_name = stumper_part.replace('st ', '', 1).strip()
                     sp = get_best_match_player(stumper_name)
                     sp['stumpings'] = sp.get('stumpings', 0) + 1

                if 'run out' in dismissal_text:
                     # Regex to find content in brackets: run out (Fielder1/Fielder2)
                     match = re.search(r'run out \((.*?)\)', dismissal_text)
                     if match:
                         fielders = match.group(1).split('/')
                         for f in fielders:
                             f_clean = re.sub(r'\(.*?\)', '', f).strip()
                             fp = get_best_match_player(f_clean)
                             if len(fielders) == 1:
                                 fp['run_outs_direct'] = fp.get('run_outs_direct', 0) + 1
                             else:
                                 fp['run_outs_throw'] = fp.get('run_outs_throw', 0) + 1
                                 
            except (ValueError, IndexError):
                pass
                
        # --- Bowling Parsing ---
        # Strictly look for 'wb:scorecard-bowl-grid-web'
        bowl_rows = soup.find_all(lambda tag: tag.name == 'div' and tag.get('class') and 'wb:scorecard-bowl-grid-web' in tag.get('class'))
        
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
                
                p = get_player(bowler_name_clean, profile_url)
                p['wickets'] = wickets # Assignment =
                p['overs_bowled'] = overs
                p['maidens'] = maidens
                p['runs_conceded'] = runs
                
            except (ValueError, IndexError):
                pass

        # --- Assign Roles (Fast Local Lookup) ---
        # Use local database for instant role lookup; fallback to HTTP only if not found
        print("Assigning player roles...")
        for p in players.values():
            name = p['name']
            # Try local database first (instant)
            if name in self.player_roles:
                p['role'] = self.player_roles[name]
            else:
                # Fallback: try HTTP fetch (slow) - only for non-WC players
                if p.get('profile_url'):
                    p['role'] = self.get_player_role(p['profile_url'])
                else:
                    p['role'] = 'Unknown'
        
        # --- Post-Processing: Deduplicate Fragments ---
        # Remove fragment entries (short names with no batting/bowling stats) if a matching full name exists
        def normalize(n): return n.lower().replace('.', ' ').strip()
        
        # Identify real players (those with actual stats)
        real_players = {k: v for k, v in players.items() 
                        if v.get('runs') is not None or v.get('wickets') is not None or v.get('overs_bowled') is not None}
        
        # Identify fragment candidates (no stats, likely from fielding credits)
        fragments = {k: v for k, v in players.items() if k not in real_players}
        
        # Merge fragment stats into real players if match found
        for frag_name, frag_data in list(fragments.items()):
            frag_norm = normalize(frag_name)
            merged = False
            
            for real_name, real_data in real_players.items():
                real_norm = normalize(real_name)
                # Check if fragment is a suffix/substring of real name
                if frag_norm in real_norm or real_norm.endswith(frag_norm):
                    # Merge fielding stats
                    real_data['catches'] = real_data.get('catches', 0) + frag_data.get('catches', 0)
                    real_data['stumpings'] = real_data.get('stumpings', 0) + frag_data.get('stumpings', 0)
                    real_data['run_outs_direct'] = real_data.get('run_outs_direct', 0) + frag_data.get('run_outs_direct', 0)
                    real_data['run_outs_throw'] = real_data.get('run_outs_throw', 0) + frag_data.get('run_outs_throw', 0)
                    merged = True
                    break
            
            # If merged, remove the fragment from players dict
            if merged:
                del players[frag_name]
                
        return list(players.values())
