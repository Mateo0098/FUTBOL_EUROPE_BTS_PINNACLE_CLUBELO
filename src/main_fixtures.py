import os
import sys
import subprocess
import pandas as pd
import difflib
import re
import unicodedata
from config import MIN_EDGE, KELLY_FACTOR, MIN_KELLY, SKIP_UPDATES, FUZZY_CUTOFF, P_MIN


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FIXTURES_PATH = os.path.join(PROJECT_ROOT, "data", "raw", "Fixtures.csv")
CUOTAS_PATH = os.path.join(PROJECT_ROOT, "cuotas_pinnacle.csv")
OUTPUT_PATH = os.path.join(PROJECT_ROOT, "data", "processed", "matches_probs_fixtures.csv")
OUTPUT_HIGH_PATH = os.path.join(PROJECT_ROOT, "data", "processed", "matches_probs_fixtures_high.csv")
OUTPUT_ODDS_FILTERED = os.path.join(PROJECT_ROOT, "data", "processed", "cuotas_pinnacle_filtradas.csv")
SCRAPE_ODDS_SCRIPT = os.path.join(PROJECT_ROOT, "test_html_odds")


def normalizar_nombre(texto):
    if not isinstance(texto, str):
        return ""
    texto = texto.lower().strip()
    texto = re.sub(r"\(.*?\)", " ", texto)
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    texto = texto.replace("ß", "ss")
    for repl in [("ae", "a"), ("oe", "o"), ("ue", "u")]:
        texto = texto.replace(repl[0], repl[1])
    texto = texto.replace(".", " ").replace("-", " ")
    tokens = texto.split()
    stop_tokens = {
        "fc", "cf", "sc", "ac", "cd", "ud", "sd", "rc", "sv", "v", "club",
        "de", "la", "el", "partido", "bayer", "eintracht", "borussia", "munich",
    }
    replacements = {
        "hamburger": "hamburg",
        "monchengladbach": "gladbach",
    }
    cleaned = []
    for token in tokens:
        if token in stop_tokens:
            continue
        cleaned.append(replacements.get(token, token))
    texto = " ".join(cleaned)
    return texto


def parse_fecha_es(s):
    if not isinstance(s, str):
        return pd.NaT
    meses = {
        "ENE": "JAN", "FEB": "FEB", "MAR": "MAR", "ABR": "APR", "MAY": "MAY", "JUN": "JUN",
        "JUL": "JUL", "AGO": "AUG", "SEP": "SEP", "OCT": "OCT", "NOV": "NOV", "DIC": "DEC",
    }
    s = s.upper()
    for es, en in meses.items():
        s = s.replace(f" {es} ", f" {en} ")
    s = s.split(",", 1)[-1].strip()
    return pd.to_datetime(s, format="%d %b %Y %H:%M", errors="coerce")


def edge(prob, odds):
    return prob * odds - 1


def kelly(prob, odds):
    if odds <= 1:
        return 0.0
    return max((prob * odds - 1) / (odds - 1), 0.0)


def double_chance_odds(odds_home, odds_draw, odds_away):
    dc_1x = (odds_draw * odds_home) / (odds_draw + odds_home) if (odds_draw + odds_home) else 0.0
    dc_x2 = (odds_draw * odds_away) / (odds_draw + odds_away) if (odds_draw + odds_away) else 0.0
    dc_12 = (odds_home * odds_away) / (odds_home + odds_away) if (odds_home + odds_away) else 0.0
    return dc_1x, dc_x2, dc_12


def split_kelly_by_odds(odds_a, odds_b, kelly_a, kelly_b):
    if odds_a <= 0 or odds_b <= 0:
        return None, None
    total = max(kelly_a or 0.0, kelly_b or 0.0)
    if total <= 0:
        return None, None
    denom = odds_a + odds_b
    if not denom:
        return None, None
    stake_a = (odds_b * total) / denom
    stake_b = total - stake_a
    return stake_a, stake_b


def compute_1x2_probs(row, gd_cols):
    p_home = 0.0
    p_draw = 0.0
    p_away = 0.0
    for col in gd_cols:
        val = float(row.get(col, 0) or 0)
        if col == "GD=0":
            p_draw += val
            continue
        if col == "GD<-5":
            p_away += val
            continue
        if col == "GD>5":
            p_home += val
            continue
        if col.startswith("GD="):
            try:
                gd = int(col.split("=", 1)[1])
            except ValueError:
                continue
            if gd > 0:
                p_home += val
            elif gd < 0:
                p_away += val
    return p_home, p_draw, p_away


