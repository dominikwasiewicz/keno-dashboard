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
# MODUŁ ALGORYTMU PREDYKCYJNEGO V17:
# 1) WIELOKOLUMNOWA MACIERZ "ZŁOTYCH LOKAT" DLA WSZYSTKICH 9 OKIEN NARAZ (5, 6, 7, 8, 9, 10, 12, 15, 20)
# 2) POD KAŻDĄ KOLUMNĄ OKNA: SZCZEGÓŁOWA HISTORIA OSTATNICH 30 LOSOWAŃ (TRAFIENIA NA ŻYWO 🟩)
# 3) AUTOMATYCZNE WYRÓŻNIENIE 🥇 1. MIEJSCA ORAZ 🥈 2. MIEJSCA WG TRAFIEŃ Z OSTATNICH 10 LOSOWAŃ
# =====================================================================
from collections import defaultdict

def render_prediction_algorithm(df_full, default_window=8, default_blue_win=8, default_backtest=10):
    st.divider()
    st.header("🧠 Algorytm V17: Tablica Złotych Lokat dla Wszystkich Okien (5–20) + Historia 30 Losowań")

    all_windows = [5, 6, 7, 8, 9, 10, 12, 15, 20]
    matrix_bt_steps = 30
    recent_rank_steps = 10

    if len(df_full) < 40 + matrix_bt_steps:
        st.warning(f"Za mało danych w bazie ({len(df_full)}), aby zbudować pełną macierz 30 losowań dla okien 5–20.")
        return

    all_lists = df_full["numbers_list"].tolist()
    all_sets = df_full["numbers_set"].tolist()
    all_ids = df_full["draw_id"].tolist()
    all_times = df_full["draw_time"].tolist()
    total_draws = len(df_full)
    latest_idx = total_draws - 1

    # =================================================================
    # SILNIK V17: LICZY ZŁOTE LOKATY I TOP 5 DLA DOWOLNEGO OKNA (w_size, b_lookback)
    # =================================================================
    def run_engine_v17(w_size, b_lookback, steps_to_test):
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

                orig_bwin_cnt = orig_pos_hits_bwin[pos_nr]
                orig_bwin_rate = orig_bwin_cnt / max(1, blue_steps_avail)
                o_r2 = orig_pos_rec2[pos_nr]
                o_r3 = orig_pos_rec3[pos_nr]

                in_prev1 = (ball in prev_set)
                in_prev2 = (ball in prev2_set)
                exact_same_pos_in_t1 = (t_idx >= 1 and prev_list[p_i] == ball)

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

                eff_pos_white_hits = max(pos_white_hits, int(round(source_white_hits * 0.80))) if is_transfer_from_strong_pos else pos_white_hits
                eff_pos_white_rate = eff_pos_white_hits / trans_count
                eff_w15_hits = max(w15_hits, source_w15_hits) if is_transfer_from_strong_pos else w15_hits

                sq_d1 = sq_1_ago[pos_nr]
                sq_d2 = sq_2_ago[pos_nr]
                sq_n1 = sq_1_ago.get(pos_nr - 1, False) or sq_1_ago.get(pos_nr + 1, False)

                b_u1 = prev1_blue_hits.get(m_col, False)
                b_adj1 = prev1_blue_hits.get(m_col - 1, False) or prev1_blue_hits.get(m_col + 1, False)

                ball_freq_in_win = win_ball_freq[ball]
                ball_t1_in_win = win_ball_t1_repeats[ball]
                ball_t1_15 = ball_15_t1_repeats[ball]

                is_dead_blue_col = (b_hit_rate < 0.25 and b_r2 == 0)
                has_recent_activity = (o_r2 >= 1) or (b_r2 >= 1) or sq_d1 or b_u1 or is_transfer_from_strong_pos

                is_top_w15_leader = (w15_hits >= max(4, max_w15_in_draw - 1))
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
                    verdict_str = "👑 POTWIERDZONA SERIA (🔴+⬜)"
                elif is_transfer_from_strong_pos and not is_very_weak_in_15:
                    is_disqualified = False
                    verdict_str = f"🔄 Transfer Serii 🔴 z Poz.{source_pos:02d} ({source_white_hits}/{trans_count}⬜)"
                elif is_top_w15_leader and has_recent_activity and not is_dead_blue_col:
                    is_disqualified = False
                    verdict_str = f"🏆 Lider Tabeli 15 ({w15_hits}/{n15_trans_now} ⬜)"
                else:
                    if is_very_weak_in_15:
                        is_disqualified = True
                        verdict_str = f"❌ Słaba w Tab.15 ({w15_hits}/{n15_trans_now} ⬜)"
                    elif o_r2 == 0 and b_r2 == 0:
                        is_disqualified = True
                        verdict_str = "❄️ Wygasła (0 traf. w 2 ost.)"
                    elif is_dead_blue_col and not sq_d1:
                        is_disqualified = True
                        verdict_str = f"❌ Zimna Kolumna 🟦M.{m_col:02d} ({b_hits_cnt}/{blue_steps_avail})"
                    elif not has_strong_base:
                        is_disqualified = True
                        verdict_str = f"❌ Słaba baza Poz.{pos_nr:02d} ({pos_white_hits}/{trans_count}⬜)"
                    elif o_r3 == 0 and b_r3 == 0:
                        is_disqualified = True
                        verdict_str = "❄️ Martwa od 3 gier"

                if 0.35 <= eff_pos_white_rate <= 0.64:
                    pts_white_pos = 22.0
                elif eff_pos_white_rate > 0.64:
                    pts_white_pos = 17.5
                else:
                    pts_white_pos = min(17.0, (eff_pos_white_rate / 0.35) * 17.0)

                w15_rel_ratio = eff_w15_hits / max(1.0, float(max_w15_in_draw))
                pts_w15_stability = round(min(12.0, w15_rel_ratio * 12.0), 1) if eff_w15_hits >= 3 else 0.0

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

                mode_on_pos, mode_cnt_on_pos = pos_modes_now[pos_nr]
                is_exact_mode = (ball == mode_on_pos and mode_cnt_on_pos >= min_thr)
                pts_mode = 9.0 if (is_exact_mode and not is_disqualified) else (5.0 if (ball in all_modes_set_now and not is_disqualified) else 0.0)
                mode_str = f"🎯 Lider Poz.{pos_nr:02d} (x{mode_cnt_on_pos})" if is_exact_mode else ("⭐ W 'Najczęstszej'" if ball in all_modes_set_now else "-")

                pts_ball_t1 = min(13.0, (ball_t1_in_win * 5.0) + (ball_t1_15 * 2.5))
                score_ball_power = round(min(22.0, pts_mode + pts_ball_t1), 1)

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
                    "Status V17": verdict_str,
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
    # OBLICZANIE MACIERZY 9 OKIEN (5, 6, 7, 8, 9, 10, 12, 15, 20) NA 30 LOSOWAŃ WSTECZ!
    # =====================================================================
    win_scorers = {}
    win_live_gold = {}
    win_history_cells = {w: [] for w in all_windows}
    win_stats_10 = {w: {"any_games": 0, "total_balls": 0, "l1_hits": 0, "l2_hits": 0} for w in all_windows}
    win_stats_30 = {w: {"any_games": 0, "total_balls": 0, "l1_hits": 0, "l2_hits": 0} for w in all_windows}

    for w_val in all_windows:
        sc_fn = run_engine_v17(w_val, w_val, matrix_bt_steps)
        win_scorers[w_val] = sc_fn
        _, df_bg_now, _, _, _, _ = sc_fn(latest_idx)
        win_live_gold[w_val] = (df_bg_now.iloc[0], df_bg_now.iloc[1])

        for step_i, step_t in enumerate(range(latest_idx - 1, latest_idx - 1 - matrix_bt_steps, -1)):
            _, df_bg_step, _, _, _, _ = sc_fn(step_t)
            nxt_s = all_sets[step_t + 1]

            r1 = df_bg_step.iloc[0]
            r2 = df_bg_step.iloc[1]
            b1, m1, p1 = int(r1["Liczba"]), int(r1["blue_m"]), int(r1["pos_nr"])
            b2, m2, p2 = int(r2["Liczba"]), int(r2["blue_m"]), int(r2["pos_nr"])

            h1 = (b1 in nxt_s)
            h2 = (b2 in nxt_s)

            if h1:
                win_stats_30[w_val]["l1_hits"] += 1
                win_stats_30[w_val]["total_balls"] += 1
            if h2:
                win_stats_30[w_val]["l2_hits"] += 1
                win_stats_30[w_val]["total_balls"] += 1
            if h1 or h2:
                win_stats_30[w_val]["any_games"] += 1

            if step_i < recent_rank_steps:
                if h1:
                    win_stats_10[w_val]["l1_hits"] += 1
                    win_stats_10[w_val]["total_balls"] += 1
                if h2:
                    win_stats_10[w_val]["l2_hits"] += 1
                    win_stats_10[w_val]["total_balls"] += 1
                if h1 or h2:
                    win_stats_10[w_val]["any_games"] += 1

            win_history_cells[w_val].append({
                "b1": b1, "m1": m1, "p1": p1, "h1": h1,
                "b2": b2, "m2": m2, "p2": p2, "h2": h2,
            })

    # =====================================================================
    # WYŁONIENIE 🥇 1. MIEJSCA I 🥈 2. MIEJSCA WG TRAFIEŃ W OSTATNICH 10 LOSOWANIACH!
    # =====================================================================
    ranked_windows = sorted(
        all_windows,
        key=lambda w: (
            win_stats_10[w]["any_games"],
            win_stats_10[w]["total_balls"],
            win_stats_30[w]["any_games"],
            win_stats_30[w]["total_balls"]
        ),
        reverse=True
    )
    first_place_win = ranked_windows[0]
    second_place_win = ranked_windows[1]

    # Zliczamy, które kule pojawiają się najczęściej w Złotych Lokatach wszystkich 9 okien naraz!
    consensus_counter = defaultdict(list)
    for w_val in all_windows:
        g1_r, g2_r = win_live_gold[w_val]
        consensus_counter[int(g1_r["Liczba"])].append(f"Okno {w_val}")
        consensus_counter[int(g2_r["Liczba"])].append(f"Okno {w_val}")

    sorted_consensus = sorted(consensus_counter.items(), key=lambda x: len(x[1]), reverse=True)
    consensus_str_list = [f"<b>{b:02d}</b> ({len(w_list)}x: {', '.join(w_list)})" for b, w_list in sorted_consensus[:4]]
    consensus_html = " &nbsp;|&nbsp; ".join(consensus_str_list)

    fp_g1, fp_g2 = win_live_gold[first_place_win]
    sp_g1, sp_g2 = win_live_gold[second_place_win]

    # =====================================================================
    # KAFELEK PODIUM (1. MIEJSCE I 2. MIEJSCE Z OSTATNICH 10 LOSOWAŃ + PEWNIAKI WIELOOKIENKOWE)
    # =====================================================================
    podium_banner_html = (
        f"<div style='background: linear-gradient(135deg, rgba(16, 48, 36, 0.96) 0%, rgba(12, 30, 24, 0.98) 100%); "
        f"border: 2px solid #ffd166; border-radius: 12px; padding: 14px 18px; margin-bottom: 14px; "
        f"box-shadow: 0 4px 16px rgba(255, 209, 102, 0.22); font-family: sans-serif;'>"
        f"<div style='font-size: 13px; font-weight: bold; color: #ffd166; text-transform: uppercase; margin-bottom: 10px;'>"
        f"🏆 PODIUM OKIEN WG OSTATNICH 10 LOSOWAŃ (Na losowanie po #{all_ids[latest_idx]} — godz. {all_times[latest_idx]}):"
        f"</div>"
        f"<div style='display: flex; flex-wrap: wrap; gap: 14px; align-items: center; margin-bottom: 10px;'>"
        # 1. Miejsce
        f"<div style='display: inline-flex; align-items: center; gap: 10px; background: rgba(255, 209, 102, 0.16); "
        f"border: 2.5px solid #ffd166; border-radius: 10px; padding: 8px 14px; box-shadow: 0 0 12px rgba(255, 209, 102, 0.35);'>"
        f"<span style='font-size: 15px; color: #ffd166; font-weight: 900;'>🥇 1. MIEJSCE: OKNO {first_place_win} "
        f"({win_stats_10[first_place_win]['any_games']}/10 gier — {win_stats_10[first_place_win]['any_games']*10}%) ➔</span>"
        f"<span style='font-size: 26px; font-weight: 900; color: #ffffff; background: #e63946; padding: 2px 10px; border-radius: 7px; border: 2px solid #ffd166;'>"
        f"{int(fp_g1['Liczba']):02d}</span>"
        f"<span style='font-size: 26px; font-weight: 900; color: #ffffff; background: #e63946; padding: 2px 10px; border-radius: 7px; border: 2px solid #ffd166;'>"
        f"{int(fp_g2['Liczba']):02d}</span>"
        f"</div>"
        # 2. Miejsce
        f"<div style='display: inline-flex; align-items: center; gap: 10px; background: rgba(0, 230, 118, 0.14); "
        f"border: 2.5px solid #00e676; border-radius: 10px; padding: 8px 14px; box-shadow: 0 0 10px rgba(0, 230, 118, 0.3);'>"
        f"<span style='font-size: 15px; color: #00e676; font-weight: 900;'>🥈 2. MIEJSCE: OKNO {second_place_win} "
        f"({win_stats_10[second_place_win]['any_games']}/10 gier — {win_stats_10[second_place_win]['any_games']*10}%) ➔</span>"
        f"<span style='font-size: 26px; font-weight: 900; color: #ffffff; background: #0077b6; padding: 2px 10px; border-radius: 7px; border: 2px solid #00e676;'>"
        f"{int(sp_g1['Liczba']):02d}</span>"
        f"<span style='font-size: 26px; font-weight: 900; color: #ffffff; background: #0077b6; padding: 2px 10px; border-radius: 7px; border: 2px solid #00e676;'>"
        f"{int(sp_g2['Liczba']):02d}</span>"
        f"</div>"
        f"</div>"
        f"<div style='font-size: 13px; color: #e6e6e6; padding-top: 6px; border-top: 1px solid rgba(255,255,255,0.15);'>"
        f"🔥 <b>Kule powtarzające się w wielu oknach naraz (Konsensus 9 okien):</b> &nbsp; <span style='color:#ffd166;'>{consensus_html}</span>"
        f"</div>"
        f"</div>"
    )
    st.markdown(podium_banner_html, unsafe_allow_html=True)

    # =====================================================================
    # BUDOWA WIELOKOLUMNOWEJ TABELI HTML: 9 OKIEN (5-20) + 30 LOSOWAŃ HISTORII POD NIMI
    # =====================================================================
    st.subheader("📊 Złote Lokaty dla Wszystkich Okien (5, 6, 7, 8, 9, 10, 12, 15, 20) + Szczegółowa Historia 30 Losowań")
    st.caption(
        "🥇 **Złota Kolumna** = 1. miejsce w ostatnich 10 losowaniach | "
        "🥈 **Zielona Kolumna** = 2. miejsce w ostatnich 10 losowaniach | "
        "Wiersze nr 1–10 (górne) decydują o aktualnym Podium, a poniżej widać pełny przekrój do 30 losowań wstecz."
    )

    header_cols_html = []
    live_picks_cols_html = []
    stats_cols_html = []

    for w_val in all_windows:
        is_1st = (w_val == first_place_win)
        is_2nd = (w_val == second_place_win)

        if is_1st:
            th_style = "background: linear-gradient(180deg, #5c4508 0%, #2b2104 100%); border-top: 3px solid #ffd166; border-left: 2.5px solid #ffd166; border-right: 2.5px solid #ffd166; color: #ffd166;"
            badge_rank = "🥇 1. MIEJSCE<br>"
            live_bg = "background: rgba(255, 209, 102, 0.20); border-left: 2.5px solid #ffd166; border-right: 2.5px solid #ffd166;"
            stat_bg = "background: rgba(255, 209, 102, 0.14); border-left: 2.5px solid #ffd166; border-right: 2.5px solid #ffd166; border-bottom: 2px solid #ffd166;"
        elif is_2nd:
            th_style = "background: linear-gradient(180deg, #0b4f30 0%, #072919 100%); border-top: 3px solid #00e676; border-left: 2.5px solid #00e676; border-right: 2.5px solid #00e676; color: #00e676;"
            badge_rank = "🥈 2. MIEJSCE<br>"
            live_bg = "background: rgba(0, 230, 118, 0.18); border-left: 2.5px solid #00e676; border-right: 2.5px solid #00e676;"
            stat_bg = "background: rgba(0, 230, 118, 0.12); border-left: 2.5px solid #00e676; border-right: 2.5px solid #00e676; border-bottom: 2px solid #00e676;"
        else:
            th_style = "background-color: #161922; border-right: 1px solid #2d3340; color: #d0d7de;"
            badge_rank = ""
            live_bg = "background-color: #12151e; border-right: 1px solid #2d3340;"
            stat_bg = "background-color: #161922; border-right: 1px solid #2d3340; border-bottom: 2px solid #333945;"

        header_cols_html.append(
            f"<th style='padding: 6px 4px; text-align: center; font-size: 11px; min-width: 96px; {th_style}'>"
            f"{badge_rank}<span style='font-size:13px; font-weight:900;'>OKNO {w_val}</span>"
            f"</th>"
        )

        g1_r, g2_r = win_live_gold[w_val]
        b1_now, p1_now, m1_now = int(g1_r["Liczba"]), int(g1_r["pos_nr"]), int(g1_r["blue_m"])
        b2_now, p2_now, m2_now = int(g2_r["Liczba"]), int(g2_r["pos_nr"]), int(g2_r["blue_m"])

        b1_box_border = "#ffd166" if is_1st else ("#00e676" if is_2nd else "#e63946")
        b2_box_border = "#ffd166" if is_1st else ("#00e676" if is_2nd else "#0077b6")

        live_picks_cols_html.append(
            f"<td style='padding: 6px 4px; text-align: center; {live_bg}'>"
            f"<div style='font-size:9px; color:#b9f6ca; font-weight:bold; margin-bottom:3px;'>TERAZ W GRZE:</div>"
            f"<div style='display:flex; justify-content:center; gap:4px;'>"
            f"<div style='display:inline-flex; flex-direction:column; align-items:center; background:#e63946; border:1.5px solid {b1_box_border}; border-radius:6px; padding:2px 5px; min-width:38px;'>"
            f"<span style='font-size:15px; font-weight:900; color:#fff; line-height:16px;'>{b1_now:02d}</span>"
            f"<span style='font-size:8px; color:#ffe3e3; line-height:9px;'>P{p1_now:02d}|M{m1_now}</span>"
            f"</div>"
            f"<div style='display:inline-flex; flex-direction:column; align-items:center; background:#0077b6; border:1.5px solid {b2_box_border}; border-radius:6px; padding:2px 5px; min-width:38px;'>"
            f"<span style='font-size:15px; font-weight:900; color:#fff; line-height:16px;'>{b2_now:02d}</span>"
            f"<span style='font-size:8px; color:#caf0f8; line-height:9px;'>P{p2_now:02d}|M{m2_now}</span>"
            f"</div>"
            f"</div>"
            f"</td>"
        )

        s10_g = win_stats_10[w_val]["any_games"]
        s10_b = win_stats_10[w_val]["total_balls"]
        s30_g = win_stats_30[w_val]["any_games"]
        s30_b = win_stats_30[w_val]["total_balls"]
        s10_col = "#ffd166" if is_1st else ("#00e676" if is_2nd else "#ffffff")

        stats_cols_html.append(
            f"<td style='padding: 5px 4px; text-align: center; font-size: 10px; {stat_bg}'>"
            f"<div style='font-weight:900; color:{s10_col}; font-size:11px;'>Ost.10: {s10_g}/10 ({s10_g*10}%)</div>"
            f"<div style='color:#9da3af; font-size:9px;'>Kul w 10: <b>{s10_b}x</b></div>"
            f"<div style='color:#6c7385; font-size:9px; margin-top:2px; border-top:1px solid #262a34; padding-top:2px;'>Ost.30: {s30_g}/30 ({s30_g/30*100:.0f}%) | {s30_b}x</div>"
            f"</td>"
        )

    matrix_body_rows_html = []
    for step_i, step_t in enumerate(range(latest_idx - 1, latest_idx - 1 - matrix_bt_steps, -1)):
        row_cells = []
        is_tenth_divider = (step_i == recent_rank_steps - 1)
        row_border_bottom = "border-bottom: 3px dashed #ffd166;" if is_tenth_divider else "border-bottom: 1px solid #222630;"

        for w_val in all_windows:
            is_1st = (w_val == first_place_win)
            is_2nd = (w_val == second_place_win)
            c_info = win_history_cells[w_val][step_i]

            b1, m1, h1 = c_info["b1"], c_info["m1"], c_info["h1"]
            b2, m2, h2 = c_info["b2"], c_info["m2"], c_info["h2"]

            if is_1st:
                td_col_style = "background-color: rgba(255, 209, 102, 0.07); border-left: 2.5px solid #ffd166; border-right: 2.5px solid #ffd166;"
            elif is_2nd:
                td_col_style = "background-color: rgba(0, 230, 118, 0.06); border-left: 2.5px solid #00e676; border-right: 2.5px solid #00e676;"
            else:
                td_col_style = "border-right: 1px solid #232731;"

            if h1 and h2:
                td_col_style += " background-color: rgba(0, 230, 118, 0.22);"

            if h1:
                pill_1 = (
                    f"<span style='display:inline-block; padding:2px 5px; border:1.5px solid #00e676; border-radius:5px; "
                    f"background:rgba(0, 230, 118, 0.32); color:#ffffff; font-weight:900; font-size:12px; box-shadow:0 0 5px rgba(0,230,118,0.5);'>"
                    f"{b1:02d}<span style='font-size:8px; color:#b9f6ca;'>M{m1}</span></span>"
                )
            else:
                pill_1 = (
                    f"<span style='display:inline-block; padding:2px 4px; border:1px solid #2b303c; border-radius:5px; "
                    f"background:#141720; color:#7d8597; font-size:11px;'>"
                    f"{b1:02d}<span style='font-size:8px; color:#525866;'>M{m1}</span></span>"
                )

            if h2:
                pill_2 = (
                    f"<span style='display:inline-block; padding:2px 5px; border:1.5px solid #00e676; border-radius:5px; "
                    f"background:rgba(0, 230, 118, 0.32); color:#ffffff; font-weight:900; font-size:12px; box-shadow:0 0 5px rgba(0,230,118,0.5);'>"
                    f"{b2:02d}<span style='font-size:8px; color:#b9f6ca;'>M{m2}</span></span>"
                )
            else:
                pill_2 = (
                    f"<span style='display:inline-block; padding:2px 4px; border:1px solid #2b303c; border-radius:5px; "
                    f"background:#141720; color:#7d8597; font-size:11px;'>"
                    f"{b2:02d}<span style='font-size:8px; color:#525866;'>M{m2}</span></span>"
                )

            row_cells.append(
                f"<td style='padding: 4px 3px; text-align: center; white-space: nowrap; {td_col_style}'>"
                f"{pill_1} {pill_2}"
                f"</td>"
            )

        step_label = f"<span style='color:#ffd166; font-weight:bold;'>#{step_i+1}</span>" if step_i < 10 else f"<span style='color:#6c7385;'>#{step_i+1}</span>"
        row_html = f"""
        <tr style='{row_border_bottom}'>
            <td style='padding: 4px 6px; color: #9da3af; white-space: nowrap; font-size: 10px; position: sticky; left: 0; background-color: #12151e; z-index: 5; border-right: 2px solid #333945;'>
                {step_label} <b>#{all_ids[step_t + 1]}</b><br><span style='font-size:9px; color:#6c7385;'>z #{all_ids[step_t]} ({all_times[step_t]})</span>
            </td>
            {''.join(row_cells)}
        </tr>
        """
        matrix_body_rows_html.append(row_html)

    multi_win_matrix_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ margin: 0; padding: 0; background-color: #0e1117; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
            .matrix-wrap {{ max-height: 760px; overflow-y: auto; overflow-x: auto; border: 1.5px solid #333945; border-radius: 10px; }}
            table {{ width: 100%; border-collapse: collapse; }}
            thead {{ position: sticky; top: 0; z-index: 20; }}
        </style>
    </head>
    <body>
        <div class="matrix-wrap">
            <table>
                <thead>
                    <tr>
                        <th style="padding: 6px 8px; text-align: left; background-color: #161922; color: #ffd166; font-size: 11px; position: sticky; left: 0; z-index: 25; border-right: 2px solid #333945;">
                            OKNO ANALIZY ➔<br><span style="font-size:9px; color:#9da3af;">(Ranking z ost. 10 gier)</span>
                        </th>
                        {''.join(header_cols_html)}
                    </tr>
                    <tr>
                        <th style="padding: 6px 8px; text-align: left; background-color: #12151e; color: #00e676; font-size: 11px; position: sticky; left: 0; z-index: 25; border-right: 2px solid #333945;">
                            🎯 ZŁOTE LOKATY<br><span style="font-size:9px; color:#b9f6ca;">NA TERAZ (po #{all_ids[latest_idx]})</span>
                        </th>
                        {''.join(live_picks_cols_html)}
                    </tr>
                    <tr>
                        <th style="padding: 5px 8px; text-align: left; background-color: #161922; color: #e6e6e6; font-size: 10px; position: sticky; left: 0; z-index: 25; border-right: 2px solid #333945; border-bottom: 2px solid #333945;">
                            📈 STATYSTYKI<br><span style="font-size:9px; color:#9da3af;">Ost. 10 vs Ost. 30</span>
                        </th>
                        {''.join(stats_cols_html)}
                    </tr>
                </thead>
                <tbody>
                    {''.join(matrix_body_rows_html)}
                </tbody>
            </table>
        </div>
    </body>
    </html>
    """
    components.html(multi_win_matrix_html, height=780, scrolling=False)

    # =====================================================================
    # SZCZEGÓŁOWY RANKING 20 LICZB I TABELE TOP 5 (AUTOMATYCZNIE DLA 🥇 1. MIEJSCA LUB WYBRANEGO OKNA)
    # =====================================================================
    st.divider()
    st.subheader(f"🔍 Szczegółowy Rozbiór Wybranego Okna (Domyślnie 🥇 1. Miejsce = Okno {first_place_win})")

    col_s1, col_s2 = st.columns([1.2, 1.0])
    with col_s1:
        detail_win = st.radio(
            "⚙️ Wybierz okno do szczegółowego podglądu Tabeli 20 liczb i TOP 5 poniżej:",
            options=all_windows,
            index=all_windows.index(first_place_win),
            horizontal=True,
            key="v17_detail_win_radio"
        )
    with col_s2:
        detail_bt = st.radio(
            "🧪 Zakres dla dolnej tabeli TOP 5 (losowań):",
            options=[10, 15, 20, 30],
            index=0,
            horizontal=True,
            key="v17_detail_bt_radio"
        )

    active_scorer = win_scorers[detail_win]
    df_predictions, df_latest_blue_gold, latest_win_freq, latest_win_t1, latest_modes_set, _ = active_scorer(latest_idx)
    latest_curr_set = all_sets[latest_idx]

    top_5_Row = df_predictions.head(5)
    top_8_Row = df_predictions.head(8)

    col_pred_table, col_hot_all = st.columns([1.45, 0.95], gap="large")
    with col_pred_table:
        st.markdown(f"#### 📊 1. Pełny Ranking 20 liczb z #{all_ids[latest_idx]} (dla Okna = {detail_win})")
        df_display_pred = df_predictions.drop(
            columns=["pos_nr", "blue_m", "pos_white_hits", "trans_count", "pos_white_pct", "w15_hits", "b_hits_cnt", "orig_bwin_cnt", "b_steps", "b_hit_pct", "recent_sum", "gold_rank_score", "is_disq"]
        ).copy()
        st.dataframe(
            df_display_pred,
            column_config={
                "Pozycja": st.column_config.TextColumn("Poz. (🟦 Miejsce)", width="medium"),
                "Liczba": st.column_config.NumberColumn("Kula", width="small"),
                "Score": st.column_config.ProgressColumn("Siła (Score)", format="%.1f pkt", min_value=0, max_value=100),
                "Status V17": st.column_config.TextColumn("Status Weryfikacji", width="medium"),
                "⬜ Własne Poz. (i z 15)": st.column_config.TextColumn(f"⬜ Własne ({detail_win} i 15)", width="medium"),
                "🟦 Kolumna M (i Stałe)": st.column_config.TextColumn(f"🟦 Kolumna M ({detail_win})", width="medium"),
                "Pod pozycją (Węzeł)": st.column_config.TextColumn("Pod pozycją", width="medium"),
                "Powtórki Kuli T+1": st.column_config.TextColumn("Powt. Kuli", width="small"),
                "⭐ 'Najczęstsza'": st.column_config.TextColumn("⭐ 'Najczęstsza'", width="small"),
            },
            hide_index=True,
            use_container_width=True,
            height=520,
            key="pred_main_ranking_tbl_v17"
        )

    with col_hot_all:
        st.markdown(f"#### 🔥 2. Najczęściej losowane kule w oknie {detail_win}")
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
            key="hot_70_check_tbl_v17"
        )

# Wywołanie modułu V17:
render_prediction_algorithm(df, default_window=8, default_blue_win=8, default_backtest=10)
