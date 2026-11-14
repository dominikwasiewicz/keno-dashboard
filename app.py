import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
import datetime

st.set_page_config(page_title="Panel Analityczny Keno (Live)", layout="wide")

@st.cache_data(ttl=60)
def fetch_keno_full_history(target_draws=1100):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }
    session = requests.Session()
    session.headers.update(headers)
    
    records = []
    seen_ids = set()
    
    urls = ["https://wynikikeno.pl/"]
    now = datetime.datetime.now()
    for days_back in range(0, 6):
        target_date = now - datetime.timedelta(days=days_back)
        formatted_date = target_date.strftime("%d-%m-%Y")
        urls.append(f"https://wynikikeno.pl/losowanie/{formatted_date}")

    for url in urls:
        if len(records) >= target_draws:
            break
        try:
            resp = session.get(url, timeout=8)
            if resp.status_code != 200:
                continue
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "html.parser")
            
            full_text = soup.get_text(" ", strip=True)
            id_matches = list(re.finditer(r"#\s*(\d{6,8})", full_text))
            
            for idx_m, match in enumerate(id_matches):
                draw_id = match.group(1)
                if draw_id in seen_ids:
                    continue
                
                prefix_start = max(0, match.start() - 40)
                prefix_text = full_text[prefix_start:match.start()]
                time_matches = re.findall(r"\b(\d{1,2}:\d{2})\b", prefix_text)
                draw_time = time_matches[-1] if time_matches else "--:--"
                
                block_start = match.end()
                block_end = id_matches[idx_m + 1].start() if (idx_m + 1 < len(id_matches)) else min(len(full_text), block_start + 450)
                block_text = full_text[block_start:block_end]
                
                mnoznik_m = re.search(r"mnożnik\s*[x×✕\*]?\s*\d+", block_text, re.I)
                if mnoznik_m:
                    balls_text = block_text[mnoznik_m.end():]
                else:
                    balls_text = re.sub(r"\b[x×✕]\s*\d+\b", "", block_text, flags=re.I)
                
                balls_text = re.sub(r"\b\d{1,2}:\d{2}\b", "", balls_text)
                
                found_nums = re.findall(r"\b([0-9]{1,2})\b", balls_text)
                valid_nums = [int(n) for n in found_nums if 1 <= int(n) <= 70]
                
                unique_nums = []
                for n in valid_nums:
                    if n not in unique_nums:
                        unique_nums.append(n)
                    if len(unique_nums) == 20:
                        break
                        
                if len(unique_nums) == 20:
                    seen_ids.add(draw_id)
                    keno_sorted = sorted(unique_nums)
                    rec = {
                        "draw_id": draw_id,
                        "draw_time": draw_time,
                        "numbers_list": keno_sorted,
                        "numbers_set": set(keno_sorted)
                    }
                    for i in range(20):
                        rec[f"pos_{i+1}"] = keno_sorted[i]
                    records.append(rec)
                    
        except Exception:
            continue

    if records:
        df = pd.DataFrame(records)
        df["nr_int"] = pd.to_numeric(df["draw_id"], errors="coerce")
        df = df.sort_values(by="nr_int").drop(columns=["nr_int"]).reset_index(drop=True)
        return df, f"🟢 Załadowano {len(df)} autentycznych losowań Keno"

    return pd.DataFrame(), "Nie udało się pobrać danych archiwalnych."

# --- POBIERANIE DANYCH ---
df, status_msg = fetch_keno_full_history(target_draws=1100)

st.title("🎯 Panel Analityczny Keno (Stabilizacja Pozycji ⬜ ➔ 🟦)")

if df.empty:
    st.error(status_msg)
    if st.button("Spróbuj ponownie"):
        st.cache_data.clear()
        st.rerun()
    st.stop()

st.caption(status_msg)
last_draw = df.iloc[-1]
numbers_str_last = ", ".join(f"{n:02d}" for n in last_draw["numbers_list"])
st.info(f"Ostatnie losowanie: **#{last_draw['draw_id']}** (godz. **{last_draw['draw_time']}**) | Liczby: **{numbers_str_last}**")