def compute_scoreline_probs(row, score_cols):
    p_btts = 0.0
    p_home_scores = 0.0
    p_away_scores = 0.0
    for col in score_cols:
        if not col.startswith("R:"):
            continue
        score = col.split(":", 1)[1]
        if "-" not in score:
            continue
        try:
            home_g, away_g = score.split("-", 1)
            home_g = int(home_g)
            away_g = int(away_g)
        except ValueError:
            continue
        val = float(row.get(col, 0) or 0)
        if home_g >= 1:
            p_home_scores += val
        if away_g >= 1:
            p_away_scores += val
        if home_g >= 1 and away_g >= 1:
            p_btts += val
    return p_btts, p_home_scores, p_away_scores


def compute_most_probable_score(row, score_cols):
    best_score = None
    best_prob = None
    for col in score_cols:
        if not col.startswith("R:"):
            continue
        score = col.split(":", 1)[1]
        if "-" not in score:
            continue
        try:
            home_g, away_g = score.split("-", 1)
            int(home_g)
            int(away_g)
        except ValueError:
            continue
        val = float(row.get(col, 0) or 0)
        if best_prob is None or val > best_prob:
            best_prob = val
            best_score = score
    return best_score, best_prob


def to_scalar(value, default=0.0):
    if isinstance(value, pd.Series):
        if value.empty:
            return default
        value = value.iloc[0]
    try:
        return float(value)
    except Exception:
        return default


def fuzzy_match_team(team_name, candidatos):
    team_norm = normalizar_nombre(team_name)
    if not team_norm:
        return None, 0.0
    nombres = candidatos["team_norm"].tolist()
    substring_matches = []
    for candidate in nombres:
        if team_norm in candidate or candidate in team_norm:
            score = difflib.SequenceMatcher(None, team_norm, candidate).ratio()
            substring_matches.append((candidate, score))
    if substring_matches:
        best = max(substring_matches, key=lambda x: x[1])[0]
        score = max(substring_matches, key=lambda x: x[1])[1]
        row = candidatos[candidatos["team_norm"] == best].iloc[0]
        return row, score
    match = difflib.get_close_matches(team_norm, nombres, n=1, cutoff=FUZZY_CUTOFF)
    if not match:
        return None, 0.0
    best = match[0]
    score = difflib.SequenceMatcher(None, team_norm, best).ratio()
    row = candidatos[candidatos["team_norm"] == best].iloc[0]
    return row, score


