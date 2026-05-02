import os
import pandas as pd
import requests
import html
from src.config import BOT_TOKEN, CHAT_ID

INPUT_PATH = os.path.join("data", "processed", "combo_picks_fixtures.csv")
BANKROLL_PATH = "bankroll.csv"


def _load_bankroll(target_name="mateo"):
    if not os.path.exists(BANKROLL_PATH):
        return 0.0
    with open(BANKROLL_PATH, encoding="utf-8") as f:
        for line in f:
            parts = [p.strip() for p in line.split(",")]
            if len(parts) != 2:
                continue
            name, amount = parts
            if name.lower() == target_name.lower():
                try:
                    return float(amount)
                except ValueError:
                    return 0.0
    return 0.0


def safe_float(value):
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def enviar_combo():
    token = BOT_TOKEN
    chat_id = CHAT_ID
    if not token or not chat_id:
        print("BOT_TOKEN o CHAT_ID no definidos.")
        return

    if not os.path.exists(INPUT_PATH):
        print("No existe combo_picks_fixtures.csv. Ejecuta combo_selector_fixtures.py primero.")
        return

    df = pd.read_csv(INPUT_PATH)
    if df.empty:
        msg = "✅ No hay selecciones para combo en esta corrida."
    else:
        bankroll = _load_bankroll("mateo")
        combo_odds = df["combo_odds"].iloc[-1]
        combo_edge = df["combo_edge"].iloc[-1] if "combo_edge" in df.columns else None
        combo_prob = df["combo_prob"].iloc[-1] if "combo_prob" in df.columns else None
        kelly_min = float(df["kelly"].min()) if "kelly" in df.columns else None
        kelly_max = float(df["kelly"].max()) if "kelly" in df.columns else None
        combo_kelly = df["combo_kelly"].iloc[-1] if "combo_kelly" in df.columns else None
        lines = []
        for _, r in df.iterrows():
            query = f"{r['local']} vs {r['visitante']}"
            google_link = f"https://www.google.com/search?q={requests.utils.quote(query)}"
            row_combo_odds = r.get("combo_odds")
            row_combo_edge = r.get("combo_edge")
            row_combo_prob = r.get("combo_prob")
            row_combo_kelly = r.get("combo_kelly")
            row_combo_kelly_val = float(row_combo_kelly) if row_combo_kelly is not None else 0.0
            stake_combo = bankroll * row_combo_kelly_val
            p_btts = safe_float(r.get("p_btts"))
            p_home_scores = safe_float(r.get("p_home_scores"))
            p_away_scores = safe_float(r.get("p_away_scores"))
            p_btts_str = f"{p_btts:.3f}" if isinstance(p_btts, (int, float)) else "N/A"
            p_home_scores_str = f"{p_home_scores:.3f}" if isinstance(p_home_scores, (int, float)) else "N/A"
            p_away_scores_str = f"{p_away_scores:.3f}" if isinstance(p_away_scores, (int, float)) else "N/A"
            score_most_probable = r.get("score_most_probable")
            score_prob = safe_float(r.get("score_most_probable_prob"))
            score_prob_str = f"{score_prob:.3f}" if isinstance(score_prob, (int, float)) else "N/A"
            score_str = html.escape(str(score_most_probable)) if score_most_probable else "N/A"
            mercado_val = str(r.get("mercado", "") or "")
            k_hd_home = safe_float(r.get("kelly_split_home_draw_home"))
            k_hd_draw = safe_float(r.get("kelly_split_home_draw_draw"))
            k_da_draw = safe_float(r.get("kelly_split_draw_away_draw"))
            k_da_away = safe_float(r.get("kelly_split_draw_away_away"))
            k_ha_home = safe_float(r.get("kelly_split_home_away_home"))
            k_ha_away = safe_float(r.get("kelly_split_home_away_away"))
            k_hd_home_str = f"{k_hd_home:.4f}" if isinstance(k_hd_home, (int, float)) else "N/A"
            k_hd_draw_str = f"{k_hd_draw:.4f}" if isinstance(k_hd_draw, (int, float)) else "N/A"
            k_da_draw_str = f"{k_da_draw:.4f}" if isinstance(k_da_draw, (int, float)) else "N/A"
            k_da_away_str = f"{k_da_away:.4f}" if isinstance(k_da_away, (int, float)) else "N/A"
            k_ha_home_str = f"{k_ha_home:.4f}" if isinstance(k_ha_home, (int, float)) else "N/A"
            k_ha_away_str = f"{k_ha_away:.4f}" if isinstance(k_ha_away, (int, float)) else "N/A"
            s_hd_home = (k_hd_home * bankroll) if isinstance(k_hd_home, (int, float)) else None
            s_hd_draw = (k_hd_draw * bankroll) if isinstance(k_hd_draw, (int, float)) else None
            s_da_draw = (k_da_draw * bankroll) if isinstance(k_da_draw, (int, float)) else None
            s_da_away = (k_da_away * bankroll) if isinstance(k_da_away, (int, float)) else None
            s_ha_home = (k_ha_home * bankroll) if isinstance(k_ha_home, (int, float)) else None
            s_ha_away = (k_ha_away * bankroll) if isinstance(k_ha_away, (int, float)) else None
            s_hd_home_str = f"{s_hd_home:.2f}" if isinstance(s_hd_home, (int, float)) else "N/A"
            s_hd_draw_str = f"{s_hd_draw:.2f}" if isinstance(s_hd_draw, (int, float)) else "N/A"
            s_da_draw_str = f"{s_da_draw:.2f}" if isinstance(s_da_draw, (int, float)) else "N/A"
            s_da_away_str = f"{s_da_away:.2f}" if isinstance(s_da_away, (int, float)) else "N/A"
            s_ha_home_str = f"{s_ha_home:.2f}" if isinstance(s_ha_home, (int, float)) else "N/A"
            s_ha_away_str = f"{s_ha_away:.2f}" if isinstance(s_ha_away, (int, float)) else "N/A"
            if mercado_val == "1X":
                dc_split_block = (
                    f"🔀 Kelly split 1X: Home {k_hd_home_str} (stake {s_hd_home_str}) | "
                    f"Draw {k_hd_draw_str} (stake {s_hd_draw_str})\n"
                )
            elif mercado_val == "X2":
                dc_split_block = (
                    f"🔀 Kelly split X2: Draw {k_da_draw_str} (stake {s_da_draw_str}) | "
                    f"Away {k_da_away_str} (stake {s_da_away_str})\n"
                )
            elif mercado_val == "12":
                dc_split_block = (
                    f"🔀 Kelly split 12: Home {k_ha_home_str} (stake {s_ha_home_str}) | "
                    f"Away {k_ha_away_str} (stake {s_ha_away_str})\n"
                )
            else:
                dc_split_block = ""
            stats_block = (
                "\n📊 Combo acumulado\n"
                "🎯 Cuota: {combo_odds:.3f} | 📈 Edge: {combo_edge:.4f} | "
                "📊 Prob: {combo_prob:.4f} | 📌 Kelly: {combo_kelly:.4f}\n"
                "📌 Kelly (min–max): {min_k:.4f}–{max_k:.4f}\n"
                "💵 Stake recomendado: {stake:.2f}"
            ).format(
                combo_odds=float(row_combo_odds) if row_combo_odds is not None else 0.0,
                combo_edge=float(row_combo_edge) if row_combo_edge is not None else 0.0,
                combo_prob=float(row_combo_prob) if row_combo_prob is not None else 0.0,
                combo_kelly=row_combo_kelly_val,
                min_k=float(kelly_min) if kelly_min is not None else 0.0,
                max_k=float(kelly_max) if kelly_max is not None else 0.0,
                stake=stake_combo,
            )
            lines.append(
                "🧩 Apuesta\n"
                "🏆 Liga: {liga}\n"
                "📅 Fecha: {fecha}\n"
                "⚽ Partido: {local} vs {visitante}\n"
                "🎯 Mercado: {mercado}\n"
                "💰 Cuota: {cuota}\n"
                "📈 Probabilidad: {p:.3f}\n"
                "🎯 Marcador más probable: {score} ({score_prob})\n"
                "⚽ BTTS (ambos anotan): {p_btts}\n"
                "🏠 Casa anota: {p_home_scores}\n"
                "🛫 Visita anota: {p_away_scores}\n"
                "{dc_split_block}"
                "📌 Kelly: {kelly}\n"
                "🔎 <a href=\"{google_link}\">Google</a>"
                "{stats}".format(
                    liga=html.escape(str(r["liga"])),
                    fecha=html.escape(str(r["fecha"])),
                    local=html.escape(str(r["local"])),
                    visitante=html.escape(str(r["visitante"])),
                    mercado=html.escape(str(r["mercado"])),
                    cuota=html.escape(str(r["cuota"])),
                    p=float(r["p_market"]),
                    score=score_str,
                    score_prob=score_prob_str,
                    p_btts=p_btts_str,
                    p_home_scores=p_home_scores_str,
                    p_away_scores=p_away_scores_str,
                    dc_split_block=dc_split_block,
                    k_hd_home=k_hd_home_str,
                    k_hd_draw=k_hd_draw_str,
                    k_da_draw=k_da_draw_str,
                    k_da_away=k_da_away_str,
                    k_ha_home=k_ha_home_str,
                    k_ha_away=k_ha_away_str,
                    kelly=html.escape(str(r["kelly"])),
                    google_link=html.escape(google_link, quote=True),
                    stats=stats_block,
                )
            )
        header = "🧩 Combo sugerido"
        msg = "{header}\n{lines}".format(
            header=header,
            lines="\n\n".join(lines),
        )

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    resp = requests.post(url, data={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"})
    if resp.ok:
        print("✅ Combo enviado a Telegram.")
    else:
        print(f"❌ Error enviando combo: {resp.status_code} - {resp.text}")


if __name__ == "__main__":
    enviar_combo()
