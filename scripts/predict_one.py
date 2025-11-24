# scripts/predict_one.py

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Any, Optional

import requests


# ============================
#  CONFIG API-FOOTBALL (APISPORTS_KEY)
# ============================

BASE_URL = "https://v3.football.api-sports.io"
TIMEOUT = 10


class ApiSportsError(Exception):
    """Erreur personnalisée pour API-FOOTBALL."""


def get_api_key() -> str:
    """
    Récupère la clé APISPORTS_KEY dans les variables d'environnement.
    """
    key = os.getenv("APISPORTS_KEY")
    if not key:
        raise ApiSportsError(
            'Variable d\'environnement APISPORTS_KEY non définie. '
            'Dans le terminal (en local) : export APISPORTS_KEY="TA_CLE_ICI"'
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


def _api_get(path: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Petit wrapper GET avec gestion des erreurs.
    """
    url = f"{BASE_URL}/{path.lstrip('/')}"
    resp = requests.get(url, headers=_headers(), params=params, timeout=TIMEOUT)

    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        raise ApiSportsError(
            f"Erreur HTTP {resp.status_code} sur {url} : {resp.text[:200]}"
        ) from e

    data = resp.json()
    if data.get("errors"):
        raise ApiSportsError(f"Erreurs API {path} : {data['errors']}")

    return data


# ============================
#  RÉSULTAT STANDARD
# ============================

@dataclass
class PredictResult:
    prediction: str
    p_home: float
    p_draw: float
    p_away: float
    comment: str
    status: str = "ok"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prediction": self.prediction,
            "p_home": self.p_home,
            "p_draw": self.p_draw,
            "p_away": self.p_away,
            "comment": self.comment,
            "status": self.status,
        }


# ============================
#  OPTION B : /predictions (OFFICIEL)
# ============================

def _to_prob(percent_str: Optional[str]) -> float:
    """
    Convertit une chaîne du type '45%' en proba 0.45.
    """
    if not percent_str:
        return 0.0
    s = percent_str.replace("%", "").strip()
    try:
        return float(s) / 100.0
    except ValueError:
        return 0.0


def predict_one_match_from_apisports(fixture_id: int) -> Dict[str, Any]:
    """
    OPTION B : va chercher les pourcentages 1N2 + infos prono depuis API-FOOTBALL
    pour un fixture précis (endpoint /predictions).

    ➜ À utiliser depuis l'endpoint FastAPI :
        GET /predict_one_api_fixture?fixture_id=XXXX
    """
    try:
        data = _api_get("predictions", {"fixture": fixture_id})
    except ApiSportsError as e:
        return PredictResult(
            prediction="Erreur API-FOOTBALL (Option B)",
            p_home=0.0,
            p_draw=0.0,
            p_away=0.0,
            comment=f"❌ {e}",
            status="error",
        ).to_dict()

    resp_list = data.get("response") or []
    if not resp_list:
        return PredictResult(
            prediction="",
            p_home=0.0,
            p_draw=0.0,
            p_away=0.0,
            comment="Aucune prédiction trouvée pour ce fixture.",
            status="error",
        ).to_dict()

    item = resp_list[0]

    # Selon la version de l'API, la clé peut s'appeler "predictions" ou "prediction"
    predictions = item.get("predictions") or item.get("prediction") or {}
    percent = predictions.get("percent", {}) or {}

    # Probabilités 1N2
    p_home = _to_prob(percent.get("home"))
    p_draw = _to_prob(percent.get("draw"))
    p_away = _to_prob(percent.get("away"))

    # Winner & advice
    advice = predictions.get("advice") or ""
    winner = predictions.get("winner") or {}
    winner_name = winner.get("name") or ""
    winner_comment = winner.get("comment") or ""

    # BTTS / Over-Under / buts attendus (si dispo)
    btts = predictions.get("btts") or ""          # ex: "Yes" / "No"
    under_over = predictions.get("under_over") or ""
    goals = predictions.get("goals") or {}
    goals_home = goals.get("home")
    goals_away = goals.get("away")

    # Issue la plus probable
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
        parts.append(f" BTTS : {btts}.")
    if under_over:
        parts.append(f" Over/Under principal : {under_over}.")
    if goals_home is not None or goals_away is not None:
        parts.append(
            f" Buts estimés (modèle API) : home={goals_home}, away={goals_away}."
        )
    if winner_name or winner_comment:
        parts.append(
            f" Winner API : {winner_name or 'N/A'} ({winner_comment or ''})."
        )
    if advice:
        parts.append(f" Conseil API : {advice}.")

    comment = " ".join(parts)

    res = PredictResult(
        prediction=prediction,
        p_home=p_home,
        p_draw=p_draw,
        p_away=p_away,
        comment=comment,
        status="ok",
    )
    return res.to_dict()


# ============================
#  ANCIEN /predict_one (par noms d'équipe)
# ============================

def predict_one_match(home: str, away: str) -> Dict[str, Any]:
    """
    Ancien endpoint basé sur les noms d'équipes.

    Pour l'instant, on le laisse en "mode message" pour ne pas te donner
    de faux pronostics :
      ➜ Le vrai flux PRO est /predict_one_api_fixture?fixture_id=XXXX
    """
    comment = (
        "Cet endpoint utilise maintenant les prédictions officielles API-FOOTBALL. "
        "Pour un prono PRO, utilise plutôt /predict_one_api_fixture?fixture_id=XXXX "
        "(avec l'ID du match récupéré via /fixtures)."
    )

    res = PredictResult(
        prediction="Endpoint par noms d'équipes (legacy)",
        p_home=0.0,
        p_draw=0.0,
        p_away=0.0,
        comment=comment,
        status="info",
    )
    return res.to_dict()