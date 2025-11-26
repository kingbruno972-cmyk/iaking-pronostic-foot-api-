# scripts/apisports_client.py

import os
from typing import Dict, Any, Optional, List
import requests

# ============================
# CONFIG API-FOOTBALL
# ============================
APISPORTS_KEY = os.environ.get("APISPORTS_KEY")
API_BASE_URL = "https://v3.football.api-sports.io"
TIMEOUT = 10

session = requests.Session()
session.headers.update({
    "x-apisports-key": APISPORTS_KEY or ""
})


class ApiSportsError(Exception):
    """Erreur API-FOOTBALL"""
    pass


def _check_key():
    if not APISPORTS_KEY:
        raise ApiSportsError("APISPORTS_KEY manquante")


def _api_get(path: str, params: Dict[str, Any]) -> Dict[str, Any]:
    _check_key()

    url = f"{API_BASE_URL}/{path.lstrip('/')}"
    resp = session.get(url, params=params, timeout=TIMEOUT)

    if resp.status_code != 200:
        raise ApiSportsError(f"HTTP {resp.status_code}: {resp.text[:200]}")

    data = resp.json()
    if data.get("errors"):
        raise ApiSportsError(str(data["errors"]))

    return data


# ============================
# NORMALISATION NOM D'ÉQUIPE
# ============================
def _normalize_name(name: str) -> str:
    return "".join(
        c.lower() for c in name if c.isalnum() or c.isspace()
    ).strip()


# ============================
# TROUVER UN MATCH PAR NOMS
# ============================
def find_fixture_by_names(home: str, away: str, season: int = 2025) -> Optional[int]:
    """
    Cherche un match en utilisant le paramètre 'search' d'API-FOOTBALL
    puis compare les noms d'équipes normalisés.
    """
    # On cherche sur le nom de l'équipe à domicile
    data = _api_get("fixtures", {
        "season": season,
        "search": home
    })

    home_norm = _normalize_name(home)
    away_norm = _normalize_name(away)

    for fx in data.get("response", []):
        teams = fx.get("teams", {})
        home_team = _normalize_name(teams.get("home", {}).get("name", ""))
        away_team = _normalize_name(teams.get("away", {}).get("name", ""))

        if home_team == home_norm and away_team == away_norm:
            return fx.get("fixture", {}).get("id")

    return None


# ============================
# UPCOMING FIXTURES
# ============================
def get_upcoming_fixtures(
    league: int,
    season: int,
    next_n: int = 10
) -> List[Dict[str, Any]]:

    data = _api_get("fixtures", {
        "league": league,
        "season": season,
        "next": next_n
    })

    return data.get("response", [])


# ============================
# PRÉDICTIONS OFFICIELLES
# ============================
def get_predictions_for_fixture(fixture_id: int) -> Dict[str, Any]:
    data = _api_get("predictions", {"fixture": fixture_id})
    resp = data.get("response", [])

    if not resp:
        raise ApiSportsError("Aucune prédiction trouvée")

    pred = resp[0].get("predictions", {})
    percent = pred.get("percent", {})

    def to_float(x):
        try:
            return float(str(x).replace("%", "")) / 100
        except Exception:
            return 0.0

    return {
        "p_home": to_float(percent.get("home")),
        "p_draw": to_float(percent.get("draw")),
        "p_away": to_float(percent.get("away")),
        "advice": pred.get("advice", ""),
        "winner_name": pred.get("winner", {}).get("name", ""),
        "goals_home": pred.get("goals", {}).get("home"),
        "goals_away": pred.get("goals", {}).get("away"),
    }