import os
import pandas as pd
from datetime import datetime
from src.config import P_MIN_COMBO, EDGE_MIN_COMBO, KELLY_FACTOR

INPUT_PATH = os.path.join("data", "processed", "matches_probs_fixtures_high.csv")
OUTPUT_PATH = os.path.join("data", "processed", "combo_picks_fixtures.csv")

def market_prob(row):
    market = row.get("mercado")
    p_home = row.get("p_home")
    p_draw = row.get("p_draw")
    p_away = row.get("p_away")
    if market == "Home":
        return p_home
    if market == "Draw":
        return p_draw
    if market == "Away":
        return p_away
    if market == "1X":
        return p_home + p_draw
    if market == "X2":
        return p_draw + p_away
    if market == "12":
        return p_home + p_away
    return None


def main():
    df = pd.read_csv(INPUT_PATH)
    if df.empty:
        os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
        pd.DataFrame([]).to_csv(OUTPUT_PATH, index=False)
        print("No hay apuestas para analizar.")
        return

    if "fecha" in df.columns:
        meses = {
            "ENE": "JAN", "FEB": "FEB", "MAR": "MAR", "ABR": "APR", "MAY": "MAY", "JUN": "JUN",
            "JUL": "JUL", "AGO": "AUG", "SEP": "SEP", "OCT": "OCT", "NOV": "NOV", "DIC": "DEC",
        }

        def parse_fecha(s):
            if not isinstance(s, str):
                return pd.NaT
            s = s.upper()
            for es, en in meses.items():
                s = s.replace(f" {es} ", f" {en} ")
            s = s.split(",", 1)[-1].strip()
            return pd.to_datetime(s, format="%d %b %Y %H:%M", errors="coerce")

        df["fecha_dt"] = df["fecha"].apply(parse_fecha)

    df["p_market"] = df.apply(market_prob, axis=1)
    df = df.dropna(subset=["p_market"])

    df = df[df["edge"] >= EDGE_MIN_COMBO]
    df = df.sort_values(["p_market", "edge"], ascending=[False, False])

    if df.empty:
        os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
        pd.DataFrame([]).to_csv(OUTPUT_PATH, index=False)
        print("No hay apuestas que cumplan los filtros del combo.")
        return

    combo_rows = []
    combo_odds = 1.0
    combo_prob = 1.0
    for _, row in df.iterrows():
        odds = float(row["cuota"])
        prob = float(row["p_market"])
        next_combo_prob = combo_prob * prob
        if next_combo_prob < P_MIN_COMBO:
            break
        combo_odds *= odds
        combo_prob = next_combo_prob
        combo_edge = combo_prob * combo_odds - 1
        if combo_odds > 1:
            combo_kelly = max((combo_prob * combo_odds - 1) / (combo_odds - 1), 0.0)
        else:
            combo_kelly = 0.0
        combo_kelly *= KELLY_FACTOR
        combo_rows.append(
            {
                "liga": row["liga"],
                "fecha": row["fecha"],
                "local": row["local"],
                "visitante": row["visitante"],
                "mercado": row["mercado"],
                "cuota": row["cuota"],
                "p_market": row["p_market"],
                "p_btts": row.get("p_btts"),
                "p_home_scores": row.get("p_home_scores"),
                "p_away_scores": row.get("p_away_scores"),
                "score_most_probable": row.get("score_most_probable"),
                "score_most_probable_prob": row.get("score_most_probable_prob"),
                "kelly_split_home_draw_home": row.get("kelly_split_home_draw_home"),
                "kelly_split_home_draw_draw": row.get("kelly_split_home_draw_draw"),
                "kelly_split_draw_away_draw": row.get("kelly_split_draw_away_draw"),
                "kelly_split_draw_away_away": row.get("kelly_split_draw_away_away"),
                "kelly_split_home_away_home": row.get("kelly_split_home_away_home"),
                "kelly_split_home_away_away": row.get("kelly_split_home_away_away"),
                "edge": row["edge"],
                "kelly": row["kelly"],
                "combo_odds": combo_odds,
                "combo_kelly": combo_kelly,
                "combo_prob": combo_prob,
                "combo_edge": combo_edge,
            }
        )

    df_out = pd.DataFrame(combo_rows)

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    df_out.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")
    print(f"Combo guardado en: {OUTPUT_PATH}")
    print(df_out)


if __name__ == "__main__":
    main()
