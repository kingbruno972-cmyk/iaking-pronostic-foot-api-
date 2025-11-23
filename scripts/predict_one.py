# scripts/predict_one.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from scripts.apisports_client import (
    get_predictions_for_fixture,
    ApiSportsError,
)


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


# =====================================================
#  MODE A : PRONO À PARTIR DES COTES 1X2
# =====================================================

def _probs_from_odds(oh: float, od: float, oa: float) -> Dict[str, float]:
    """
    Transforme des cotes 1X2 en probabilités normalisées.
    p = (1/odds) / somme(1/odds)
    """
    if oh <= 0 or od <= 0 or oa <= 0:
        raise ValueError("Toutes les cotes doivent être > 0")

    inv_home = 1.0 / oh
    inv_draw = 1.0 / od
    inv_away = 1.0 / oa

    total = inv_home + inv_draw + inv_away

    p_home = inv_home / total
    p_draw = inv_draw / total
    p_away = inv_away / total

    return {
        "p_home": p_home,
        "p_draw": p_draw,
        "p_away": p_away,
    }


def predict_one_match(
    home: str,
    away: str,
    odds_home: Optional[float] = None,
    odds_draw: Optional[float] = None,
    odds_away: Optional[float] = None,
) -> Dict:
    """
    Endpoint principal /predict_one

    2 modes :
    - Si les 3 cotes 1X2 sont fournies => calcule les probas à partir des cotes
    - Sinon => renvoie des probas 33/33/33 (démo)
    """

    home_clean = home.strip()
    away_clean = away.strip()

    if not home_clean or not away_clean:
        res = PredictResult(
            prediction="",
            p_home=0.0,
            p_draw=0.0,
            p_away=0.0,
            comment="Nom d'équipe manquant (home / away).",
            status="error",
        )
        return res.to_dict()

    comment_parts = []

    # ====== CAS 1 : cotes fournies ======
    if odds_home is not None and odds_draw is not None and odds_away is not None:
        try:
            probs = _probs_from_odds(odds_home, odds_draw, odds_away)
            p_home = probs["p_home"]
            p_draw = probs["p_draw"]
            p_away = probs["p_away"]

            comment_parts.append(
                f"Probabilités calculées à partir des cotes 1X2 "
                f"(home={odds_home}, draw={odds_draw}, away={odds_away}). "
                f"p_home={p_home:.3f}, p_draw={p_draw:.3f}, p_away={p_away:.3f}."
            )
        except Exception as e:
            # Si problème avec les cotes, on tombe en mode démo
            p_home = p_draw = p_away = 1.0 / 3.0
            comment_parts.append(
                f"Erreur dans les cotes fournies ({e}), "
                "probas mises à 33.3% / 33.3% / 33.3% (démo)."
            )

    # ====== CAS 2 : pas de cotes => mode démo ======
    else:
        p_home = p_draw = p_away = 1.0 / 3.0
        comment_parts.append(
            "Aucune cote fournie, mode démo : probas 33.3% / 33.3% / 33.3%."
        )

    # Issue la plus probable
    if p_home >= p_draw and p_home >= p_away:
        prediction = f"Victoire de {home_clean}"
    elif p_away >= p_home and p_away >= p_draw:
        prediction = f"Victoire de {away_clean}"
    else:
        prediction = "Match nul"

    comment_parts.append(f"Issue la plus probable : {prediction}")

    comment = " ".join(comment_parts)

    res = PredictResult(
        prediction=prediction,
        p_home=p_home,
        p_draw=p_draw,
        p_away=p_away,
        comment=comment,
        status="ok",
    )
    return res.to_dict()


# =====================================================
#  MODE B : PRONO VIA API-FOOTBALL /predictions
# =====================================================

def predict_one_match_from_apisports(fixture_id: int) -> Dict:
    """
    Option B : va chercher les pourcentages 1N2 depuis API-FOOTBALL
    pour un fixture précis (endpoint /predictions).
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

    p_home = pred["p_home"]
    p_draw = pred["p_draw"]
    p_away = pred["p_away"]

    # On choisit l’issue la plus probable
    if p_home >= p_draw and p_home >= p_away:
        prediction = "Victoire domicile"
    elif p_away >= p_home and p_away >= p_draw:
        prediction = "Victoire extérieur"
    else:
        prediction = "Match nul"

    advice = pred.get("advice") or ""
    winner_name = pred.get("winner_name") or ""
    winner_comment = pred.get("winner_comment") or ""

    comment = (
        f"Prono API-FOOTBALL (Option B). "
        f"p_home={p_home:.3f}, p_draw={p_draw:.3f}, p_away={p_away:.3f}. "
        f"Issue la plus probable : {prediction}. "
        f"Advice API : {advice or 'N/A'}. "
        f"Winner API : {winner_name} ({winner_comment})."
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