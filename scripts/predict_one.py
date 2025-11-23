# scripts/predict_one.py

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import requests

# ============================
#  CONFIG API-FOOTBALL (RAPIDAPI) – OPTION A (H2H)
# ============================

RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")
RAPIDAPI_HOST = "api-football-v1.p.rapidapi.com"
BASE_URL = "https://api-football-v1.p.rapidapi.com/v3"

# Ligue 1 France
DEFAULT_LEAGUE_ID = 61     # ID Ligue 1 dans API-FOOTBALL
DEFAULT_SEASON = 2024      # à adapter chaque saison
TIMEOUT = 10

session = requests.Session()
session.headers.update(
    {
        "x-rapidapi-key": RAPIDAPI_KEY or "",
        "x-rapidapi-host": RAPIDAPI_HOST,
    }
)


class APIFootballError(Exception):
    """Erreur custom pour API-FOOTBALL."""


@dataclass
class PredictResult:
    prediction: str
    p_home: float
    p_draw: float
    p_away: float
    comment: str
    status: str = "ok"

    def to_dict(self) -> Dict:
        return {
            "prediction": self.prediction,
            "p_home": self.p_home,
            "p_draw": self.p_draw,
            "p_away": self.p_away,
            "comment": self.comment,
            "status": self.status,
        }


# ============================
#  APPELS API-FOOTBALL (H2H) – OPTION A
# ============================

def _api_get(path: str, params: Dict) -> Dict:
    """Wrapper GET simple avec gestion d'erreurs."""
    if not RAPIDAPI_KEY:
        raise APIFootballError(
            "RAPIDAPI_KEY n'est pas définie (variable d'environnement)."
        )

    url = f"{BASE_URL}/{path.lstrip('/')}"
    resp = session.get(url, params=params, timeout=TIMEOUT)

    if resp.status_code != 200:
        raise APIFootballError(
            f"HTTP {resp.status_code} sur {url} : {resp.text[:200]}"
        )

    data = resp.json()
    if data.get("errors"):
        raise APIFootballError(str(data["errors"]))

    return data


def get_team_id(
    name: str,
    league_id: int = DEFAULT_LEAGUE_ID,
    season: int = DEFAULT_SEASON,
) -> Optional[int]:
    """
    Retourne l'ID API-FOOTBALL pour une équipe (par son nom).
    On filtre par Ligue 1 + saison pour éviter les doublons.
    """
    data = _api_get(
        "teams",
        {
            "name": name,
            "league": league_id,
            "season": season,
        },
    )

    resp_list = data.get("response") or []
    if not resp_list:
        return None

    return resp_list[0]["team"]["id"]


def get_head_to_head_stats(
    home_id: int, away_id: int, last: int = 20
) -> Tuple[int, int, int, int]:
    """
    Récupère les derniers face-à-face entre home_id et away_id.
    Retourne : (home_wins, draws, away_wins, nb_matchs)
    """
    data = _api_get(
        "fixtures/headtohead",
        {
            "h2h": f"{home_id}-{away_id}",
            "last": last,
        },
    )

    fixtures = data.get("response") or []

    home_wins = 0
    away_wins = 0
    draws = 0

    for f in fixtures:
        teams = f.get("teams", {})
        home_team = teams.get("home", {})
        away_team = teams.get("away", {})

        home_team_id = home_team.get("id")
        away_team_id = away_team.get("id")

        winner_is_home = home_team.get("winner")
        winner_is_away = away_team.get("winner")

        # Match nul
        if winner_is_home is None and winner_is_away is None:
            draws += 1
            continue

        # Victoire "home"
        if winner_is_home:
            if home_team_id == home_id:
                home_wins += 1
            elif home_team_id == away_id:
                away_wins += 1
            continue

        # Victoire "away"
        if winner_is_away:
            if away_team_id == home_id:
                home_wins += 1
            elif away_team_id == away_id:
                away_wins += 1
            continue

    total = home_wins + draws + away_wins
    return home_wins, draws, away_wins, total


