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
# MODUŁ ALGORYTMU PREDYKCYJNEGO V24:
# 1) PRIORYTET ŻYWEGO KWADRATU ⬜/🟦 W T-1 (+22-26 PKT) — PROMUJE 32, 18, 46 NAD ZIMNE 63 I 42!
# 2) BLOKADA DOMINUJĄCEGO LIDERA (🔒#1): GDY TYP #1 MA >=80 PKT (LUB +10 PKT PRZEWAGI) I KWADRAT W T-1,
#    NIE MOŻE ZOSTAĆ POMINIĘTY PRZEZ PARĘ SLOTÓW (DZIĘKI TEMU 32 Z 93 PKT ZAWSZE GRA W PARZE GŁÓWNEJ!)
# 3) BRAK KARY DLA ŚWIEŻYCH KUL NA AKTYWNYCH POZYCJACH (46) + OCHRONA GORĄCYCH POWTÓREK >=3x (11)
# 4) ZACHOWANA W 100% IDENTYCZNA, CZYTELNA GRAFIKA Z WERSJI V23
# =====================================================================
from collections import defaultdict
from itertools import combinations
from datetime import datetime, timedelta

def render_prediction_algorithm(df_full, default_window=8, default_blue_win=8, default_backtest=10):
    st.divider()

    all_windows = [5, 6, 7, 8, 9, 10, 12, 15]
    matrix_bt_steps = 30
    recent_rank_steps = 10

    if len(df_full) < 40 + matrix_bt_steps:
        st.warning(f"Za mało danych w bazie ({len(df_full)}), aby wykonać pełną analizę 30 losowań.")
        return

    all_lists = df_full["numbers_list"].tolist()
    all_sets = df_full["numbers_set"].tolist()
    all_ids = df_full["draw_id"].tolist()
    all_times = df_full["draw_time"].tolist()
    total_draws = len(df_full)
    latest_idx = total_draws - 1

    last_draw_id = int(all_ids[latest_idx])
    target_draw_id = last_draw_id + 1
    last_time_str = str(all_times[latest_idx]).strip()
    try:
        t_obj = datetime.strptime(last_time_str[-5:], "%H:%M")
        target_time_str = (t_obj + timedelta(minutes=4)).strftime("%H:%M")
    except Exception:
        target_time_str = "T+1 (za 4 min)"

    st.header(f"🧠 Algorytm V24 — Super-Selektor na Losowanie #{target_draw_id} (godz. {target_time_str})")

    # =================================================================
    # SILNIK V24: PRIORYTET ŻYWEGO KWADRATU ⬜/🟦 W T-1 + OCHRONA POZ.13 (46) I KULI 11
    # =================================================================
    def run_engine_v24(w_size, b_lookback, steps_to_test):
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

            ball_15_freq = {b: 0 for b in range(1, 71)}
            ball_15_t1_repeats = {b: 0 for b in range(1, 71)}
            for k_idx, d15_l in enumerate(w15_lists_slice):
                for b in d15_l:
                    ball_15_freq[b] += 1
                    if k_idx < len(w15_lists_slice) - 1 and b in w15_sets_slice[k_idx + 1]:
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

            min_strong_white_hits = max(2, int(round(trans_count * 0.30)))

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

                orig_bwin_cnt = orig_pos_hits_bwin[pos_nr]
                orig_bwin_rate = orig_bwin_cnt / max(1, blue_steps_avail)
                o_r2 = orig_pos_rec2[pos_nr]
                o_r3 = orig_pos_rec3[pos_nr]

                in_prev1 = (ball in prev_set)
                exact_same_pos_in_t1 = (t_idx >= 1 and prev_list[p_i] == ball)

                sq_d1 = sq_1_ago[pos_nr]
                sq_d2 = sq_2_ago[pos_nr]
                sq_n1 = sq_1_ago.get(pos_nr - 1, False) or sq_1_ago.get(pos_nr + 1, False)

                b_u1 = prev1_blue_hits.get(m_col, False)
                b_adj1 = prev1_blue_hits.get(m_col - 1, False) or prev1_blue_hits.get(m_col + 1, False)

                ball_freq_in_win = win_ball_freq[ball]
                ball_freq_rate = ball_freq_in_win / max(1, w_size)
                ball_t1_in_win = win_ball_t1_repeats[ball]
                ball_t1_15 = ball_15_t1_repeats[ball]
                ball_f_15 = ball_15_freq[ball]

                # Transfer serii tylko z bliskiej pozycji (+/- 1) i TYLKO gdy kolumna docelowa nie jest uśpiona,
                # oraz kula ma powtórki T+1 (koniec z faworyzowaniem 42 na martwej Poz.12 nad 46 na Poz.13!)
                source_pos = None
                source_white_hits = 0
                is_transfer_from_strong_pos = False
                if in_prev1 and prev_list:
                    source_pos = prev_list.index(ball) + 1
                    _, source_white_hits = blue_col_map_now[source_pos]
                    if (
                        source_pos != pos_nr
                        and abs(source_pos - pos_nr) <= 1
                        and (o_r2 >= 1 or b_r2 >= 1)
                        and (ball_t1_in_win >= 2 or ball_t1_15 >= 2)
                        and source_white_hits >= min_strong_white_hits
                    ):
                        is_transfer_from_strong_pos = True

                has_direct_t1_square = (sq_d1 or b_u1)
                is_top_w15_leader = (w15_hits >= max(4, max_w15_in_draw - 1))
                is_sweet_spot_ball = (0.33 <= ball_freq_rate <= 0.58 and (ball_t1_in_win >= 2 or ball_t1_15 >= 2))
                # Ochrona dla gorących powtarzalnych kul jak 11 (3x powtórki T+1!)
                is_hot_repeater = (ball_t1_in_win >= 3 or (ball_t1_in_win >= 2 and ball in all_modes_set_now))
                is_overheated_ball = (ball_freq_rate > 0.65 and ball_t1_in_win <= 1 and not (in_prev1 and sq_d1))

                # =========================================================================
                # PUNKTACJA V24 (0 - 100 PKT):
                # 1) ŻYWY KWADRAT W T-1 (⬜/🟦 — główny motor trafień 32, 18, 46!) — do 26 pkt
                # 2) Siła Pozycji (okno bieżące + Tabela 15) — do 30 pkt
                # 3) Siła Tabeli Niebieskiej 🟦 + Strefa M.01-M.06 — do 22 pkt
                # 4) Siła i powtarzalność kuli (ochrona 11 i Złotej Fali) — do 22 pkt
                # =========================================================================
                if sq_d1 and b_u1:
                    pts_node = 26.0
                    path_str = "⬜+🟦 Podwójny kwadrat w T-1!"
                elif sq_d1:
                    pts_node = 22.0
                    path_str = "⬜ Biały kwadrat pod nią w T-1!"
                elif b_u1:
                    pts_node = 19.0
                    path_str = "🟦 Niebieski kwadrat pod nią w T-1!"
                elif is_transfer_from_strong_pos:
                    pts_node = 10.0
                    path_str = f"🔄🔴 Transfer z Poz.{source_pos:02d}"
                elif sq_d2 and (o_r2 >= 1 or b_r2 >= 1):
                    pts_node = 7.5
                    path_str = f"Aktywna w t-2 (⬜:{o_r2}x, 🟦:{b_r2}x)"
                elif o_r2 >= 1 or b_r2 >= 1:
                    pts_node = 6.0
                    path_str = f"Aktywna w 2 ost. (⬜:{o_r2}x, 🟦:{b_r2}x)"
                elif sq_n1 or b_adj1:
                    pts_node = 3.5
                    path_str = "Kwadrat tuż obok"
                else:
                    pts_node = 0.0
                    path_str = "Brak kwadratu w 2 ost."

                if 0.33 <= pos_white_rate <= 0.62:
                    pts_white_pos = 16.0
                elif pos_white_rate > 0.62:
                    pts_white_pos = 14.0
                else:
                    pts_white_pos = round(min(13.0, (pos_white_rate / 0.33) * 13.0), 1)

                w15_rel_ratio = w15_hits / max(1.0, float(max_w15_in_draw))
                pts_w15_stability = round(min(14.0, w15_rel_ratio * 14.0), 1) if w15_hits >= 3 else round(w15_rel_ratio * 7.0, 1)

                pts_blue_rate = round(min(14.5, (b_hit_rate / 0.50) * 14.5), 1)
                pts_blue_rank_zone = 4.5 if (m_col <= 6 and (b_hit_rate >= 0.25 or sq_d1)) else (2.0 if (m_col <= 10 and b_hit_rate >= 0.30) else 0.0)
                pts_orig_bwin = round(min(3.0, (orig_bwin_rate / 0.45) * 3.0), 1)
                score_blue = min(22.0, pts_blue_rate + pts_blue_rank_zone + pts_orig_bwin)

                mode_on_pos, mode_cnt_on_pos = pos_modes_now[pos_nr]
                is_exact_mode = (ball == mode_on_pos and mode_cnt_on_pos >= min_thr)
                pts_mode = 5.5 if is_exact_mode else (3.0 if ball in all_modes_set_now else 0.0)
                mode_str = f"🎯 Lider Poz.{pos_nr:02d} (x{mode_cnt_on_pos})" if is_exact_mode else ("⭐ W 'Najczęstszej'" if ball in all_modes_set_now else "-")

                ball_bonus = 6.0 if is_hot_repeater else (4.5 if is_sweet_spot_ball else (-4.0 if is_overheated_ball else 0.0))
                pts_ball_t1 = min(16.5, max(0.0, (ball_t1_in_win * 3.8) + (ball_t1_15 * 2.0) + ball_bonus))
                score_ball = round(min(22.0, pts_mode + pts_ball_t1), 1)

                # Bonus za potwierdzoną serię na własnej pozycji z kwadratem w T-1 (np. 32!)
                series_bonus = 0.0
                if in_prev1 and (sq_d1 or exact_same_pos_in_t1) and (ball_t1_in_win >= 2 or ball_t1_15 >= 2):
                    series_bonus = 5.0
                    path_str += " | 👑 Seria"
                elif in_prev1 and has_direct_t1_square:
                    series_bonus = 2.5
                    path_str += " | 🔴 z T-1"

                # Miękkie kary dla zimnych kolumn bez kwadratu w T-1 (np. 63 na zimnym M.12 i 42 na uśpionej Poz.12!)
                soft_penalty = 0.0
                if not has_direct_t1_square:
                    if not is_hot_repeater:
                        soft_penalty += 6.0  # Chłodzenie pozycji bez żywego kwadratu w T-1
                    if o_r3 == 0 and b_r3 == 0:
                        soft_penalty += 12.0
                    elif o_r2 == 0 and b_r2 == 0 and not is_top_w15_leader:
                        soft_penalty += 8.0
                    if b_hit_rate < 0.28 and b_r2 == 0:
                        soft_penalty += 6.0
                    # Kara za brak powtórek kuli TYLKO gdy NIE MA kwadratu pod pozycją (chroni świeżą 46 na Poz.13!)
                    if ball_t1_in_win == 0 and ball_t1_15 == 0:
                        soft_penalty += 4.5

                if w15_hits <= 1 and n15_trans_now >= 12 and not has_direct_t1_square:
                    soft_penalty += 12.0

                raw_score = pts_node + pts_white_pos + pts_w15_stability + score_blue + score_ball + series_bonus - soft_penalty
                final_score = round(min(99.0, max(5.0, raw_score)), 1)

                if in_prev1 and (sq_d1 or exact_same_pos_in_t1) and (ball_t1_in_win >= 2 or ball_t1_15 >= 2):
                    verdict_str = "👑 POTWIERDZONA SERIA (🔴+⬜)"
                elif sq_d1 and b_u1:
                    verdict_str = "💎 PODWÓJNY KWADRAT (⬜+🟦)"
                elif sq_d1:
                    verdict_str = f"⬜ Żywy Kwadrat Poz.{pos_nr:02d} ({w15_hits}/14)"
                elif b_u1:
                    verdict_str = f"🟦 Żywy Kwadrat M.{m_col:02d} ({b_hits_cnt}/{blue_steps_avail})"
                elif is_hot_repeater:
                    verdict_str = f"🔥 Gorąca Kula ({ball_t1_in_win}x powt.)"
                elif is_top_w15_leader:
                    verdict_str = f"🏆 Lider Tabeli 15 ({w15_hits}/{n15_trans_now} ⬜)"
                elif soft_penalty >= 14.0:
                    verdict_str = f"❄️ Chłodna Poz.{pos_nr:02d} (brak ⬜ w T-1)"
                else:
                    verdict_str = "⏳ Aktywna w t-2"

                w_disp_str = f"{pos_white_hits}/{trans_count} ({pos_white_rate*100:.0f}%) | z 15: {w15_hits}/14"

                candidates.append({
                    "pos_nr": pos_nr,
                    "blue_m": m_col,
                    "pos_white_hits": pos_white_hits,
                    "trans_count": trans_count,
                    "pos_white_pct": round(pos_white_rate * 100.0, 1),
                    "w15_hits": w15_hits,
                    "b_hits_cnt": b_hits_cnt,
                    "orig_bwin_cnt": orig_bwin_cnt,
                    "b_steps": blue_steps_avail,
                    "b_hit_pct": round(b_hit_rate * 100.0, 1),
                    "has_t1_sq": 1 if has_direct_t1_square else 0,
                    "ball_t1_total": ball_t1_in_win + ball_t1_15,
                    "Pozycja": f"Poz. {pos_nr:02d} (🟦 M.{m_col:02d})",
                    "Liczba": ball,
                    "Score": final_score,
                    "Status V24": verdict_str,
                    "⬜ Własne Poz. (i z 15)": w_disp_str,
                    "🟦 Kolumna M (i Stałe)": f"M.{m_col:02d}: {b_hits_cnt}/{blue_steps_avail} | Stałe: {orig_bwin_cnt}/{blue_steps_avail}",
                    "Pod pozycją (Węzeł)": path_str,
                    "Powtórki Kuli T+1": f"{ball_t1_in_win}x (z 15: {ball_t1_15}x na {ball_f_15})",
                    "⭐ 'Najczęstsza'": mode_str
                })

            df_cand = pd.DataFrame(candidates).sort_values(
                by=["Score", "has_t1_sq", "w15_hits", "b_hit_pct"],
                ascending=[False, False, False, False],
                kind="mergesort"
            ).reset_index(drop=True)

            df_cand.insert(0, "Rank", [f"#{i+1}" for i in range(len(df_cand))])
            return df_cand, win_ball_freq, win_ball_t1_repeats, all_modes_set_now, min_thr

        return score_at_t

    # =====================================================================
    # FUNKCJA BLOKADY DOMINUJĄCEGO LIDERA (🔒#1) — IDENTYCZNA W BACKTEŚCIE I NA ŻYWO!
    # Jeśli Typ #1 ma >=80 pkt (lub +10 pkt przewagi nad #2) i żywy kwadrat w T-1,
    # to ZAWSZE wchodzi do 2 Głównych Liczb (koniec z pomijaniem kuli 32 mającej 93 pkt!)
    # =====================================================================
    def resolve_pair_with_leader_lock(top5_df, base_s1, base_s2):
        r0 = top5_df.iloc[0]
        r1 = top5_df.iloc[1]
        s0 = float(r0["Score"])
        s1_val = float(r1["Score"])
        is_dominant_leader = (int(r0["has_t1_sq"]) == 1) and (s0 >= 80.0 or (s0 - s1_val) >= 10.0)
        if is_dominant_leader and 0 not in (base_s1, base_s2):
            return 0, base_s1, True
        return base_s1, base_s2, False

    # =====================================================================
    # SKANER OKIEN (5–15) Z OCHRONĄ ANTY-OVERFITTING (55% STABILNOŚĆ 30g + 45% FORMA 10g)
    # =====================================================================
    all_pair_combos = list(combinations(range(5), 2))
    win_scorers = {}
    win_live_top5 = {}
    win_summary_data = {}
    consensus_ball_windows = defaultdict(list)
    consensus_ball_scores = defaultdict(float)

    for w_val in all_windows:
        sc_fn = run_engine_v24(w_val, w_val, matrix_bt_steps)
        win_scorers[w_val] = sc_fn
        df_cand_now, _, _, _, _ = sc_fn(latest_idx)
        live_t5_df = df_cand_now.head(5)
        live_t5 = [live_t5_df.iloc[idx] for idx in range(5)]
        win_live_top5[w_val] = live_t5

        for idx_5, r_row in enumerate(live_t5):
            b_num = int(r_row["Liczba"])
            consensus_ball_windows[b_num].append(w_val)
            consensus_ball_scores[b_num] += float(r_row["Score"]) * (1.25 if idx_5 < 3 else 0.95)

        slot_hits_10 = {s: 0 for s in range(5)}
        slot_hits_30 = {s: 0 for s in range(5)}
        pair_stats = {
            c: {"both_10": 0, "any_10": 0, "rec4_any": 0, "both_30": 0, "any_30": 0}
            for c in all_pair_combos
        }
        top5_2plus_10 = 0
        top5_2plus_30 = 0

        for step_i, step_t in enumerate(range(latest_idx - 1, latest_idx - 1 - matrix_bt_steps, -1)):
            df_cand_step, _, _, _, _ = sc_fn(step_t)
            step_t5_df = df_cand_step.head(5)
            nxt_s = all_sets[step_t + 1]
            h_flags = [int(step_t5_df.iloc[idx]["Liczba"]) in nxt_s for idx in range(5)]
            h_cnt = sum(1 for f in h_flags if f)

            if h_cnt >= 2:
                top5_2plus_30 += 1
            for s_i in range(5):
                if h_flags[s_i]:
                    slot_hits_30[s_i] += 1
                    if step_i < recent_rank_steps:
                        slot_hits_10[s_i] += 1

            if step_i < recent_rank_steps and h_cnt >= 2:
                top5_2plus_10 += 1

            for ic, jc in all_pair_combos:
                eff_i, eff_j, _ = resolve_pair_with_leader_lock(step_t5_df, ic, jc)
                c_hits = (1 if h_flags[eff_i] else 0) + (1 if h_flags[eff_j] else 0)
                if c_hits == 2:
                    pair_stats[(ic, jc)]["both_30"] += 1
                if c_hits >= 1:
                    pair_stats[(ic, jc)]["any_30"] += 1
                if step_i < recent_rank_steps:
                    if c_hits == 2:
                        pair_stats[(ic, jc)]["both_10"] += 1
                    if c_hits >= 1:
                        pair_stats[(ic, jc)]["any_10"] += 1
                    if step_i < 4 and c_hits >= 1:
                        pair_stats[(ic, jc)]["rec4_any"] += 1

        def pair_quality_key(c):
            ps = pair_stats[c]
            rate_any_30 = ps["any_30"] / matrix_bt_steps
            rate_both_30 = ps["both_30"] / matrix_bt_steps
            rate_any_10 = ps["any_10"] / recent_rank_steps
            rate_both_10 = ps["both_10"] / recent_rank_steps
            rate_rec4 = ps["rec4_any"] / 4.0
            slot_sum_30 = (slot_hits_30[c[0]] + slot_hits_30[c[1]]) / (2.0 * matrix_bt_steps)

            stability_30 = (rate_any_30 * 50.0) + (rate_both_30 * 65.0) + (slot_sum_30 * 30.0)
            momentum_10 = (rate_any_10 * 40.0) + (rate_both_10 * 50.0) + (rate_rec4 * 25.0)
            return (stability_30 * 0.55) + (momentum_10 * 0.45)

        best_pair_c = max(all_pair_combos, key=pair_quality_key)
        c1, c2 = best_pair_c
        if (slot_hits_30[c2] + slot_hits_10[c2] * 2) > (slot_hits_30[c1] + slot_hits_10[c1] * 2):
            base_s1, base_s2 = c2, c1
        else:
            base_s1, base_s2 = c1, c2

        # Zastosowanie Blokady Dominującego Lidera na aktualnym losowaniu
        act_s1, act_s2, leader_locked_now = resolve_pair_with_leader_lock(live_t5_df, base_s1, base_s2)

        rem_slots = [s for s in range(5) if s not in (act_s1, act_s2)]
        best_s3 = max(rem_slots, key=lambda s: (slot_hits_30[s] * 0.6 + slot_hits_10[s] * 1.4, float(live_t5[s]["Score"])))

        bp_score = pair_quality_key(best_pair_c)
        win_power_score = bp_score + ((top5_2plus_30 / matrix_bt_steps) * 20.0) + ((top5_2plus_10 / recent_rank_steps) * 15.0)

        win_summary_data[w_val] = {
            "w_val": w_val,
            "power": win_power_score,
            "base_s1": base_s1,
            "base_s2": base_s2,
            "best_s1": act_s1,
            "best_s2": act_s2,
            "best_s3": best_s3,
            "leader_locked": leader_locked_now,
            "s1_hits10": slot_hits_10[act_s1],
            "s2_hits10": slot_hits_10[act_s2],
            "s3_hits10": slot_hits_10[best_s3],
            "s1_hits30": slot_hits_30[act_s1],
            "s2_hits30": slot_hits_30[act_s2],
            "s3_hits30": slot_hits_30[best_s3],
            "pair_any_10": pair_stats[best_pair_c]["any_10"],
            "pair_both_10": pair_stats[best_pair_c]["both_10"],
            "pair_any_30": pair_stats[best_pair_c]["any_30"],
            "pair_both_30": pair_stats[best_pair_c]["both_30"],
            "top5_2plus_10": top5_2plus_10,
            "top5_2plus_30": top5_2plus_30,
            "b1": int(live_t5[act_s1]["Liczba"]),
            "b2": int(live_t5[act_s2]["Liczba"]),
            "b3": int(live_t5[best_s3]["Liczba"]),
            "b1_score": float(live_t5[act_s1]["Score"]),
            "b2_score": float(live_t5[act_s2]["Score"]),
            "b3_score": float(live_t5[best_s3]["Score"]),
            "slot_hits_10": slot_hits_10,
            "slot_hits_30": slot_hits_30
        }

    for w_val in all_windows:
        wi = win_summary_data[w_val]
        c_b1 = len(consensus_ball_windows[wi["b1"]])
        c_b2 = len(consensus_ball_windows[wi["b2"]])
        wi["c_b1"] = c_b1
        wi["c_b2"] = c_b2
        wi["c_b3"] = len(consensus_ball_windows[wi["b3"]])
        wi["power"] += (c_b1 + c_b2) * 1.25

    ranked_windows = sorted(all_windows, key=lambda w: win_summary_data[w]["power"], reverse=True)
    first_place_win = ranked_windows[0]
    second_place_win = ranked_windows[1]

    w1_info = win_summary_data[first_place_win]
    w2_info = win_summary_data[second_place_win]

    # =====================================================================
    # WYZNACZENIE 2 GŁÓWNYCH LICZB ORAZ DECYZJA O 3. LICZBIE DODATKOWEJ
    # =====================================================================
    main_ball_1 = w1_info["b1"]
    main_ball_2 = w1_info["b2"]
    cand_ball_3 = w1_info["b3"]

    c3_win_count = w1_info["c_b3"]
    c3_slot_pct30 = (w1_info["s3_hits30"] / matrix_bt_steps) * 100.0
    c3_score = w1_info["b3_score"]
    c3_has_sq = int(win_live_top5[first_place_win][w1_info["best_s3"]]["has_t1_sq"]) == 1

    is_3rd_ball_strong = (
        (c3_has_sq and c3_score >= 65.0 and c3_win_count >= 3)
        or (w1_info["s3_hits30"] >= 10 and w1_info["s3_hits10"] >= 4 and c3_win_count >= 3)
        or (w1_info["s3_hits30"] >= 13 and c3_score >= 62.0)
    )

    if is_3rd_ball_strong:
        third_ball_html = (
            f"<div style='display: inline-flex; align-items: center; gap: 10px; background: rgba(0, 230, 118, 0.18); "
            f"border: 2.5px solid #00e676; border-radius: 10px; padding: 10px 16px; box-shadow: 0 0 12px rgba(0, 230, 118, 0.35);'>"
            f"<div>"
            f"<div style='font-size: 13px; color: #00e676; font-weight: 900;'>➕ 3. LICZBA DODATKOWA (BARDZO DUŻE SZANSE — GRAJ TRÓJKĘ!):</div>"
            f"<div style='font-size: 11px; color: #b9f6ca;'>Kolumna <b>Typ #{w1_info['best_s3']+1}</b> (30g: {w1_info['s3_hits30']}/30 = {c3_slot_pct30:.0f}% | 10g: {w1_info['s3_hits10']}/10) | W {c3_win_count}/8 oknach | Siła: {c3_score:.1f} pkt</div>"
            f"</div>"
            f"<span style='font-size: 30px; font-weight: 900; color: #ffffff; background: #0077b6; padding: 3px 14px; border-radius: 8px; border: 2px solid #00e676;'>{cand_ball_3:02d}</span>"
            f"</div>"
        )
    else:
        third_ball_html = (
            f"<div style='display: inline-flex; align-items: center; gap: 10px; background: rgba(255, 255, 255, 0.06); "
            f"border: 1.5px dashed #8a94a6; border-radius: 10px; padding: 10px 16px;'>"
            f"<div>"
            f"<div style='font-size: 13px; color: #ffd166; font-weight: 800;'>⚠️ 3. LICZBA REZERWOWA (UMIARKOWANE SZANSE — LEPIEJ GRAJ TYLKO 2 GŁÓWNE!):</div>"
            f"<div style='font-size: 11px; color: #9da3af;'>Kolumna <b>Typ #{w1_info['best_s3']+1}</b> (30g: {w1_info['s3_hits30']}/30 = {c3_slot_pct30:.0f}% | 10g: {w1_info['s3_hits10']}/10 | w {c3_win_count}/8 oknach) — ostrożnie:</div>"
            f"</div>"
            f"<span style='font-size: 24px; font-weight: 800; color: #d0d7de; background: #2b3548; padding: 2px 11px; border-radius: 7px; border: 1px solid #8a94a6;'>{cand_ball_3:02d}</span>"
            f"</div>"
        )

    sorted_consensus = sorted(
        consensus_ball_windows.items(),
        key=lambda x: (len(x[1]), consensus_ball_scores[x[0]]),
        reverse=True
    )
    consensus_str_list = [f"<b>{b:02d}</b> ({len(w_l)}/8 okn.)" for b, w_l in sorted_consensus[:5]]
    consensus_html = " &nbsp;|&nbsp; ".join(consensus_str_list)

    # =====================================================================
    # GŁÓWNY PANEL DECYZYJNY V24 (IDENTYCZNA GRAFIKA JAK W V23)
    # =====================================================================
    p30_pct = (w1_info["pair_any_30"] / matrix_bt_steps) * 100.0
    lock_tag_txt = " 🔒(Blokada Dominującego #1!)" if w1_info["leader_locked"] else ""
    hero_v24_html = (
        f"<div style='background: linear-gradient(135deg, rgba(14, 48, 35, 0.98) 0%, rgba(9, 28, 21, 0.99) 100%); "
        f"border: 3px solid #ffd166; border-radius: 14px; padding: 16px 20px; margin-bottom: 18px; "
        f"box-shadow: 0 6px 20px rgba(255, 209, 102, 0.25); font-family: sans-serif;'>"
        f"<div style='display:flex; flex-wrap:wrap; justify-content:space-between; align-items:center; background:rgba(0,0,0,0.55); "
        f"border:2px solid #00e676; border-radius:9px; padding:10px 16px; margin-bottom:14px;'>"
        f"<div style='font-size:16px; font-weight:900; color:#00e676;'>"
        f"🎯 TERAZ OBSTAWIASZ NA LOSOWANIE: <span style='color:#ffffff; background:#e63946; padding:3px 10px; border-radius:6px; font-size:18px;'>#{target_draw_id} (godz. {target_time_str})</span>"
        f"</div>"
        f"<div style='font-size:13px; color:#ffd166; font-weight:bold;'>"
        f"🏆 Wybrano (30g+10g): <b>OKNO {first_place_win}</b> — kolumny <b>Typ #{w1_info['best_s1']+1} + Typ #{w1_info['best_s2']+1}</b>{lock_tag_txt} "
        f"(30g: <b>{w1_info['pair_any_30']}/30 = {p30_pct:.0f}%</b>, pełne 2z2: <b>{w1_info['pair_both_30']}x</b> | 10g: <b>{w1_info['pair_any_10']}/10</b>)"
        f"</div>"
        f"</div>"
        f"<div style='display: flex; flex-wrap: wrap; gap: 16px; align-items: center; margin-bottom: 14px;'>"
        f"<div style='display: inline-flex; align-items: center; gap: 12px; background: rgba(0, 0, 0, 0.65); "
        f"border: 3px solid #ffd166; border-radius: 12px; padding: 10px 18px; box-shadow: 0 0 16px rgba(255, 209, 102, 0.45);'>"
        f"<div>"
        f"<div style='font-size: 14px; color: #ffd166; font-weight: 900;'>👑 2 GŁÓWNE LICZBY DO GRY NA #{target_draw_id}:</div>"
        f"<div style='font-size: 11px; color: #e6e6e6;'>"
        f"1. <b>Typ #{w1_info['best_s1']+1}</b> (Siła: {w1_info['b1_score']:.0f} | 30g: {w1_info['s1_hits30']}/30 | w {w1_info['c_b1']}/8 okn.) &nbsp;|&nbsp; "
        f"2. <b>Typ #{w1_info['best_s2']+1}</b> (Siła: {w1_info['b2_score']:.0f} | 30g: {w1_info['s2_hits30']}/30 | w {w1_info['c_b2']}/8 okn.)"
        f"</div>"
        f"</div>"
        f"<span style='font-size: 32px; font-weight: 900; color: #ffffff; background: #e63946; padding: 3px 15px; border-radius: 9px; border: 2.5px solid #ffd166;'>{main_ball_1:02d}</span>"
        f"<span style='font-size: 32px; font-weight: 900; color: #ffffff; background: #e63946; padding: 3px 15px; border-radius: 9px; border: 2.5px solid #ffd166;'>{main_ball_2:02d}</span>"
        f"</div>"
        f"{third_ball_html}"
        f"</div>"
        f"<div style='display: flex; flex-wrap: wrap; justify-content: space-between; gap: 12px; font-size: 13px; color: #e6e6e6; padding-top: 10px; border-top: 1px solid rgba(255,255,255,0.18);'>"
        f"<div>🥈 <b>2. Miejsce (Okno {second_place_win} — 30g: {w2_info['pair_any_30']}/30, 2z2: {w2_info['pair_both_30']}x | 10g: {w2_info['pair_any_10']}/10):</b> "
        f"Para: <b style='color:#00e676; font-size:16px;'>{w2_info['b1']:02d}, {w2_info['b2']:02d}</b> (+3. liczba: <b>{w2_info['b3']:02d}</b>)</div>"
        f"<div>🔥 <b>Zgodność wszystkich okien (5–15):</b> <span style='color:#ffd166;'>{consensus_html}</span></div>"
        f"</div>"
        f"</div>"
    )
    st.markdown(hero_v24_html, unsafe_allow_html=True)

    # =====================================================================
    # TABELA 1: ZESTAWIENIE OKIEN ANALIZY (5–15)
    # =====================================================================
    st.subheader(f"📊 1. Zestawienie Okien Analizy (5–15) — Stabilność 30 gier + Forma 10 gier na #{target_draw_id}")

    win_rows_html = []
    for rank_i, w_val in enumerate(ranked_windows):
        wi = win_summary_data[w_val]
        t5_w = win_live_top5[w_val]
        is_1st = (rank_i == 0)
        is_2nd = (rank_i == 1)

        if is_1st:
            tr_style = "background: rgba(255, 209, 102, 0.16); border-left: 4px solid #ffd166; border-bottom: 2px solid #ffd166;"
            rank_badge = "<span style='background:#ffd166; color:#000; font-weight:900; padding:3px 8px; border-radius:6px; font-size:12px;'>🥇 1. MIEJSCE (GRAJ TO!)</span>"
        elif is_2nd:
            tr_style = "background: rgba(0, 230, 118, 0.12); border-left: 4px solid #00e676; border-bottom: 1.5px solid #00e676;"
            rank_badge = "<span style='background:#00e676; color:#000; font-weight:900; padding:3px 8px; border-radius:6px; font-size:12px;'>🥈 2. MIEJSCE</span>"
        else:
            tr_style = "background: #141720; border-bottom: 1px solid #262a34;"
            rank_badge = f"<span style='color:#8a94a6; font-size:12px;'>#{rank_i+1} miejsce</span>"

        t5_str_pills = []
        for s_idx, r_t5 in enumerate(t5_w):
            b_v = int(r_t5["Liczba"])
            s_h30 = wi["slot_hits_30"][s_idx]
            is_sel_pair = s_idx in (wi["best_s1"], wi["best_s2"])
            if is_sel_pair:
                t5_str_pills.append(
                    f"<span style='display:inline-block; padding:3px 8px; margin:2px; border:2px solid #ffd166; border-radius:6px; "
                    f"background:#e63946; color:#fff; font-weight:900; font-size:13px;'>Typ #{s_idx+1}: {b_v:02d} <span style='font-size:10px; color:#ffd166;'>({s_h30}/30)</span></span>"
                )
            else:
                t5_str_pills.append(
                    f"<span style='display:inline-block; padding:3px 7px; margin:2px; border:1px solid #333945; border-radius:6px; "
                    f"background:#1c202b; color:#b0b8c8; font-size:12px;'>Typ #{s_idx+1}: <b>{b_v:02d}</b> <span style='font-size:10px; color:#6c7385;'>({s_h30}/30)</span></span>"
                )

        p30_w_pct = (wi["pair_any_30"] / matrix_bt_steps) * 100.0
        lock_ico = " 🔒" if wi["leader_locked"] else ""
        win_rows_html.append(f"""
        <tr style='{tr_style}'>
            <td style='padding: 8px 10px; white-space: nowrap;'>{rank_badge}<br><b style='font-size:15px; color:#fff;'>OKNO {w_val} LOSOWAŃ</b></td>
            <td style='padding: 8px 10px; text-align: center; white-space: nowrap;'>
                <span style='font-size:14px; font-weight:900; color:#00e676;'>30g: {wi['pair_any_30']}/30 ({p30_w_pct:.0f}%) | 2z2: {wi['pair_both_30']}x</span><br>
                <span style='font-size:11px; color:#ffd166;'>Ost. 10g: {wi['pair_any_10']}/10 ({wi['pair_any_10']*10}%) | 2z2: {wi['pair_both_10']}x</span>
            </td>
            <td style='padding: 8px 10px; text-align: center; white-space: nowrap;'>
                <b style='color:#ffd166; font-size:13px;'>Typ #{wi['best_s1']+1} ({wi['s1_hits30']}/30) + Typ #{wi['best_s2']+1} ({wi['s2_hits30']}/30){lock_ico}</b><br>
                <span style='font-size:11px; color:#9da3af;'>+3. kolumna: Typ #{wi['best_s3']+1} ({wi['s3_hits30']}/30)</span>
            </td>
            <td style='padding: 8px 10px; text-align: center; white-space: nowrap;'>
                <span style='font-size:20px; font-weight:900; color:#fff; background:#e63946; padding:3px 10px; border-radius:7px; border:2px solid #ffd166; margin-right:4px;'>{wi['b1']:02d}</span>
                <span style='font-size:20px; font-weight:900; color:#fff; background:#e63946; padding:3px 10px; border-radius:7px; border:2px solid #ffd166; margin-right:8px;'>{wi['b2']:02d}</span>
                <span style='font-size:16px; font-weight:800; color:#00e676; background:#1c2536; padding:3px 8px; border-radius:6px; border:1.5px solid #00e676;'>+{wi['b3']:02d}</span>
            </td>
            <td style='padding: 8px 10px; white-space: nowrap;'>{''.join(t5_str_pills)}</td>
        </tr>
        """)

    clean_windows_table_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ margin: 0; padding: 0; background-color: #0e1117; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
            .tbl-wrap {{ overflow-x: auto; border: 1.5px solid #333945; border-radius: 10px; }}
            table {{ width: 100%; border-collapse: collapse; }}
            th {{ background-color: #161922; color: #ffd166; padding: 10px 8px; font-size: 12px; text-align: center; border-bottom: 2px solid #333945; white-space: nowrap; }}
        </style>
    </head>
    <body>
        <div class="tbl-wrap">
            <table>
                <thead>
                    <tr>
                        <th style="text-align:left;">OKNO ANALIZY</th>
                        <th>SKUTECZNOŚĆ PARY (30 GIER vs 10 GIER)</th>
                        <th>KTÓRE KOLUMNY WYBRAŁ ALGORYTM?</th>
                        <th>🎯 2 GŁÓWNE LICZBY (+3. DODATKOWA)</th>
                        <th style="text-align:left;">WSZYSTKIE 5 KOLUMN NA #{target_draw_id} (Złote = Wybrane do Pary)</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(win_rows_html)}
                </tbody>
            </table>
        </div>
    </body>
    </html>
    """
    components.html(clean_windows_table_html, height=480, scrolling=True)

    # =====================================================================
    # TABELA NR 2 — IDENTYCZNY CZYTELNY UKŁAD + AUTO-SYNC DO ZWYCIĘSKIEGO OKNA
    # =====================================================================
    st.divider()
    col_s1, col_s2 = st.columns([1.3, 0.9])
    with col_s1:
        auto_opt_label = "⭐ Auto (Zwycięskie)"
        win_radio_opts = [auto_opt_label] + all_windows
        selected_win_opt = st.radio(
            f"⚙️ Okno dla Tabeli nr 2 (⭐ Auto = aktualnie Okno {first_place_win}):",
            options=win_radio_opts,
            index=0,
            horizontal=True,
            key="v24_detail_win_radio"
        )
        detail_win = first_place_win if selected_win_opt == auto_opt_label else int(selected_win_opt)
    with col_s2:
        detail_bt = st.radio(
            "🧪 Liczba wierszy historii w Tabeli nr 2:",
            options=[10, 15, 20, 30],
            index=2,
            horizontal=True,
            key="v24_detail_bt_radio"
        )

    active_scorer = win_scorers[detail_win]
    df_predictions, latest_win_freq, latest_win_t1, latest_modes_set, _ = active_scorer(latest_idx)
    latest_curr_set = all_sets[latest_idx]
    det_info = win_summary_data[detail_win]
    base_s1, base_s2 = det_info["base_s1"], det_info["base_s2"]
    sel_s1, sel_s2, sel_s3 = det_info["best_s1"], det_info["best_s2"], det_info["best_s3"]

    top_5_Row = df_predictions.head(5)

    bt_html_rows = []
    top5_slot_hits = {slot: 0 for slot in range(1, 6)}

    # PIERWSZY WIERSZ: NAJNOWSZE LOSOWANIE W GRZE
    live_g1_ball = int(top_5_Row.iloc[sel_s1]["Liczba"])
    live_g2_ball = int(top_5_Row.iloc[sel_s2]["Liczba"])
    live_g3_ball = int(top_5_Row.iloc[sel_s3]["Liczba"])
    live_g1_m = int(top_5_Row.iloc[sel_s1]["blue_m"])
    live_g2_m = int(top_5_Row.iloc[sel_s2]["blue_m"])

    live_slot_cells_html = []
    for slot_idx, (_, r_pred) in enumerate(top_5_Row.iterrows()):
        b_val = int(r_pred["Liczba"])
        k_pos = int(r_pred["pos_nr"])
        b_m = int(r_pred["blue_m"])
        is_main_pair = slot_idx in (sel_s1, sel_s2)
        is_third_add = (slot_idx == sel_s3)

        if is_main_pair:
            cell_box = (
                f"<div style='display:inline-flex; flex-direction:column; align-items:center; justify-content:center; "
                f"width:56px; height:38px; border:2.5px solid #ffd166; border-radius:7px; "
                f"background:#e63946; color:#ffffff; font-weight:900; box-shadow:0 0 8px rgba(255,209,102,0.6);'>"
                f"<span style='font-size:15px; line-height:15px;'>🎯{b_val:02d}</span>"
                f"<span style='font-size:8px; color:#ffd166; line-height:9px;'>P{k_pos:02d}|M.{b_m:02d}</span></div>"
            )
        elif is_third_add:
            cell_box = (
                f"<div style='display:inline-flex; flex-direction:column; align-items:center; justify-content:center; "
                f"width:56px; height:38px; border:2px dashed #00e676; border-radius:7px; "
                f"background:#0077b6; color:#ffffff; font-weight:bold;'>"
                f"<span style='font-size:14px; line-height:14px;'>+{b_val:02d}</span>"
                f"<span style='font-size:8px; color:#b9f6ca; line-height:9px;'>P{k_pos:02d}|M.{b_m:02d}</span></div>"
            )
        else:
            cell_box = (
                f"<div style='display:inline-flex; flex-direction:column; align-items:center; justify-content:center; "
                f"width:54px; height:36px; border:1px solid #3c4252; border-radius:6px; background-color:#1c202b;'>"
                f"<span style='font-size:13px; color:#d0d7de; line-height:14px;'>{b_val:02d}</span>"
                f"<span style='font-size:8px; color:#8a94a6; line-height:9px;'>P{k_pos:02d}|M.{b_m:02d}</span></div>"
            )
        live_slot_cells_html.append(f"<td style='padding:5px 3px; text-align:center; border-right:1px solid #333945;'>{cell_box}</td>")

    live_pair_cell = (
        f"<span style='padding:3px 7px; border:2px solid #ffd166; border-radius:6px; background:#e63946; color:#fff; font-weight:900; font-size:13px;'>"
        f"{live_g1_ball:02d}(M.{live_g1_m})</span> "
        f"<span style='padding:3px 7px; border:2px solid #ffd166; border-radius:6px; background:#e63946; color:#fff; font-weight:900; font-size:13px;'>"
        f"{live_g2_ball:02d}(M.{live_g2_m})</span> "
        f"<span style='padding:2px 5px; border:1.5px dashed #00e676; border-radius:5px; background:#0077b6; color:#fff; font-weight:bold; font-size:11px;'>+{live_g3_ball:02d}</span>"
    )

    bt_html_rows.append(f"""
    <tr style='background: linear-gradient(90deg, rgba(255, 209, 102, 0.22) 0%, rgba(0, 230, 118, 0.18) 100%); border-top: 2.5px solid #ffd166; border-bottom: 3px solid #ffd166;'>
        <td style='padding: 7px 6px; color: #ffd166; font-weight:900; white-space: nowrap; font-size: 11px;'>
            🔥 #{last_draw_id}<br><span style='font-size:9px; color:#fff;'>({last_time_str} — TERAZ!)</span>
        </td>
        <td style='padding: 7px 6px; font-weight: 900; color: #00e676; white-space: nowrap; font-size: 12px; border-right:2px solid #ffd166;'>
            🎯 #{target_draw_id}<br><span style='font-size:9px; color:#ffd166;'>({target_time_str} — W GRZE)</span>
        </td>
        <td style='padding: 7px 6px; text-align: center; white-space: nowrap; border-right:2px solid #ffd166;'>{live_pair_cell}</td>
        {''.join(live_slot_cells_html)}
        <td style='padding: 7px 6px; text-align: center; font-weight: 900; font-size: 11px; color: #ffd166; border-left:2px solid #ffd166;'>⏳ W GRZE</td>
        <td style='padding: 7px 6px; text-align: center; font-weight: 900; font-size: 11px; color: #00e676;'>#{target_draw_id}</td>
    </tr>
    """)

    for step_t in range(latest_idx - 1, latest_idx - 1 - detail_bt, -1):
        df_step_pred, _, _, _, _ = active_scorer(step_t)
        next_actual_set = all_sets[step_t + 1]

        top5_df = df_step_pred.head(5)
        top8_df = df_step_pred.head(8)

        top5_nums = top5_df["Liczba"].tolist()
        top8_nums = top8_df["Liczba"].tolist()

        # Identyczna zasada Blokady Dominującego Lidera w każdym wierszu historii!
        st_s1, st_s2, st_locked = resolve_pair_with_leader_lock(top5_df, base_s1, base_s2)
        g1_ball = int(top5_df.iloc[st_s1]["Liczba"])
        g2_ball = int(top5_df.iloc[st_s2]["Liczba"])
        g1_m = int(top5_df.iloc[st_s1]["blue_m"])
        g2_m = int(top5_df.iloc[st_s2]["blue_m"])
        g1_hit = (g1_ball in next_actual_set)
        g2_hit = (g2_ball in next_actual_set)

        slot_cells_html = []
        for slot_idx, (_, r_pred) in enumerate(top5_df.iterrows()):
            slot_nr = slot_idx + 1
            b_val = int(r_pred["Liczba"])
            k_pos = int(r_pred["pos_nr"])
            b_m = int(r_pred["blue_m"])

            is_hit_slot = (b_val in next_actual_set)
            is_sel_col = slot_idx in (sel_s1, sel_s2)
            col_bg_tint = "background-color:rgba(255, 209, 102, 0.06);" if is_sel_col else ""

            if is_hit_slot:
                top5_slot_hits[slot_nr] += 1
                b_col = "#ffd166" if is_sel_col else "#00e676"
                cell_box = (
                    f"<div style='display:inline-flex; flex-direction:column; align-items:center; justify-content:center; "
                    f"width:54px; height:34px; border:2px solid {b_col}; border-radius:6px; "
                    f"background-color:rgba(0, 230, 118, 0.30); color:#ffffff; font-weight:bold;'>"
                    f"<span style='font-size:13px; line-height:13px;'>{b_val:02d}</span>"
                    f"<span style='font-size:8px; color:#b9f6ca; line-height:9px;'>P{k_pos:02d}|M.{b_m:02d}</span></div>"
                )
            else:
                cell_box = (
                    f"<div style='display:inline-flex; flex-direction:column; align-items:center; justify-content:center; "
                    f"width:54px; height:34px; border:1px solid #2b303c; border-radius:6px; background-color:#151821;'>"
                    f"<span style='font-size:12px; color:#a8b0c0; line-height:13px;'>{b_val:02d}</span>"
                    f"<span style='font-size:8px; color:#6c7385; line-height:9px;'>P{k_pos:02d}|M.{b_m:02d}</span></div>"
                )
            slot_cells_html.append(f"<td style='padding:3px 3px; text-align:center; border-right:1px solid #232731; {col_bg_tint}'>{cell_box}</td>")

        lck_str = "🔒" if st_locked else ""
        g1_badge = f"<span style='padding:2px 5px; border:1.5px solid #ffd166; border-radius:4px; background:rgba(255,209,102,0.30); color:#fff; font-weight:bold;'>{lck_str}{g1_ball:02d}(M.{g1_m})🟩</span>" if g1_hit else f"<span style='color:#9da3af;'>{lck_str}{g1_ball:02d}(M.{g1_m})</span>"
        g2_badge = f"<span style='padding:2px 5px; border:1.5px solid #00e676; border-radius:4px; background:rgba(0,230,118,0.28); color:#fff; font-weight:bold;'>{g2_ball:02d}(M.{g2_m})🟩</span>" if g2_hit else f"<span style='color:#9da3af;'>{g2_ball:02d}(M.{g2_m})</span>"
        golden_cell_html = f"{g1_badge} &nbsp; {g2_badge}"

        hits_5_cnt = sum(1 for n in top5_nums if n in next_actual_set)
        hits_8_cnt = sum(1 for n in top8_nums if n in next_actual_set)

        h5_color = "#00e676" if hits_5_cnt >= 2 else ("#ffd166" if hits_5_cnt == 1 else "#6c7385")
        h5_bg = "rgba(0, 230, 118, 0.16)" if hits_5_cnt >= 2 else "transparent"

        bt_html_rows.append(f"""
        <tr style='border-bottom: 1px solid #262a34;'>
            <td style='padding: 5px 6px; color: #9da3af; white-space: nowrap; font-size: 11px;'>#{all_ids[step_t]}<br><span style='font-size:9px; color:#6c7385;'>({all_times[step_t]})</span></td>
            <td style='padding: 5px 6px; font-weight: bold; color: #ffffff; white-space: nowrap; font-size: 11px; border-right:2px solid #333945;'>#{all_ids[step_t + 1]}</td>
            <td style='padding: 5px 6px; text-align: center; white-space: nowrap; font-size: 11px; border-right:2px solid #333945;'>{golden_cell_html}</td>
            {''.join(slot_cells_html)}
            <td style='padding: 5px 6px; text-align: center; font-weight: bold; font-size: 12px; color: {h5_color}; background-color: {h5_bg}; border-left:2px solid #333945;'>{hits_5_cnt} / 5</td>
            <td style='padding: 5px 6px; text-align: center; font-weight: bold; font-size: 12px; color: #4da6ff;'>{hits_8_cnt} / 8</td>
        </tr>
        """)

    st.markdown(
        f"### 📋 2. Czytelna Tabela Główna (Okno {detail_win}) — Pierwszy wiersz u góry to Twoje typy na **#{target_draw_id} ({target_time_str})**, "
        f"a złote nagłówki wskazują 2 Główne Liczby (**Typ #{sel_s1+1} + Typ #{sel_s2+1}**)"
    )

    col_headers_t5 = []
    for s_i in range(5):
        s_nr = s_i + 1
        h_cnt = top5_slot_hits[s_nr]
        if s_i in (sel_s1, sel_s2):
            col_headers_t5.append(
                f"<th style='background:#4a3805; color:#ffd166; border-top:3px solid #ffd166; border-left:2px solid #ffd166; border-right:2px solid #ffd166;'>"
                f"👑 GRAJ TYP #{s_nr}<br><span style='font-size:10px; color:#fff;'>({h_cnt}/{detail_bt} = {h_cnt/detail_bt*100:.0f}%)</span></th>"
            )
        elif s_i == sel_s3:
            col_headers_t5.append(
                f"<th style='background:#083d25; color:#00e676; border-top:2px dashed #00e676;'>"
                f"➕ 3. LICZBA (#{s_nr})<br><span style='font-size:9px; color:#b9f6ca;'>({h_cnt}/{detail_bt} = {h_cnt/detail_bt*100:.0f}%)</span></th>"
            )
        else:
            col_headers_t5.append(
                f"<th style='color:#d0d7de;'>Typ #{s_nr}<br><span style='font-size:9px; color:#8a94a6;'>({h_cnt}/{detail_bt})</span></th>"
            )

    bt_matrix_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ margin: 0; padding: 0; background-color: #0e1117; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
            .table-container {{ max-height: 640px; overflow-y: auto; overflow-x: auto; border: 1.5px solid #ffd166; border-radius: 10px; }}
            table {{ width: 100%; border-collapse: collapse; }}
            thead {{ position: sticky; top: 0; background-color: #161922; z-index: 10; border-bottom: 2px solid #333945; }}
            th {{ padding: 7px 5px; text-align: center; color: #e6e6e6; font-size: 11px; white-space: nowrap; }}
        </style>
    </head>
    <body>
        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th style="text-align:left;">Z losowania</th>
                        <th style="text-align:left; border-right:2px solid #333945;">Do (T+1)</th>
                        <th style="border-right:2px solid #333945; color:#ffd166;">👑 2 Główne (Typ #{sel_s1+1}+#{sel_s2+1})</th>
                        {''.join(col_headers_t5)}
                        <th style="border-left:2px solid #333945; color:#00e676;">TOP 5</th>
                        <th style="color:#4da6ff;">TOP 8</th>
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
    components.html(bt_matrix_html, height=660, scrolling=False)

    # =====================================================================
    # SPÓJNY RANKING 20 LICZB I GORĄCE KULE
    # =====================================================================
    col_pred_table, col_hot_all = st.columns([1.45, 0.95], gap="large")
    with col_pred_table:
        st.markdown(f"#### 📊 3. Pełny Ranking 20 liczb z #{last_draw_id} ➔ na #{target_draw_id} (Okno = {detail_win})")
        df_display_pred = df_predictions.drop(
            columns=["pos_nr", "blue_m", "pos_white_hits", "trans_count", "pos_white_pct", "w15_hits", "b_hits_cnt", "orig_bwin_cnt", "b_steps", "b_hit_pct", "has_t1_sq", "ball_t1_total"]
        ).copy()
        st.dataframe(
            df_display_pred,
            column_config={
                "Rank": st.column_config.TextColumn("Typ #", width="small"),
                "Pozycja": st.column_config.TextColumn("Poz. (🟦 Miejsce)", width="medium"),
                "Liczba": st.column_config.NumberColumn("Kula", width="small"),
                "Score": st.column_config.ProgressColumn("Siła (Score)", format="%.1f pkt", min_value=0, max_value=100),
                "Status V24": st.column_config.TextColumn("Status Weryfikacji", width="medium"),
                "⬜ Własne Poz. (i z 15)": st.column_config.TextColumn(f"⬜ Własne ({detail_win} i 15)", width="medium"),
                "🟦 Kolumna M (i Stałe)": st.column_config.TextColumn(f"🟦 Kolumna M ({detail_win})", width="medium"),
                "Pod pozycją (Węzeł)": st.column_config.TextColumn("Pod pozycją", width="medium"),
                "Powtórki Kuli T+1": st.column_config.TextColumn("Powt. Kuli", width="small"),
                "⭐ 'Najczęstsza'": st.column_config.TextColumn("⭐ 'Najczęstsza'", width="small"),
            },
            hide_index=True,
            use_container_width=True,
            height=520,
            key="pred_main_ranking_tbl_v24"
        )

    with col_hot_all:
        st.markdown(f"#### 🔥 4. Najczęściej losowane kule w oknie {detail_win}")
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
                f"W oknie ({detail_win})": f"{f_cnt}x ({f_cnt/detail_win*100:.0f}%)",
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
            height=520,
            key="hot_70_check_tbl_v24"
        )

# Wywołanie modułu V24:
render_prediction_algorithm(df, default_window=8, default_blue_win=8, default_backtest=10)
