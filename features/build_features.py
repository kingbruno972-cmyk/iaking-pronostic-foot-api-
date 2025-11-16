import pandas as pd
from .elo import compute_elo_table

def last_n_stats(df, team, date, n=5):
    past = df[
        ((df["home"] == team) | (df["away"] == team))
        & (df["date"] < date)
    ].sort_values("date").tail(n)

    if past.empty:
        return pd.Series({
            "form_goals_for": 0,
            "form_goals_against": 0,
            "form_points": 0,
        })

    gf = []
    ga = []
    pts = []

    for _, row in past.iterrows():
        if row["home"] == team:
            gfor = row["home_goals"]
            gagn = row["away_goals"]
            gf.append(gfor)
            ga.append(gagn)
            if gfor > gagn:
                pts.append(3)
            elif gfor == gagn:
                pts.append(1)
            else:
                pts.append(0)
        else:
            gfor = row["away_goals"]
            gagn = row["home_goals"]
            gf.append(gfor)
            ga.append(gagn)
            if gfor > gagn:
                pts.append(3)
            elif gfor == gagn:
                pts.append(1)
            else:
                pts.append(0)

    return pd.Series({
        "form_goals_for": sum(gf) / n,
        "form_goals_against": sum(ga) / n,
        "form_points": sum(pts),
    })

def build_features(df):
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    elo = compute_elo_table(df)

    # merge ELO home
    df = df.merge(
        elo[["date","league","team","elo"]],
        left_on=["date","league","home"],
        right_on=["date","league","team"],
        how="left"
    ).rename(columns={"elo":"elo_home"}).drop(columns=["team"])

    # merge ELO away
    df = df.merge(
        elo[["date","league","team","elo"]],
        left_on=["date","league","away"],
        right_on=["date","league","team"],
        how="left"
    ).rename(columns={"elo":"elo_away"}).drop(columns=["team"])

    df["f_elo_diff"] = (df["elo_home"] - df["elo_away"]).fillna(0.0)

    # Features de forme
    stats_home = []
    stats_away = []
    for _, row in df.iterrows():
        stats_home.append(last_n_stats(df, row["home"], row["date"]))
        stats_away.append(last_n_stats(df, row["away"], row["date"]))

    stats_home = pd.DataFrame(stats_home)
    stats_away = pd.DataFrame(stats_away)

    # join des features
    df = pd.concat([df, stats_home.add_prefix("home_"), stats_away.add_prefix("away_")], axis=1)

    # target
    df["target_1x2"] = df.apply(
        lambda r: "home" if r["home_goals"] > r["away_goals"] else ("away" if r["away_goals"] > r["home_goals"] else "draw"),
        axis=1
    )

    keep = [
        "league","season","date","home","away",
        "home_goals","away_goals","target_1x2",
        "f_elo_diff",
        "home_form_goals_for","home_form_goals_against","home_form_points",
        "away_form_goals_for","away_form_goals_against","away_form_points"
    ]

    return df[keep]
