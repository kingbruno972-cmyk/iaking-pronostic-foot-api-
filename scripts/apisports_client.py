# scripts/apisports_client.py

from __future__ import annotations

import os
from typing import Dict, List
import requests

# ============================
# CONFIG
# ============================

API_BASE_URL = "https://v3.football.api-sports.io"
APISPORTS_KEY = os.environ.get("APISPORTS_KEY")
TIMEOUT = 10

session = requests.Session()
session.headers.update(
    {
        "x-apisports-key": APISPORTS_KEY or "",
    }
)


class ApiSportsError(Exception):
    """Erreur custom pour API-SPORTS / API-FOOTBALL."""
    pass


# ============================
# REQUEST WRAPPER
# ============================

def _api_get(path: str, params: Dict) -> Dict:
    """
    Wrapper GET générique vers API-FOOTBALL officiel.
    Gère les erreurs proprement.
    """
    if not APISPORTS_KEY:
        raise ApiSportsError(
            "Variable d'environnement APISPORTS_KEY non définie. "
            "export APISPORTS_KEY=\"TA_CLE_ICI\""
        )

    url = f"{API_BASE_URL}/{path.lstrip('/')}"
    resp = session.get(url, params=params, timeout=TIMEOUT)

    if resp.status_code != 200:
        raise ApiSportsError(
            f"HTTP {resp.status_code} sur {url}: {resp.text[:300]}"
        )

    data = resp.json()

    if data.get("errors"):
        raise ApiSportsError(str(data["errors"]))

    return data


# ============================
# 1) PRONOS OFFICIELS API-FOOTBALL (/predictions)
# ============================

def get_predictions_for_fixture(fixture_id: int) -> Dict:
    """
    Récupère les pourcentages 1N2, BTTS, O/U, advice, winner
    depuis /predictions pour un fixture donné.
    """
    data = _api_get(
        "predictions",
        {"fixture": fixture_id},
    )

    resp = data.get("response") or []
    if not resp:
        raise ApiSportsError(f"Aucune prédiction trouvée pour fixture={fixture_id}")

    item = resp[0]

    predictions = item.get("predictions", {}) or {}
    winner = predictions.get("winner") or {}

    # Pourcentages 1N2 ("45%")
    def parse_pct(val: str | None) -> float:
        if not val:
            return 0.0
        return float(val.replace("%", "").strip()) / 100.0

    p_home = parse_pct(predictions.get("percent_home"))
    p_draw = parse_pct(predictions.get("percent_draw"))
    p_away = parse_pct(predictions.get("percent_away"))

    advice = predictions.get("advice") or ""
    btts = predictions.get("btts") or ""
    under_over = predictions.get("under") or ""
    goals = predictions.get("goals") or {}
    goals_home = goals.get("home")
    goals_away = goals.get("away")

    return {
        "p_home": p_home,
        "p_draw": p_draw,
        "p_away": p_away,
        "advice": advice,
        "btts": btts,
        "under_over": under_over,
        "goals_home": goals_home,
        "goals_away": goals_away,
        "winner_name": winner.get("name"),
        "winner_comment": winner.get("comment"),
    }


# ============================
# 2) LISTE DES PROCHAINS MATCHS
# ============================

def get_upcoming_fixtures(
    league: int,
    season: int,
    next_n: int = 20,
) -> List[Dict]:
    """
    Retourne une liste simplifiée des prochains matchs d'une ligue :
    [
      {
        "fixture_id": 1387820,
        "date": "2025-11-28T19:45:00+00:00",
        "home_name": "Metz",
        "away_name": "Rennes",
        "league_id": 61,
        "league_name": "Ligue 1",
        "round": "Regular Season - 14"
      },
      ...
    ]
    """

    data = _api_get(
        "fixtures",
        {
            "league": league,
            "season": season,
            "next": next_n,
        },
    )

    fixtures = []

    for item in data.get("response") or []:
        f = item.get("fixture", {})
        l = item.get("league", {})
        t = item.get("teams", {})

        fixtures.append(
            {
                "fixture_id": f.get("id"),
                "date": f.get("date"),
                "home_name": t.get("home", {}).get("name"),
                "away_name": t.get("away", {}).get("name"),
                "league_id": l.get("id"),
                "league_name": l.get("name"),
                "round": l.get("round"),
            }
        )

    return fixtures