def predict_one_match(home: str, away: str) -> Dict:
    """
    OPTION A : Prono 1N2 basé sur les head-to-head API-FOOTBALL.
    """
    home_clean = home.strip()
    away_clean = away.strip()

    if not home_clean or not away_clean:
        return PredictResult(
            prediction="",
            p_home=0.0,
            p_draw=0.0,
            p_away=0.0,
            comment="Nom d'équipe manquant.",
            status="error",
        ).to_dict()

    try:
        # 1) IDs des équipes
        home_id = get_team_id(home_clean)
        away_id = get_team_id(away_clean)

        if home_id is None or away_id is None:
            return PredictResult(
                prediction="",
                p_home=0.0,
                p_draw=0.0,
                p_away=0.0,
                comment=(
                    f"Impossible de trouver les équipes '{home_clean}' "
                    f"et/ou '{away_clean}' dans API-FOOTBALL (Ligue 1 {DEFAULT_SEASON})."
                ),
                status="error",
            ).to_dict()

        # 2) Head-to-head
        home_wins, draws, away_wins, total = get_head_to_head_stats(
            home_id, away_id, last=20
        )

        if total == 0:
            p_home = p_draw = p_away = 1.0 / 3.0
            prediction = "Données insuffisantes, probas équilibrées."
            comment = (
                "Aucun face-à-face récent trouvé entre ces deux équipes. "
                "Probabilités 1N2 mises à 33.3% / 33.3% / 33.3%."
            )
        else:
            # Lissage
            home_adj = home_wins + 1
            draw_adj = draws + 1
            away_adj = away_wins + 1
            denom = home_adj + draw_adj + away_adj

            p_home = home_adj / denom
            p_draw = draw_adj / denom
            p_away = away_adj / denom

            if p_home >= p_draw and p_home >= p_away:
                prediction = f"Victoire de {home_clean}"
            elif p_away >= p_home and p_away >= p_draw:
                prediction = f"Victoire de {away_clean}"
            else:
                prediction = "Match nul"

            comment = (
                f"Probas issues des {total} derniers face-à-face (Ligue 1) : "
                f"home_wins={home_wins}, draws={draws}, away_wins={away_wins}. "
                f"Après lissage : p_home={p_home:.3f}, p_draw={p_draw:.3f}, "
                f"p_away={p_away:.3f}. Issue la plus probable : {prediction}."
            )

        res = PredictResult(
            prediction=prediction,
            p_home=p_home,
            p_draw=p_draw,
            p_away=p_away,
            comment=comment,
            status="ok",
        )
        return res.to_dict()

    except APIFootballError as e:
        res = PredictResult(
            prediction="",
            p_home=0.0,
            p_draw=0.0,
            p_away=0.0,
            comment=f"Erreur API-FOOTBALL (H2H) : {e}",
            status="error",
        )
        return res.to_dict()

    except Exception as e:
        res = PredictResult(
            prediction="",
            p_home=0.0,
            p_draw=0.0,
            p_away=0.0,
            comment=f"Erreur interne backend : {e}",
            status="error",
        )
        return res.to_dict()


# ============================
#  OPTION B : PRONOS OFFICIELS API-SPORTS (/predictions)
# ============================

from scripts.apisports_client import (
    get_predictions_for_fixture,
    ApiSportsError,
)


def predict_one_match_from_apisports(fixture_id: int) -> Dict:
    """
    Option B : va chercher les pourcentages 1N2 + BTTS + Over/Under
    depuis API-FOOTBALL pour un fixture précis.
    """
    try:
        pred = get_predictions_for_fixture(fixture_id)
    except ApiSportsError as e:
        # En cas de problème API, on renvoie une erreur propre
        return {
            "prediction": "Erreur API-FOOTBALL",
            "p_home": 0.0,
            "p_draw": 0.0,
            "p_away": 0.0,
            "comment": f"❌ {e}",
            "status": "error",
        }

    p_home = float(pred.get("p_home", 0.0))
    p_draw = float(pred.get("p_draw", 0.0))
    p_away = float(pred.get("p_away", 0.0))

    advice = pred.get("advice") or ""
    winner_name = pred.get("winner_name") or ""
    winner_comment = pred.get("winner_comment") or ""
    btts = pred.get("btts") or ""
    under_over = pred.get("under_over") or ""
    goals_home = pred.get("goals_home")
    goals_away = pred.get("goals_away")

    # On choisit l’issue la plus probable
    if p_home >= p_draw and p_home >= p_away:
        prediction = "Victoire domicile"
    elif p_away >= p_home and p_away >= p_draw:
        prediction = "Victoire extérieur"
    else:
        prediction = "Match nul"

    # Construction du commentaire PRO
    parts = []

    parts.append(
        f"Prono API-FOOTBALL (Option B). "
        f"p_home={p_home:.3f}, p_draw={p_draw:.3f}, p_away={p_away:.3f}. "
        f"Issue la plus probable : {prediction}."
    )

    if btts:
        parts.append(f"BTTS : {btts}.")          # ex. 'Yes' / 'No' / etc.
    if under_over:
        parts.append(f"Over/Under principal : {under_over}.")

    if goals_home is not None or goals_away is not None:
        parts.append(
            f"Buts estimés (modèle API) : home={goals_home}, away={goals_away}."
        )

    if winner_name or winner_comment:
        parts.append(
            f"Winner API : {winner_name or 'N/A'} ({winner_comment or ''})."
        )

    if advice:
        parts.append(f"Conseil API : {advice}.")

    comment = " ".join(parts)

    res = PredictResult(
        prediction=prediction,
        p_home=p_home,
        p_draw=p_draw,
        p_away=p_away,
        comment=comment,
    )
    return res.to_dict()