def main():
    if SKIP_UPDATES:
        print("Saltando actualización de cuotas (SKIP_UPDATES=True).")
    else:
        print("Actualizando cuotas...")
        subprocess.run([sys.executable, SCRAPE_ODDS_SCRIPT], check=True, cwd=PROJECT_ROOT)

    df_fix = pd.read_csv(FIXTURES_PATH)
    if df_fix.empty:
        os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
        pd.DataFrame([]).to_csv(OUTPUT_PATH, index=False)
        print("Fixtures.csv vacío.")
        return

    df_fix["fixture_date"] = pd.to_datetime(df_fix["Date"], errors="coerce").dt.date
    date_min = df_fix["fixture_date"].min()
    date_max = df_fix["fixture_date"].max()
    if pd.isna(date_min) or pd.isna(date_max):
        raise ValueError("No se pudieron parsear las fechas en Fixtures.csv")

    gd_cols = [c for c in df_fix.columns if c.startswith("GD")]
    if not gd_cols:
        raise ValueError("No se encontraron columnas GD en Fixtures.csv")

    df_fix["p_home"], df_fix["p_draw"], df_fix["p_away"] = zip(
        *df_fix.apply(lambda r: compute_1x2_probs(r, gd_cols), axis=1)
    )
    score_cols = [c for c in df_fix.columns if c.startswith("R:")]
    df_fix["p_btts"], df_fix["p_home_scores"], df_fix["p_away_scores"] = zip(
        *df_fix.apply(lambda r: compute_scoreline_probs(r, score_cols), axis=1)
    )
    df_fix["score_most_probable"], df_fix["score_most_probable_prob"] = zip(
        *df_fix.apply(lambda r: compute_most_probable_score(r, score_cols), axis=1)
    )

    df_cuotas = pd.read_csv(CUOTAS_PATH)
    df_cuotas["home_norm"] = df_cuotas["Local"].apply(normalizar_nombre)
    df_cuotas["away_norm"] = df_cuotas["Visitante"].apply(normalizar_nombre)
    df_cuotas["cuota_date"] = pd.to_datetime(
        df_cuotas["Fecha"].apply(parse_fecha_es),
        errors="coerce",
    ).dt.date
    df_cuotas_dated = df_cuotas[
        (df_cuotas["cuota_date"] >= date_min)
        & (df_cuotas["cuota_date"] <= date_max)
    ].copy()
    df_cuotas_undated = df_cuotas[df_cuotas["cuota_date"].isna()].copy()
    total_fixtures = len(df_fix)
    total_cuotas = len(df_cuotas_dated)
    total_cuotas_undated = len(df_cuotas_undated)
    matched_rows = []
    matched_count = 0
    matched_odds_idx = set()

    for _, fix in df_fix.iterrows():
        home_match, home_score = fuzzy_match_team(
            fix["Home"],
            df_cuotas_dated[["Local", "home_norm"]].rename(columns={"Local": "team", "home_norm": "team_norm"}),
        )
        away_match, away_score = fuzzy_match_team(
            fix["Away"],
            df_cuotas_dated[["Visitante", "away_norm"]].rename(columns={"Visitante": "team", "away_norm": "team_norm"}),
        )
        odds_row = None
        if home_match is not None and away_match is not None:
            odds_row = df_cuotas_dated[
                (df_cuotas_dated["home_norm"] == home_match["team_norm"])
                & (df_cuotas_dated["away_norm"] == away_match["team_norm"])
            ]
            if not odds_row.empty:
                odds_row = odds_row.iloc[0]
                matched_odds_idx.add(odds_row.name)
        if odds_row is None:
            home_match, home_score = fuzzy_match_team(
                fix["Home"],
                df_cuotas_undated[["Local", "home_norm"]].rename(columns={"Local": "team", "home_norm": "team_norm"}),
            )
            away_match, away_score = fuzzy_match_team(
                fix["Away"],
                df_cuotas_undated[["Visitante", "away_norm"]].rename(columns={"Visitante": "team", "away_norm": "team_norm"}),
            )
            if home_match is None or away_match is None:
                continue
            odds_row = df_cuotas_undated[
                (df_cuotas_undated["home_norm"] == home_match["team_norm"])
                & (df_cuotas_undated["away_norm"] == away_match["team_norm"])
            ]
            if odds_row.empty:
                continue
            odds_row = odds_row.iloc[0]
            matched_odds_idx.add(odds_row.name)
        merged = fix.to_dict()
        for col in ["Liga", "URL", "Local", "Visitante", "Fecha", "Cuota_Local", "Cuota_Empate", "Cuota_Visitante"]:
            merged[col] = odds_row.get(col)
        merged["match_score_local"] = round(home_score, 3)
        merged["match_score_visitante"] = round(away_score, 3)
        matched_rows.append(merged)
        matched_count += 1

    os.makedirs(os.path.dirname(OUTPUT_ODDS_FILTERED), exist_ok=True)
    df_cuotas_dated_unmatched = df_cuotas_dated.loc[
        ~df_cuotas_dated.index.isin(matched_odds_idx)
    ]
    df_cuotas_undated_unmatched = df_cuotas_undated.loc[
        ~df_cuotas_undated.index.isin(matched_odds_idx)
    ]
    df_cuotas_unmatched = pd.concat(
        [df_cuotas_dated_unmatched, df_cuotas_undated_unmatched], ignore_index=True
    )
    df_cuotas_unmatched.drop(columns=["cuota_date"], errors="ignore").to_csv(
        OUTPUT_ODDS_FILTERED, index=False, encoding="utf-8-sig"
    )

    unmatched = total_fixtures - matched_count
    match_pct = (matched_count / total_fixtures * 100) if total_fixtures else 0.0
    unmatched_pct = (unmatched / total_fixtures * 100) if total_fixtures else 0.0
    print(
        "Cruce fixtures vs cuotas:",
        f"fixtures={total_fixtures}, cuotas={total_cuotas},",
        f"match={matched_count} ({match_pct:.1f}%),",
        f"no_match={unmatched} ({unmatched_pct:.1f}%),",
        f"cuotas_dated={total_cuotas}, cuotas_undated={total_cuotas_undated}",
    )

    df_merge = pd.DataFrame(matched_rows)

    rows = []
    rows_high = []
    for _, r in df_merge.iterrows():
        odds_home = to_scalar(r.get("Cuota_Local", 0))
        odds_draw = to_scalar(r.get("Cuota_Empate", 0))
        odds_away = to_scalar(r.get("Cuota_Visitante", 0))

        dc_1x, dc_x2, dc_12 = double_chance_odds(odds_home, odds_draw, odds_away)
        kelly_home_ind = kelly(r["p_home"], odds_home) * KELLY_FACTOR
        kelly_draw_ind = kelly(r["p_draw"], odds_draw) * KELLY_FACTOR
        kelly_away_ind = kelly(r["p_away"], odds_away) * KELLY_FACTOR
        split_hd_home, split_hd_draw = split_kelly_by_odds(
            odds_home, odds_draw, kelly_home_ind, kelly_draw_ind
        )
        split_da_draw, split_da_away = split_kelly_by_odds(
            odds_draw, odds_away, kelly_draw_ind, kelly_away_ind
        )
        split_ha_home, split_ha_away = split_kelly_by_odds(
            odds_home, odds_away, kelly_home_ind, kelly_away_ind
        )

        markets = [
            ("Home", r["p_home"], odds_home),
            ("Draw", r["p_draw"], odds_draw),
            ("Away", r["p_away"], odds_away),
            ("1X", r["p_home"] + r["p_draw"], dc_1x),
            ("X2", r["p_draw"] + r["p_away"], dc_x2),
            ("12", r["p_home"] + r["p_away"], dc_12),
        ]

        for market, prob, odds in markets:
            if odds <= 1:
                continue
            e = edge(prob, odds)
            if e < MIN_EDGE:
                continue
            k = kelly(prob, odds) * KELLY_FACTOR
            if k <= MIN_KELLY:
                continue
            rows.append(
                {
                    "liga": r.get("Liga", "") or r.get("Country", ""),
                    "fecha": r.get("Fecha", "") or r.get("Date", ""),
                    "local": r.get("Home", ""),
                    "visitante": r.get("Away", ""),
                    "mercado": market,
                    "cuota": odds,
                    "p_home": round(r["p_home"], 4),
                    "p_draw": round(r["p_draw"], 4),
                    "p_away": round(r["p_away"], 4),
                    "p_btts": round(r["p_btts"], 4),
                    "p_home_scores": round(r["p_home_scores"], 4),
                    "p_away_scores": round(r["p_away_scores"], 4),
                    "score_most_probable": r.get("score_most_probable", "") or "",
                    "score_most_probable_prob": (
                        round(r["score_most_probable_prob"], 4)
                        if pd.notna(r.get("score_most_probable_prob"))
                        else None
                    ),
                    "kelly_split_home_draw_home": (
                        round(split_hd_home, 4) if split_hd_home is not None else None
                    ),
                    "kelly_split_home_draw_draw": (
                        round(split_hd_draw, 4) if split_hd_draw is not None else None
                    ),
                    "kelly_split_draw_away_draw": (
                        round(split_da_draw, 4) if split_da_draw is not None else None
                    ),
                    "kelly_split_draw_away_away": (
                        round(split_da_away, 4) if split_da_away is not None else None
                    ),
                    "kelly_split_home_away_home": (
                        round(split_ha_home, 4) if split_ha_home is not None else None
                    ),
                    "kelly_split_home_away_away": (
                        round(split_ha_away, 4) if split_ha_away is not None else None
                    ),
                    "edge": round(e, 4),
                    "kelly": round(k, 4),
                }
            )
        for market, prob, odds in markets:
            if odds <= 1:
                continue
            if prob < P_MIN:
                continue
            e = edge(prob, odds)
            k = kelly(prob, odds) * KELLY_FACTOR
            rows_high.append(
                {
                    "liga": r.get("Liga", "") or r.get("Country", ""),
                    "fecha": r.get("Fecha", "") or r.get("Date", ""),
                    "local": r.get("Home", ""),
                    "visitante": r.get("Away", ""),
                    "mercado": market,
                    "cuota": odds,
                    "p_home": round(r["p_home"], 4),
                    "p_draw": round(r["p_draw"], 4),
                    "p_away": round(r["p_away"], 4),
                    "p_btts": round(r["p_btts"], 4),
                    "p_home_scores": round(r["p_home_scores"], 4),
                    "p_away_scores": round(r["p_away_scores"], 4),
                    "score_most_probable": r.get("score_most_probable", "") or "",
                    "score_most_probable_prob": (
                        round(r["score_most_probable_prob"], 4)
                        if pd.notna(r.get("score_most_probable_prob"))
                        else None
                    ),
                    "kelly_split_home_draw_home": (
                        round(split_hd_home, 4) if split_hd_home is not None else None
                    ),
                    "kelly_split_home_draw_draw": (
                        round(split_hd_draw, 4) if split_hd_draw is not None else None
                    ),
                    "kelly_split_draw_away_draw": (
                        round(split_da_draw, 4) if split_da_draw is not None else None
                    ),
                    "kelly_split_draw_away_away": (
                        round(split_da_away, 4) if split_da_away is not None else None
                    ),
                    "kelly_split_home_away_home": (
                        round(split_ha_home, 4) if split_ha_home is not None else None
                    ),
                    "kelly_split_home_away_away": (
                        round(split_ha_away, 4) if split_ha_away is not None else None
                    ),
                    "edge": round(e, 4),
                    "kelly": round(k, 4),
                }
            )

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    df_out = pd.DataFrame(rows)
    df_out.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")
    print(f"Probabilidades guardadas en: {OUTPUT_PATH}")
    print(df_out.head(20))

    df_high = pd.DataFrame(rows_high)
    df_high.to_csv(OUTPUT_HIGH_PATH, index=False, encoding="utf-8-sig")
    print(f"Probabilidades guardadas en: {OUTPUT_HIGH_PATH}")
    print(df_high.head(20))


if __name__ == "__main__":
    main()

