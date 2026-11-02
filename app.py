import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
import datetime
from collections import defaultdict
from itertools import combinations

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
            
            elements = soup.find_all(["li", "p", "div", "tr"])
            for el in elements:
                text = el.get_text(" ", strip=True)
                
                if "#" not in text or "mnożnik" not in text.lower():
                    continue
                    
                nr_m = re.search(r"#\s*(\d{6,8})", text)
                if not nr_m:
                    continue
                draw_id = nr_m.group(1)
                
                if draw_id in seen_ids:
                    continue
                    
                time_m = re.search(r"\b(\d{1,2}:\d{2})\b", text)
                draw_time = time_m.group(1) if time_m else "--:--"
                
                # KLUCZOWA NAPRAWA: Bierzemy tekst WYŁĄCZNIE po słowie "mnożnik",
                # dzięki czemu odrzucamy godzinę (np. 18:01) i nagłówek z początku wiersza.
                mnoznik_m = re.search(r"mnożnik\s*x\d+\.?", text, re.I)
                pure_numbers_text = text[mnoznik_m.end():] if mnoznik_m else text[nr_m.end():]
                
                found_nums = re.findall(r"\b([0-9]{1,2})\b", pure_numbers_text)
                valid_nums = [int(n) for n in found_nums if 1 <= int(n) <= 70]
                
                # Zbieramy unikalne liczby zachowując ich poprawną kolejność
                unique_nums = []
                for n in valid_nums:
                    if n not in unique_nums:
                        unique_nums.append(n)
                        
                # Keno ma zawsze dokładnie 20 unikalnych liczb w losowaniu
                if len(unique_nums) >= 20:
                    keno_sorted = sorted(unique_nums[:20]) # Bierzemy pierwsze 20 i porządkujemy rosnąco
                    
                    if len(keno_sorted) == 20:
                        seen_ids.add(draw_id)
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

