import requests
from bs4 import BeautifulSoup
import re

url = "https://www.cricbuzz.com/live-cricket-scorecard/141936/banw-vs-thaiw-21st-match-super-six-icc-womens-t20-world-cup-global-qualifier-2026"
headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'
}

response = requests.get(url, headers=headers)
soup = BeautifulSoup(response.content, 'html.parser')

innings = soup.find_all('div', id=re.compile(r'^innings_\d+'))
print(f"Found {len(innings)} innings divs:")
for i in innings:
    print(i.get('id'))
