import csv
import io

def parse_csv(csv_text):
    f = io.StringIO(csv_text.strip())
    reader = csv.reader(f)
    rows = list(reader)
    if not rows: return {}

    squads = {}
    # Format A (Zoom Auction style)
    # Row 0: NameA, , NameB, , NameC, , ...
    # Row 2+: PlayerA, PriceA, PlayerB, PriceB...
    if len(rows) > 0 and len(rows[0]) > 0 and (len(rows) < 2 or rows[1].count('') >= len(rows[1])-1 or "Participant" not in rows[0]):
        participants = {} # col_idx -> name
        for i, name in enumerate(rows[0]):
            if name.strip():
                participants[i] = name.strip()
                squads[name.strip()] = []
        
        for row in rows[2:]:
            for col_idx, p_name in participants.items():
                if col_idx < len(row) and col_idx + 1 < len(row):
                    player = row[col_idx].strip()
                    price_str = row[col_idx+1].strip()
                    if player and price_str:
                        squads[p_name].append({"name": player, "buy_price": int(price_str)})
    else:
        # Format B (Gameweek Auction Squads.csv style)
        headers = rows[0]
        p_idx = headers.index("Participant")
        pl_idx = headers.index("Player")
        pr_idx = headers.index("Price")
        
        for row in rows[1:]:
            if len(row) > max(p_idx, pl_idx, pr_idx):
                p_name = row[p_idx].strip()
                player = row[pl_idx].strip()
                price_str = row[pr_idx].strip()
                if p_name and player and price_str:
                    if p_name not in squads: squads[p_name] = []
                    squads[p_name].append({"name": player, "buy_price": int(price_str)})
    return squads

format_a = """Smudge49,,Ladda CC,,Mithuphetamine,,
,
Buttler,60,Miller,6,Brewis,70"""

print(parse_csv(format_a))

format_b = """Participant,Player,Role,Team,Price
Smudge49,Jos Buttler,WK-Batsman,England,60"""

print(parse_csv(format_b))
