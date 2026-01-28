import requests
from bs4 import BeautifulSoup

# Example profile URL (Nigar Sultana from previous output)
# We need to see if we can get the role from the profile page.
# Note: Scorecard has links like /profiles/11388/nigar-sultana
url = "https://www.cricbuzz.com/profiles/11388/nigar-sultana"
headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'
}

try:
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, 'html.parser')
    
    print(f"Checking Profile: {url}")
    
    # Usually role is in some div
    # Look for "Role" keyword
    text_content = soup.get_text()
    if "Role" in text_content:
        print("Found 'Role' in text.")
        
    # Dump the personal info section logic
    # Cricbuzz profiles often have a "cb-col cb-col-100 cb-bg-grey" or similar section
    # Let's print the first few instances of "Role" context
    
    # Or just dump the HTML of the personal details block
    # Often id="playerProfile" or similar
    
    # Let's search for the element containing "Role"
    role_label = soup.find(string="Role")
    if role_label:
        parent = role_label.parent
        print(f"Role Label Parent: {parent}")
        # Next sibling or parent's sibling?
        print(f"Role Context: {parent.parent.prettify()}")
        
except Exception as e:
    print(f"Error: {e}")