st.title("🎯 Panel Analityczny Keno (Kaskada: 20 ⬜ ➔ 15 🟦 ➔ 10/12/15 🟩)")

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
# FUNKCJA GENERUJĄCA KASKADĘ
# =====================================================================
def render_keno_cascade(section_id=1, default_top_val=20):
    st.divider()
    
    # 1. Konfiguracja dla Pierwszej Tabeli (domyślnie 20, z opcjami)
    top_ranges = [15, 20, 25, 30, 50, 100]
    available_top = [opt for opt in top_ranges if opt <= len(df)]
    if not available_top:
        available_top = [len(df)]
        
    default_top_idx = available_top.index(default_top_val) if default_top_val in available_top else 0

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
    # POZIOM 1: TABELA LOSOWAŃ KENO (BIAŁE KWADRATY) + ANALIZA POZYCJI
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
    # POZIOM 2: DRUGA TABELA (NIEBIESKA 🟦) — SPRAWDZA SZTYWNO 15 LOSOWAŃ
    # -----------------------------------------------------------------
    st.divider()
    blue_steps = 15
    rolling_window = int(selected_window)

    st.subheader(f"🟦 2. Druga Tabela (Niebieska): Sprawdzenie 15 losowań wg kolumny 'Ostatnia'")
    st.caption(f"Przenosi wartości z kolumny 'Ostatnia' z Pierwszej Tabeli (okno {rolling_window}) i sprawdza dokładnie **15 losowań**[cite: 15].")

    all_sets = df["numbers_set"].tolist()
    all_lists = df["numbers_list"].tolist()
    all_ids = df["draw_id"].tolist()
    all_times = df["draw_time"].tolist()
    total_df_rows = len(df)

    max_green_steps = 15
    earliest_t_needed = max(rolling_window - 1, total_df_rows - 1 - blue_steps - max_green_steps)

    blue_row_data_by_t = {}

    for t in range(earliest_t_needed, total_df_rows):
        is_latest = (t == total_df_rows - 1)
        if is_latest:
            pos_ranking_sorted = []
            for _, r_row in df_pos_stats_full.iterrows():
                pos_ranking_sorted.append({
                    "orig_pos": int(r_row["orig_pos_num"]),
                    "raw_hits": int(r_row["raw_hits"]),
                    "ostatnia_val": int(r_row["Ostatnia"])
                })
        else:
            win_start = t - rolling_window + 1
            win_end = t + 1
            win_sets = all_sets[win_start:win_end]
            win_lists = all_lists[win_start:win_end]
            total_trans = len(win_sets) - 1
            nums_t = all_lists[t]
            
            pos_temp = []
            for i in range(1, 21):
                p_idx = i - 1
                repeat_t1_count = sum(1 for k in range(total_trans) if win_lists[k][p_idx] in win_sets[k + 1])
                pos_temp.append({
                    "orig_pos": i,
                    "raw_hits": repeat_t1_count,
                    "ostatnia_val": nums_t[p_idx]
                })
                
            df_rank_step = pd.DataFrame(pos_temp).sort_values(
                by="raw_hits", ascending=False, kind="mergesort"
            ).reset_index(drop=True)
            pos_ranking_sorted = df_rank_step.to_dict("records")

        next_draw_set = all_sets[t + 1] if not is_latest else set()
        
        row_items = []
        for rank_idx, item in enumerate(pos_ranking_sorted):
            ball_val = int(item["ostatnia_val"])
            hit_blue = (ball_val in next_draw_set) if not is_latest else False
            row_items.append({
                "blue_pos": rank_idx + 1,
                "ball": ball_val,
                "orig_pos": int(item["orig_pos"]),
                "t1_score": int(item["raw_hits"]),
                "hit_blue": hit_blue
            })
        blue_row_data_by_t[t] = row_items

    start_idx_blue = max(rolling_window - 1, total_df_rows - 1 - blue_steps)
    rolling_rows_html = []
    rank_pos_blue_hits = {r: 0 for r in range(1, 21)}
    latest_rank_numbers = {}
    latest_rank_orig_pos = {}
    evaluated_draws_count = 0

    headers_rolling_html = "".join([
        f"<th style='padding: 6px 2px; text-align: center; color: #4da6ff; font-size: 11px; width: 30px; border-right: 1px solid #2a2e39;'>{col_i}</th>" 
        for col_i in range(1, 21)
    ])

    for t in range(total_df_rows - 1, start_idx_blue - 1, -1):
        is_latest_unverified = (t == total_df_rows - 1)
        row_items = blue_row_data_by_t[t]

        if not is_latest_unverified:
            evaluated_draws_count += 1

        row_blue_count = 0
        cells_html = []

        for item in row_items:
            new_pos_nr = item["blue_pos"]
            ball_val = item["ball"]
            orig_pos = item["orig_pos"]

            if is_latest_unverified:
                latest_rank_numbers[new_pos_nr] = ball_val
                latest_rank_orig_pos[new_pos_nr] = orig_pos
                cell_content = f"<span style='color:#ffd166; font-weight:bold; font-size:11px;'>{ball_val:02d}</span>"
            else:
                if item["hit_blue"]:
                    rank_pos_blue_hits[new_pos_nr] += 1
                    row_blue_count += 1
                    cell_content = (
                        f"<span title='Poz. 🟦 {new_pos_nr:02d} (z Poz. {orig_pos:02d}) - TRAFIONA w #{all_ids[t+1]}' "
                        f"style='display:inline-flex; align-items:center; justify-content:center; "
                        f"width:26px; height:26px; border:2px solid #00aaff; border-radius:4px; "
                        f"background-color:rgba(0, 170, 255, 0.35); color:#ffffff; font-weight:bold; "
                        f"font-size:11px; margin:1px; box-sizing:border-box; box-shadow: 0 0 5px rgba(0,170,255,0.6);'>"
                        f"{ball_val:02d}</span>"
                    )
                else:
                    cell_content = f"<span style='color:#a8b0c0; font-size:11px;'>{ball_val:02d}</span>"

            cells_html.append(f"<td style='padding: 4px 2px; text-align: center; border-right: 1px solid #232731;'>{cell_content}</td>")

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
        st.markdown(f"#### 📋 2. Tabela Losowań wg kolejności 'Ostatnia' 🟦 (sprawdzane 15 losowań)")
        rolling_full_html = f"""
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
                            {headers_rolling_html}
                            <th style="width: 60px; text-align: center; color: #00aaff;">🟦 Suma</th>
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
        components.html(rolling_full_html, height=600, scrolling=False)

    with col_roll_pos:
        st.markdown(f"#### 📊 2. Tabela Pozycji Trafień 🟦 (z 15 losowań)")
        pos_summary_rows = []
        for r in range(1, 21):
            b_hits = rank_pos_blue_hits[r]
            eff_pct = (b_hits / evaluated_draws_count * 100.0) if evaluated_draws_count > 0 else 0.0
            curr_ball = latest_rank_numbers.get(r, 0)
            orig_p = latest_rank_orig_pos.get(r, 0)
            
            pos_summary_rows.append({
                "blue_pos_num": r,
                "Pozycja w tabeli": f"Poz. {r:02d}",
                "raw_blue": b_hits,
                "🟦 Trafienia": f"{b_hits} ({eff_pct:.1f}%)",
                "Teraz w grze": int(curr_ball),
                "Z pozycji": f"Poz. {orig_p:02d}"
            })
            
        df_roll_pos_full = pd.DataFrame(pos_summary_rows).sort_values(
            by="raw_blue", ascending=False, kind="mergesort"
        ).reset_index(drop=True)
        
        df_roll_pos = df_roll_pos_full.drop(columns=["raw_blue", "blue_pos_num"])
        
        st.dataframe(
            df_roll_pos,
            column_config={
                "Pozycja w tabeli": st.column_config.TextColumn("Pozycja (1-20)", width="small"),
                "🟦 Trafienia": st.column_config.TextColumn("🟦 Niebieskie kwadraty", width="small"),
                "Teraz w grze": st.column_config.NumberColumn("Ostatnia (Teraz)", width="small"),
                "Z pozycji": st.column_config.TextColumn("Skąd (Oryg.)", width="small"),
            },
            hide_index=True,
            use_container_width=True,
            height=600,
            key=f"roll_pos_tbl_{section_id}"
        )

    # -----------------------------------------------------------------
    # POZIOM 3: TRZECIA TABELA (ZIELONA 🟩) — DOMYŚLNIE 10 (DO WYBORU 10, 12, 15)
    # -----------------------------------------------------------------
    st.divider()
    st.subheader("🟩 3. Trzecia Tabela (Zielona): Sprawdzenie wg Tabeli Pozycji Trafień 🟦")
    
    green_steps = st.radio(
        "3️⃣ Wybierz liczbę losowań do sprawdzenia w Trzeciej Tabeli 🟩 (domyślnie 10, opcje: 10, 12, 15):",
        options=[10, 12, 15],
        index=0,  # Domyślnie 10 losowań
        horizontal=True,
        key=f"green_steps_radio_{section_id}"
    )

    start_idx_green = max(rolling_window - 1, total_df_rows - 1 - green_steps)
    green_rows_html = []
    rank_pos_green_hits = {r: 0 for r in range(1, 21)}
    latest_green_numbers = {}
    latest_green_from_blue = {}
    evaluated_green_draws = 0

    headers_green_html = "".join([
        f"<th style='padding: 6px 2px; text-align: center; color: #00e676; font-size: 11px; width: 30px; border-right: 1px solid #2a2e39;'>{col_i}</th>" 
        for col_i in range(1, 21)
    ])

    for t in range(total_df_rows - 1, start_idx_green - 1, -1):
        is_latest_unverified = (t == total_df_rows - 1)
        
        if is_latest_unverified:
            green_ranking_sorted = []
            for _, b_row in df_roll_pos_full.iterrows():
                green_ranking_sorted.append({
                    "blue_pos": int(b_row["blue_pos_num"]),
                    "raw_blue": int(b_row["🟦 Trafienia"].split()[0]),
                    "ball_val": int(b_row["Teraz w grze"])
                })
        else:
            hist_start = max(earliest_t_needed, t - blue_steps)
            hist_end = t
            
            blue_counts_at_t = {r: 0 for r in range(1, 21)}
            for k_step in range(hist_start, hist_end):
                for b_item in blue_row_data_by_t[k_step]:
                    if b_item["hit_blue"]:
                        blue_counts_at_t[b_item["blue_pos"]] += 1
                        
            current_blue_row = {b_item["blue_pos"]: b_item["ball"] for b_item in blue_row_data_by_t[t]}
            
            temp_green = []
            for r in range(1, 21):
                temp_green.append({
                    "blue_pos": r,
                    "raw_blue": blue_counts_at_t[r],
                    "ball_val": current_blue_row[r]
                })
                
            df_green_step = pd.DataFrame(temp_green).sort_values(
                by="raw_blue", ascending=False, kind="mergesort"
            ).reset_index(drop=True)
            green_ranking_sorted = df_green_step.to_dict("records")

        next_draw_set = all_sets[t + 1] if not is_latest_unverified else set()
        if not is_latest_unverified:
            evaluated_green_draws += 1

        row_green_count = 0
        cells_green_html = []

        for rank_idx, g_item in enumerate(green_ranking_sorted):
            green_pos_nr = rank_idx + 1
            ball_val = int(g_item["ball_val"])
            from_blue_pos = int(g_item["blue_pos"])
            blue_score = int(g_item["raw_blue"])

            if is_latest_unverified:
                latest_green_numbers[green_pos_nr] = ball_val
                latest_green_from_blue[green_pos_nr] = from_blue_pos
                cell_content = f"<span style='color:#ffd166; font-weight:bold; font-size:11px;'>{ball_val:02d}</span>"
            else:
                is_hit_green = (ball_val in next_draw_set)
                if is_hit_green:
                    rank_pos_green_hits[green_pos_nr] += 1
                    row_green_count += 1
                    cell_content = (
                        f"<span title='Poz. 🟩 {green_pos_nr:02d} (z Poz. 🟦 {from_blue_pos:02d}, 🟦={blue_score}) - TRAFIONA w #{all_ids[t+1]}' "
                        f"style='display:inline-flex; align-items:center; justify-content:center; "
                        f"width:26px; height:26px; border:2px solid #00e676; border-radius:4px; "
                        f"background-color:rgba(0, 230, 118, 0.32); color:#ffffff; font-weight:bold; "
                        f"font-size:11px; margin:1px; box-sizing:border-box; box-shadow: 0 0 5px rgba(0,230,118,0.6);'>"
                        f"{ball_val:02d}</span>"
                    )
                else:
                    cell_content = f"<span style='color:#a8b0c0; font-size:11px;'>{ball_val:02d}</span>"

            cells_green_html.append(f"<td style='padding: 4px 2px; text-align: center; border-right: 1px solid #232731;'>{cell_content}</td>")

        d_id = all_ids[t]
        d_time = all_times[t]

        if is_latest_unverified:
            sum_green_html = "<td style='padding: 4px 6px; text-align: center; font-weight: bold; font-size: 11px; color: #ffd166; border-left: 2px solid #333945;'>⏳ W grze</td>"
        else:
            badge_color = "#00e676" if row_green_count > 0 else "#6c7385"
            badge_bg = "rgba(0, 230, 118, 0.18)" if row_green_count > 0 else "transparent"
            sum_green_html = f"<td style='padding: 4px 6px; text-align: center; font-weight: bold; font-size: 12px; color: {badge_color}; background-color: {badge_bg}; border-left: 2px solid #333945;'>{row_green_count}</td>"

        row_g_html = f"""
        <tr style='border-bottom: 1px solid #262a34;'>
            <td style='padding: 6px 6px; font-weight: bold; color: #ffffff; white-space: nowrap; font-size: 11px;'>{d_id}</td>
            <td style='padding: 6px 6px; color: #9da3af; white-space: nowrap; font-size: 11px;'>{d_time}</td>
            {''.join(cells_green_html)}
            {sum_green_html}
        </tr>
        """
        green_rows_html.append(row_g_html)

    col_green_tab, col_green_pos = st.columns([1.6, 0.9], gap="large")

    with col_green_tab:
        st.markdown(f"#### 📋 3. Tabela Losowań wg kolejności z Tabeli Niebieskiej 🟩 (sprawdzane {green_steps} losowań)")
        green_full_html = f"""
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
                            {headers_green_html}
                            <th style="width: 60px; text-align: center; color: #00e676;">🟩 Suma</th>
                        </tr>
                    </thead>
                    <tbody>
                        {''.join(green_rows_html)}
                    </tbody>
                </table>
            </div>
        </body>
        </html>
        """
        components.html(green_full_html, height=600, scrolling=False)

    with col_green_pos:
        st.markdown(f"#### 📊 3. Tabela Pozycji Trafień 🟩 (z {green_steps} losowań)")
        green_summary_rows = []
        for r in range(1, 21):
            g_hits = rank_pos_green_hits[r]
            eff_pct = (g_hits / evaluated_green_draws * 100.0) if evaluated_green_draws > 0 else 0.0
            curr_ball = latest_green_numbers.get(r, "-")
            from_b = latest_green_from_blue.get(r, "-")
            
            green_summary_rows.append({
                "Pozycja w tabeli": f"Poz. {r:02d}",
                "raw_green": g_hits,
                "🟩 Trafienia": f"{g_hits} ({eff_pct:.1f}%)",
                "Teraz w grze": curr_ball,
                "Z pozycji 🟦": f"Poz. {from_b:02d}" if isinstance(from_b, int) else "-"
            })
            
        df_green_pos = pd.DataFrame(green_summary_rows).sort_values(
            by="raw_green", ascending=False, kind="mergesort"
        ).drop(columns=["raw_green"])
        
        st.dataframe(
            df_green_pos,
            column_config={
                "Pozycja w tabeli": st.column_config.TextColumn("Pozycja (1-20)", width="small"),
                "🟩 Trafienia": st.column_config.TextColumn("🟩 Zielone kwadraty", width="small"),
                "Teraz w grze": st.column_config.NumberColumn("Ostatnia (Teraz)", width="small"),
                "Z pozycji 🟦": st.column_config.TextColumn("Skąd (z 🟦)", width="small"),
            },
            hide_index=True,
            use_container_width=True,
            height=600,
            key=f"green_pos_tbl_{section_id}"
        )


# =====================================================================
# WYWOŁANIE GŁÓWNEJ KASKADY (Domyślnie 20 dla Tabeli 1)
# =====================================================================
render_keno_cascade(section_id=1, default_top_val=20)


import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
import datetime

st.set_page_config(page_title="Panel Analityczny Keno (Live)", layout="wide")

@st.cache_data(ttl=60)
def fetch_keno_full_history(target_draws=550):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }
    session = requests.Session()
    session.headers.update(headers)
    
    records = []
    seen_ids = set()
    
    urls = ["https://wynikikeno.pl/"]
    now = datetime.datetime.now()
    for days_back in range(0, 4):
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
            
            elements = soup.find_all(["li", "p", "div", "tr"])
            for el in elements:
                text = el.get_text(" ", strip=True)
                
                if "#" not in text or "mnożnik" not in text.lower():
                    continue
                    
                time_m = re.search(r"\b(\d{1,2}:\d{2})\b", text)
                draw_time = time_m.group(1) if time_m else "--:--"
                
                nr_m = re.search(r"#\s*(\d{6,8})", text)
                if not nr_m:
                    continue
                draw_id = nr_m.group(1)
                
                if draw_id in seen_ids:
                    continue
                    
                mnoznik_m = re.search(r"mnożnik\s*x\d+\.?", text, re.I)
                pure_numbers_text = text[mnoznik_m.end():] if mnoznik_m else text[nr_m.end():]
                
                found_nums = re.findall(r"\b([0-9]{1,2})\b", pure_numbers_text)
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

# --- WIDOK DASHBOARDU ---
df, status_msg = fetch_keno_full_history(target_draws=550)

st.title("🎯 Panel Analityczny Keno (Live)")

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

# Wybór okna analizy: 15 (domyślnie), 20, 25, 30, 35, 50, 100
base_ranges = [15, 20, 25, 30, 35, 50, 100]
available_options = [opt for opt in base_ranges if opt <= len(df)]
if not available_options:
    available_options = [len(df)]

default_index = available_options.index(15) if 15 in available_options else 0

selected_window = st.radio(
    "Wybierz zakres analizy losowań:",
    options=available_options,
    index=default_index,
    horizontal=True,
    key="top_window_selector"
)

df_window = df.tail(selected_window).copy().reset_index(drop=True)
st.divider()

col_draws, col_stats = st.columns([1.6, 0.9], gap="large")

# Lewa kolumna: Tabela losowań z kwadratami i kółkami
with col_draws:
    st.subheader(f"📋 Tabela Losowań Keno (ostatnie {selected_window})")
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
            body {{
                margin: 0;
                padding: 0;
                background-color: #0e1117;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            }}
            .table-container {{
                max-height: 620px;
                overflow-y: auto;
                overflow-x: auto;
                border: 1px solid #333945;
                border-radius: 8px;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
            }}
            thead {{
                position: sticky;
                top: 0;
                background-color: #161922;
                z-index: 10;
                border-bottom: 2px solid #333945;
            }}
            th {{
                padding: 8px 6px;
                text-align: left;
                color: #e6e6e6;
                font-size: 12px;
            }}
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
    
    components.html(full_html, height=640, scrolling=False)

# Prawa kolumna: Podsumowanie pozycji (zawsze zablokowane od największej do najmniejszej liczby powtórzeń)
with col_stats:
    st.subheader("📊 Analiza pozycji (Trafienia T+1)")
    
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
        
    # Sortujemy stabilnie (kind="mergesort"), aby kolejność przy remisach była w 100% powtarzalna
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
        height=640
    )


# =====================================================================
# MODUŁ: TEST KROCZĄCY WG RANKINGU "OSTATNIA" Z ANALIZY POZYCJI
# =====================================================================
st.divider()
st.subheader("🟦 Test Kroczący: Tabela z kolumny 'Ostatnia' wg rankingu Pozycji (Trafienia T+1)")
st.caption(
    "Dla każdego losowania skrypt bierze posortowaną kolumnę 'Ostatnia' z tabeli 'Analiza pozycji (Trafienia T+1)' "
    "i układa liczby na pozycjach 1–20 (1. wiersz = Poz. 1, 2. wiersz = Poz. 2 itd.). "
    "Niebieski kwadrat 🟦 oznacza trafienie w następnym losowaniu."
)

col_tk1, col_tk2 = st.columns([1.2, 1])

with col_tk1:
    rolling_options = [opt for opt in [15, 20, 25, 30, 35, 50, 100] if opt <= len(df)]
    if not rolling_options:
        rolling_options = [len(df)]
    default_roll_idx = rolling_options.index(15) if 15 in rolling_options else 0

    rolling_window = st.radio(
        "Wybierz zakres okna dla 'Pozycje analityczne (Trafienia T+1)':",
        options=rolling_options,
        index=default_roll_idx,  # Domyślnie 15
        horizontal=True,
        key="rolling_win_selector"
    )

with col_tk2:
    max_available_test = max(5, len(df) - rolling_window)
    test_steps = st.number_input(
        "Ile losowań (wierszy) sprawdzić i wyświetlić w tabeli:",
        min_value=5,
        max_value=max_available_test,
        value=min(15, max_available_test),  # Domyślnie 15
        step=5,
        key="rolling_test_steps"
    )

if len(df) <= rolling_window + 2:
    st.warning(f"Za mało losowań w bazie ({len(df)}), aby wykonać test dla okna {rolling_window}.")
else:
    all_sets = df["numbers_set"].tolist()
    all_lists = df["numbers_list"].tolist()
    all_ids = df["draw_id"].tolist()
    all_times = df["draw_time"].tolist()
    
    total_df_rows = len(df)
    start_idx = max(rolling_window - 1, total_df_rows - 1 - test_steps)
    
    rolling_rows_html = []
    rank_pos_blue_hits = {r: 0 for r in range(1, 21)}
    latest_rank_numbers = {}
    latest_rank_orig_pos = {}
    
    evaluated_draws_count = 0
    
    headers_rolling_html = "".join([
        f"<th style='padding: 6px 2px; text-align: center; color: #4da6ff; font-size: 11px; width: 30px; border-right: 1px solid #2a2e39;'>{col_i}</th>" 
        for col_i in range(1, 21)
    ])
    
    # Pętla od najnowszego losowania w dół
    for t in range(total_df_rows - 1, start_idx - 1, -1):
        is_latest_unverified = (t == total_df_rows - 1)
        
        # Jeśli to najnowszy wiersz i mamy wybrane to samo okno co u góry, bierzemy dane BEZPOŚREDNIO z górnej tabeli!
        if is_latest_unverified and rolling_window == int(selected_window):
            pos_ranking_sorted = []
            for _, r_row in df_pos_stats_full.iterrows():
                pos_ranking_sorted.append({
                    "orig_pos": int(r_row["orig_pos_num"]),
                    "raw_hits": int(r_row["raw_hits"]),
                    "ostatnia_val": int(r_row["Ostatnia"])
                })
        else:
            win_start = t - rolling_window + 1
            win_end = t + 1
            
            win_sets = all_sets[win_start:win_end]
            win_lists = all_lists[win_start:win_end]
            total_trans = len(win_sets) - 1
            nums_t = all_lists[t]
            
            pos_temp = []
            for i in range(1, 21):
                p_idx = i - 1
                repeat_t1_count = 0
                for k in range(total_trans):
                    if win_lists[k][p_idx] in win_sets[k + 1]:
                        repeat_t1_count += 1
                        
                pos_temp.append({
                    "orig_pos": i,
                    "raw_hits": repeat_t1_count,
                    "ostatnia_val": nums_t[p_idx]
                })
                
            df_rank_step = pd.DataFrame(pos_temp).sort_values(
                by="raw_hits", ascending=False, kind="mergesort"
            ).reset_index(drop=True)
            pos_ranking_sorted = df_rank_step.to_dict("records")
        
        next_draw_set = all_sets[t + 1] if not is_latest_unverified else set()
        
        if not is_latest_unverified:
            evaluated_draws_count += 1
            
        row_blue_count = 0
        cells_html = []
        
        for rank_idx, item in enumerate(pos_ranking_sorted):
            new_pos_nr = rank_idx + 1
            ball_val = int(item["ostatnia_val"])
            orig_pos = int(item["orig_pos"])
            t1_score = int(item["raw_hits"])
            
            if is_latest_unverified:
                latest_rank_numbers[new_pos_nr] = ball_val
                latest_rank_orig_pos[new_pos_nr] = orig_pos
                cell_content = (
                    f"<span title='Nowa Poz. {new_pos_nr:02d} (z Poz. {orig_pos:02d}, T+1={t1_score}) - oczekuje na losowanie' "
                    f"style='color:#ffd166; font-weight:bold; font-size:11px;'>{ball_val:02d}</span>"
                )
            else:
                is_hit_blue = (ball_val in next_draw_set)
                if is_hit_blue:
                    rank_pos_blue_hits[new_pos_nr] += 1
                    row_blue_count += 1
                    cell_content = (
                        f"<span title='Nowa Poz. {new_pos_nr:02d} (z Poz. {orig_pos:02d}, T+1={t1_score}) - TRAFIONA w #{all_ids[t+1]}' "
                        f"style='display:inline-flex; align-items:center; justify-content:center; "
                        f"width:26px; height:26px; border:2px solid #00aaff; border-radius:4px; "
                        f"background-color:rgba(0, 170, 255, 0.35); color:#ffffff; font-weight:bold; "
                        f"font-size:11px; margin:1px; box-sizing:border-box; box-shadow: 0 0 5px rgba(0,170,255,0.6);'>"
                        f"{ball_val:02d}</span>"
                    )
                else:
                    cell_content = (
                        f"<span title='Nowa Poz. {new_pos_nr:02d} (z Poz. {orig_pos:02d}, T+1={t1_score})' "
                        f"style='color:#a8b0c0; font-size:11px;'>{ball_val:02d}</span>"
                    )
                    
            cells_html.append(f"<td style='padding: 4px 2px; text-align: center; border-right: 1px solid #232731;'>{cell_content}</td>")
            
        d_id = all_ids[t]
        d_time = all_times[t]
        
        if is_latest_unverified:
            sum_cell_html = "<td style='padding: 4px 6px; text-align: center; font-weight: bold; font-size: 11px; color: #ffd166; border-left: 2px solid #333945;'>⏳ W grze</td>"
        else:
            badge_color = "#00aaff" if row_blue_count > 0 else "#6c7385"
            badge_bg = "rgba(0, 170, 255, 0.18)" if row_blue_count > 0 else "transparent"
            sum_cell_html = (
                f"<td style='padding: 4px 6px; text-align: center; font-weight: bold; font-size: 12px; "
                f"color: {badge_color}; background-color: {badge_bg}; border-left: 2px solid #333945;'>"
                f"{row_blue_count}</td>"
            )
            
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
        st.markdown(f"#### 📋 Tabela Losowań wg kolejności 'Ostatnia' (okno {rolling_window})")
        st.caption(
            "Kolumny **1–20** to kolejne liczby z kolumny **'Ostatnia'** tabeli *Analiza pozycji (Trafienia T+1)* "
            "(1 = 1. wiersz od góry, 2 = 2. wiersz itd.). 🟦 **Niebieski kwadrat** = trafienie tej liczby w następnym losowaniu (T+1)."
        )
        
        rolling_full_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{
                    margin: 0;
                    padding: 0;
                    background-color: #0e1117;
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                }}
                .table-container {{
                    max-height: 620px;
                    overflow-y: auto;
                    overflow-x: auto;
                    border: 1px solid #333945;
                    border-radius: 8px;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                }}
                thead {{
                    position: sticky;
                    top: 0;
                    background-color: #161922;
                    z-index: 10;
                    border-bottom: 2px solid #333945;
                }}
                th {{
                    padding: 8px 6px;
                    text-align: left;
                    color: #e6e6e6;
                    font-size: 12px;
                }}
            </style>
        </head>
        <body>
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th style="width: 75px;">Nr</th>
                            <th style="width: 55px;">Czas</th>
                            {headers_rolling_html}
                            <th style="width: 60px; text-align: center; color: #00aaff;">🟦 Suma</th>
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
        components.html(rolling_full_html, height=640, scrolling=False)

    with col_roll_pos:
        st.markdown(f"#### 📊 Tabela Pozycji Trafień 🟦 (okno {rolling_window})")
        st.caption(f"Zliczone niebieskie kwadraty dla nowych pozycji (1–20), posortowane od najwyższych trafień (na bazie {evaluated_draws_count} sprawdzonych losowań).")
        
        pos_summary_rows = []
        for r in range(1, 21):
            b_hits = rank_pos_blue_hits[r]
            eff_pct = (b_hits / evaluated_draws_count * 100.0) if evaluated_draws_count > 0 else 0.0
            curr_ball = latest_rank_numbers.get(r, "-")
            orig_p = latest_rank_orig_pos.get(r, "-")
            
            pos_summary_rows.append({
                "Pozycja w tabeli": f"Poz. {r:02d}",
                "raw_blue": b_hits,
                "🟦 Trafienia": f"{b_hits} ({eff_pct:.1f}%)",
                "Teraz w grze": curr_ball,
                "Z pozycji": f"Poz. {orig_p:02d}" if isinstance(orig_p, int) else "-"
            })
            
        df_roll_pos = pd.DataFrame(pos_summary_rows).sort_values(
            by="raw_blue", ascending=False, kind="mergesort"
        ).drop(columns=["raw_blue"])
        
        st.dataframe(
            df_roll_pos,
            column_config={
                "Pozycja w tabeli": st.column_config.TextColumn("Pozycja (1-20)", width="small"),
                "🟦 Trafienia": st.column_config.TextColumn("🟦 Niebieskie kwadraty", width="small"),
                "Teraz w grze": st.column_config.NumberColumn("Ostatnia (Teraz)", width="small"),
                "Z pozycji": st.column_config.TextColumn("Skąd (Oryg.)", width="small"),
            },
            hide_index=True,
            use_container_width=True,
            height=640
        )





# =====================================================================
# STATYSTYKI TRAFIEŃ T+1 DLA AKTUALNYCH LICZB
# =====================================================================
st.divider()
st.subheader(f"🎯 Statystyka Trafień T+1 dla liczb z ostatniego losowania (okno {selected_window})")
st.caption("Ocena prawdopodobieństwa przejścia do następnego losowania dla każdej z 20 liczb aktualnie wylosowanych.")

summary_next = []
sets_list = df_window["numbers_set"].tolist()
total_transitions = len(df_window) - 1

for i in range(1, 21):
    pos_col = f"pos_{i}"
    pos_values = df_window[pos_col].tolist()
    curr_number = last_draw[pos_col]
    
    pos_t1_hits = 0
    exact_num_t1_hits = 0
    exact_num_occurrences = 0
    
    if total_transitions > 0:
        for k in range(total_transitions):
            val_at_pos = pos_values[k]
            next_draw_set = sets_list[k + 1]
            
            if val_at_pos in next_draw_set:
                pos_t1_hits += 1
                
            if val_at_pos == curr_number:
                exact_num_occurrences += 1
                if val_at_pos in next_draw_set:
                    exact_num_t1_hits += 1
                    
        pct_pos = (pos_t1_hits / total_transitions) * 100
    else:
        pct_pos = 0.0

    if pct_pos >= 35.0:
        status = "🔥 Bardzo wysoka"
    elif pct_pos >= 28.0:
        status = "⚡ Wysoka"
    else:
        status = "⚪ Standardowa"

    summary_next.append({
        "Pozycja": f"Poz. {i:02d}",
        "Liczba w grze": curr_number,
        "Skuteczność pozycji w T+1": f"{pos_t1_hits}x ({pct_pos:.1f}%)",
        "Trafienia tej liczby w T+1": f"{exact_num_t1_hits} z {exact_num_occurrences} wystąpień",
        "Ocena szansy": status,
        "raw_pct": pct_pos
    })

df_summary_next = pd.DataFrame(summary_next).sort_values(by="raw_pct", ascending=False).drop(columns=["raw_pct"])

st.dataframe(
    df_summary_next,
    column_config={
        "Pozycja": st.column_config.TextColumn("Pozycja", width="small"),
        "Liczba w grze": st.column_config.NumberColumn("Liczba w grze (T)", width="small"),
        "Skuteczność pozycji w T+1": st.column_config.TextColumn("Trafienia pozycji w T+1", width="medium"),
        "Trafienia tej liczby w T+1": st.column_config.TextColumn("Powtórzenia tej liczby", width="medium"),
        "Ocena szansy": st.column_config.TextColumn("Potencjał T+1", width="small")
    },
    hide_index=True,
    use_container_width=True,
    height=360
)


# =====================================================================
# SYMULACJA KROCZĄCA (WALK-FORWARD BACKTEST)
# =====================================================================
st.divider()
st.subheader("🔁 Test Kroczący: Czy najwyższe wartości wygrywają w kolejnym losowaniu?")
st.caption("Analiza 200 losowań: bierzemy 20 losowań, wyłaniamy 'faworytów', sprawdzamy losowanie T+1, przesuwamy o 1.")

col_b1, col_b2, col_b3 = st.columns(3)
with col_b1:
    backtest_steps = st.slider("Liczba kroków testowych (losowań T+1):", min_value=20, max_value=min(300, max(20, len(df) - 21)), value=min(200, max(20, len(df) - 21)), step=10, key="wf1_steps")
with col_b2:
    window_len = st.number_input("Wielkość okna analizy (losowań wstecz):", min_value=5, max_value=50, value=20, key="wf1_win")
with col_b3:
    top_k = st.selectbox("Ile najwyższych liczb typować:", options=[3, 4, 5, 6, 8, 10], index=2, key="wf1_topk")

strategy = st.radio(
    "Kryterium wyboru 'najwyższych wartości':",
    options=[
        "Najczęściej padające w oknie 20 losowań (tzw. gorące liczby)",
        "Liczby z pozycji o najwyższej skuteczności T+1 w oknie"
    ],
    horizontal=True,
    key="wf1_strat"
)

if len(df) < (window_len + backtest_steps):
    st.warning(f"Za mało pobranych losowań w bazie ({len(df)}) na test {backtest_steps} kroków z oknem {window_len}. Zmniejsz liczbę kroków lub pobierz więcej danych.")
else:
    total_needed = window_len + backtest_steps
    eval_df = df.tail(total_needed).reset_index(drop=True)
    
    simulation_rows = []
    total_hits_all = 0
    total_picks_all = 0
    hit_distribution = {i: 0 for i in range(top_k + 1)}

    for step in range(backtest_steps):
        win = eval_df.iloc[step : step + window_len]
        target = eval_df.iloc[step + window_len]
        target_set = target["numbers_set"]
        
        if "gorące liczby" in strategy:
            all_numbers = [n for sub in win["numbers_list"] for n in sub]
            freq_series = pd.Series(all_numbers).value_counts()
            top_picks = freq_series.head(top_k).index.tolist()
        else:
            w_sets = win["numbers_set"].tolist()
            pos_scores = []
            for p in range(1, 21):
                col = f"pos_{p}"
                vals = win[col].tolist()
                t1_hits = sum(1 for idx in range(len(w_sets) - 1) if vals[idx] in w_sets[idx + 1])
                pos_scores.append((p, t1_hits))
            pos_scores.sort(key=lambda x: x[1], reverse=True)
            best_pos = [p for p, _ in pos_scores[:top_k]]
            last_in_window = win.iloc[-1]
            top_picks = [last_in_window[f"pos_{p}"] for p in best_pos]

        hits = sorted(list(set(top_picks).intersection(target_set)))
        hit_cnt = len(hits)
        
        total_hits_all += hit_cnt
        total_picks_all += top_k
        if hit_cnt in hit_distribution:
            hit_distribution[hit_cnt] += 1
        else:
            hit_distribution[top_k] += 1

        simulation_rows.append({
            "Krok": step + 1,
            "Okno analizy": f"#{win.iloc[0]['draw_id']} – #{win.iloc[-1]['draw_id']}",
            "Sprawdzane T+1": f"#{target['draw_id']} ({target['draw_time']})",
            "Typowane (Top)": ", ".join(f"{n:02d}" for n in top_picks),
            "Trafione liczby": ", ".join(f"{n:02d}" for n in hits) if hits else "—",
            "Trafień": f"{hit_cnt} / {top_k}",
            "Skuteczność": f"{(hit_cnt / top_k) * 100:.0f}%",
            "_raw_hits": hit_cnt
        })

    avg_hits = total_hits_all / backtest_steps
    actual_pct = (total_hits_all / total_picks_all) * 100
    expected_pct = (20 / 70) * 100
    expected_avg_hits = top_k * (20 / 70)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Średnia trafień na losowanie", f"{avg_hits:.2f} / {top_k}", delta=f"{avg_hits - expected_avg_hits:+.2f} vs losowa")
    m2.metric("Skuteczność typowanych liczb", f"{actual_pct:.1f}%", delta=f"{actual_pct - expected_pct:+.1f}% vs losowa (28.6%)")
    m3.metric("Łącznie trafionych kul", f"{total_hits_all} z {total_picks_all}")
    m4.metric("Maksymalne trafienie", f"{max(r['_raw_hits'] for r in simulation_rows)} / {top_k}")

    dist_cols = st.columns(top_k + 1)
    for hits_k, count in hit_distribution.items():
        with dist_cols[hits_k]:
            pct_draws = (count / backtest_steps) * 100
            st.metric(f"Trafień: {hits_k}", f"{count}x", f"{pct_draws:.1f}% losowań")

    df_sim = pd.DataFrame(simulation_rows).drop(columns=["_raw_hits"])
    st.dataframe(
        df_sim,
        use_container_width=True,
        hide_index=True,
        height=450
    )


# =====================================================================
# MODUŁ: TEST KROCZĄCY WG POZYCJI T+1 ORAZ LICZB NAJCZĘSTSZYCH
# =====================================================================
st.divider()
st.subheader("🔁 Analiza krocząca: Pozycje T+1 oraz Liczby Najczęstsze")
st.caption("Porównanie skuteczności typowania z pozycji o najwyższych Trafieniach T+1 oraz z liczb najczęściej padających w oknie.")

col_c1, col_c2, col_c3, col_c4 = st.columns(4)
with col_c1:
    backtest_steps_2 = st.slider(
        "Liczba kroków testowych (przesunięć):", 
        min_value=10, 
        max_value=min(300, max(10, len(df) - 51)), 
        value=min(200, max(10, len(df) - 51)), 
        step=10,
        key="wf2_steps"
    )
with col_c2:
    window_len_2 = st.number_input(
        "Wielkość okna (losowań wstecz):", 
        min_value=5, 
        max_value=100, 
        value=20, 
        step=5,
        key="wf2_win"
    )
with col_c3:
    top_n_pos_2 = st.selectbox(
        "Ile pozycji z max T+1:", 
        options=[1, 2, 3, 4, 5, 6, 7, 8, 10], 
        index=4,
        key="wf2_toppos"
    )
with col_c4:
    top_n_freq = st.slider(
        "Ile najczęstszych liczb (TOP):", 
        min_value=1, 
        max_value=10, 
        value=5, 
        step=1,
        key="wf2_topfreq"
    )

total_needed_2 = int(window_len_2) + int(backtest_steps_2)

if len(df) < total_needed_2:
    st.warning(
        f"Zbyt mało losowań w bazie danych ({len(df)}) do wykonania testu {backtest_steps_2} kroków "
        f"z oknem {window_len_2} (potrzeba łącznie {total_needed_2} losowań). "
        f"Zmniejsz liczbę kroków lub rozmiar okna."
    )
else:
    eval_df = df.tail(total_needed_2).reset_index(drop=True)
    
    simulation_rows = []
    pos_hits_all = 0
    pos_picks_all = 0
    freq_hits_all = 0
    freq_picks_all = 0
    combined_hits_all = 0
    combined_picks_all = 0

    for step in range(backtest_steps_2):
        win = eval_df.iloc[step : step + window_len_2].reset_index(drop=True)
        target = eval_df.iloc[step + window_len_2]
        target_set = target["numbers_set"]
        
        win_sets = win["numbers_set"].tolist()
        transitions_in_win = len(win) - 1
        pos_stats_window = []
        last_draw_in_win = win.iloc[-1]
        
        for p in range(1, 21):
            col = f"pos_{p}"
            pos_vals = win[col].tolist()
            
            t1_count = 0
            for k in range(transitions_in_win):
                if pos_vals[k] in win_sets[k + 1]:
                    t1_count += 1
            
            pct = (t1_count / transitions_in_win * 100) if transitions_in_win > 0 else 0.0
            current_val = last_draw_in_win[col]
            
            pos_stats_window.append({
                "pos_nr": p,
                "label": f"Poz. {p:02d}",
                "hits_t1": t1_count,
                "pct": pct,
                "last_val": current_val
            })
            
        pos_stats_sorted = sorted(pos_stats_window, key=lambda x: (x["hits_t1"], x["pct"]), reverse=True)
        chosen_top_pos = pos_stats_sorted[:top_n_pos_2]
        picks_pos = [x["last_val"] for x in chosen_top_pos]
        
        all_window_numbers = [n for sub in win["numbers_list"] for n in sub]
        freq_series = pd.Series(all_window_numbers).value_counts()
        picks_freq = freq_series.head(top_n_freq).index.tolist()
        
        combined_picks = sorted(list(set(picks_pos).union(set(picks_freq))))
        
        hits_pos = sorted(list(set(picks_pos).intersection(target_set)))
        hits_freq = sorted(list(set(picks_freq).intersection(target_set)))
        hits_combined = sorted(list(set(combined_picks).intersection(target_set)))
        
        pos_hits_all += len(hits_pos)
        pos_picks_all += len(picks_pos)
        
        freq_hits_all += len(hits_freq)
        freq_picks_all += len(picks_freq)
        
        combined_hits_all += len(hits_combined)
        combined_picks_all += len(combined_picks)

        simulation_rows.append({
            "Krok": step + 1,
            f"Okno ({window_len_2})": f"#{win.iloc[0]['draw_id']}–#{win.iloc[-1]['draw_id']}",
            "Testowane T+1": f"#{target['draw_id']}",
            "Typy Pozycje T+1": ", ".join(f"{n:02d}" for n in picks_pos),
            "Trafione Pozycje": ", ".join(f"{n:02d}" for n in hits_pos) if hits_pos else "—",
            "Trafienia Pozycji": f"{len(hits_pos)}/{len(picks_pos)}",
            "Typy Najczęstsze": ", ".join(f"{n:02d}" for n in picks_freq),
            "Trafione Najczęstsze": ", ".join(f"{n:02d}" for n in hits_freq) if hits_freq else "—",
            "Trafienia Najczęstszych": f"{len(hits_freq)}/{len(picks_freq)}",
            "Trafienia Razem (Suma)": f"{len(hits_combined)}/{len(combined_picks)}"
        })

    expected_pct = (20 / 70) * 100
    
    pos_pct = (pos_hits_all / pos_picks_all) * 100 if pos_picks_all > 0 else 0
    freq_pct = (freq_hits_all / freq_picks_all) * 100 if freq_picks_all > 0 else 0
    comb_pct = (combined_hits_all / combined_picks_all) * 100 if combined_picks_all > 0 else 0

    m1, m2, m3 = st.columns(3)
    m1.metric(
        f"Skuteczność: Pozycje T+1 (TOP {top_n_pos_2})", 
        f"{pos_pct:.1f}%", 
        delta=f"{pos_pct - expected_pct:+.1f}% vs norma losowa (28.6%)"
    )
    m2.metric(
        f"Skuteczność: Najczęstsze (TOP {top_n_freq})", 
        f"{freq_pct:.1f}%", 
        delta=f"{freq_pct - expected_pct:+.1f}% vs norma losowa (28.6%)"
    )
    m3.metric(
        "Skuteczność: Pula Razem (Unikalne)", 
        f"{comb_pct:.1f}%", 
        delta=f"{comb_pct - expected_pct:+.1f}% vs norma losowa (28.6%)"
    )

    st.write("**Szczegółowa tabela porównawcza krok po kroku:**")
    df_sim_results = pd.DataFrame(simulation_rows)
    
    st.dataframe(
        df_sim_results,
        column_config={
            "Krok": st.column_config.NumberColumn("Krok", width="small"),
            f"Okno ({window_len_2})": st.column_config.TextColumn(f"Okno ({window_len_2})", width="medium"),
            "Testowane T+1": st.column_config.TextColumn("Losowanie T+1", width="small"),
            "Typy Pozycje T+1": st.column_config.TextColumn("Typy Pozycje", width="medium"),
            "Trafione Pozycje": st.column_config.TextColumn("Trafione z Pozycji", width="medium"),
            "Trafienia Pozycji": st.column_config.TextColumn("Wynik Pozycji", width="small"),
            "Typy Najczęstsze": st.column_config.TextColumn("Typy Najczęstsze", width="medium"),
            "Trafione Najczęstsze": st.column_config.TextColumn("Trafione z Najczęstszych", width="medium"),
            "Trafienia Najczęstszych": st.column_config.TextColumn("Wynik Najczęstszych", width="small"),
            "Trafienia Razem (Suma)": st.column_config.TextColumn("Trafienia Razem", width="small")
        },
        use_container_width=True,
        hide_index=True,
        height=500
    )


# =====================================================================
# MODUŁ: KORELACJA KRZYŻOWA (PRECYZYJNY WYBÓR POJEDYNCZYCH WARTOŚCI)
# =====================================================================
st.divider()
st.subheader("🎯 Filtr Korelacji Krzyżowej (Precyzyjny wybór wartości)")
st.caption(
    "Wybierz konkretne poziomy Trafień T+1 oraz krotności Mody z listy, a także określ dokładny limit typowanych liczb."
)

col_k1, col_k2 = st.columns(2)
with col_k1:
    backtest_steps_3 = st.slider(
        "Liczba kroków testowych (przesunięć):",
        min_value=10,
        max_value=min(300, max(10, len(df) - 51)),
        value=min(200, max(10, len(df) - 51)),
        step=10,
        key="cross_steps_multi"
    )
with col_k2:
    window_len_3 = st.number_input(
        "Wielkość okna (losowań wstecz):",
        min_value=5,
        max_value=100,
        value=20,
        step=5,
        key="cross_win_multi"
    )

col_s1, col_s2, col_s3 = st.columns(3)

with col_s1:
    selected_t1 = st.multiselect(
        "Wybierz konkretne Trafienia T+1:",
        options=[10, 9, 8, 7, 6, 5, 4, 3, 2, 1],
        default=[7, 8],
        help="Zaznacz poszczególne wartości, np. 7 i 8"
    )

with col_s2:
    selected_modes = st.multiselect(
        "Wybierz krotności Mody (x):",
        options=[10, 9, 8, 7, 6, 5, 4, 3, 2, 1],
        default=[5, 6],
        help="Zaznacz poszczególne krotności powtórzeń, np. 5 i 6"
    )

with col_s3:
    max_picks_limit = st.number_input(
        "Ile maksymalnie liczb/pozycji typować:",
        min_value=1,
        max_value=20,
        value=2,
        step=1,
        help="Ogranicza liczbę typowanych kul, jeśli warunek spełni więcej pozycji."
    )

exclude_edges = st.checkbox("Wyklucz pozycje skrajne (Poz. 01 i Poz. 20)", value=True, key="chk_edges_multi")

total_needed_3 = int(window_len_3) + int(backtest_steps_3)

if len(df) < total_needed_3:
    st.warning(
        f"Zbyt mało losowań w bazie danych ({len(df)}) do wykonania testu {backtest_steps_3} kroków "
        f"z oknem {window_len_3}. Zmniejsz liczbę kroków lub rozmiar okna."
    )
elif not selected_t1 or not selected_modes:
    st.info("Wybierz przynajmniej jedną wartość z listy Trafień T+1 oraz przynajmniej jedną krotność Mody.")
else:
    eval_df = df.tail(total_needed_3).reset_index(drop=True)

    sim_rows = []
    total_picks = 0
    total_hits = 0
    active_steps_count = 0

    for step in range(backtest_steps_3):
        win = eval_df.iloc[step : step + window_len_3].reset_index(drop=True)
        target = eval_df.iloc[step + window_len_3]
        target_set = target["numbers_set"]
        last_draw_win = win.iloc[-1]
        
        win_sets = win["numbers_set"].tolist()
        transitions_in_win = len(win) - 1

        matching_positions = []

        start_p = 2 if exclude_edges else 1
        end_p = 20 if exclude_edges else 21

        for p in range(start_p, end_p):
            col = f"pos_{p}"
            pos_vals = win[col].tolist()

            t1_count = 0
            for k in range(transitions_in_win):
                if pos_vals[k] in win_sets[k + 1]:
                    t1_count += 1

            series = win[col]
            mode_val = series.mode().iloc[0]
            mode_count = int((series == mode_val).sum())

            if (t1_count in selected_t1) and (mode_count in selected_modes):
                matching_positions.append({
                    "pos_nr": p,
                    "pos_label": f"Poz. {p:02d}",
                    "current_val": last_draw_win[col],
                    "t1_hits": t1_count,
                    "mode_count": mode_count,
                    "mode_val": mode_val
                })

        matching_positions.sort(key=lambda x: (x["t1_hits"], x["mode_count"]), reverse=True)
        chosen_positions = matching_positions[:int(max_picks_limit)]

        picks = [item["current_val"] for item in chosen_positions]
        pos_names = [f"{item['pos_label']} (T1:{item['t1_hits']}, x{item['mode_count']})" for item in chosen_positions]

        hits = sorted(list(set(picks).intersection(target_set)))
        hit_cnt = len(hits)
        picks_cnt = len(picks)

        if picks_cnt > 0:
            active_steps_count += 1
            total_picks += picks_cnt
            total_hits += hit_cnt
            pct_step = (hit_cnt / picks_cnt) * 100
        else:
            pct_step = 0.0

        sim_rows.append({
            "Krok": step + 1,
            f"Okno ({window_len_3})": f"#{win.iloc[0]['draw_id']}–#{win.iloc[-1]['draw_id']}",
            "Testowane T+1": f"#{target['draw_id']}",
            "Dopasowane pozycje": ", ".join(pos_names) if pos_names else "Brak dopasowania",
            "Typowane kule": ", ".join(f"{n:02d}" for n in picks) if picks else "—",
            "Trafione kule": ", ".join(f"{n:02d}" for n in hits) if hits else "—",
            "Wynik": f"{hit_cnt} / {picks_cnt}" if picks_cnt > 0 else "0 / 0",
            "Skuteczność": f"{pct_step:.0f}%" if picks_cnt > 0 else "—",
            "_picks_cnt": picks_cnt
        })

    expected_pct = (20 / 70) * 100
    actual_pct = (total_hits / total_picks * 100) if total_picks > 0 else 0.0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric(
        "Skuteczność typowanych kul",
        f"{actual_pct:.1f}%",
        delta=f"{actual_pct - expected_pct:+.1f}% vs norma (28.6%)"
    )
    m2.metric(
        "Kroki z dopasowaniem",
        f"{active_steps_count} / {backtest_steps_3}",
        f"{(active_steps_count / backtest_steps_3) * 100:.1f}% losowań"
    )
    m3.metric("Łącznie sprawdzonych kul", f"{total_picks} szt.")
    m4.metric("Łącznie trafionych kul", f"{total_hits} szt.")

    df_sim_cross = pd.DataFrame(sim_rows).drop(columns=["_picks_cnt"])

    show_only_active = st.checkbox("Pokaż tylko kroki, w których znaleziono dopasowania", value=False)
    if show_only_active:
        df_sim_cross = df_sim_cross[df_sim_cross["Dopasowane pozycje"] != "Brak dopasowania"].reset_index(drop=True)

    st.dataframe(
        df_sim_cross,
        column_config={
            "Krok": st.column_config.NumberColumn("Krok", width="small"),
            f"Okno ({window_len_3})": st.column_config.TextColumn(f"Okno ({window_len_3})", width="medium"),
            "Testowane T+1": st.column_config.TextColumn("Losowanie T+1", width="small"),
            "Dopasowane pozycje": st.column_config.TextColumn("Wybrane pozycje i ich cechy", width="large"),
            "Typowane kule": st.column_config.TextColumn("Typowane kule", width="medium"),
            "Trafione kule": st.column_config.TextColumn("Trafione kule", width="medium"),
            "Wynik": st.column_config.TextColumn("Wynik", width="small"),
            "Skuteczność": st.column_config.TextColumn("Skuteczność %", width="small")
        },
        use_container_width=True,
        hide_index=True,
        height=520
    )


# =====================================================================
# WERYFIKACJA POWTÓRZEŃ DLA 2 I 3 POZYCJI
# =====================================================================
st.divider()
st.subheader("🔬 Weryfikacja powtórzeń dla 2 i 3 pozycji")

col_opt, col_custom = st.columns([1.5, 1])

with col_opt:
    draws_choice = st.radio(
        "Wybierz zakres analizy losowań:",
        options=["300", "500", "1000", "Własna wartość"],
        horizontal=True,
        index=1,  # Domyślnie 500
        key="draws_choice_radio"
    )

with col_custom:
    if draws_choice == "Własna wartość":
        chosen_limit = st.number_input(
            "Wpisz ręcznie ilość losowań:",
            min_value=10,
            max_value=max(10, len(df)),
            value=min(600, len(df)),
            step=50,
            key="custom_draws_input"
        )
    else:
        chosen_limit = int(draws_choice)

available_total = len(df)
effective_limit = min(chosen_limit, available_total)
target_data = df.tail(effective_limit).reset_index(drop=True)
total_rows = len(target_data)

col_k, col_info = st.columns([1, 2])
with col_k:
    k_target = st.radio(
        "Wielkość badanego zestawu pozycji:",
        options=[2, 3],
        horizontal=True,
        key="k_target_selector"
    )

with col_info:
    if chosen_limit > available_total:
        st.warning(f"Żądano **{chosen_limit}**, ale w bazie jest obecnie **{available_total}** losowań. Analizowane wiersze: **{total_rows}** (przejść T ➔ T+1: **{total_rows - 1}**).")
    else:
        st.info(f"Analizowana baza losowań: **{total_rows}** wierszy (przejść T ➔ T+1: **{total_rows - 1}**).")


from collections import defaultdict
from itertools import combinations
combo_appearances = defaultdict(list)

for idx in range(total_rows - 1):
    curr_nums = target_data.iloc[idx]["numbers_list"]
    next_set = target_data.iloc[idx + 1]["numbers_set"]
    
    hits = [i + 1 for i, n in enumerate(curr_nums) if n in next_set]
    
    if len(hits) >= k_target:
        for combo in combinations(hits, k_target):
            combo_appearances[combo].append(idx)

results = []
for combo, indices in combo_appearances.items():
    cnt = len(indices)
    if cnt >= 2:
        gaps = [indices[i+1] - indices[i] for i in range(len(indices)-1)]
        min_g = min(gaps)
        max_g = max(gaps)
        avg_g = round(sum(gaps) / len(gaps), 1)
    elif cnt == 1:
        min_g, max_g, avg_g = "-", "-", "-"
    else:
        continue

    results.append({
        f"Zestaw {k_target} pozycji": ", ".join(f"Poz. {p:02d}" for p in combo),
        "Ilość trafień": cnt,
        "Odstęp minimalny": min_g,
        "Odstęp średni": avg_g,
        "Odstęp maksymalny": max_g,
        "raw_count": cnt
    })

df_res = pd.DataFrame(results)

if not df_res.empty:
    df_res = df_res.sort_values(by="raw_count", ascending=False).drop(columns=["raw_count"])
    st.dataframe(df_res, use_container_width=True, hide_index=True)
else:
    st.warning("Brak danych do wyświetlenia.")


# =====================================================================
# DRUGA TABELA: SZCZEGÓŁOWA SPRAWDZARKA WYBRANYCH POZYCJI
# =====================================================================
st.divider()
st.subheader("🎯 Sprawdzarka dowolnego zestawu 2 lub 3 pozycji (Odstępy, Dni i Oczekiwanie)")

available_positions = [f"Poz. {i:02d}" for i in range(1, 21)]
selected_pos_labels = st.multiselect(
    "Wybierz 2 lub 3 pozycje do zbadania:",
    options=available_positions,
    default=["Poz. 09", "Poz. 17"],
    max_selections=3,
    help="Możesz wybrać 2 pozycje (np. 9 i 17) albo dobrać trzecią pozycję.",
    key="pos_multiselect_checker"
)

if len(selected_pos_labels) < 2:
    st.info("Wybierz co najmniej 2 pozycje, aby rozpocząć analizę.")
else:
    selected_indices = [int(p.replace("Poz. ", "")) for p in selected_pos_labels]
    
    occurrences = []
    
    for idx in range(total_rows - 1):
        curr_row = target_data.iloc[idx]
        next_set = target_data.iloc[idx + 1]["numbers_set"]
        nums = curr_row["numbers_list"]
        
        all_hit = True
        hit_details = {}
        for pos_num in selected_indices:
            ball = nums[pos_num - 1]
            if ball in next_set:
                hit_details[f"Kula Poz. {pos_num:02d}"] = ball
            else:
                all_hit = False
                break
                
        if all_hit:
            hit_record = {
                "idx": idx,
                "draw_id": curr_row["draw_id"],
                "draw_time": curr_row.get("draw_time", "--:--"),
                "total_squares": sum(1 for n in nums if n in next_set)
            }
            hit_record.update(hit_details)
            occurrences.append(hit_record)
            
    timeline = []
    gaps_draws = []
    
    for i in range(len(occurrences)):
        curr = occurrences[i]
        if i > 0:
            prev = occurrences[i - 1]
            gap_draws = curr["idx"] - prev["idx"]
            gaps_draws.append(gap_draws)
            gap_days = round(gap_draws / 260.0, 2)
            gap_draws_str = str(gap_draws)
            gap_days_str = f"~{gap_days:.2f} dn."
        else:
            gap_draws_str = "— (pierwsze)"
            gap_days_str = "— (start)"
            
        row_entry = {
            "Nr trafienia": i + 1,
            "Losowanie bazowe": f"#{curr['draw_id']} ({curr['draw_time']})",
            "Łącznie kwadratów": curr["total_squares"]
        }
        for pos_num in selected_indices:
            row_entry[f"Kula Poz. {pos_num:02d}"] = curr[f"Kula Poz. {pos_num:02d}"]
            
        row_entry["Odstęp (losowań)"] = gap_draws_str
        row_entry["Odstęp (dni)"] = gap_days_str
        timeline.append(row_entry)
        
    df_timeline = pd.DataFrame(timeline)
    
    last_evaluated_idx = total_rows - 2
    
    if occurrences:
        last_hit_idx = occurrences[-1]["idx"]
        current_wait_draws = last_evaluated_idx - last_hit_idx
        current_wait_days = round(current_wait_draws / 260.0, 2)
        last_hit_label = f"#{occurrences[-1]['draw_id']} ({occurrences[-1]['draw_time']})"
    else:
        current_wait_draws = max(0, total_rows - 1)
        current_wait_days = round(current_wait_draws / 260.0, 2)
        last_hit_label = "Brak w wybranym zakresie"

    k_name = ", ".join(selected_pos_labels)
    st.write(f"### Zestaw: **{k_name}**")
    
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Łącznie trafień", f"{len(df_timeline)} razy")
    
    if gaps_draws:
        avg_gap = round(sum(gaps_draws) / len(gaps_draws), 1)
        avg_days = round(avg_gap / 260.0, 2)
        diff_from_avg = round(current_wait_draws - avg_gap, 1)
        
        m2.metric("Odstęp minimalny", f"{min(gaps_draws)} los.")
        m3.metric("Odstęp średni", f"{avg_gap} los. (~{avg_days} dn.)")
        m4.metric("Odstęp maksymalny", f"{max(gaps_draws)} los.")
        m5.metric(
            "Aktualne oczekiwanie",
            f"{current_wait_draws} los. (~{current_wait_days} dn.)",
            delta=f"{diff_from_avg:+} los. vs średnia",
            delta_color="inverse"
        )
    else:
        m2.metric("Odstęp minimalny", "—")
        m3.metric("Odstęp średni", "—")
        m4.metric("Odstęp maksymalny", "—")
        m5.metric("Aktualne oczekiwanie", f"{current_wait_draws} losowań")

    st.caption(f"ℹ️ Ostatnie trafienie zestawu: **{last_hit_label}** | Ostatnie zbadane losowanie w bazie: **#{target_data.iloc[-1]['draw_id']}**")
    
    st.write("")
    if not df_timeline.empty:
        st.dataframe(df_timeline.iloc[::-1].reset_index(drop=True), use_container_width=True, hide_index=True)
    else:
        st.warning(f"Zestaw {k_name} nie trafił wspólnie ani razu w wybranym zakresie losowań.")
