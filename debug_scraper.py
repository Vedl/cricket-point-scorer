import requests
from bs4 import BeautifulSoup

url = "https://www.cricbuzz.com/live-cricket-scorecard/141936/banw-vs-thaiw-21st-match-super-six-icc-womens-t20-world-cup-global-qualifier-2026"
headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'
}

try:
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, 'html.parser')

    bowl_rows = soup.find_all(lambda tag: tag.name == 'div' and tag.get('class') and any('scorecard-bowl-grid' in c for c in tag.get('class')))
    
    if len(bowl_rows) > 1:
        print("Bowling Row 1 HTML:")
        print(bowl_rows[1].prettify())

except Exception as e:
    print(f"Error: {e}")
