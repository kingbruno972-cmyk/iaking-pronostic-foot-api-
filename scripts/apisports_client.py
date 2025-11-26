# scripts/apisports_client.py

from __future__ import annotations

import os
from typing import Dict, Any, Optional, List
import requests

# ================================
# CONFIG API-FOOTBALL
# ================================
APISPORTS_KEY = os.environ.get("APISPORTS_KEY")
API_BASE_URL = "https://v3.football.api-sports.io"
TIMEOUT = 10

session = requests.Session()
session.headers.update({
    "x-apisports-key": APISPORTS_KEY or "",
})


class ApiSportsError(Exception):
    """Erreur custom pour API-FOOTBALL."""
    pass


def _check_key() -> None:
    if not APISPORTS_KEY:
        raise ApiSportsError("Variable d'environnement APISPORTS_KEY non définie.")


def _api_get(path: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Wrapper GET simple avec gestion d'erreurs."""
    _check_key()

    url = f"{API_BASE_URL}/{path.lstrip('/')}"
    resp = session.get(url, params=params, timeout=TIMEOUT)

    if resp.status_code != 200:
        raise ApiSportsError(
            f"HTTP {resp.status_code} sur {url} : {resp.text[:200]}"
        )

    data = resp.json()
    errors = data.get("errors") or {}
    if errors:
        raise ApiSportsError(str(errors))

    return data


# ================================
# UTILITAIRES MATCH
# ================================
def _normalize_name(name: str) -> str:
    """Normalise un nom d'équipe pour la comparaison."""
    return "".join(
        c.lower() for c in name if c.isalnum() or c.isspace()
    ).strip()


def _fixture_match_names(
    fixture: Dict[str, Any],
    home_name: str,
    away_name: str,
) -> bool:
    """Retourne True si le fixture correspond aux 2 équipes."""
    teams = fixture.get("teams", {})
    home = teams.get("home", {})
    away = teams.get("away", {})

    f_home = _normalize_name(home.get("name", ""))
    f_away = _normalize_name(away.get("name", ""))

    return (
        f_home == _normalize_name(home_name)
        and f_away == _normalize_name(away_name)
    )


# ================================
# MULTI-LIGUE
# ================================
DEFAULT_SEASON = 2025

LEAGUES_TO_SCAN: List[int] = [
    61,   # Ligue 1
    39,   # Premier League
    140,  # Liga
    135,  # Serie A
    78,   # Bundesliga
    2,    # Champions League
    3,    # Europa League
]


def find_fixture_any_league(
    home: str,
    away: str,
    season: int = DEFAULT_SEASON,
) -> Optional[int]:
    """Cherche un match (fixture_id) dans plusieurs ligues."""
    for lg in LEAGUES_TO_SCAN:
        data = _api_get("fixtures", {
            "league": lg,
            "season": season,
        })

        for fx in data.get("response", []):
            if _fixture_match_names(fx, home, away):
                return fx.get("fixture", {}).get("id")

    return None


def get_upcoming_fixtures(
    league: int,
    season: int,
    next_n: int = 10,
) -> List[Dict[str, Any]]:
    """
    Retourne les prochains matchs d'une ligue.
    """
    data = _api_get("fixtures", {
        "league": league,
        "season": season,
        "next": next_n,
    })
    return data.get("response", [])


# ================================
# PRÉDICTIONS OFFICIELLES
# ================================
def get_predictions_for_fixture(fixture_id: int) -> Dict[str, Any]:
    """
    Récupère les prédictions officielles API-FOOTBALL pour un fixture donné.
    """
    data = _api_get("predictions", {"fixture": fixture_id})
    resp = data.get("response", [])
    if not resp:
        raise ApiSportsError("Aucune prédiction trouvée")

    pred = resp[0].get("predictions", {})
    percent = pred.get("percent", {})

    def to_float(x: Any) -> float:
        try:
            return float(str(x).replace("%", "")) / 100.0
        except Exception:
            return 0.0

    return {
        "p_home": to_float(percent.get("home")),
        "p_draw": to_float(percent.get("draw")),
        "p_away": to_float(percent.get("away")),
        "advice": pred.get("advice", ""),
        "winner_name": pred.get("winner", {}).get("name", ""),
        "winner_comment": pred.get("winner", {}).get("comment", ""),
        "goals_home": pred.get("goals", {}).get("home"),
        "goals_away": pred.get("goals", {}).get("away"),
    }