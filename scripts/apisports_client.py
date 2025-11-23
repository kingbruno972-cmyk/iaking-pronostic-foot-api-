# scripts/apisports_client.py

from __future__ import annotations

import os
from typing import Any, Dict, List

import requests


BASE_URL = "https://v3.football.api-sports.io"


class ApiSportsError(Exception):
    """Erreur personnalisée pour API-FOOTBALL."""


def get_api_key() -> str:
    key = os.getenv("APISPORTS_KEY")
    if not key:
        raise ApiSportsError(
            "Variable d'environnement APISPORTS_KEY non définie. "
            'Dans le terminal : export APISPORTS_KEY="TA_CLE_ICI"'
        )
    return key


def _headers() -> Dict[str, str]:
    """
    Headers pour API-FOOTBALL (site officiel, pas RapidAPI).
    """
    return {
        "x-apisports-key": get_api_key(),
        "x-apisports-host": "v3.football.api-sports.io",
    }


def get_league_fixtures(
    league_id: int,
    season: int,
    date: str | None = None,
) -> List[Dict[str, Any]]:
    """
    Récupère les fixtures d'une ligue + saison.
    - league_id: ex. 61 pour Ligue 1
    - season: ex. 2021, 2022, 2023 (free plan)
    - date: optionnel, format 'YYYY-MM-DD' pour filtrer un jour précis
    """
    url = f"{BASE_URL}/fixtures"
    params: Dict[str, Any] = {
        "league": league_id,
        "season": season,
    }
    if date:
        params["date"] = date

    resp = requests.get(url, headers=_headers(), params=params, timeout=10)
    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        raise ApiSportsError(
            f"Erreur HTTP {resp.status_code} sur /fixtures: {resp.text}"
        ) from e

    data = resp.json()
    if data.get("errors"):
        raise ApiSportsError(f"Erreurs API /fixtures: {data['errors']}")

    return data.get("response", [])


def get_predictions_for_fixture(fixture_id: int) -> Dict[str, Any]:
    """
    Appelle /predictions pour un fixture donné.
    On suppose que le endpoint est disponible dans ton plan.
    On retourne :
      - proba 1N2 (p_home/p_draw/p_away)
      - conseil (advice)
      - vainqueur (winner_name + winner_comment)
      - BTTS (btts)
      - Over/Under principal (under_over)
      - buts attendus (goals_home/goals_away) si dispo
    """
    url = f"{BASE_URL}/predictions"
    params = {"fixture": fixture_id}

    resp = requests.get(url, headers=_headers(), params=params, timeout=10)
    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        raise ApiSportsError(
            f"Erreur HTTP {resp.status_code} sur /predictions: {resp.text}"
        ) from e

    data = resp.json()
    if data.get("errors"):
        raise ApiSportsError(f"Erreurs API /predictions: {data['errors']}")

    resp_list = data.get("response", [])
    if not resp_list:
        raise ApiSportsError("Aucune prédiction trouvée pour ce fixture.")

    # Structure typique API-FOOTBALL
    item = resp_list[0]
    predictions = item.get("predictions") or item.get("prediction") or {}
    percent = predictions.get("percent", {}) or {}

    # 1) Probabilités 1N2 (en % -> proba)
    home_pct = percent.get("home")
    draw_pct = percent.get("draw")
    away_pct = percent.get("away")

    def _to_prob(v: str | None) -> float:
        if not v:
            return 0.0
        v = v.replace("%", "").strip()
        try:
            return float(v) / 100.0
        except ValueError:
            return 0.0

    p_home = _to_prob(home_pct)
    p_draw = _to_prob(draw_pct)
    p_away = _to_prob(away_pct)

    # 2) BTTS / Over-Under / Goals
    btts = predictions.get("btts") or ""
    under_over = predictions.get("under_over") or ""
    goals_block = predictions.get("goals") or {}
    goals_home = goals_block.get("home")
    goals_away = goals_block.get("away")

    # 3) Winner + Advice
    advice = predictions.get("advice") or ""
    winner = predictions.get("winner") or {}
    winner_name = winner.get("name") or ""
    winner_comment = winner.get("comment") or ""

    return {
        "p_home": p_home,
        "p_draw": p_draw,
        "p_away": p_away,
        "advice": advice,
        "winner_name": winner_name,
        "winner_comment": winner_comment,
        "btts": btts,
        "under_over": under_over,
        "goals_home": goals_home,
        "goals_away": goals_away,
        "raw": data,  # pour debug si besoin
    }