import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import log_loss
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
import joblib
from features.build_features import build_features

RAW = "data/raw/matches.csv"
ALL_LABELS = ['away', 'draw', 'home']

def align_proba_matrix(classes, proba):
    import pandas as pd
    dfp = pd.DataFrame(proba, columns=list(classes))
    for c in ALL_LABELS:
        if c not in dfp.columns:
            dfp[c] = 1e-9
    dfp = dfp[ALL_LABELS]
    dfp = dfp.div(dfp.sum(axis=1), axis=0)
    return dfp.values

if __name__ == "__main__":
    df = pd.read_csv(RAW, parse_dates=["date"]).sort_values("date")
    df_feat = build_features(df)
    features = [c for c in df_feat.columns if c.startswith(("f_","home_form_","away_form_"))]
    X = df_feat[features]
    y = df_feat["target_1x2"]

    try:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.3, shuffle=True, stratify=y, random_state=42
        )
    except ValueError:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.3, shuffle=True, random_state=42
        )

    base = Pipeline([
        ("scaler", StandardScaler(with_mean=False)),
        ("clf", LogisticRegression(max_iter=500, class_weight="balanced", multi_class="auto"))
    ])

    model = None
    # Try cv=3, then cv=2, else no calibration
    for cv in (3, 2):
        try:
            model = CalibratedClassifierCV(base, cv=cv, method="sigmoid")
            model.fit(X_train, y_train)
            break
        except Exception as e:
            print(f"[Calib] Échec avec cv={cv}: {e}")
            model = None

    if model is None:
        print("[Calib] Fallback: pas de calibration, logistique pure.")
        model = base
        model.fit(X_train, y_train)

    p_train = model.predict_proba(X_train)
    p_test  = model.predict_proba(X_test)
    classes = model.classes_

    p_train_al = align_proba_matrix(classes, p_train)
    p_test_al  = align_proba_matrix(classes, p_test)

    print("Features utilisées:", features)
    print("Classes apprises:", list(classes))
    print("LogLoss train:", log_loss(y_train, p_train_al, labels=ALL_LABELS))
    print("LogLoss test:",  log_loss(y_test,  p_test_al,  labels=ALL_LABELS))

    joblib.dump(model, "models/model_1x2.pkl")
    joblib.dump(features, "models/feature_columns.pkl")
    print("Saved models/model_1x2.pkl and models/feature_columns.pkl")
