import os
import pandas as pd
import requests
from datetime import datetime
import html
import json
import time
from src.config import BOT_TOKEN, CHAT_ID
def _chunk_messages(blocks, max_len=3800):
    combined = []
    current = ""
    for block in blocks:
        if not current:
            current = block
            continue
        if len(current) + 2 + len(block) <= max_len:
            current = f"{current}\n\n{block}"
        else:
            combined.append(current)
            current = block
    if current:
        combined.append(current)
    return combined


def enviar_telegram():
    token = BOT_TOKEN
    chat_id = CHAT_ID
    if not token or not chat_id:
        print("BOT_TOKEN o CHAT_ID no definidos.")
        return

    df = pd.read_csv("data/processed/matches_probs_fixtures.csv")
    fixtures_df = pd.read_csv("data/raw/Fixtures.csv")
    fixtures_df["fixture_date"] = pd.to_datetime(
        fixtures_df["Date"], errors="coerce"
    ).dt.date
    date_min = fixtures_df["fixture_date"].min()
    date_max = fixtures_df["fixture_date"].max()
    range_str = (
        f"{date_min} a {date_max}"
        if pd.notna(date_min) and pd.notna(date_max)
        else "rango no disponible"
    )
    bankroll_df = pd.read_csv("bankroll.csv", header=None)
    bankroll = float(bankroll_df.iloc[0, 1]) if not bankroll_df.empty else 0.0
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
        df = df.sort_values("fecha_dt")
    if df.empty:
        msg = (
            f"📅 Rango fixtures: {range_str}\n"
            "✅ Sin apuestas con edge/kelly en esta corrida."
        )
    else:
        header = f"📅 Rango fixtures: {range_str}"
        rule_text = (
            "📌 Regla de selección de mercados: "
            "elegir el mayor Kelly; si la diferencia es < 0.01, "
            "elegir el mayor edge; si empatan, elegir la cuota más baja."
        )
        rule_text = html.escape(rule_text)
        msgs = []
        message_entries = []
        group_cols = ["liga", "fecha", "local", "visitante"]
        for _, group in df.groupby(group_cols):
            group = group.sort_values("edge", ascending=False)
            blocks = []
            r0 = group.iloc[0]
            query = f"{r0['local']} vs {r0['visitante']}"
            google_link = f"https://www.google.com/search?q={requests.utils.quote(query)}"

            def safe_float(val):
                try:
                    return float(val)
                except Exception:
                    return None

            def market_prob(market, row):
                p_home = safe_float(row.get("p_home"))
                p_draw = safe_float(row.get("p_draw"))
                p_away = safe_float(row.get("p_away"))
                if market == "Home":
                    return p_home
                if market == "Draw":
                    return p_draw
                if market == "Away":
                    return p_away
                if market == "1X" and p_home is not None and p_draw is not None:
                    return p_home + p_draw
                if market == "X2" and p_draw is not None and p_away is not None:
                    return p_draw + p_away
                if market == "12" and p_home is not None and p_away is not None:
                    return p_home + p_away
                return None
            group_markets = set(group.get("mercado", []))
            dc_market = None
            for candidate in ("1X", "X2", "12"):
                if candidate in group_markets:
                    dc_market = candidate
                    break
            for _, r in group.iterrows():
                prob = market_prob(r.get("mercado"), r)
                stake = float(r["kelly"]) * bankroll if bankroll else 0.0
                prob_str = f"{prob:.3f}" if isinstance(prob, (int, float)) else "N/A"
                score_most_probable = r.get("score_most_probable")
                score_prob = safe_float(r.get("score_most_probable_prob"))
                score_prob_str = f"{score_prob:.3f}" if isinstance(score_prob, (int, float)) else "N/A"
                score_str = html.escape(str(score_most_probable)) if score_most_probable else "N/A"
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
                p_btts = safe_float(r.get("p_btts"))
                p_home_scores = safe_float(r.get("p_home_scores"))
                p_away_scores = safe_float(r.get("p_away_scores"))
                p_btts_str = f"{p_btts:.3f}" if isinstance(p_btts, (int, float)) else "N/A"
                p_home_scores_str = f"{p_home_scores:.3f}" if isinstance(p_home_scores, (int, float)) else "N/A"
                p_away_scores_str = f"{p_away_scores:.3f}" if isinstance(p_away_scores, (int, float)) else "N/A"
                if dc_market == "1X":
                    dc_split_block = (
                        f"🔀 Kelly split 1X: Home {k_hd_home_str} (stake {s_hd_home_str}) | "
                        f"Draw {k_hd_draw_str} (stake {s_hd_draw_str})\n"
                    )
                elif dc_market == "X2":
                    dc_split_block = (
                        f"🔀 Kelly split X2: Draw {k_da_draw_str} (stake {s_da_draw_str}) | "
                        f"Away {k_da_away_str} (stake {s_da_away_str})\n"
                    )
                elif dc_market == "12":
                    dc_split_block = (
                        f"🔀 Kelly split 12: Home {k_ha_home_str} (stake {s_ha_home_str}) | "
                        f"Away {k_ha_away_str} (stake {s_ha_away_str})\n"
                    )
                else:
                    dc_split_block = ""
                block = (
                    "📌 Apuesta recomendada\n"
                    "🏟️ {liga}\n"
                    "📅 {fecha}\n"
                    "⚽ {local} vs {visitante}\n"
                    "🎯 Mercado: {mercado}\n"
                    "💰 Cuota: {cuota}\n"
                    "📈 Prob: {prob}\n"
                    "🎯 Marcador más probable: {score} ({score_prob})\n"
                    "⚽ BTTS (ambos anotan): {p_btts}\n"
                    "🏠 Casa anota: {p_home_scores}\n"
                    "🛫 Visita anota: {p_away_scores}\n"
                    "{dc_split_block}"
                    "✅ Edge: {edge}\n"
                    "📌 Kelly: {kelly}\n"
                    "💵 Stake (Kelly*bankroll): {stake:.2f}\n"
                    "🔎 <a href=\"{google_link}\">Ver en Google</a>"
                ).format(
                    liga=html.escape(str(r["liga"])),
                    fecha=html.escape(str(r["fecha"])),
                    local=html.escape(str(r["local"])),
                    visitante=html.escape(str(r["visitante"])),
                    mercado=html.escape(str(r["mercado"])),
                    cuota=html.escape(str(r["cuota"])),
                    prob=prob_str,
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
                    edge=html.escape(str(r["edge"])),
                    kelly=html.escape(str(r["kelly"])),
                    stake=stake,
                    google_link=html.escape(google_link, quote=True),
                )
                blocks.append(block)
            group_edge = group["edge"].max() if "edge" in group.columns and not group.empty else 0.0
            group_dt = group["fecha_dt"].iloc[0] if "fecha_dt" in group.columns and not group.empty else pd.NaT
            if pd.notna(group_dt):
                sort_key = (0, group_dt.timestamp())
            else:
                sort_key = (1, str(r0.get("fecha", "")))
            message_entries.append(
                {
                    "sort_key": sort_key,
                    "edge": float(group_edge) if pd.notna(group_edge) else 0.0,
                    "msg": "\n\n".join(blocks),
                }
            )

        message_entries.sort(key=lambda x: (x["sort_key"][0], x["sort_key"][1], -x["edge"]))
        msgs = []
        for idx, entry in enumerate(message_entries):
            if idx > 0:
                msgs.append("────────")
            msgs.append(entry["msg"])
        prefix = f"{header}\n{rule_text}"
        msgs_with_prefix = [prefix] + msgs
        combined_msgs = _chunk_messages(msgs_with_prefix, max_len=3800)
        # region agent log
        with open("debug-61591f.log", "a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "sessionId": "61591f",
                        "runId": "pre",
                        "hypothesisId": "H1",
                        "location": "telegram_test_fixtures.py:chunked",
                        "message": "Chunked message counts",
                        "data": {
                            "entries": len(message_entries),
                            "chunks": len(combined_msgs),
                            "total_parts": len(msgs_with_prefix),
                            "prefix_len": len(prefix),
                            "max_len": 3800,
                        },
                        "timestamp": int(time.time() * 1000),
                    }
                )
                + "\n"
            )
        # endregion

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    if df.empty:
        resp = requests.post(url, data={"chat_id": chat_id, "text": msg})
        if resp.ok:
            print("✅ Mensaje enviado a Telegram.")
        else:
            print(f"❌ Error enviando mensaje: {resp.status_code} - {resp.text}")
    else:
        ok = True
        max_chunks_per_run = 10
        for idx, msg in enumerate(combined_msgs):
            if not ok:
                break
            if idx >= max_chunks_per_run:
                remaining = len(combined_msgs) - idx
                print(
                    "ℹ️ Se alcanzó el límite de envíos por corrida. "
                    f"Quedan {remaining} mensajes pendientes."
                )
                # region agent log
                with open("debug-61591f.log", "a", encoding="utf-8") as f:
                    f.write(
                        json.dumps(
                            {
                                "sessionId": "61591f",
                                "runId": "pre",
                                "hypothesisId": "H6",
                                "location": "telegram_test_fixtures.py:send_chunk_cap",
                                "message": "Hit per-run chunk cap",
                                "data": {
                                    "max_chunks_per_run": max_chunks_per_run,
                                    "sent": idx,
                                    "remaining": remaining,
                                },
                                "timestamp": int(time.time() * 1000),
                            }
                        )
                        + "\n"
                    )
                # endregion
                break
            # region agent log
            with open("debug-61591f.log", "a", encoding="utf-8") as f:
                f.write(
                    json.dumps(
                        {
                            "sessionId": "61591f",
                            "runId": "pre",
                            "hypothesisId": "H4",
                            "location": "telegram_test_fixtures.py:send_chunk_start",
                            "message": "Sending chunk",
                            "data": {"chunk_idx": idx, "text_len": len(msg)},
                            "timestamp": int(time.time() * 1000),
                        }
                    )
                    + "\n"
                )
            # endregion
            resp = requests.post(url, data={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"})
            # region agent log
            retry_after = None
            try:
                retry_after = resp.json().get("parameters", {}).get("retry_after")
            except Exception:
                retry_after = None
            with open("debug-61591f.log", "a", encoding="utf-8") as f:
                f.write(
                    json.dumps(
                        {
                            "sessionId": "61591f",
                            "runId": "pre",
                            "hypothesisId": "H5",
                            "location": "telegram_test_fixtures.py:send_chunk_result",
                            "message": "Chunk send result",
                            "data": {
                                "chunk_idx": idx,
                                "status_code": resp.status_code,
                                "ok": resp.ok,
                                "retry_after": retry_after,
                            },
                            "timestamp": int(time.time() * 1000),
                        }
                    )
                    + "\n"
                )
            # endregion
            if not resp.ok:
                ok = False
                print(f"❌ Error enviando mensaje: {resp.status_code} - {resp.text}")
                break
        if ok:
            footer = (
                "ℹ️ Glosario\n"
                "Mercado: selección recomendada (Home/Draw/Away).\n"
                "Cuota: precio de la apuesta para ese mercado.\n"
                "Prob: probabilidad estimada del mercado ganador.\n"
                "Edge: ventaja esperada = p*cuota - 1.\n"
                "Kelly: fracción de bankroll sugerida (ya ajustada por KELLY_FACTOR)."
            )
            resp = requests.post(url, data={"chat_id": chat_id, "text": footer, "parse_mode": "HTML"})
            if not resp.ok:
                print(f"❌ Error enviando glosario: {resp.status_code} - {resp.text}")
            else:
                print("✅ Mensajes enviados a Telegram.")


if __name__ == "__main__":
    enviar_telegram()