# =====================================================================
# FUNKCJA GENERUJĄCA SEKCJĘ (TABELA 1 + STABILIZOWANA TABELA 2 NIEBIESKA)
# =====================================================================
def render_keno_section(section_id=1, default_top_val=20):
    st.divider()
    
    top_ranges = [11, 15, 20, 25, 30, 50, 100, ]
    available_top = [opt for opt in top_ranges if opt <= len(df)]
    if not available_top:
        available_top = [len(df)]
        
    default_top_idx = available_top.index(15) if default_top_val in available_top else 0

    selected_window = st.radio(
        "1️⃣ Wybierz zakres analizy dla Pierwszej Tabeli:",
        options=available_top,
        index=default_top_idx,
        horizontal=True,
        key=f"top_win_radio_{section_id}"
    )
    
    df_window = df.tail(selected_window).copy().reset_index(drop=True)
    
    col_draws, col_stats = st.columns([1.6, 0.9], gap="large")
    
    # -----------------------------------------------------------------
    # POZIOM 1: TABELA LOSOWAŃ KENO (BIAŁE KWADRATY I CZERWONE KÓŁKA)
    # -----------------------------------------------------------------
    with col_draws:
        st.subheader(f"📋 1. Tabela Losowań Keno (ostatnie {selected_window})")
        st.caption("⬜ **Kwadrat**: liczba na pozycji dająca trafienie w T+1 | 🔴 **Czerwone kółko**: trafienie z losowania T-1")
        
        total_rows = len(df_window)
        table_rows_html = []
        
        headers_cols_html = "".join([
            f"<th style='padding: 6px 2px; text-align: center; color: #4da6ff; font-size: 11px; width: 30px; border-right: 1px solid #2a2e39;'>{col_i}</th>" 
            for col_i in range(1, 21)
        ])

        for idx in range(total_rows - 1, -1, -1):
            row = df_window.iloc[idx]
            d_id = row["draw_id"]
            d_time = row["draw_time"]
            nums = row["numbers_list"]
            
            next_set = df_window.iloc[idx + 1]["numbers_set"] if idx + 1 < total_rows else set()
            prev_set = df_window.iloc[idx - 1]["numbers_set"] if idx - 1 >= 0 else set()
            
            cells_html = []
            for n in nums:
                is_source = (n in next_set)
                is_hit = (n in prev_set)
                
                if is_source and is_hit:
                    cell_content = (
                        f"<span style='display:inline-flex; align-items:center; justify-content:center; "
                        f"width:26px; height:26px; border:2px solid #ffffff; border-radius:4px; margin:1px; box-sizing:border-box;'>"
                        f"<span style='display:inline-flex; align-items:center; justify-content:center; "
                        f"width:20px; height:20px; border:2px solid #ff3333; border-radius:50%; "
                        f"background-color:rgba(255, 51, 51, 0.3); color:#ff5555; font-weight:bold; font-size:11px; box-sizing:border-box;'>"
                        f"{n:02d}</span></span>"
                    )
                elif is_source:
                    cell_content = (
                        f"<span style='display:inline-flex; align-items:center; justify-content:center; "
                        f"width:26px; height:26px; border:2px solid #ffffff; border-radius:4px; "
                        f"background-color:rgba(255, 255, 255, 0.08); color:#ffffff; font-weight:bold; "
                        f"font-size:11px; margin:1px; box-sizing:border-box;'>{n:02d}</span>"
                    )
                elif is_hit:
                    cell_content = (
                        f"<span style='display:inline-flex; align-items:center; justify-content:center; "
                        f"width:24px; height:24px; border:2px solid #ff3333; border-radius:50%; "
                        f"background-color:rgba(255, 51, 51, 0.25); color:#ff5555; font-weight:bold; "
                        f"font-size:11px; margin:1px; box-sizing:border-box;'>{n:02d}</span>"
                    )
                else:
                    cell_content = f"<span style='color:#a8b0c0; font-size:11px;'>{n:02d}</span>"
                    
                cells_html.append(f"<td style='padding: 4px 2px; text-align: center; border-right: 1px solid #232731;'>{cell_content}</td>")
                
            row_html = f"""
            <tr style='border-bottom: 1px solid #262a34;'>
                <td style='padding: 6px 6px; font-weight: bold; color: #ffffff; white-space: nowrap; font-size: 11px;'>{d_id}</td>
                <td style='padding: 6px 6px; color: #9da3af; white-space: nowrap; font-size: 11px;'>{d_time}</td>
                {''.join(cells_html)}
            </tr>
            """
            table_rows_html.append(row_html)
            
        full_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ margin: 0; padding: 0; background-color: #0e1117; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
                .table-container {{ max-height: 580px; overflow-y: auto; overflow-x: auto; border: 1px solid #333945; border-radius: 8px; }}
                table {{ width: 100%; border-collapse: collapse; }}
                thead {{ position: sticky; top: 0; background-color: #161922; z-index: 10; border-bottom: 2px solid #333945; }}
                th {{ padding: 8px 6px; text-align: left; color: #e6e6e6; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th style="width: 75px;">Nr</th>
                            <th style="width: 55px;">Czas</th>
                            {headers_cols_html}
                        </tr>
                    </thead>
                    <tbody>
                        {''.join(table_rows_html)}
                    </tbody>
                </table>
            </div>
        </body>
        </html>
        """
        components.html(full_html, height=600, scrolling=False)

    with col_stats:
        st.subheader(f"📊 1. Analiza pozycji (Trafienia T+1 z {selected_window})")
        
        sets_list = df_window["numbers_set"].tolist()
        total_transitions = len(df_window) - 1
        
        pos_stats = []
        for i in range(1, 21):
            pos_col = f"pos_{i}"
            pos_values = df_window[pos_col].tolist()
            
            repeat_t1_count = 0
            if total_transitions > 0:
                for k in range(total_transitions):
                    val_at_pos = pos_values[k]
                    next_draw_set = sets_list[k + 1]
                    if val_at_pos in next_draw_set:
                        repeat_t1_count += 1
                repeat_pct = (repeat_t1_count / total_transitions) * 100
            else:
                repeat_pct = 0.0

            series = df_window[pos_col]
            if not series.empty:
                mode_val = series.mode().iloc[0]
                most_common_cnt = int((series == mode_val).sum())
            else:
                mode_val = "-"
                most_common_cnt = 0
            
            pos_stats.append({
                "orig_pos_num": i,
                "Pozycja": f"Poz. {i:02d}",
                "raw_hits": repeat_t1_count,
                "Trafienia T+1": f"{repeat_t1_count} ({repeat_pct:.1f}%)",
                "Ostatnia": int(last_draw[pos_col]),
                "Najczęstsza": f"{mode_val} (x{most_common_cnt})",
                "Średnia": round(series.mean(), 1)
            })
            
        df_pos_stats_full = pd.DataFrame(pos_stats).sort_values(
            by="raw_hits", ascending=False, kind="mergesort"
        ).reset_index(drop=True)
        
        df_pos_stats = df_pos_stats_full.drop(columns=["raw_hits", "orig_pos_num"])
        
        st.dataframe(
            df_pos_stats,
            column_config={
                "Pozycja": st.column_config.TextColumn("Pozycja", width="small"),
                "Trafienia T+1": st.column_config.TextColumn("Trafienia T+1", width="small"),
                "Ostatnia": st.column_config.NumberColumn("Ostatnia", width="small"),
                "Najczęstsza": st.column_config.TextColumn("Najczęstsza", width="small"),
                "Średnia": st.column_config.NumberColumn("Średnia", format="%.1f", width="small")
            },
            hide_index=True,
            use_container_width=True,
            height=600,
            key=f"pos_stats_tbl_{section_id}"
        )

    # -----------------------------------------------------------------
    # POZIOM 2: DRUGA TABELA (NIEBIESKA 🟦) — ZACHOWYWANIE POZYCJI
    # -----------------------------------------------------------------
    st.divider()
    st.subheader("🟦 2. Tabela Niebieska: Śledzenie pozycji bez przemieszania")
    
    col_opt1, col_opt2 = st.columns([1.8, 1])
    with col_opt1:
        stabilization_mode = st.radio(
            "Wybierz sposób utrzymania pozycji w Tabeli Niebieskiej:",
            options=[
                "Tryb B (Stos liderów): Nowy lider wchodzi na pozycję, poprzedni zostaje pod nim (z etykietą P..)",
                "Tryb A (Stałe kolumny): Pozycje zakotwiczone na starcie zostają w swojej kolumnie do końca"
            ],
            index=0,
            key=f"stab_mode_{section_id}"
        )
    with col_opt2:
        blue_steps = st.radio(
            "Liczba losowań w Tabeli Niebieskiej:",
            options=[15, 20, 25, 30],
            index=0,
            horizontal=True,
            key=f"blue_steps_{section_id}"
        )

    rolling_window = int(selected_window)
    all_sets = df["numbers_set"].tolist()
    all_lists = df["numbers_list"].tolist()
    all_ids = df["draw_id"].tolist()
    all_times = df["draw_time"].tolist()
    total_df_rows = len(df)

    start_idx_blue = max(rolling_window - 1, total_df_rows - 1 - blue_steps)

    # Funkcja pomocnicza wyliczająca ranking 1..20 w dowolnym punkcie t
    def get_ranking_at_step(t_idx):
        if t_idx == total_df_rows - 1:
            return [
                {
                    "orig_pos": int(r_row["orig_pos_num"]),
                    "raw_hits": int(r_row["raw_hits"]),
                    "ball": int(r_row["Ostatnia"])
                }
                for _, r_row in df_pos_stats_full.iterrows()
            ]
        win_start = t_idx - rolling_window + 1
        win_end = t_idx + 1
        win_sets = all_sets[win_start:win_end]
        win_lists = all_lists[win_start:win_end]
        total_trans = len(win_sets) - 1
        nums_t = all_lists[t_idx]
        
        pos_temp = []
        for i in range(1, 21):
            p_idx = i - 1
            repeat_t1_count = sum(1 for k in range(total_trans) if win_lists[k][p_idx] in win_sets[k + 1])
            pos_temp.append({
                "orig_pos": i,
                "raw_hits": repeat_t1_count,
                "ball": nums_t[p_idx]
            })
        df_step = pd.DataFrame(pos_temp).sort_values(by="raw_hits", ascending=False, kind="mergesort").reset_index(drop=True)
        return df_step.to_dict("records")

    # Jeśli wybrano Tryb A: ustalamy kolejność pozycji raz w punkcie startowym (start_idx_blue)
    anchored_order = [item["orig_pos"] for item in get_ranking_at_step(start_idx_blue)]

    rolling_rows_html = []
    col_blue_hits = {r: 0 for r in range(1, 21)}
    orig_pos_blue_hits = {p: 0 for p in range(1, 21)}
    orig_pos_appearances = {p: 0 for p in range(1, 21)}
    latest_col_data = {}
    evaluated_draws_count = 0

    is_mode_b = stabilization_mode.startswith("Tryb B")

    if is_mode_b:
        headers_rolling_html = "".join([
            f"<th style='padding: 6px 2px; text-align: center; color: #4da6ff; font-size: 11px; width: 42px; border-right: 1px solid #2a2e39;'>M.{col_i}</th>" 
            for col_i in range(1, 21)
        ])
    else:
        headers_rolling_html = "".join([
            f"<th title='Zakotwiczona oryginalna Poz. {anchored_order[col_i-1]:02d}' style='padding: 6px 2px; text-align: center; color: #4da6ff; font-size: 11px; width: 38px; border-right: 1px solid #2a2e39;'>"
            f"{col_i}<br><span style='font-size:9px; color:#8a94a6;'>(P{anchored_order[col_i-1]:02d})</span></th>" 
            for col_i in range(1, 21)
        ])

    for t in range(total_df_rows - 1, start_idx_blue - 1, -1):
        is_latest_unverified = (t == total_df_rows - 1)
        next_draw_set = all_sets[t + 1] if not is_latest_unverified else set()
        nums_t = all_lists[t]

        if not is_latest_unverified:
            evaluated_draws_count += 1

        if is_mode_b:
            # TRYB B: W każdym wierszu na pozycję 1..20 wchodzi aktualny lider tego miejsca,
            # a poprzedni lider zostaje w wierszu pod nim (widać jego numer P.. i czy trafił w T+1)
            step_ranking = get_ranking_at_step(t)
        else:
            # TRYB A: Kolumny 1..20 trzymają na stałe pozycje ustalone na starcie testu
            step_ranking = [
                {
                    "orig_pos": orig_p,
                    "raw_hits": 0,
                    "ball": nums_t[orig_p - 1]
                }
                for orig_p in anchored_order
            ]

        row_blue_count = 0
        cells_html = []

        for rank_idx, item in enumerate(step_ranking):
            col_nr = rank_idx + 1
            ball_val = int(item["ball"])
            orig_pos = int(item["orig_pos"])
            pos_tag = f"<span style='font-size:8px; color:#7c8698; display:block; line-height:9px;'>P{orig_pos:02d}</span>" if is_mode_b else ""

            if is_latest_unverified:
                latest_col_data[col_nr] = {"ball": ball_val, "orig_pos": orig_pos}
                cell_content = (
                    f"<div style='display:flex; flex-direction:column; align-items:center;'>"
                    f"<span style='color:#ffd166; font-weight:bold; font-size:11px;'>{ball_val:02d}</span>"
                    f"{pos_tag}</div>"
                )
            else:
                orig_pos_appearances[orig_pos] += 1
                is_hit = (ball_val in next_draw_set)
                if is_hit:
                    col_blue_hits[col_nr] += 1
                    orig_pos_blue_hits[orig_pos] += 1
                    row_blue_count += 1
                    cell_content = (
                        f"<div title='Miejsce {col_nr} | Oryg. Poz. {orig_pos:02d} | Liczba {ball_val:02d} TRAFIONA w #{all_ids[t+1]}' "
                        f"style='display:inline-flex; flex-direction:column; align-items:center; justify-content:center; "
                        f"width:34px; height:28px; border:2px solid #00aaff; border-radius:4px; "
                        f"background-color:rgba(0, 170, 255, 0.35); color:#ffffff; font-weight:bold; "
                        f"font-size:11px; margin:1px; box-sizing:border-box; box-shadow: 0 0 5px rgba(0,170,255,0.6);'>"
                        f"<span style='line-height:11px;'>{ball_val:02d}</span>"
                        f"{pos_tag}</div>"
                    )
                else:
                    cell_content = (
                        f"<div title='Miejsce {col_nr} | Oryg. Poz. {orig_pos:02d}' "
                        f"style='display:flex; flex-direction:column; align-items:center;'>"
                        f"<span style='color:#a8b0c0; font-size:11px;'>{ball_val:02d}</span>"
                        f"{pos_tag}</div>"
                    )

            cells_html.append(f"<td style='padding: 3px 1px; text-align: center; border-right: 1px solid #232731;'>{cell_content}</td>")

        d_id = all_ids[t]
        d_time = all_times[t]

        if is_latest_unverified:
            sum_cell_html = "<td style='padding: 4px 6px; text-align: center; font-weight: bold; font-size: 11px; color: #ffd166; border-left: 2px solid #333945;'>⏳ W grze</td>"
        else:
            badge_color = "#00aaff" if row_blue_count > 0 else "#6c7385"
            badge_bg = "rgba(0, 170, 255, 0.18)" if row_blue_count > 0 else "transparent"
            sum_cell_html = f"<td style='padding: 4px 6px; text-align: center; font-weight: bold; font-size: 12px; color: {badge_color}; background-color: {badge_bg}; border-left: 2px solid #333945;'>{row_blue_count}</td>"

        row_html = f"""
        <tr style='border-bottom: 1px solid #262a34;'>
            <td style='padding: 6px 6px; font-weight: bold; color: #ffffff; white-space: nowrap; font-size: 11px;'>{d_id}</td>
            <td style='padding: 6px 6px; color: #9da3af; white-space: nowrap; font-size: 11px;'>{d_time}</td>
            {''.join(cells_html)}
            {sum_cell_html}
        </tr>
        """
        rolling_rows_html.append(row_html)

    col_roll_tab, col_roll_pos = st.columns([1.6, 0.9], gap="large")
    
    with col_roll_tab:
        if is_mode_b:
            st.markdown(f"#### 📋 2. Tabela Losowań 🟦 — Stos Liderów (ostatnie {blue_steps} losowań)")
            st.caption("Gdy w nowym losowaniu inna pozycja ma najwięcej trafień, wskakuje na górę (np. na `M.1`), a poprzednia **zostaje dokładnie w wierszu pod nią** wraz z podpisem `P..` (np. `P10`, wyżej `P15`) i jest sprawdzana na kolejne losowanie.")
        else:
            st.markdown(f"#### 📋 2. Tabela Losowań 🟦 — Stałe Zakotwiczone Pozycje (ostatnie {blue_steps} losowań)")
            st.caption("Pozycje wyłonione na początku badanego okresu **zostają w swoich kolumnach do samego końca**, bez przeskakiwania między miejscami.")

        rolling_full_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ margin: 0; padding: 0; background-color: #0e1117; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
                .table-container {{ max-height: 600px; overflow-y: auto; overflow-x: auto; border: 1px solid #333945; border-radius: 8px; }}
                table {{ width: 100%; border-collapse: collapse; }}
                thead {{ position: sticky; top: 0; background-color: #161922; z-index: 10; border-bottom: 2px solid #333945; }}
                th {{ padding: 6px 4px; text-align: left; color: #e6e6e6; font-size: 11px; }}
            </style>
        </head>
        <body>
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th style="width: 70px;">Nr</th>
                            <th style="width: 50px;">Czas</th>
                            {headers_rolling_html}
                            <th style="width: 55px; text-align: center; color: #00aaff;">🟦 Suma</th>
                        </tr>
                    </thead>
                    <tbody>
                        {''.join(rolling_rows_html)}
                    </tbody>
                </table>
            </div>
        </body>
        </html>
        """
        components.html(rolling_full_html, height=620, scrolling=False)

    with col_roll_pos:
        st.markdown(f"#### 📊 2. Tabela Pozycji Trafień 🟦 (z {blue_steps} losowań)")
        st.caption("Zestawienie trafień dla poszczególnych miejsc (1–20) z pokazaniem, która pozycja zajmuje dane miejsce teraz oraz ile ma trafień.")
        
        pos_summary_rows = []
        for r in range(1, 21):
            b_hits = col_blue_hits[r]
            eff_pct = (b_hits / evaluated_draws_count * 100.0) if evaluated_draws_count > 0 else 0.0
            curr_info = latest_col_data.get(r, {"ball": 0, "orig_pos": r})
            curr_ball = curr_info["ball"]
            orig_p = curr_info["orig_pos"]
            
            # Ile razy sama oryginalna pozycja (np. Poz. 10) trafiła w całym okresie 15 losowań (nawet gdy spadła niżej)
            orig_total_hits = orig_pos_blue_hits[orig_p]
            
            pos_summary_rows.append({
                "Miejsce": f"Miejsce {r:02d}",
                "raw_blue": b_hits,
                "🟦 Trafienia miejsca": f"{b_hits} ({eff_pct:.1f}%)",
                "Aktualna Poz.": f"Poz. {orig_p:02d}",
                "Trafienia tej Poz.": f"{orig_total_hits}/{evaluated_draws_count}",
                "Teraz w grze": int(curr_ball)
            })
            
        df_roll_pos = pd.DataFrame(pos_summary_rows).sort_values(
            by="raw_blue", ascending=False, kind="mergesort"
        ).drop(columns=["raw_blue"])
        
        st.dataframe(
            df_roll_pos,
            column_config={
                "Miejsce": st.column_config.TextColumn("Miejsce (1-20)", width="small"),
                "🟦 Trafienia miejsca": st.column_config.TextColumn("🟦 Trafienia kolumny", width="small"),
                "Aktualna Poz.": st.column_config.TextColumn("Jaka pozycja teraz", width="small"),
                "Trafienia tej Poz.": st.column_config.TextColumn("Stałe traf. pozycji", width="small"),
                "Teraz w grze": st.column_config.NumberColumn("W grze", width="small"),
            },
            hide_index=True,
            use_container_width=True,
            height=620,
            key=f"roll_pos_tbl_{section_id}"
        )


# =====================================================================
# WYWOŁANIE GŁÓWNEJ SEKCJI (Domyślnie 20 dla Tabeli 1, 15 dla Niebieskiej)
# =====================================================================
render_keno_section(section_id=1, default_top_val=20)









# =====================================================================
# MODUŁ ALGORYTMU PREDYKCYJNEGO V16:
# 1) BLOKADA SŁABYCH POZYCJI Z TABELI 15 (ODWALA KULE 43 NA POZ.08 I 53 NA POZ.14 MAJĄCE 2/14 = 14.3%!)
# 2) DETEKTOR "TRANSFERU SERII 🔴 Z KWADRATU ⬜" (ŁAPIE KULE TYPU 26 PRZECHODZĄCE Z POZ.04 NA POZ.05!)
# 3) RELATYWNY LIDER TABELI 15 (PROMUJE POZ.03 -> KULA 09, GDY MA NAJWIĘCEJ TRAFIEŃ W TABELI 15: 5/14!)
# 4) PEŁNA SPÓJNOŚĆ SKANERA Z KROPKAMI + 3 UNIKALNE ZŁOTE LOKATY
# =====================================================================
from collections import defaultdict

def render_prediction_algorithm(df_full, default_window=8, default_blue_win=8, default_backtest=10):
    st.divider()
    st.header("🧠 Algorytm V16: Transfer Serii 🔴 (Typu Kula 26) + Relatywny Lider Tabeli 15 (Typu Kula 09) + Blokada 14%")

    pred_options = [5, 6, 7, 8, 9, 10, 12, 15]
    blue_options = [5, 6, 7, 8, 9, 10, 12, 15]
    bt_options = [6, 8, 10, 12, 15, 20, 30]

    if "pred_win_v16" not in st.session_state:
        url_val = st.query_params.get("pred_win_v16", str(default_window))
        saved_int = int(url_val) if str(url_val).isdigit() else default_window
        st.session_state.pred_win_v16 = saved_int if saved_int in pred_options else default_window

    if "blue_win_v16" not in st.session_state:
        url_bval = st.query_params.get("blue_win_v16", str(default_blue_win))
        saved_bint = int(url_bval) if str(url_bval).isdigit() else default_blue_win
        st.session_state.blue_win_v16 = saved_bint if saved_bint in blue_options else default_blue_win

    if "bt_steps_v16" not in st.session_state:
        url_bt = st.query_params.get("bt_steps_v16", str(default_backtest))
        saved_bt = int(url_bt) if str(url_bt).isdigit() else default_backtest
        st.session_state.bt_steps_v16 = saved_bt if saved_bt in bt_options else default_backtest

    if "auto_set_w1" in st.session_state and "auto_set_b2" in st.session_state:
        new_w1 = st.session_state.pop("auto_set_w1")
        new_b2 = st.session_state.pop("auto_set_b2")
        st.session_state.pred_win_v16 = new_w1 if new_w1 in pred_options else default_window
        st.session_state.blue_win_v16 = new_b2 if new_b2 in blue_options else default_blue_win
        st.session_state.pred_win_radio_v16 = st.session_state.pred_win_v16
        st.session_state.blue_win_radio_v16 = st.session_state.blue_win_v16
        st.query_params["pred_win_v16"] = str(st.session_state.pred_win_v16)
        st.query_params["blue_win_v16"] = str(st.session_state.blue_win_v16)

    def update_pred_params():
        st.session_state.pred_win_v16 = st.session_state.pred_win_radio_v16
        st.session_state.blue_win_v16 = st.session_state.blue_win_radio_v16
        st.session_state.bt_steps_v16 = st.session_state.bt_steps_radio_v16
        st.query_params["pred_win_v16"] = str(st.session_state.pred_win_radio_v16)
        st.query_params["blue_win_v16"] = str(st.session_state.blue_win_radio_v16)
        st.query_params["bt_steps_v16"] = str(st.session_state.bt_steps_radio_v16)
        # Czyścimy stary komunikat skanera przy ręcznej zmianie kropek, by nie mylił innymi ustawieniami!
        st.session_state.pop("last_scan_msg_v16", None)

    col_cfg1, col_cfg2, col_cfg3 = st.columns([1.05, 1.05, 1.1])
    with col_cfg1:
        window_size = st.radio(
            "⚙️ 1. Okno Pierwszej Tabeli ⬜/🔴 (5–15, domyślnie 8):",
            options=pred_options,
            index=pred_options.index(st.session_state.pred_win_v16),
            horizontal=True,
            key="pred_win_radio_v16",
            on_change=update_pred_params
        )
    with col_cfg2:
        blue_lookback = st.radio(
            "🟦 2. Okno Tabeli Niebieskiej (5–15, domyślnie 8):",
            options=blue_options,
            index=blue_options.index(st.session_state.blue_win_v16),
            horizontal=True,
            key="blue_win_radio_v16",
            on_change=update_pred_params
        )
    with col_cfg3:
        backtest_steps = st.radio(
            "🧪 3. Weryfikacja wsteczna (losowań — domyślnie 10):",
            options=bt_options,
            index=bt_options.index(st.session_state.bt_steps_v16),
            horizontal=True,
            key="bt_steps_radio_v16",
            on_change=update_pred_params
        )

    max_possible_bt = max(6, len(df_full) - max(window_size, 15) - max(blue_lookback, 15) - 5)
    actual_bt_steps = min(backtest_steps, max_possible_bt)

    if len(df_full) < window_size + blue_lookback + 15:
        st.warning(f"Za mało danych w bazie ({len(df_full)}), aby wykonać pełny test.")
        return

    all_lists = df_full["numbers_list"].tolist()
    all_sets = df_full["numbers_set"].tolist()
    all_ids = df_full["draw_id"].tolist()
    all_times = df_full["draw_time"].tolist()
    total_draws = len(df_full)

    # =================================================================
    # SILNIK V16: TRANSFER SERII (KULA 26) + LIDER TABELI 15 (KULA 09) + BLOKADA 14% (KULA 43/53)
    # =================================================================
    def run_engine_v16(w_size, b_lookback, steps_to_test):
        earliest_needed = max(max(w_size, b_lookback, 15) - 1, total_draws - 1 - steps_to_test - max(b_lookback, 15) - 4)
        local_meta = {}
        min_mode_thr = 3 if w_size >= 12 else 2

        for t_i in range(earliest_needed, total_draws):
            w_start = t_i - w_size + 1
            w_lists = all_lists[w_start : t_i + 1]
            w_sets = all_sets[w_start : t_i + 1]
            n_trans = max(1, len(w_lists) - 1)
            curr_l = all_lists[t_i]
            next_s = all_sets[t_i + 1] if (t_i + 1 < total_draws) else set()

            w15_start = max(0, t_i - 14)
            w15_lists = all_lists[w15_start : t_i + 1]
            w15_sets = all_sets[w15_start : t_i + 1]
            n15_trans = max(1, len(w15_lists) - 1)

            pos_modes = {}
            all_modes_set = set()
            white_hits_w = {}
            white_hits_15 = {}

            for i in range(1, 21):
                p_idx = i - 1
                rep_w = sum(1 for k in range(n_trans) if w_lists[k][p_idx] in w_sets[k + 1])
                white_hits_w[i] = rep_w
                white_hits_15[i] = sum(1 for k in range(n15_trans) if w15_lists[k][p_idx] in w15_sets[k + 1])

                col_vals = [w_lists[k][p_idx] for k in range(len(w_lists))]
                s_col = pd.Series(col_vals)
                m_val = int(s_col.mode().iloc[0])
                m_cnt = int((s_col == m_val).sum())
                pos_modes[i] = (m_val, m_cnt)
                if m_cnt >= min_mode_thr:
                    all_modes_set.add(m_val)

            b_start = t_i - b_lookback + 1
            b_lists = all_lists[b_start : t_i + 1]
            b_sets = all_sets[b_start : t_i + 1]
            b_trans = max(1, len(b_lists) - 1)

            pos_temp_blue = []
            for i in range(1, 21):
                p_idx = i - 1
                rep_b = sum(1 for k in range(b_trans) if b_lists[k][p_idx] in b_sets[k + 1])
                pos_temp_blue.append({
                    "orig_pos": i,
                    "raw_hits": rep_b,
                    "ball": curr_l[p_idx]
                })

            df_rank_step = pd.DataFrame(pos_temp_blue).sort_values(
                by="raw_hits", ascending=False, kind="mergesort"
            ).reset_index(drop=True)

            blue_col_for_orig_pos = {}
            blue_hit_by_col = {}
            for rank_idx, r_item in df_rank_step.iterrows():
                m_col = rank_idx + 1
                o_pos = int(r_item["orig_pos"])
                b_val = int(r_item["ball"])
                blue_col_for_orig_pos[o_pos] = (m_col, white_hits_w[o_pos])
                blue_hit_by_col[m_col] = (b_val in next_s) if (t_i + 1 < total_draws) else False

            local_meta[t_i] = {
                "blue_col_map": blue_col_for_orig_pos,
                "blue_hit_by_col": blue_hit_by_col,
                "white_hits_15": white_hits_15,
                "n15_trans": n15_trans,
                "pos_modes": pos_modes,
                "all_modes_set": all_modes_set,
                "min_mode_thr": min_mode_thr
            }

        def score_at_t(t_idx):
            win_start = t_idx - w_size + 1
            win_lists = all_lists[win_start : t_idx + 1]
            win_sets = all_sets[win_start : t_idx + 1]
            trans_count = max(1, len(win_lists) - 1)

            curr_nums = all_lists[t_idx]
            prev_list = all_lists[t_idx - 1] if t_idx >= 1 else []
            prev_set = all_sets[t_idx - 1] if t_idx >= 1 else set()
            prev2_set = all_sets[t_idx - 2] if t_idx >= 2 else set()

            meta_now = local_meta[t_idx]
            blue_col_map_now = meta_now["blue_col_map"]
            white_hits_15_now = meta_now["white_hits_15"]
            n15_trans_now = meta_now["n15_trans"]
            pos_modes_now = meta_now["pos_modes"]
            all_modes_set_now = meta_now["all_modes_set"]
            min_thr = meta_now["min_mode_thr"]

            # Najwyższy wynik w Tabeli 15 w bieżącym kroku (np. w #1523559 wynosił 5/14 = 35.7% na Poz.03!)
            max_w15_in_draw = max(white_hits_15_now.values()) if white_hits_15_now else 5

            blue_col_hits = {m: 0 for m in range(1, 21)}
            blue_col_rec2 = {m: 0 for m in range(1, 21)}
            blue_col_rec3 = {m: 0 for m in range(1, 21)}
            orig_pos_hits_bwin = {p: 0 for p in range(1, 21)}
            orig_pos_rec2 = {p: 0 for p in range(1, 21)}
            orig_pos_rec3 = {p: 0 for p in range(1, 21)}
            blue_steps_avail = 0

            start_b = max(earliest_needed, t_idx - b_lookback)
            for b_t in range(start_b, t_idx):
                blue_steps_avail += 1
                b_hits_map = local_meta[b_t]["blue_hit_by_col"]
                is_r2 = (b_t >= t_idx - 2)
                is_r3 = (b_t >= t_idx - 3)
                for m_c in range(1, 21):
                    if b_hits_map.get(m_c, False):
                        blue_col_hits[m_c] += 1
                        if is_r2:
                            blue_col_rec2[m_c] += 1
                        if is_r3:
                            blue_col_rec3[m_c] += 1

                b_nums = all_lists[b_t]
                b_next_set = all_sets[b_t + 1]
                for p_i in range(20):
                    if b_nums[p_i] in b_next_set:
                        orig_pos_hits_bwin[p_i + 1] += 1
                        if is_r2:
                            orig_pos_rec2[p_i + 1] += 1
                        if is_r3:
                            orig_pos_rec3[p_i + 1] += 1

            prev1_blue_hits = local_meta[t_idx - 1]["blue_hit_by_col"] if (t_idx - 1) in local_meta else {}
            prev2_blue_hits = local_meta[t_idx - 2]["blue_hit_by_col"] if (t_idx - 2) in local_meta else {}

            # Zliczamy wystąpienia i powtórki kul w oknie 15 (by nie gubić powtórek przy krótkim oknie 7!)
            w15_start_idx = max(0, t_idx - 14)
            w15_lists_slice = all_lists[w15_start_idx : t_idx + 1]
            w15_sets_slice = all_sets[w15_start_idx : t_idx + 1]

            win_ball_freq = {b: 0 for b in range(1, 71)}
            win_ball_t1_repeats = {b: 0 for b in range(1, 71)}
            for k_idx, d_list in enumerate(win_lists):
                for b in d_list:
                    win_ball_freq[b] += 1
                    if k_idx < trans_count and b in win_sets[k_idx + 1]:
                        win_ball_t1_repeats[b] += 1

            ball_15_t1_repeats = {b: 0 for b in range(1, 71)}
            for k_idx in range(len(w15_lists_slice) - 1):
                for b in w15_lists_slice[k_idx]:
                    if b in w15_sets_slice[k_idx + 1]:
                        ball_15_t1_repeats[b] += 1

            sq_1_ago = {p: False for p in range(1, 21)}
            sq_2_ago = {p: False for p in range(1, 21)}
            if t_idx >= 1:
                for p_i in range(20):
                    if all_lists[t_idx - 1][p_i] in all_sets[t_idx]:
                        sq_1_ago[p_i + 1] = True
            if t_idx >= 2:
                for p_i in range(20):
                    if all_lists[t_idx - 2][p_i] in all_sets[t_idx - 1]:
                        sq_2_ago[p_i + 1] = True

            min_strong_white_hits = max(2, int(round(trans_count * 0.33)))
            min_hot_t1 = max(2, int(round(w_size * 0.20)))

            candidates = []
            for p_i in range(20):
                pos_nr = p_i + 1
                ball = curr_nums[p_i]

                m_col, pos_white_hits = blue_col_map_now[pos_nr]
                b_hits_cnt = blue_col_hits[m_col]
                b_hit_rate = b_hits_cnt / max(1, blue_steps_avail)
                b_r2 = blue_col_rec2[m_col]
                b_r3 = blue_col_rec3[m_col]

                pos_white_rate = pos_white_hits / trans_count
                w15_hits = white_hits_15_now[pos_nr]
                w15_rate = w15_hits / n15_trans_now

                orig_bwin_cnt = orig_pos_hits_bwin[pos_nr]
                orig_bwin_rate = orig_bwin_cnt / max(1, blue_steps_avail)
                o_r2 = orig_pos_rec2[pos_nr]
                o_r3 = orig_pos_rec3[pos_nr]

                in_prev1 = (ball in prev_set)
                in_prev2 = (ball in prev2_set)
                exact_same_pos_in_t1 = (t_idx >= 1 and prev_list[p_i] == ball)

                # =========================================================================
                # NOWOŚĆ V16 (NAPRAWA DLA KULI 26 NA POZ.05):
                # Jeśli kula ma teraz czerwone kółko 🔴 (in_prev1), sprawdzamy, z jakiej pozycji
                # przyszła z losowania T-1 (source_pos)!
                # W #1523559 kula 26 przyszła z Poz.04 (która miała 3/6 = 50% ⬜ oraz 4/14 w Tab.15!).
                # Dzięki temu kula 26 dziedziczy siłę swojej pozycji źródłowej Poz.04!
                # =========================================================================
                source_pos = None
                source_white_hits = 0
                source_w15_hits = 0
                is_transfer_from_strong_pos = False
                if in_prev1 and prev_list:
                    source_pos = prev_list.index(ball) + 1
                    _, source_white_hits = blue_col_map_now[source_pos]
                    source_w15_hits = white_hits_15_now[source_pos]
                    if source_pos != pos_nr and (source_white_hits >= min_strong_white_hits or source_w15_hits >= max_w15_in_draw - 1):
                        is_transfer_from_strong_pos = True

                # Efektywne trafienia pozycji (uwzględniające transfer serii z pozycji źródłowej!)
                eff_pos_white_hits = max(pos_white_hits, int(round(source_white_hits * 0.80))) if is_transfer_from_strong_pos else pos_white_hits
                eff_pos_white_rate = eff_pos_white_hits / trans_count
                eff_w15_hits = max(w15_hits, source_w15_hits) if is_transfer_from_strong_pos else w15_hits
                eff_w15_rate = eff_w15_hits / n15_trans_now

                sq_d1 = sq_1_ago[pos_nr]
                sq_d2 = sq_2_ago[pos_nr]
                sq_n1 = sq_1_ago.get(pos_nr - 1, False) or sq_1_ago.get(pos_nr + 1, False)

                b_u1 = prev1_blue_hits.get(m_col, False)
                b_u2 = prev2_blue_hits.get(m_col, False)
                b_adj1 = prev1_blue_hits.get(m_col - 1, False) or prev1_blue_hits.get(m_col + 1, False)

                ball_freq_in_win = win_ball_freq[ball]
                ball_t1_in_win = win_ball_t1_repeats[ball]
                ball_t1_15 = ball_15_t1_repeats[ball]

                is_dead_blue_col = (b_hit_rate < 0.25 and b_r2 == 0)
                has_recent_activity = (o_r2 >= 1) or (b_r2 >= 1) or sq_d1 or b_u1 or is_transfer_from_strong_pos

                # =========================================================================
                # NAPRAWA V16 (RELATYWNY LIDER TABELI 15 -> ŁAPIE KULĘ 09 NA POZ.03!):
                # Pozycja jest Liderem Tabeli 15, jeśli ma max_w15_in_draw (np. 5/14 jak Poz.03, Poz.07, Poz.12, Poz.15, Poz.18!)
                # =========================================================================
                is_top_w15_leader = (w15_hits >= max(4, max_w15_in_draw - 1))

                # =========================================================================
                # NAPRAWA V16 (BLOKADA DLA KULI 43 NA POZ.08 I 53 NA POZ.14 MAJĄCYCH 2/14 = 14.3%!):
                # Jeśli pozycja w 15 losowaniach ma <= 2 trafienia (<= 14.3%) i NIE jest transferem gorącej kuli (jak 26),
                # to jest to SŁABA POZYCJA i nie może wejść do TOP 5 dzięki samemu M.15!
                # =========================================================================
                is_very_weak_in_15 = (eff_w15_hits <= 2 and n15_trans_now >= 12)

                has_strong_base = (
                    not is_very_weak_in_15
                    and (
                        (eff_pos_white_hits >= min_strong_white_hits and not is_dead_blue_col)
                        or (is_top_w15_leader and has_recent_activity)
                        or is_transfer_from_strong_pos
                    )
                )

                is_true_series_king = (
                    in_prev1
                    and (sq_d1 or exact_same_pos_in_t1 or is_transfer_from_strong_pos)
                    and has_strong_base
                    and not is_dead_blue_col
                    and ((in_prev2 and sq_d2) or (ball_t1_in_win >= min_hot_t1) or (ball_t1_15 >= 2))
                )

                is_disqualified = False
                verdict_str = "🔥 Lider Pozycji"

                if is_true_series_king:
                    is_disqualified = False
                    verdict_str = f"👑 POTWIERDZONA SERIA (🔴+⬜)"
                elif is_transfer_from_strong_pos and not is_very_weak_in_15:
                    is_disqualified = False
                    verdict_str = f"🔄 Transfer Serii 🔴 z Poz.{source_pos:02d} ({source_white_hits}/{trans_count}⬜)"
                elif is_top_w15_leader and has_recent_activity and not is_dead_blue_col:
                    is_disqualified = False
                    verdict_str = f"🏆 Lider Tabeli 15 ({w15_hits}/{n15_trans_now} ⬜)"
                else:
                    if is_very_weak_in_15:
                        # Bezwzględnie odrzuca Poz.08 (kula 43 -> 2/14) oraz Poz.14 (kula 53 -> 2/14)!
                        is_disqualified = True
                        verdict_str = f"❌ Słaba w Tab.15 ({w15_hits}/{n15_trans_now} ⬜)"
                    elif o_r2 == 0 and b_r2 == 0:
                        is_disqualified = True
                        verdict_str = f"❄️ Wygasła (0 traf. w 2 ost.)"
                    elif is_dead_blue_col and not sq_d1:
                        is_disqualified = True
                        verdict_str = f"❌ Zimna Kolumna 🟦M.{m_col:02d} ({b_hits_cnt}/{blue_steps_avail})"
                    elif not has_strong_base:
                        is_disqualified = True
                        verdict_str = f"❌ Słaba baza Poz.{pos_nr:02d} ({pos_white_hits}/{trans_count}⬜)"
                    elif o_r3 == 0 and b_r3 == 0:
                        is_disqualified = True
                        verdict_str = f"❄️ Martwa od 3 gier"

                # =========================================================================
                # PUNKTACJA V16 (0 - 100 PKT):
                # =========================================================================
                if 0.35 <= eff_pos_white_rate <= 0.64:
                    pts_white_pos = 22.0
                elif eff_pos_white_rate > 0.64:
                    pts_white_pos = 17.5
                else:
                    pts_white_pos = min(17.0, (eff_pos_white_rate / 0.35) * 17.0)

                # Relatywna siła w Tabeli 15 (0 - 12 pkt — daje kuli 09 z Poz.03 aż 12 pkt za 1. miejsce 5/14 w Tab.15!)
                w15_rel_ratio = eff_w15_hits / max(1.0, float(max_w15_in_draw))
                pts_w15_stability = round(min(12.0, w15_rel_ratio * 12.0), 1) if eff_w15_hits >= 3 else 0.0

                effective_blue_hits = max(b_hits_cnt, orig_bwin_cnt)
                pts_blue_col = min(16.0, (b_hit_rate / 0.48) * 16.0) + min(4.0, (orig_bwin_rate / 0.45) * 4.0)

                if sq_d1 and b_u1:
                    pts_now_sq = 13.0
                    path_str = "⬜+🟦 Podwójny kwadrat pod nią!"
                elif is_transfer_from_strong_pos and (b_u1 or sq_n1):
                    pts_now_sq = 12.0
                    path_str = f"🔄🔴 Przeszła z ⬜ Poz.{source_pos:02d}!"
                elif sq_d1:
                    pts_now_sq = 11.0
                    path_str = "⬜ Biały kwadrat pod nią!"
                elif b_u1:
                    pts_now_sq = 10.5
                    path_str = "🟦 Niebieski kwadrat pod nią!"
                elif is_transfer_from_strong_pos:
                    pts_now_sq = 9.5
                    path_str = f"🔄🔴 Przeszła z ⬜ Poz.{source_pos:02d}"
                elif sq_d2 and (sq_n1 or b_adj1):
                    pts_now_sq = 8.0
                    path_str = "⬜ Kwadrat w t-2 i obok w t-1"
                elif o_r2 >= 1 or b_r2 >= 1:
                    pts_now_sq = 5.5
                    path_str = f"Aktywna w t-2 (⬜:{o_r2}x, 🟦:{b_r2}x)"
                else:
                    pts_now_sq = 0.0
                    path_str = "Brak trafień w 2 ost."

                score_pos_and_blue = round(min(64.0, pts_white_pos + pts_w15_stability + pts_blue_col + pts_now_sq), 1)

                # 2. Siła samej kuli (do 22 pkt)
                mode_on_pos, mode_cnt_on_pos = pos_modes_now[pos_nr]
                is_exact_mode = (ball == mode_on_pos and mode_cnt_on_pos >= min_thr)
                pts_mode = 9.0 if (is_exact_mode and not is_disqualified) else (5.0 if (ball in all_modes_set_now and not is_disqualified) else 0.0)
                mode_str = f"🎯 Lider Poz.{pos_nr:02d} (x{mode_cnt_on_pos})" if is_exact_mode else ("⭐ W 'Najczęstszej'" if ball in all_modes_set_now else "-")

                pts_ball_t1 = min(13.0, (ball_t1_in_win * 5.0) + (ball_t1_15 * 2.5))
                score_ball_power = round(min(22.0, pts_mode + pts_ball_t1), 1)

                # 3. Bonus za Serię / Transfer / Lidera 15 (do 14 pkt)
                if is_true_series_king:
                    pts_series = 14.0
                    path_str += " | 👑 Seria"
                elif is_transfer_from_strong_pos:
                    pts_series = 11.0
                    path_str += f" | 🔥 Seria z P{source_pos:02d}"
                elif is_top_w15_leader and (sq_d1 or b_u1):
                    pts_series = 10.0
                    path_str += f" | 🏆 Lider 15 ({w15_hits}/14)"
                elif in_prev1 and (sq_d1 or b_u1):
                    pts_series = 6.0
                    path_str += " | 🔴 z T-1"
                else:
                    pts_series = 0.0

                raw_score = score_pos_and_blue + score_ball_power + pts_series
                final_score = round(max(5.0, raw_score - 55.0 if is_disqualified else raw_score), 1)

                gold_rank_score = (
                    (b_hit_rate * 100.0 * 1.05)
                    + (eff_pos_white_rate * 100.0 * 0.95)
                    + (w15_rel_ratio * 35.0)
                    + (pts_now_sq * 2.0)
                    + (pts_ball_t1 * 1.1)
                )

                w_disp_str = (
                    f"{pos_white_hits}/{trans_count} (z P{source_pos:02d}:{source_white_hits}/{trans_count}) | z 15: {w15_hits}/14"
                    if is_transfer_from_strong_pos
                    else f"{pos_white_hits}/{trans_count} ({pos_white_rate*100:.0f}%) | z 15: {w15_hits}/14"
                )

                candidates.append({
                    "pos_nr": pos_nr,
                    "blue_m": m_col,
                    "pos_white_hits": eff_pos_white_hits,
                    "trans_count": trans_count,
                    "pos_white_pct": round(eff_pos_white_rate * 100.0, 1),
                    "w15_hits": eff_w15_hits,
                    "b_hits_cnt": b_hits_cnt,
                    "orig_bwin_cnt": orig_bwin_cnt,
                    "b_steps": blue_steps_avail,
                    "b_hit_pct": round(b_hit_rate * 100.0, 1),
                    "recent_sum": b_r2 + o_r2 + (2 if (sq_d1 or b_u1 or is_transfer_from_strong_pos) else 0),
                    "gold_rank_score": gold_rank_score,
                    "is_disq": 1 if is_disqualified else 0,
                    "Pozycja": f"Poz. {pos_nr:02d} (🟦 M.{m_col:02d})",
                    "Liczba": ball,
                    "Score": final_score,
                    "Status V16": verdict_str,
                    "⬜ Własne Poz. (i z 15)": w_disp_str,
                    "🟦 Kolumna M (i Stałe)": f"M.{m_col:02d}: {b_hits_cnt}/{blue_steps_avail} | Stałe: {orig_bwin_cnt}/{blue_steps_avail}",
                    "Pod pozycją (Węzeł)": path_str,
                    "Powtórki Kuli T+1": f"{ball_t1_in_win}x (z 15: {ball_t1_15}x)",
                    "⭐ 'Najczęstsza'": mode_str
                })

            df_cand = pd.DataFrame(candidates).sort_values(
                by=["is_disq", "Score", "w15_hits", "pos_white_pct"],
                ascending=[True, False, False, False],
                kind="mergesort"
            ).reset_index(drop=True)

            df_blue_gold = pd.DataFrame(candidates).sort_values(
                by=["is_disq", "gold_rank_score", "Score"],
                ascending=[True, False, False],
                kind="mergesort"
            ).reset_index(drop=True)

            return df_cand, df_blue_gold, win_ball_freq, win_ball_t1_repeats, all_modes_set_now, min_thr

        return score_at_t

    # =====================================================================
    # AUTO-SKANER SZYBKICH OKIEN V16 (5–12) Z PODWÓJNĄ WAGĄ DLA OSTATNICH 5 GIER!
    # =====================================================================
    with st.expander(f"🔍 AUTO-SKANER BIEŻĄCEJ FORMY V16 (Szuka najlepszego szybkiego okna 5–12 na ostatnich {actual_bt_steps} losowaniach!)", expanded=True):
        st.caption(
            f"Skaner bada szybkie okna **[5, 6, 7, 8, 9, 10, 12]** na ostatnich **{actual_bt_steps}** losowaniach, "
            f"nadając **podwójną wagę ostatnim 5 losowaniom**."
        )
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            auto_joint_btn = st.button(
                f"🚀 1. Znajdź najlepsze AKTUALNE okno (5–12) na ostatnich {actual_bt_steps} grach i je zaznacz",
                type="primary",
                use_container_width=True
            )
        with col_btn2:
            auto_blue_btn = st.button(
                f"🟦 2. Znajdź najlepsze okno samej Tabeli Niebieskiej (5–12) na ostatnich {actual_bt_steps} grach",
                use_container_width=True
            )

        if auto_joint_btn or auto_blue_btn:
            scan_windows = [5, 6, 7, 8, 9, 10, 12]
            scan_results = []
            latest_idx_scan = total_draws - 1
            very_recent_limit = min(5, actual_bt_steps)

            progress_bar = st.progress(0, text=f"Sprawdzam bieżącą formę szybkich okien (5–12) na ostatnich {actual_bt_steps} grach...")
            for idx_w, w_test in enumerate(scan_windows):
                w1_val = window_size if auto_blue_btn else w_test
                b2_val = w_test
                label_mode = f"Tab.1={w1_val} | 🟦={b2_val}" if auto_blue_btn else f"Okno = {w_test}"

                scorer_fn = run_engine_v16(w1_val, b2_val, actual_bt_steps)
                g1_hits, g2_hits, g_any_hits = 0, 0, 0
                weighted_gold_pts = 0
                t5_hits_total = 0
                recent5_t5_hits = 0
                recent5_gold_hits = 0
                slot_h = {s: 0 for s in range(1, 6)}

                for step_i, step_t in enumerate(range(latest_idx_scan - 1, latest_idx_scan - 1 - actual_bt_steps, -1)):
                    df_p, df_bg, _, _, _, _ = scorer_fn(step_t)
                    nxt_s = all_sets[step_t + 1]
                    is_very_recent = (step_i < very_recent_limit)
                    weight = 2 if is_very_recent else 1

                    for s_i, (_, r_p) in enumerate(df_p.head(5).iterrows()):
                        if int(r_p["Liczba"]) in nxt_s:
                            t5_hits_total += 1
                            slot_h[s_i + 1] += 1
                            if is_very_recent:
                                recent5_t5_hits += 1

                    b1 = int(df_bg.iloc[0]["Liczba"])
                    b2 = int(df_bg.iloc[1]["Liczba"])
                    h1, h2 = (b1 in nxt_s), (b2 in nxt_s)
                    if h1: g1_hits += 1
                    if h2: g2_hits += 1
                    if h1 or h2:
                        g_any_hits += 1
                        weighted_gold_pts += weight
                        if is_very_recent:
                            recent5_gold_hits += 1

                best_slot_nr = max(range(1, 6), key=lambda s: slot_h[s])
                best_slot_cnt = slot_h[best_slot_nr]
                best_slot_pct = (best_slot_cnt / actual_bt_steps) * 100.0
                g_any_pct = (g_any_hits / actual_bt_steps) * 100.0
                t5_avg_pct = (t5_hits_total / (actual_bt_steps * 5)) * 100.0
                rec5_gold_pct = (recent5_gold_hits / very_recent_limit) * 100.0
                rec5_t5_pct = (recent5_t5_hits / (very_recent_limit * 5)) * 100.0

                df_live_p, df_live_bg, _, _, _, _ = scorer_fn(latest_idx_scan)
                live_slot_ball = int(df_live_p.iloc[best_slot_nr - 1]["Liczba"])
                live_unq_gold = []
                for _, r_lbg in df_live_bg.iterrows():
                    b_cand = int(r_lbg["Liczba"])
                    if b_cand != live_slot_ball and b_cand not in live_unq_gold and len(live_unq_gold) < 2:
                        live_unq_gold.append(b_cand)
                live_g1, live_g2 = live_unq_gold[0], live_unq_gold[1]

                current_form_power = (
                    (rec5_gold_pct * 0.40)
                    + (rec5_t5_pct * 0.30)
                    + (g_any_pct * 0.15)
                    + (best_slot_pct * 0.15)
                )

                scan_results.append({
                    "Ustawienie": f"👉 {label_mode}",
                    "w1_val": w1_val,
                    "b2_val": b2_val,
                    "current_form_power": current_form_power,
                    "weighted_gold_pts": weighted_gold_pts,
                    "rec5_gold_raw": recent5_gold_hits,
                    "g_any_raw": g_any_pct,
                    "slot_raw": best_slot_pct,
                    f"🔥 Ostatnie {very_recent_limit} gier (Teraz!)": f"Złote: {recent5_gold_hits}/{very_recent_limit} ({rec5_gold_pct:.0f}%) | TOP5: {recent5_t5_hits} traf.",
                    f"Złote 🟦 ({actual_bt_steps} gier)": f"{g_any_hits}/{actual_bt_steps} ({g_any_pct:.1f}%)",
                    "Najlepszy Slot TOP 5": f"Typ #{best_slot_nr}: {best_slot_cnt}/{actual_bt_steps} ({best_slot_pct:.0f}%) ➔ Kula {live_slot_ball:02d}",
                    "3 Unikalne Lokaty TERAZ": f"Slot: {live_slot_ball:02d} | 🟦: {live_g1:02d}, {live_g2:02d}",
                    "Średnia TOP 5": f"{t5_avg_pct:.1f}% ({t5_hits_total}/{actual_bt_steps*5})"
                })
                progress_bar.progress((idx_w + 1) / len(scan_windows))

            progress_bar.empty()
            df_scan = pd.DataFrame(scan_results).sort_values(
                by=["current_form_power", "weighted_gold_pts", "rec5_gold_raw", "slot_raw"],
                ascending=[False, False, False, False],
                kind="mergesort"
            ).reset_index(drop=True)

            winner_row = df_scan.iloc[0]
            win_w1 = int(winner_row["w1_val"])
            win_b2 = int(winner_row["b2_val"])

            st.session_state["last_scan_df_v16"] = df_scan.drop(
                columns=["w1_val", "b2_val", "current_form_power", "weighted_gold_pts", "rec5_gold_raw", "g_any_raw", "slot_raw"]
            )
            st.session_state["last_scan_msg_v16"] = (
                f"✅ **SKANER WYBRAŁ NAJBARDZIEJ AKTUALNE SZYBKIE OKNO (NA BAZIE OSTATNICH {actual_bt_steps} GIER):** "
                f"**Okno Tabeli 1 = `{win_w1}` | Okno Tabeli Niebieskiej 🟦 = `{win_b2}`**\n\n"
                f"- **Bieżąca forma (ostatnie {very_recent_limit} gier — waga 2x):** **{winner_row[f'🔥 Ostatnie {very_recent_limit} gier (Teraz!)']}**\n"
                f"- **Wynik w całym teście ({actual_bt_steps} gier):** Złote Lokaty: **{winner_row[f'Złote 🟦 ({actual_bt_steps} gier)']}** | **{winner_row['Najlepszy Slot TOP 5']}**\n"
                f"- **3 Unikalne Złote Lokaty na teraz:** **{winner_row['3 Unikalne Lokaty TERAZ']}**"
            )

            st.session_state["auto_set_w1"] = win_w1
            st.session_state["auto_set_b2"] = win_b2
            st.rerun()

        if "last_scan_msg_v16" in st.session_state:
            st.success(st.session_state["last_scan_msg_v16"])
        if "last_scan_df_v16" in st.session_state:
            st.dataframe(st.session_state["last_scan_df_v16"], hide_index=True, use_container_width=True)

    # =====================================================================
    # GŁÓWNE OBLICZENIE DLA AKTUALNIE ZAZNACZONYCH WARTOŚCI (window_size, blue_lookback)
    # =====================================================================
    latest_idx = total_draws - 1
    active_scorer = run_engine_v16(window_size, blue_lookback, actual_bt_steps)
    df_predictions, df_latest_blue_gold, latest_win_freq, latest_win_t1, latest_modes_set, min_mode_threshold = active_scorer(latest_idx)
    latest_curr_set = all_sets[latest_idx]

    top_5_Row = df_predictions.head(5)
    top_8_Row = df_predictions.head(8)

    bt_html_rows = []
    total_top5_hits = 0
    total_top8_hits = 0
    golden_1_bt_hits = 0
    golden_2_bt_hits = 0
    golden_at_least_one_bt = 0

    top5_slot_hits = {slot: 0 for slot in range(1, 6)}
    keno_pos_in_top5_selected = {p: 0 for p in range(1, 21)}
    keno_pos_in_top5_hits = {p: 0 for p in range(1, 21)}

    for step_t in range(latest_idx - 1, latest_idx - 1 - actual_bt_steps, -1):
        df_step_pred, df_step_bg, _, _, _, _ = active_scorer(step_t)
        next_actual_set = all_sets[step_t + 1]

        top5_df = df_step_pred.head(5)
        top8_df = df_step_pred.head(8)

        top5_nums = top5_df["Liczba"].tolist()
        top8_nums = top8_df["Liczba"].tolist()

        g1_ball = int(df_step_bg.iloc[0]["Liczba"])
        g2_ball = int(df_step_bg.iloc[1]["Liczba"])
        g1_m = int(df_step_bg.iloc[0]["blue_m"])
        g2_m = int(df_step_bg.iloc[1]["blue_m"])
        g1_hit = (g1_ball in next_actual_set)
        g2_hit = (g2_ball in next_actual_set)
        if g1_hit:
            golden_1_bt_hits += 1
        if g2_hit:
            golden_2_bt_hits += 1
        if g1_hit or g2_hit:
            golden_at_least_one_bt += 1

        slot_cells_html = []
        for slot_idx, (_, r_pred) in enumerate(top5_df.iterrows()):
            slot_nr = slot_idx + 1
            b_val = int(r_pred["Liczba"])
            k_pos = int(r_pred["pos_nr"])
            b_m = int(r_pred["blue_m"])

            keno_pos_in_top5_selected[k_pos] += 1
            is_hit_slot = (b_val in next_actual_set)
            if is_hit_slot:
                top5_slot_hits[slot_nr] += 1
                keno_pos_in_top5_hits[k_pos] += 1
                cell_box = (
                    f"<div style='display:inline-flex; flex-direction:column; align-items:center; justify-content:center; "
                    f"width:58px; height:36px; border:2px solid #00e676; border-radius:6px; "
                    f"background-color:rgba(0, 230, 118, 0.28); color:#ffffff; font-weight:bold; box-shadow:0 0 6px rgba(0,230,118,0.5);'>"
                    f"<span style='font-size:14px; line-height:14px;'>{b_val:02d}</span>"
                    f"<span style='font-size:9px; color:#b9f6ca; line-height:10px;'>P{k_pos:02d}|M.{b_m:02d}</span></div>"
                )
            else:
                cell_box = (
                    f"<div style='display:inline-flex; flex-direction:column; align-items:center; justify-content:center; "
                    f"width:58px; height:36px; border:1px solid #2b303c; border-radius:6px; background-color:#151821;'>"
                    f"<span style='font-size:13px; color:#a8b0c0; line-height:14px;'>{b_val:02d}</span>"
                    f"<span style='font-size:9px; color:#6c7385; line-height:10px;'>P{k_pos:02d}|M.{b_m:02d}</span></div>"
                )
            slot_cells_html.append(f"<td style='padding:4px 4px; text-align:center; border-right:1px solid #232731;'>{cell_box}</td>")

        g1_badge = f"<span style='padding:2px 6px; border:1.5px solid #ffd166; border-radius:4px; background:rgba(255,209,102,0.28); color:#fff; font-weight:bold;'>{g1_ball:02d}(M.{g1_m})🟩</span>" if g1_hit else f"<span style='color:#9da3af;'>{g1_ball:02d}(M.{g1_m})</span>"
        g2_badge = f"<span style='padding:2px 6px; border:1.5px solid #00e676; border-radius:4px; background:rgba(0,230,118,0.25); color:#fff; font-weight:bold;'>{g2_ball:02d}(M.{g2_m})🟩</span>" if g2_hit else f"<span style='color:#9da3af;'>{g2_ball:02d}(M.{g2_m})</span>"
        golden_cell_html = f"{g1_badge} &nbsp; {g2_badge}"

        hits_5_cnt = sum(1 for n in top5_nums if n in next_actual_set)
        hits_8_cnt = sum(1 for n in top8_nums if n in next_actual_set)

        total_top5_hits += hits_5_cnt
        total_top8_hits += hits_8_cnt

        h5_color = "#00e676" if hits_5_cnt >= 2 else ("#ffd166" if hits_5_cnt == 1 else "#6c7385")
        h5_bg = "rgba(0, 230, 118, 0.16)" if hits_5_cnt >= 2 else "transparent"

        row_bt_html = f"""
        <tr style='border-bottom: 1px solid #262a34;'>
            <td style='padding: 6px 8px; color: #9da3af; white-space: nowrap; font-size: 11px;'>#{all_ids[step_t]}<br><span style='font-size:10px; color:#6c7385;'>({all_times[step_t]})</span></td>
            <td style='padding: 6px 8px; font-weight: bold; color: #ffffff; white-space: nowrap; font-size: 11px; border-right:2px solid #333945;'>#{all_ids[step_t + 1]}</td>
            <td style='padding: 6px 8px; text-align: center; white-space: nowrap; font-size: 11px; border-right:2px solid #333945;'>{golden_cell_html}</td>
            {''.join(slot_cells_html)}
            <td style='padding: 6px 8px; text-align: center; font-weight: bold; font-size: 13px; color: {h5_color}; background-color: {h5_bg}; border-left:2px solid #333945;'>{hits_5_cnt} / 5</td>
            <td style='padding: 6px 8px; text-align: center; font-weight: bold; font-size: 13px; color: #4da6ff;'>{hits_8_cnt} / 8</td>
        </tr>
        """
        bt_html_rows.append(row_bt_html)

    sorted_slots = sorted(range(1, 6), key=lambda s: top5_slot_hits[s], reverse=True)
    best_slot_1, best_slot_2 = sorted_slots[0], sorted_slots[1]
    best_slot_row_now = top_5_Row.iloc[best_slot_1 - 1]
    best_slot_1_pct = (top5_slot_hits[best_slot_1] / actual_bt_steps) * 100.0

    slot_ball_val = int(best_slot_row_now["Liczba"])
    unique_gold_leaders = []
    seen_gold_balls = {slot_ball_val}
    for _, r_bg in df_latest_blue_gold.iterrows():
        b_c = int(r_bg["Liczba"])
        if b_c not in seen_gold_balls and len(unique_gold_leaders) < 2:
            unique_gold_leaders.append(r_bg)
            seen_gold_balls.add(b_c)

    raw_gold_1 = unique_gold_leaders[0]
    raw_gold_2 = unique_gold_leaders[1]
    g1_bt_pct_raw = (golden_1_bt_hits / actual_bt_steps) * 100.0
    g2_bt_pct_raw = (golden_2_bt_hits / actual_bt_steps) * 100.0

    if golden_2_bt_hits > golden_1_bt_hits:
        golden_row_1, golden_row_2 = raw_gold_2, raw_gold_1
        gold_1_label, gold_2_label = f"Lider #2 (Skut. {g2_bt_pct_raw:.0f}%)", f"Lider #1 (Skut. {g1_bt_pct_raw:.0f}%)"
    else:
        golden_row_1, golden_row_2 = raw_gold_1, raw_gold_2
        gold_1_label, gold_2_label = f"Lider #1 (Skut. {g1_bt_pct_raw:.0f}%)", f"Lider #2 (Skut. {g2_bt_pct_raw:.0f}%)"

    curr_in_modes = [b for b in all_lists[latest_idx] if b in latest_modes_set]
    curr_modes_str = ", ".join(f"{b:02d}" for b in curr_in_modes) if curr_in_modes else "brak"
    top8_balls_only = ", ".join(f"{int(r['Liczba']):02d}" for _, r in top_8_Row.iterrows())

    gold_balls_set = {int(golden_row_1["Liczba"]), int(golden_row_2["Liczba"]), slot_ball_val}
    top5_badges_html = ""
    for idx_r, (_, r) in enumerate(top_5_Row.iterrows()):
        s_nr = idx_r + 1
        b_num = int(r["Liczba"])
        p_num = int(r["pos_nr"])
        m_num = int(r["blue_m"])
        w_cnt = int(r["pos_white_hits"])
        t_cnt = int(r["trans_count"])
        b_cnt = int(r["b_hits_cnt"])
        b_st = int(r["b_steps"])
        is_gold = b_num in gold_balls_set
        border_col = "#ffd166" if is_gold else "#00e676"
        bg_col = "rgba(255, 209, 102, 0.18)" if is_gold else "rgba(0, 230, 118, 0.14)"
        top5_badges_html += (
            f"<div style='display:inline-flex; align-items:center; gap:8px; padding:6px 12px; margin:4px 6px 4px 0; "
            f"border:2px solid {border_col}; border-radius:8px; background:{bg_col};'>"
            f"<span style='font-size:13px; color:#d0d7de; font-weight:600;'>#{s_nr}:</span>"
            f"<span style='font-size:22px; font-weight:900; color:#ffffff; letter-spacing:0.5px;'>{b_num:02d}</span>"
            f"<span style='font-size:13px; font-weight:bold; color:#ffd166;'>(Poz.{p_num:02d}: {w_cnt}/{t_cnt}⬜ | 🟦M.{m_num:02d}: {b_cnt}/{b_st})</span>"
            f"</div>"
        )

    green_hero_html = (
        f"<div style='background: linear-gradient(135deg, rgba(16, 54, 39, 0.95) 0%, rgba(13, 38, 29, 0.95) 100%); "
        f"border: 2px solid #00e676; border-radius: 12px; padding: 16px 20px; margin-bottom: 18px; "
        f"box-shadow: 0 4px 15px rgba(0, 230, 118, 0.18); font-family: sans-serif;'>"
        f"<div style='font-size: 14px; font-weight: bold; color: #b9f6ca; margin-bottom: 12px; text-transform: uppercase; letter-spacing: 0.5px;'>"
        f"🎯 Wskazanie Algorytmu V16 (Okno Tab.1 ⬜: {window_size} | Okno Tab.🟦: {blue_lookback} | Badana Historia: ostatnie {actual_bt_steps} gier) po #{all_ids[latest_idx]} ({all_times[latest_idx]})"
        f"</div>"
        f"<div style='margin-bottom: 14px;'>"
        f"<div style='font-size: 13px; color: #ffd166; font-weight: bold; margin-bottom: 8px;'>"
        f"🏆 3 UNIKALNE ZŁOTE LOKATY V16 (Z detektorem Transferu Serii 🔴 i blokadą słabych pozycji 14%):"
        f"</div>"
        f"<div style='display: flex; flex-wrap: wrap; gap: 12px; align-items: center;'>"
        f"<div style='display: inline-flex; align-items: center; gap: 10px; background: rgba(0, 0, 0, 0.55); "
        f"border: 2.5px solid #ff9f1c; border-radius: 10px; padding: 8px 16px; box-shadow: 0 0 12px rgba(255, 159, 28, 0.4);'>"
        f"<span style='font-size: 15px; color: #ff9f1c; font-weight: bold;'>🎯 Najlepszy Slot (#{best_slot_1} — {best_slot_1_pct:.0f}%) ➔ Kula</span>"
        f"<span style='font-size: 28px; font-weight: 900; color: #ffffff; background: #ff9f1c; padding: 2px 12px; border-radius: 8px; border: 2px solid #ffffff;'>"
        f"{slot_ball_val:02d}</span>"
        f"<span style='font-size: 15px; font-weight: 800; color: #ffd166;'>"
        f"Poz.{int(best_slot_row_now['pos_nr']):02d} ({int(best_slot_row_now['pos_white_hits'])}/{int(best_slot_row_now['trans_count'])}⬜ | 🟦M.{int(best_slot_row_now['blue_m']):02d}: {int(best_slot_row_now['b_hits_cnt'])}/{int(best_slot_row_now['b_steps'])})</span>"
        f"</div>"
        f"<div style='display: inline-flex; align-items: center; gap: 10px; background: rgba(0, 0, 0, 0.45); "
        f"border: 2.5px solid #ffd166; border-radius: 10px; padding: 8px 16px; box-shadow: 0 0 10px rgba(255, 209, 102, 0.35);'>"
        f"<span style='font-size: 15px; color: #ffd166; font-weight: bold;'>{gold_1_label} ➔ Kula</span>"
        f"<span style='font-size: 28px; font-weight: 900; color: #ffffff; background: #e63946; padding: 2px 12px; border-radius: 8px; border: 2px solid #ffffff;'>"
        f"{int(golden_row_1['Liczba']):02d}</span>"
        f"<span style='font-size: 15px; font-weight: 800; color: #4da6ff;'>"
        f"Poz.{int(golden_row_1['pos_nr']):02d} ({int(golden_row_1['pos_white_hits'])}/{int(golden_row_1['trans_count'])}⬜) | "
        f"<span style='color:#00e676;'>🟦M.{int(golden_row_1['blue_m']):02d}: {int(golden_row_1['b_hits_cnt'])}/{int(golden_row_1['b_steps'])}</span></span>"
        f"</div>"
        f"<div style='display: inline-flex; align-items: center; gap: 10px; background: rgba(0, 0, 0, 0.45); "
        f"border: 2.5px solid #00e676; border-radius: 10px; padding: 8px 16px; box-shadow: 0 0 10px rgba(0, 230, 118, 0.3);'>"
        f"<span style='font-size: 15px; color: #00e676; font-weight: bold;'>{gold_2_label} ➔ Kula</span>"
        f"<span style='font-size: 28px; font-weight: 900; color: #ffffff; background: #0077b6; padding: 2px 12px; border-radius: 8px; border: 2px solid #ffffff;'>"
        f"{int(golden_row_2['Liczba']):02d}</span>"
        f"<span style='font-size: 15px; font-weight: 800; color: #4da6ff;'>"
        f"Poz.{int(golden_row_2['pos_nr']):02d} ({int(golden_row_2['pos_white_hits'])}/{int(golden_row_2['trans_count'])}⬜) | "
        f"<span style='color:#00e676;'>🟦M.{int(golden_row_2['blue_m']):02d}: {int(golden_row_2['b_hits_cnt'])}/{int(golden_row_2['b_steps'])}</span></span>"
        f"</div>"
        f"</div>"
        f"</div>"
        f"<div style='margin-bottom: 10px;'>"
        f"<div style='font-size: 13px; color: #e6e6e6; font-weight: bold; margin-bottom: 6px;'>🔥 Pełne TOP 5 Aktywnych Liczb wg łącznej siły Score (#1 – #5):</div>"
        f"<div>{top5_badges_html}</div>"
        f"</div>"
        f"<div style='display: flex; flex-wrap: wrap; gap: 20px; font-size: 14px; color: #e6e6e6; padding-top: 8px; border-top: 1px solid rgba(255,255,255,0.15);'>"
        f"<div>⭐ <b>W kolumnie 'Najczęstsza' (Tabela 1):</b> <span style='font-size:18px; font-weight:900; color:#ffd166;'>{curr_modes_str}</span></div>"
        f"<div>📌 <b>Koszyk TOP 8:</b> <span style='font-size:18px; font-weight:900; color:#00e676;'>{top8_balls_only}</span></div>"
        f"</div>"
        f"</div>"
    )
    st.markdown(green_hero_html, unsafe_allow_html=True)

    col_pred_table, col_hot_all = st.columns([1.45, 0.95], gap="large")

    with col_pred_table:
        st.subheader(f"📊 1. Ranking 20 liczb z #{all_ids[latest_idx]} (V16: Tab.1={window_size} | Tab.🟦={blue_lookback})")
        df_display_pred = df_predictions.drop(
            columns=["pos_nr", "blue_m", "pos_white_hits", "trans_count", "pos_white_pct", "w15_hits", "b_hits_cnt", "orig_bwin_cnt", "b_steps", "b_hit_pct", "recent_sum", "gold_rank_score", "is_disq"]
        ).copy()
        st.dataframe(
            df_display_pred,
            column_config={
                "Pozycja": st.column_config.TextColumn("Poz. (🟦 Miejsce)", width="medium"),
                "Liczba": st.column_config.NumberColumn("Kula", width="small"),
                "Score": st.column_config.ProgressColumn("Siła (Score)", format="%.1f pkt", min_value=0, max_value=100),
                "Status V16": st.column_config.TextColumn("Status Weryfikacji", width="medium"),
                "⬜ Własne Poz. (i z 15)": st.column_config.TextColumn(f"⬜ Własne ({window_size} i 15)", width="medium"),
                "🟦 Kolumna M (i Stałe)": st.column_config.TextColumn(f"🟦 Kolumna M ({blue_lookback})", width="medium"),
                "Pod pozycją (Węzeł)": st.column_config.TextColumn("Pod pozycją", width="medium"),
                "Powtórki Kuli T+1": st.column_config.TextColumn("Powt. Kuli", width="small"),
                "⭐ 'Najczęstsza'": st.column_config.TextColumn("⭐ 'Najczęstsza'", width="small"),
            },
            hide_index=True,
            use_container_width=True,
            height=560,
            key="pred_main_ranking_tbl"
        )

    with col_hot_all:
        st.subheader(f"🔥 2. Najczęściej losowane kule w oknie {window_size}")
        hot70_rows = []
        for b_num in range(1, 71):
            f_cnt = latest_win_freq[b_num]
            if f_cnt == 0:
                continue
            in_last = (b_num in latest_curr_set)
            in_modes = (b_num in latest_modes_set)
            pos_in_last = (all_lists[latest_idx].index(b_num) + 1) if in_last else None
            hot70_rows.append({
                "Kula": b_num,
                "f_raw": f_cnt,
                "t1_raw": latest_win_t1[b_num],
                "in_last_raw": 1 if in_last else 0,
                f"W oknie ({window_size})": f"{f_cnt}x ({f_cnt/window_size*100:.0f}%)",
                "Powtórki T+1": f"{latest_win_t1[b_num]}x" if latest_win_t1[b_num] > 0 else "❌ 0x",
                "W kol. 'Najczęstsza'?": "⭐ TAK" if in_modes else "-",
                "Teraz w grze?": f"✅ TAK (Poz. {pos_in_last:02d})" if in_last else "⏳ Przerwa"
            })
        df_hot70 = pd.DataFrame(hot70_rows).sort_values(
            by=["t1_raw", "f_raw", "in_last_raw"], ascending=[False, False, False], kind="mergesort"
        ).head(25).drop(columns=["f_raw", "t1_raw", "in_last_raw"])

        st.dataframe(
            df_hot70,
            hide_index=True,
            use_container_width=True,
            height=560,
            key="hot_70_check_tbl"
        )

    st.divider()
    st.subheader(f"🧪 3. Bieżąca weryfikacja wsteczna (Ostatnie {actual_bt_steps} losowań — Okno Tab.1: {window_size} | Okno Tab.🟦: {blue_lookback})")

    avg_top5 = (total_top5_hits / (actual_bt_steps * 5)) * 100
    avg_top8 = (total_top8_hits / (actual_bt_steps * 8)) * 100
    g_any_pct = (golden_at_least_one_bt / actual_bt_steps) * 100
    best_s1_pct = (top5_slot_hits[best_slot_1] / actual_bt_steps) * 100
    best_s2_pct = (top5_slot_hits[best_slot_2] / actual_bt_steps) * 100

    st.info(
        f"📈 **Bieżąca skuteczność z ostatnich {actual_bt_steps} losowań (Okno Tab.1={window_size}, Okno Tab.🟦={blue_lookback}):**\n"
        f"- **Najlepsze sloty w TOP 5 TERAZ:** **Typ #{best_slot_1}** trafia **{top5_slot_hits[best_slot_1]}/{actual_bt_steps} ({best_s1_pct:.1f}%)**, "
        f"a **Typ #{best_slot_2}** trafia **{top5_slot_hits[best_slot_2]}/{actual_bt_steps} ({best_s2_pct:.1f}%)**\n"
        f"- **Złote Lokaty 🟦/⬜ (Lider #1 i #2):** Lider #1 trafił **{golden_1_bt_hits}/{actual_bt_steps} ({g1_bt_pct_raw:.1f}%)**, "
        f"Lider #2 trafił **{golden_2_bt_hits}/{actual_bt_steps} ({g2_bt_pct_raw:.1f}%)** — w **{golden_at_least_one_bt}/{actual_bt_steps} ({g_any_pct:.1f}%)** gier wchodzi min. 1 Złota Lokata!\n"
        f"- **Całe TOP 5 liczb:** **{total_top5_hits}/{actual_bt_steps*5} ({avg_top5:.1f}%)** | **Całe TOP 8:** **{total_top8_hits}/{actual_bt_steps*8} ({avg_top8:.1f}%)**"
    )

    st.markdown(f"#### 🏆 A. Które miejsce wewnątrz 'Typowanie TOP 5' (Typ #1 – #5) trafia najczęściej w ostatnich {actual_bt_steps} grach?")
    slot_summary_rows = []
    for s_nr in range(1, 6):
        s_hits = top5_slot_hits[s_nr]
        s_pct = (s_hits / actual_bt_steps) * 100.0
        curr_row_s = top_5_Row.iloc[s_nr - 1]
        is_best = (s_nr in [best_slot_1, best_slot_2])
        slot_summary_rows.append({
            "Lokata w TOP 5": f"⭐ Typ #{s_nr} z TOP 5" if is_best else f"Typ #{s_nr} z TOP 5",
            "raw_hits": s_hits,
            "Trafienia": f"{s_hits} / {actual_bt_steps}",
            "Skuteczność %": round(s_pct, 1),
            "Aktualna Kula (Teraz w grze)": int(curr_row_s["Liczba"]),
            "Własne ⬜ i Niebieska 🟦": f"Poz.{int(curr_row_s['pos_nr']):02d} ({int(curr_row_s['pos_white_hits'])}/{int(curr_row_s['trans_count'])}⬜ | 🟦M.{int(curr_row_s['blue_m']):02d}: {int(curr_row_s['b_hits_cnt'])}/{int(curr_row_s['b_steps'])})",
            "Status Weryfikacji": curr_row_s["Status V16"]
        })

    df_slot_sum = pd.DataFrame(slot_summary_rows).sort_values(
        by="raw_hits", ascending=False, kind="mergesort"
    ).drop(columns=["raw_hits"])

    st.dataframe(df_slot_sum, hide_index=True, use_container_width=True, key="top5_slots_summary_tbl")

    st.markdown(f"#### 📊 B. Skuteczność oryginalnych Pozycji Keno (Poz. 01 – Poz. 20), gdy wejdą do TOP 5 (ostatnie {actual_bt_steps} gier)")
    kpos_summary_rows = []
    for p_nr in range(1, 21):
        sel_cnt = keno_pos_in_top5_selected[p_nr]
        hit_cnt = keno_pos_in_top5_hits[p_nr]
        hit_pct = (hit_cnt / sel_cnt * 100.0) if sel_cnt > 0 else 0.0
        curr_ball_at_p = all_lists[latest_idx][p_nr - 1]
        in_curr_top5 = p_nr in top_5_Row["pos_nr"].tolist()

        kpos_summary_rows.append({
            "Pozycja Keno": f"Poz. {p_nr:02d}",
            "raw_hits": hit_cnt,
            "raw_pct": hit_pct,
            "Wybrana do TOP 5": f"{sel_cnt}x",
            "Trafienia": f"{hit_cnt} / {sel_cnt}",
            "Skuteczność %": round(hit_pct, 1),
            "Aktualna Kula na tej Poz.": int(curr_ball_at_p),
            "Czy teraz w TOP 5?": "🔥 TAK (W TOP 5)" if in_curr_top5 else "Poza TOP 5"
        })

    df_kpos_sum = pd.DataFrame(kpos_summary_rows).sort_values(
        by=["raw_hits", "raw_pct"], ascending=[False, False], kind="mergesort"
    ).drop(columns=["raw_hits", "raw_pct"])

    st.dataframe(
        df_kpos_sum,
        column_config={
            "Pozycja Keno": st.column_config.TextColumn("Pozycja (1-20)", width="small"),
            "Wybrana do TOP 5": st.column_config.TextColumn("Weszła do TOP 5", width="small"),
            "Trafienia": st.column_config.TextColumn("Trafienia", width="small"),
            "Skuteczność %": st.column_config.ProgressColumn("Skuteczność %", format="%.1f%%", min_value=0, max_value=70),
            "Aktualna Kula na tej Poz.": st.column_config.NumberColumn("Kula Teraz", width="small"),
            "Czy teraz w TOP 5?": st.column_config.TextColumn("Status Teraz", width="medium"),
        },
        hide_index=True,
        use_container_width=True,
        height=380,
        key="top5_kenopos_summary_tbl"
    )

    st.markdown(f"#### 📋 C. Szczegółowa historia ostatnich {actual_bt_steps} losowań (2 Złote Lokaty 🟦 + 5 kolumn TOP 5 — 🟩 = Trafienie w T+1)")
    bt_matrix_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ margin: 0; padding: 0; background-color: #0e1117; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
            .table-container {{ max-height: 620px; overflow-y: auto; overflow-x: auto; border: 1px solid #333945; border-radius: 8px; }}
            table {{ width: 100%; border-collapse: collapse; }}
            thead {{ position: sticky; top: 0; background-color: #161922; z-index: 10; border-bottom: 2px solid #333945; }}
            th {{ padding: 8px 6px; text-align: center; color: #e6e6e6; font-size: 11px; white-space: nowrap; }}
        </style>
    </head>
    <body>
        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th style="text-align:left;">Z losowania</th>
                        <th style="text-align:left; border-right:2px solid #333945;">Do (T+1)</th>
                        <th style="border-right:2px solid #333945; color:#00aaff;">🏆 2 Złote Lokaty 🟦<br><span style="font-size:9px; color:#8a94a6;">(Lider #1: {golden_1_bt_hits}/{actual_bt_steps} | #2: {golden_2_bt_hits}/{actual_bt_steps})</span></th>
                        <th style="color:#ffd166;">Typ #1<br><span style="font-size:9px; color:#8a94a6;">({top5_slot_hits[1]}/{actual_bt_steps})</span></th>
                        <th style="color:#ffd166;">Typ #2<br><span style="font-size:9px; color:#8a94a6;">({top5_slot_hits[2]}/{actual_bt_steps})</span></th>
                        <th style="color:#ffd166;">Typ #3<br><span style="font-size:9px; color:#8a94a6;">({top5_slot_hits[3]}/{actual_bt_steps})</span></th>
                        <th style="color:#ffd166;">Typ #4<br><span style="font-size:9px; color:#8a94a6;">({top5_slot_hits[4]}/{actual_bt_steps})</span></th>
                        <th style="color:#ffd166;">Typ #5<br><span style="font-size:9px; color:#8a94a6;">({top5_slot_hits[5]}/{actual_bt_steps})</span></th>
                        <th style="border-left:2px solid #333945; color:#00e676;">Traf. TOP 5</th>
                        <th style="color:#4da6ff;">Traf. TOP 8</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(bt_html_rows)}
                </tbody>
            </table>
        </div>
    </body>
    </html>
    """
    components.html(bt_matrix_html, height=640, scrolling=False)

# Wywołanie modułu V16:
render_prediction_algorithm(df, default_window=8, default_blue_win=8, default_backtest=10)
