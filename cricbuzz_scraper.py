import requests
from bs4 import BeautifulSoup
import re

class CricbuzzScraper:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'
        }

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
                         cp = get_player(bowler_name)
                         cp['catches'] = cp.get('catches', 0) + 1
                     else:
                         if ' b ' in dismissal_text:
                             catcher_part = dismissal_text.split(' b ')[0]
                             ifcatcher_name = catcher_part.replace('c ', '', 1).strip()
                             ifcatcher_name = re.sub(r'\(.*?\)', '', ifcatcher_name).strip()
                             cp = get_player(ifcatcher_name)
                             cp['catches'] = cp.get('catches', 0) + 1

                if 'st ' in dismissal_text and 'b ' in dismissal_text:
                     stumper_part = dismissal_text.split(' b ')[0]
                     stumper_name = stumper_part.replace('st ', '', 1).strip()
                     sp = get_player(stumper_name)
                     sp['stumpings'] = sp.get('stumpings', 0) + 1
                     
                if 'run out' in dismissal_text:
                     match = re.search(r'run out \((.*?)\)', dismissal_text)
                     if match:
                         fielders = match.group(1).split('/')
                         for f in fielders:
                             f_clean = re.sub(r'\(.*?\)', '', f).strip()
                             fp = get_player(f_clean)
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

        # --- Batch Fetch Roles ---
        # Only fetch for players with stats to stay efficient
        print("Fetching player roles...")
        for p in players.values():
            if p.get('profile_url'):
                p['role'] = self.get_player_role(p['profile_url'])
                # print(f"  {p['name']}: {p['role']}")
                
        return list(players.values())
