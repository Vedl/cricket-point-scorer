with open("fantasy_auction/fantasy_auction.py", "r") as f:
    content = f.read()

start = content.find("def admin_page():")
end = content.find("def calculator_page():", start)

print(f"Start: {start}, End: {end}")
