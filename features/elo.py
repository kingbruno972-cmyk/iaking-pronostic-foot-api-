import pandas as pd

def compute_elo_table(df, base=1500, k=20, home_adv=60):
    clubs = set(df.home.unique()).union(set(df.away.unique()))
    rating = {c: base for c in clubs}
    rows = []
    for _, r in df.sort_values("date").iterrows():
        a, b = r.home, r.away
        ra, rb = rating[a], rating[b]
        # expected scores with home advantage
        ea = 1 / (1 + 10 ** (-(((ra + home_adv) - rb) / 400)))
        eb = 1 - ea
        # actual
        if r.home_goals > r.away_goals:
            sa, sb = 1, 0
        elif r.home_goals < r.away_goals:
            sa, sb = 0, 1
        else:
            sa, sb = 0.5, 0.5
        # update
        ra2 = ra + k * (sa - ea)
        rb2 = rb + k * (sb - eb)
        rating[a], rating[b] = ra2, rb2
        rows.append({"date": r.date, "league": r.league, "team": a, "elo": ra2})
        rows.append({"date": r.date, "league": r.league, "team": b, "elo": rb2})
    return pd.DataFrame(rows)
