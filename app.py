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
# MODUŁ ALGORYTMU PREDYKCYJNEGO V31 (NAPRAWA V30 + RADAR OPÓŹNIEŃ ECHO T+2 + TEST NA CAŁEJ BAZIE):
# 1) NAPRAWA BŁĘDÓW V30: ZŁOTA FALA DO 62% (ŁAPIE 3/5=60%), KONIEC Z KARĄ DLA 3x Z RZĘDU, TRANSFER ±1⬜
# 2) NOWY MODUŁ "🔄 RADAR OPÓŹNIEŃ (ECHO T+2)": ŚLEDZI PUDŁA Z POPRZEDNIEGO TYPOWANIA NA KOLEJNĄ GRĘ
# 3) NOWA KOLUMNA "🔄 Echo T+2" W TABELI NR 2 + PROPOZYCJA MIKSU (#1 ŚWIEŻA + #1 ECHO)
# 4) NOWY "🔭 TEST 3: EFEKT OPÓŹNIENIA T+2" W PANELU A/B — EMPIRYCZNY SPRAWDZIAN NA CAŁEJ BAZIE ~1130 GIER
# =====================================================================
from collections import defaultdict, Counter
from datetime import datetime, timedelta

def render_prediction_algorithm(df_full, default_window=10, default_blue_win=10, default_backtest=20):
    st.divider()

    all_windows = [5, 6, 7, 8, 9, 10, 12, 15]
    eval_long = 30
    eval_short = 10

    if len(df_full) < 65:
        st.warning(f"Za mało danych w bazie ({len(df_full)}), aby uruchomić moduł V31 (wymagane min. 65 losowań).")
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

    st.header(f"🧠 Algorytm V31 — Naprawiony Silnik + Radar Opóźnień (Echo T+2) na #{target_draw_id} (godz. {target_time_str})")

    # =================================================================
    # WYBÓR TRYBU SILNIKA
    # =================================================================
    mode_map = {
        "⬜ Bez Tabeli Niebieskiej (Tylko Tabela 1 + Kule)": "no_blue",
        "🔄 Hybryda (Tabela 1 + Niebieska 🟦)": "hybrid",
    }
    selected_mode_label = st.radio(
        "🎛️ Tryb silnika V31 (w trybie ⬜ Bez Niebieskiej kolumny M.xx są całkowicie wyłączone i ukryte):",
        options=list(mode_map.keys()),
        index=0,
        horizontal=True,
        key="v31_engine_mode_radio"
    )
    active_mode = mode_map[selected_mode_label]
    is_no_blue = (active_mode == "no_blue")
    mode_tag = "⬜ BEZ NIEBIESKIEJ" if is_no_blue else "🔄 HYBRYDA"

    # =================================================================
    # SILNIK V31: NAPRAWIONA ZŁOTA FALA (30-62%), SERIA 3x BEZ KARY + TRANSFER ±1⬜
    # =================================================================
    def build_scorer_v31(w_size, steps_back, engine_mode="no_blue"):
        earliest_needed = max(max(w_size, 15) - 1, total_draws - 1 - steps_back - max(w_size, 15) - 6)
        min_mode_thr = 3 if w_size >= 12 else 2
        use_blue = (engine_mode == "hybrid")
        local_meta = {}

        for t_i in range(earliest_needed, total_draws):
            w_lists = all_lists[t_i - w_size + 1 : t_i + 1]
            w_sets = all_sets[t_i - w_size + 1 : t_i + 1]
            n_trans = max(1, len(w_lists) - 1)
            curr_l = all_lists[t_i]
            next_s = all_sets[t_i + 1] if (t_i + 1 < total_draws) else set()

            w15_lists = all_lists[max(0, t_i - 14) : t_i + 1]
            w15_sets = all_sets[max(0, t_i - 14) : t_i + 1]
            n15_trans = max(1, len(w15_lists) - 1)

            white_hits_w = [0] * 21
            white_hits_15 = [0] * 21
            pos_modes = {}
            all_modes_set = set()
            pos_rank_tmp = []

            for i in range(1, 21):
                p_idx = i - 1
                rw = sum(1 for k in range(n_trans) if w_lists[k][p_idx] in w_sets[k + 1])
                white_hits_w[i] = rw
                white_hits_15[i] = sum(1 for k in range(n15_trans) if w15_lists[k][p_idx] in w15_sets[k + 1])

                cnts = Counter(w_lists[k][p_idx] for k in range(len(w_lists)))
                m_cnt = max(cnts.values())
                m_val = min(k for k, v in cnts.items() if v == m_cnt)
                pos_modes[i] = (m_val, m_cnt)
                if m_cnt >= min_mode_thr:
                    all_modes_set.add(m_val)

                if use_blue:
                    pos_rank_tmp.append((rw, i, curr_l[p_idx]))

            blue_col_for_pos = {}
            blue_hit_by_col = {}
            if use_blue:
                pos_rank_tmp.sort(key=lambda x: (-x[0], x[1]))
                for r_idx, (_, o_pos, b_val) in enumerate(pos_rank_tmp):
                    m_col = r_idx + 1
                    blue_col_for_pos[o_pos] = m_col
                    blue_hit_by_col[m_col] = (b_val in next_s) if (t_i + 1 < total_draws) else False

            local_meta[t_i] = {
                "white_hits_w": white_hits_w,
                "white_hits_15": white_hits_15,
                "n15_trans": n15_trans,
                "pos_modes": pos_modes,
                "all_modes_set": all_modes_set,
                "blue_col_for_pos": blue_col_for_pos,
                "blue_hit_by_col": blue_hit_by_col
            }

        score_cache = {}

        def score_at_t(t_idx, return_df=False):
            if t_idx in score_cache and not return_df:
                return score_cache[t_idx]

            w_lists = all_lists[t_idx - w_size + 1 : t_idx + 1]
            w_sets = all_sets[t_idx - w_size + 1 : t_idx + 1]
            trans_count = max(1, len(w_lists) - 1)
            curr_nums = all_lists[t_idx]

            prev1_list = all_lists[t_idx - 1] if t_idx >= 1 else []
            prev1_set = all_sets[t_idx - 1] if t_idx >= 1 else set()
            prev2_set = all_sets[t_idx - 2] if t_idx >= 2 else set()
            prev3_set = all_sets[t_idx - 3] if t_idx >= 3 else set()

            meta_now = local_meta[t_idx]
            white_w_now = meta_now["white_hits_w"]
            white_15_now = meta_now["white_hits_15"]
            n15_trans_now = meta_now["n15_trans"]
            pos_modes_now = meta_now["pos_modes"]
            all_modes_set_now = meta_now["all_modes_set"]
            blue_col_map = meta_now["blue_col_for_pos"]
            max_w15 = max(white_15_now[1:]) if total_draws > 1 else 5

            sq1 = [False] * 21
            sq2 = [False] * 21
            sq3 = [False] * 21
            if t_idx >= 1:
                s0, l1 = all_sets[t_idx], all_lists[t_idx - 1]
                for p in range(20):
                    if l1[p] in s0:
                        sq1[p + 1] = True
            if t_idx >= 2:
                s1, l2 = all_sets[t_idx - 1], all_lists[t_idx - 2]
                for p in range(20):
                    if l2[p] in s1:
                        sq2[p + 1] = True
            if t_idx >= 3:
                s2, l3 = all_sets[t_idx - 2], all_lists[t_idx - 3]
                for p in range(20):
                    if l3[p] in s2:
                        sq3[p + 1] = True

            blue_hits = [0] * 21
            blue_r2 = [0] * 21
            blue_steps = 0
            prev1_blue = {}
            prev2_blue = {}
            if use_blue:
                start_b = max(earliest_needed, t_idx - w_size)
                for b_t in range(start_b, t_idx):
                    blue_steps += 1
                    bmap = local_meta[b_t]["blue_hit_by_col"]
                    is_r2 = (b_t >= t_idx - 2)
                    for mc in range(1, 21):
                        if bmap.get(mc, False):
                            blue_hits[mc] += 1
                            if is_r2:
                                blue_r2[mc] += 1
                prev1_blue = local_meta[t_idx - 1]["blue_hit_by_col"] if (t_idx - 1) in local_meta else {}
                prev2_blue = local_meta[t_idx - 2]["blue_hit_by_col"] if (t_idx - 2) in local_meta else {}

            win_ball_freq = [0] * 71
            win_ball_t1 = [0] * 71
            for k_i, d_l in enumerate(w_lists):
                nxt_ws = w_sets[k_i + 1] if k_i < trans_count else None
                for b in d_l:
                    win_ball_freq[b] += 1
                    if nxt_ws is not None and b in nxt_ws:
                        win_ball_t1[b] += 1

            w15_lists_s = all_lists[max(0, t_idx - 14) : t_idx + 1]
            w15_sets_s = all_sets[max(0, t_idx - 14) : t_idx + 1]
            ball15_freq = [0] * 71
            ball15_t1 = [0] * 71
            last_k15 = len(w15_lists_s) - 1
            for k_i, d_l in enumerate(w15_lists_s):
                nxt_15s = w15_sets_s[k_i + 1] if k_i < last_k15 else None
                for b in d_l:
                    ball15_freq[b] += 1
                    if nxt_15s is not None and b in nxt_15s:
                        ball15_t1[b] += 1

            denom_b = max(1, blue_steps)
            candidates = []

            for p_i in range(20):
                pos_nr = p_i + 1
                ball = curr_nums[p_i]

                pw_hits = white_w_now[pos_nr]
                pw_rate = pw_hits / trans_count
                w15_h = white_15_now[pos_nr]
                w15_ratio = w15_h / max(1.0, float(max_w15))

                s_d1, s_d2, s_d3 = sq1[pos_nr], sq2[pos_nr], sq3[pos_nr]
                o_r3 = (1 if s_d1 else 0) + (1 if s_d2 else 0) + (1 if s_d3 else 0)
                s_adj = (pos_nr > 1 and sq1[pos_nr - 1]) or (pos_nr < 20 and sq1[pos_nr + 1])

                bf_win = win_ball_freq[ball]
                bf_rate = bf_win / max(1, w_size)
                bt1_win = win_ball_t1[ball]
                bt1_15 = ball15_t1[ball]

                in_p1 = (ball in prev1_set)
                in_p2 = (ball in prev2_set)
                in_p3 = (ball in prev3_set)
                streak_len = 1 + (1 if in_p1 else 0) + (1 if (in_p1 and in_p2) else 0) + (1 if (in_p1 and in_p2 and in_p3) else 0)

                # NOWOŚĆ V31: Wykrywanie sąsiedniego transferu z białego kwadratu (np. 03 z Poz.02⬜ -> Poz.01🔴!)
                is_adj_transfer = False
                src_pos = None
                if in_p1 and prev1_list:
                    src_pos = prev1_list.index(ball) + 1
                    if src_pos != pos_nr and abs(src_pos - pos_nr) <= 1 and sq1[src_pos]:
                        is_adj_transfer = True

                mode_ball, mode_cnt = pos_modes_now[pos_nr]
                is_exact_mode = (ball == mode_ball and mode_cnt >= min_mode_thr)
                mode_str = f"🎯 Lider P{pos_nr:02d} (x{mode_cnt})" if is_exact_mode else ("⭐ W 'Najczęstszej'" if ball in all_modes_set_now else "-")

                # FILAR 1: SIŁA POZYCJI (wyraźna różnica między 1/4=25% a 3/4=75%!)
                if 0.33 <= pw_rate <= 0.62:
                    pts_pw = 18.0
                elif pw_rate <= 0.78:
                    pts_pw = 16.5 if pw_rate > 0.62 else (pw_rate / 0.33) * 13.0
                else:
                    pts_pw = 14.0

                pts_w15 = (w15_ratio * 18.0) if w15_h >= 3 else (w15_ratio * 10.0)
                pillar_pos = pts_pw + pts_w15

                # FILAR 2: ŚWIEŻOŚĆ WĘZŁA (+ TRANSFER ±1⬜)
                m_col = blue_col_map.get(pos_nr, 0) if use_blue else 0
                b_cnt = blue_hits[m_col] if use_blue else 0
                b_rate = (b_cnt / denom_b) if use_blue else 0.0
                b_u1 = prev1_blue.get(m_col, False) if use_blue else False
                b_u2 = prev2_blue.get(m_col, False) if use_blue else False

                if use_blue:
                    if s_d1 and b_u1:
                        pts_node = 16.0
                        path_str = "⬜+🟦 Podwójny kwadrat w T-1"
                    elif s_d1:
                        pts_node = 13.5
                        path_str = "⬜ Biały kwadrat w T-1"
                    elif is_adj_transfer:
                        pts_node = 13.5
                        path_str = f"🔄⬜ Transfer z Poz.{src_pos:02d}⬜"
                    elif b_u1:
                        pts_node = 12.5
                        path_str = f"🟦 Niebieski kwadrat M.{m_col:02d} w T-1"
                    elif s_d2 and b_u2:
                        pts_node = 11.0
                        path_str = "⬜+🟦 Aktywna w T-2"
                    elif s_d2 or b_u2:
                        pts_node = 8.0
                        path_str = "Aktywna w T-2"
                    elif s_adj:
                        pts_node = 4.5
                        path_str = "⬜ Kwadrat obok"
                    else:
                        pts_node = 0.0
                        path_str = "Cisza w 2 ost."

                    pts_blue = min(18.0, (b_rate / 0.50) * 16.0 + (2.0 if (m_col <= 6 and b_rate >= 0.30) else 0.0))
                    pos_fatigue = -4.0 if (s_d1 and s_d2 and s_d3) else 0.0
                    pillar_node = max(0.0, pts_node + pts_blue + pos_fatigue)
                else:
                    if s_d1 and s_d2 and s_d3:
                        pts_node = 16.0
                        path_str = "⬜⬜⬜ 3x z rzędu (lekkie chłodzenie)"
                    elif s_d1 and s_d2:
                        pts_node = 22.0
                        path_str = "⬜⬜ Seria białych kwadratów (T-1 & T-2)"
                    elif s_d1:
                        pts_node = 20.0
                        path_str = "⬜ Biały kwadrat w T-1"
                    elif is_adj_transfer:
                        pts_node = 19.0
                        path_str = f"🔄⬜ Transfer z Poz.{src_pos:02d}⬜"
                    elif s_d2:
                        pts_node = 13.5
                        path_str = "⬜ Biały kwadrat w T-2"
                    elif s_d3:
                        pts_node = 8.5
                        path_str = "⬜ Biały kwadrat w T-3"
                    elif s_adj:
                        pts_node = 5.5
                        path_str = "⬜ Kwadrat na sąsiedniej pozycji"
                    else:
                        pts_node = 0.0
                        path_str = "Brak ⬜ w 3 ost."

                    pts_recent_density = min(10.0, o_r3 * 3.5)
                    pillar_node = pts_node + pts_recent_density

                # FILAR 3: NAPRAWIONA DYNAMIKA KULI (ZŁOTA FALA 30–62%, KONIEC Z KARĄ DLA 3x Z RZĘDU!)
                is_overheated = (bf_rate >= 0.75) or (streak_len >= 4)
                is_golden_wave = (0.30 <= bf_rate <= 0.62) and (bt1_win >= 1 or bt1_15 >= 2)

                if is_overheated:
                    pts_wave = -8.0
                    wave_tag = f"🌡️ Przegrzana ({bf_win}/{w_size} = {bf_rate*100:.0f}%)"
                elif is_golden_wave and streak_len == 3:
                    # Naprawa dla kuli 3 (3/5=60%, 2x powt. T+1, 3x z rzędu): silna, aktywna fala bez kary!
                    pts_wave = 14.5
                    wave_tag = f"🔥 Aktywna Seria 3x ({bf_win}/{w_size}={bf_rate*100:.0f}%)"
                elif is_golden_wave:
                    pts_wave = 15.5
                    wave_tag = f"🎯 Złota Fala ({bf_win}/{w_size} = {bf_rate*100:.0f}%)"
                elif streak_len == 3:
                    pts_wave = 10.5
                    wave_tag = f"🔴🔴 Seria 3x ({bf_win}/{w_size})"
                elif 0.25 <= bf_rate <= 0.68:
                    pts_wave = 9.5
                    wave_tag = f"⚖️ Stabilna ({bf_win}/{w_size})"
                else:
                    pts_wave = 5.0
                    wave_tag = f"🌱 Świeża ({bf_win}/{w_size})"

                pts_rep = min(11.0, bt1_win * 3.4 + bt1_15 * 1.2)
                pts_mode = 5.5 if is_exact_mode else (3.0 if ball in all_modes_set_now else 0.0)
                pillar_ball = pts_wave + pts_rep + pts_mode

                cold_adj = 0.0
                if o_r3 == 0 and not is_adj_transfer and (not use_blue or blue_r2[m_col] == 0):
                    cold_adj -= 7.0
                if w15_h <= 1 and n15_trans_now >= 12 and not s_d1 and not is_adj_transfer:
                    cold_adj -= 6.0

                raw_total = (pillar_pos * (0.88 if use_blue else 1.0)) + pillar_node + pillar_ball + cold_adj
                final_score = round(min(98.0, max(5.0, raw_total)), 1)

                if is_overheated:
                    verdict_str = f"🌡️ Schłodzona ({bf_win}/{w_size}={bf_rate*100:.0f}%)"
                elif is_adj_transfer and is_golden_wave:
                    verdict_str = f"🔥 Transfer z P{src_pos:02d}⬜ + Złota Fala"
                elif is_golden_wave and (s_d1 or (use_blue and b_u1)):
                    verdict_str = "💎 Złota Fala + Kwadrat T-1"
                elif is_golden_wave and w15_h >= max(4, max_w15 - 1):
                    verdict_str = "🏆 Lider 15 + Złota Fala"
                elif is_adj_transfer:
                    verdict_str = f"🔄 Transfer z P{src_pos:02d}⬜"
                elif s_d1:
                    verdict_str = f"⬜ Żywy Kwadrat Poz.{pos_nr:02d}"
                elif use_blue and b_u1:
                    verdict_str = f"🟦 Żywy Kwadrat M.{m_col:02d}"
                elif w15_h >= max(4, max_w15 - 1):
                    verdict_str = f"🏆 Lider Tabeli 15 ({w15_h}/{n15_trans_now})"
                elif cold_adj <= -7.0:
                    verdict_str = f"❄️ Uśpiona Poz.{pos_nr:02d}"
                else:
                    verdict_str = wave_tag

                pos_label = f"Poz. {pos_nr:02d}" if not use_blue else f"Poz. {pos_nr:02d} (🟦 M.{m_col:02d})"

                candidates.append({
                    "pos_nr": pos_nr,
                    "blue_m": m_col,
                    "w15_hits": w15_h,
                    "pw_pct": round(pw_rate * 100.0, 1),
                    "b_pct": round(b_rate * 100.0, 1),
                    "is_overheated": 1 if is_overheated else 0,
                    "bt1_win": bt1_win,
                    "Pozycja": pos_label,
                    "Liczba": ball,
                    "Score": final_score,
                    "Status V31": verdict_str,
                    "⬜ Własne (okno i 15)": f"{pw_hits}/{trans_count} ({pw_rate*100:.0f}%) | 15: {w15_h}/{n15_trans_now}",
                    "🟦 Kolumna M": f"M.{m_col:02d}: {b_cnt}/{blue_steps} ({b_rate*100:.0f}%)" if use_blue else "-",
                    "Węzeł": path_str,
                    "Fala Kuli": f"{bf_win}/{w_size} ({bf_rate*100:.0f}%) | T+1: {bt1_win}x",
                    "⭐ Najczęstsza": mode_str
                })

            candidates.sort(key=lambda x: (-x["Score"], x["is_overheated"], -x["bt1_win"], -x["w15_hits"]))
            for idx_c, c_it in enumerate(candidates):
                c_it["Rank"] = f"#{idx_c + 1}"

            res = (candidates, win_ball_freq, win_ball_t1, all_modes_set_now)
            score_cache[t_idx] = res

            if return_df:
                df_c = pd.DataFrame(candidates)
                cols = ["Rank"] + [c for c in df_c.columns if c != "Rank"]
                return df_c[cols], win_ball_freq, win_ball_t1, all_modes_set_now
            return res

        return score_at_t

    # Funkcja pomocnicza: wyznacza opóźnione pudła (Echo T+2) z poprzedniego kroku (t_idx - 1)
    def get_echo_candidates_at_t(scorer_fn, t_idx):
        prev_cands, _, _, _ = scorer_fn(t_idx - 1, return_df=False)
        actual_at_t = all_sets[t_idx]
        missed_pair = [c for c in prev_cands[:2] if c["Liczba"] not in actual_at_t]
        missed_rest = [c for c in prev_cands[2:5] if c["Liczba"] not in actual_at_t]
        return missed_pair, missed_rest

    # =================================================================
    # 🔬 PANEL TESTÓW A/B + TEST 3: EMPIRYCZNY SPRAWDZIAN EFEKTU OPÓŹNIENIA (ECHO T+2)
    # =================================================================
    with st.expander(f"🔬 TESTY A/B V31 & SPRAWDZENIE EFEKTU OPÓŹNIENIA T+2 (na bazie do {max(30, total_draws - 48)} gier!)", expanded=False):
        st.caption(
            "Sprawdź na całej bazie: **(1)** Hybryda vs Bez Niebieskiej, **(2)** wszystkie 8 okien oraz "
            "**(3)** Twoją teorię **Opóźnienia (Echo T+2)** — czy pudła z poprzedniego typowania naprawdę wpadają częściej w kolejnej grze!"
        )
        ab_max = max(30, total_draws - 48)
        ab_len_opts = [x for x in [100, 250, 500] if x < ab_max] + [ab_max]

        c_ab1, c_ab2 = st.columns([1.15, 0.85])
        with c_ab1:
            ab_len = st.radio(
                "📊 Liczba losowań w teście:",
                options=ab_len_opts,
                index=len(ab_len_opts) - 1,
                format_func=lambda x: f"Cała baza ({x})" if x == ab_max else f"{x} gier",
                horizontal=True,
                key="v31_ab_len"
            )
        with c_ab2:
            ab_win = st.radio(
                "⚙️ Okno do Testu 1 i Testu 3 (Echo):",
                options=[5, 6, 8, 10, 15],
                index=3,
                horizontal=True,
                key="v31_ab_win"
            )

        b_t1, b_t2, b_t3 = st.columns(3)
        with b_t1:
            run_t1 = st.button(f"🚀 Test 1: Hybryda vs Bez Nieb. ({ab_len}g)", use_container_width=True, key="v31_btn_t1")
        with b_t2:
            run_t2 = st.button(f"📊 Test 2: Wszystkie 8 Okien ({ab_len}g)", use_container_width=True, key="v31_btn_t2")
        with b_t3:
            run_t3 = st.button(f"🔭 Test 3: Sprawdź Echo T+2 ({ab_len}g)", type="primary", use_container_width=True, key="v31_btn_t3")

        def eval_clean_v31(w_sz, e_mode, n_eval):
            sc = build_scorer_v31(w_sz, n_eval + 4, engine_mode=e_mode)
            p_any = p_both = t5_hits = t5_2p = t5_3p = s1_h = s2_h = 0
            for st_i in range(n_eval):
                t_c = latest_idx - 1 - st_i
                cands, _, _, _ = sc(t_c, return_df=False)
                nxt = all_sets[t_c + 1]
                hf = [cands[k]["Liczba"] in nxt for k in range(5)]
                hc = sum(1 for x in hf if x)
                t5_hits += hc
                if hc >= 2: t5_2p += 1
                if hc >= 3: t5_3p += 1
                if hf[0]: s1_h += 1
                if hf[1]: s2_h += 1
                if hf[0] or hf[1]: p_any += 1
                if hf[0] and hf[1]: p_both += 1
            return {
                "p_any": p_any, "p_both": p_both, "t5_hits": t5_hits,
                "t5_2p": t5_2p, "t5_3p": t5_3p, "s1_h": s1_h, "s2_h": s2_h
            }

        if run_t1:
            prog = st.progress(0, text=f"Testuję V31 na {ab_len} losowaniach (Okno {ab_win})...")
            r_nb = eval_clean_v31(ab_win, "no_blue", ab_len)
            prog.progress(0.5)
            r_hy = eval_clean_v31(ab_win, "hybrid", ab_len)
            prog.progress(1.0)
            prog.empty()

            rows_t1 = []
            for lbl, d in [("⬜ Bez Niebieskiej V31 (Tylko Tab.1)", r_nb), ("🔄 Hybryda V31 (Tab.1 + 🟦)", r_hy)]:
                pb = d["p_any"] + d["p_both"]
                pb_pct = (pb / (ab_len * 2.0)) * 100.0
                rows_t1.append({
                    "Tryb V31": lbl, "raw_pb": pb_pct, "raw_pa": d["p_any"] / ab_len * 100.0,
                    "Para #1+#2 (na 1 kulę)": f"{pb_pct:.2f}% ({pb}/{ab_len*2})",
                    "Para: min. 1 traf.": f"{d['p_any']/ab_len*100:.1f}% ({d['p_any']}/{ab_len})",
                    "Para: pełne 2/2": f"{d['p_both']/ab_len*100:.2f}% ({d['p_both']}x)",
                    "Śr. TOP 5 (kula)": f"{d['t5_hits']/(ab_len*5.0)*100:.2f}%",
                    "TOP 5: 2+ / 3+": f"{d['t5_2p']/ab_len*100:.1f}% ({d['t5_2p']}) | 3+: {d['t5_3p']/ab_len*100:.1f}%",
                    "#1 / #2": f"{d['s1_h']/ab_len*100:.1f}% / {d['s2_h']/ab_len*100:.1f}%"
                })
            win_t1 = max(rows_t1, key=lambda x: (x["raw_pb"], x["raw_pa"]))
            rows_t1.append({
                "Tryb V31": "🎲 Losowy wybór (teoria Keno 20/70)", "raw_pb": 28.57, "raw_pa": 49.28,
                "Para #1+#2 (na 1 kulę)": "28.57% (baza losowa)", "Para: min. 1 traf.": "49.28% (baza losowa)",
                "Para: pełne 2/2": "7.87% (baza losowa)", "Śr. TOP 5 (kula)": "28.57% (baza losowa)",
                "TOP 5: 2+ / 3+": "44.44% | 3+: 13.67%", "#1 / #2": "28.6% / 28.6%"
            })
            st.session_state["v31_t1_df"] = pd.DataFrame(rows_t1).drop(columns=["raw_pb", "raw_pa"])
            st.session_state["v31_t1_msg"] = (
                f"🏆 **WYNIK TESTU 1 ({ab_len} gier, Okno {ab_win}):** **{win_t1['Tryb V31']}** — "
                f"Para #1+#2: **{win_t1['Para #1+#2 (na 1 kulę)']}** ({win_t1['raw_pb'] - 28.57:+.2f} pkt proc. vs losowe `28.57%`)."
            )

        if run_t2:
            prog = st.progress(0, text=f"Testuję wszystkie 8 okien [{mode_tag}] na {ab_len} grach...")
            rows_t2 = []
            for idx_w, w_val in enumerate(all_windows):
                d = eval_clean_v31(w_val, active_mode, ab_len)
                pb = d["p_any"] + d["p_both"]
                pb_pct = (pb / (ab_len * 2.0)) * 100.0
                rows_t2.append({
                    f"Okno ({mode_tag})": f"Okno {w_val}", "raw_pb": pb_pct,
                    "Para #1+#2 (na 1 kulę)": f"{pb_pct:.2f}% ({pb}/{ab_len*2})",
                    "Para: min. 1 traf.": f"{d['p_any']/ab_len*100:.1f}% ({d['p_any']}/{ab_len})",
                    "Para: pełne 2/2": f"{d['p_both']/ab_len*100:.2f}% ({d['p_both']}x)",
                    "Śr. TOP 5": f"{d['t5_hits']/(ab_len*5.0)*100:.2f}%",
                    "TOP 5: 2+ traf.": f"{d['t5_2p']/ab_len*100:.1f}% ({d['t5_2p']})"
                })
                prog.progress((idx_w + 1) / len(all_windows))
            prog.empty()
            rows_t2.sort(key=lambda x: -x["raw_pb"])
            st.session_state["v31_t2_df"] = pd.DataFrame(rows_t2).drop(columns=["raw_pb"])
            st.session_state["v31_t2_msg"] = (
                f"🏆 **NAJLEPSZE OKNO NA {ab_len} GRACH ({mode_tag}):** **{rows_t2[0][f'Okno ({mode_tag})']}** — "
                f"Para #1+#2: **{rows_t2[0]['Para #1+#2 (na 1 kulę)']}** | Min. 1: **{rows_t2[0]['Para: min. 1 traf.']}**."
            )

        if run_t3:
            prog = st.progress(0, text=f"Sprawdzam efekt opóźnienia (Echo T+2) na {ab_len} losowaniach (Okno {ab_win}, {mode_tag})...")
            sc_e = build_scorer_v31(ab_win, ab_len + 6, engine_mode=active_mode)

            # 1) Normalna Para #1+#2 (T+1)
            norm_any = norm_both = 0
            # 2) Echo T+2 z pudeł Pary #1+#2 (gdy co najmniej 1 z #1/#2 nie wpadła w T)
            echo_p_balls_tot = echo_p_balls_hits = 0
            echo_p_games_2miss = echo_p_2miss_any = echo_p_2miss_both = 0
            # 3) Echo T+2 ze wszystkich pudeł TOP 5
            echo_5_balls_tot = echo_5_balls_hits = echo_5_games_any = 0
            # 4) Miks: #1 Świeża (z T) + #1 Echo (najwyższe pudło z T-1)
            mix_any = mix_both = 0

            for st_i in range(ab_len):
                t_c = latest_idx - 1 - st_i
                nxt = all_sets[t_c + 1]
                cands_now, _, _, _ = sc_e(t_c, return_df=False)
                mp_prev, mr_prev = get_echo_candidates_at_t(sc_e, t_c)

                # Normalna para #1+#2
                nh1, nh2 = (cands_now[0]["Liczba"] in nxt), (cands_now[1]["Liczba"] in nxt)
                if nh1 or nh2: norm_any += 1
                if nh1 and nh2: norm_both += 1

                # Echo z pudeł pary #1+#2
                for c_m in mp_prev:
                    echo_p_balls_tot += 1
                    if c_m["Liczba"] in nxt:
                        echo_p_balls_hits += 1
                if len(mp_prev) == 2:
                    echo_p_games_2miss += 1
                    eh1, eh2 = (mp_prev[0]["Liczba"] in nxt), (mp_prev[1]["Liczba"] in nxt)
                    if eh1 or eh2: echo_p_2miss_any += 1
                    if eh1 and eh2: echo_p_2miss_both += 1

                # Echo ze wszystkich pudeł TOP 5
                all_m5 = mp_prev + mr_prev
                h5_echo = 0
                for c_m in all_m5:
                    echo_5_balls_tot += 1
                    if c_m["Liczba"] in nxt:
                        echo_5_balls_hits += 1
                        h5_echo += 1
                if h5_echo >= 1:
                    echo_5_games_any += 1

                # Miks: #1 świeża + #1 Echo (a jeśli w TOP 5 nie było pudeł, bierzemy #2 świeżą)
                fresh_1 = cands_now[0]["Liczba"]
                echo_1 = all_m5[0]["Liczba"] if len(all_m5) > 0 else cands_now[1]["Liczba"]
                mh1, mh2 = (fresh_1 in nxt), (echo_1 in nxt)
                if mh1 or mh2: mix_any += 1
                if mh1 and mh2: mix_both += 1

                if st_i % 100 == 0:
                    prog.progress(min(0.99, (st_i + 1) / ab_len))

            prog.progress(1.0)
            prog.empty()

            norm_pb = ((norm_any + norm_both) / (ab_len * 2.0)) * 100.0
            echo_p_pb = (echo_p_balls_hits / max(1, echo_p_balls_tot)) * 100.0
            echo_5_pb = (echo_5_balls_hits / max(1, echo_5_balls_tot)) * 100.0
            mix_pb = ((mix_any + mix_both) / (ab_len * 2.0)) * 100.0

            rows_t3 = [
                {
                    "Strategia (Okno " + str(ab_win) + ", " + mode_tag + ")": "🎯 Standardowa Para #1+#2 (świeże z T)",
                    "Trafność na 1 kulę": f"{norm_pb:.2f}% ({norm_any+norm_both}/{ab_len*2})",
                    "Min. 1 z pary (2 kule)": f"{norm_any/ab_len*100:.1f}% ({norm_any}/{ab_len})",
                    "Pełne 2/2": f"{norm_both/ab_len*100:.2f}% ({norm_both}x)",
                    "Uwagi": "Bieżący model V31"
                },
                {
                    "Strategia (Okno " + str(ab_win) + ", " + mode_tag + ")": "🔄 Echo T+2: Pudła Pary #1+#2 z T-1",
                    "Trafność na 1 kulę": f"{echo_p_pb:.2f}% ({echo_p_balls_hits}/{echo_p_balls_tot})",
                    "Min. 1 z pary (2 kule)": f"{echo_p_2miss_any/max(1,echo_p_games_2miss)*100:.1f}% ({echo_p_2miss_any}/{echo_p_games_2miss} po 0/2)",
                    "Pełne 2/2": f"{echo_p_2miss_both/max(1,echo_p_games_2miss)*100:.2f}% ({echo_p_2miss_both}x)",
                    "Uwagi": "Kule z #1/#2 pominięte w T, sprawdzone w T+1"
                },
                {
                    "Strategia (Okno " + str(ab_win) + ", " + mode_tag + ")": "🔄 Echo T+2: Wszystkie pudła TOP 5 z T-1",
                    "Trafność na 1 kulę": f"{echo_5_pb:.2f}% ({echo_5_balls_hits}/{echo_5_balls_tot})",
                    "Min. 1 z pary (2 kule)": f"Min. 1 z puli: {echo_5_games_any/ab_len*100:.1f}% ({echo_5_games_any}/{ab_len})",
                    "Pełne 2/2": "-",
                    "Uwagi": "Śr. ~3,5 pudła z TOP 5 przechodzi na T+1"
                },
                {
                    "Strategia (Okno " + str(ab_win) + ", " + mode_tag + ")": "⚡ MIKS: #1 Świeża (z T) + #1 Echo (z T-1)",
                    "Trafność na 1 kulę": f"{mix_pb:.2f}% ({mix_any+mix_both}/{ab_len*2})",
                    "Min. 1 z pary (2 kule)": f"{mix_any/ab_len*100:.1f}% ({mix_any}/{ab_len})",
                    "Pełne 2/2": f"{mix_both/ab_len*100:.2f}% ({mix_both}x)",
                    "Uwagi": "Połączenie świeżego lidera z opóźnionym pudłem"
                },
                {
                    "Strategia (Okno " + str(ab_win) + ", " + mode_tag + ")": "🎲 Losowy wybór (teoria Keno 20/70)",
                    "Trafność na 1 kulę": "28.57% (baza losowa)",
                    "Min. 1 z pary (2 kule)": "49.28% (baza losowa)",
                    "Pełne 2/2": "7.87% (baza losowa)",
                    "Uwagi": "Punkt odniesienia niezależnych losowań"
                }
            ]
            st.session_state["v31_t3_df"] = pd.DataFrame(rows_t3)
            diff_echo = echo_p_pb - 28.57
            diff_mix = mix_pb - norm_pb
            st.session_state["v31_t3_msg"] = (
                f"🔭 **WYNIK TESTU OPÓŹNIENIA ECHO T+2 ({ab_len} gier, Okno {ab_win}):** "
                f"Opóźnione pudła pary `#1+#2` trafiają w kolejnym losowaniu **`{echo_p_pb:.2f}%`** (`{diff_echo:+.2f}` pkt proc. vs losowe `28.57%`) | "
                f"**MIKS (#1 Świeża + #1 Echo)** daje **`{mix_pb:.2f}%`** (`{diff_mix:+.2f}` pkt proc. względem czystego `#1+#2`: `{norm_pb:.2f}%`)."
            )

        if "v31_t3_msg" in st.session_state:
            st.success(st.session_state["v31_t3_msg"])
        if "v31_t3_df" in st.session_state:
            st.dataframe(st.session_state["v31_t3_df"], hide_index=True, use_container_width=True)
        if "v31_t1_msg" in st.session_state:
            st.info(st.session_state["v31_t1_msg"])
        if "v31_t1_df" in st.session_state:
            st.dataframe(st.session_state["v31_t1_df"], hide_index=True, use_container_width=True)
        if "v31_t2_msg" in st.session_state:
            st.info(st.session_state["v31_t2_msg"])
        if "v31_t2_df" in st.session_state:
            st.dataframe(st.session_state["v31_t2_df"], hide_index=True, use_container_width=True)

    # =================================================================
    # OBLICZENIE WSZYSTKICH 8 OKIEN (5–15) — CZYSTE #1 + #2 (+#3)
    # =================================================================
    win_scorers = {}
    win_summary = {}
    win_live_top5 = {}
    consensus_cnt = defaultdict(int)
    consensus_score = defaultdict(float)

    for w_val in all_windows:
        sc = build_scorer_v31(w_val, eval_long + 5, engine_mode=active_mode)
        win_scorers[w_val] = sc
        cands_now, _, _, _ = sc(latest_idx, return_df=False)
        t5_now = cands_now[:5]
        win_live_top5[w_val] = t5_now

        for idx_k, r_k in enumerate(t5_now[:3]):
            bv = int(r_k["Liczba"])
            consensus_cnt[bv] += 1
            consensus_score[bv] += float(r_k["Score"]) * (1.2 if idx_k < 2 else 0.8)

        p_any_30 = p_both_30 = p_any_10 = p_both_10 = p_rec5 = 0
        t5_2p_30 = t5_2p_10 = 0
        s_hits_30 = [0, 0, 0, 0, 0]
        s_hits_10 = [0, 0, 0, 0, 0]

        for step_i in range(eval_long):
            t_s = latest_idx - 1 - step_i
            cands_s, _, _, _ = sc(t_s, return_df=False)
            nxt = all_sets[t_s + 1]
            hf = [cands_s[k]["Liczba"] in nxt for k in range(5)]
            hc = sum(1 for x in hf if x)
            ph = (1 if hf[0] else 0) + (1 if hf[1] else 0)

            if hc >= 2:
                t5_2p_30 += 1
                if step_i < eval_short:
                    t5_2p_10 += 1
            for k in range(5):
                if hf[k]:
                    s_hits_30[k] += 1
                    if step_i < eval_short:
                        s_hits_10[k] += 1
            if ph >= 1:
                p_any_30 += 1
                if step_i < eval_short: p_any_10 += 1
                if step_i < 5: p_rec5 += 1
            if ph == 2:
                p_both_30 += 1
                if step_i < eval_short: p_both_10 += 1

        ball_pct_30 = ((p_any_30 + p_both_30) / (eval_long * 2.0)) * 100.0
        ball_pct_10 = ((p_any_10 + p_both_10) / (eval_short * 2.0)) * 100.0

        # Poprawiony ranking okien: większa waga realnej skuteczności na kulę + min. 1 w 30g!
        power = (
            (ball_pct_30 * 1.8)
            + ((p_any_30 / eval_long) * 35.0)
            + (p_both_30 * 1.8)
            + ((t5_2p_30 / eval_long) * 16.0)
            + (ball_pct_10 * 0.65)
            + (p_rec5 * 1.5)
        )

        win_summary[w_val] = {
            "w_val": w_val, "power": power,
            "p_any_30": p_any_30, "p_both_30": p_both_30, "ball_pct_30": ball_pct_30,
            "p_any_10": p_any_10, "p_both_10": p_both_10, "p_rec5": p_rec5,
            "t5_2p_30": t5_2p_30, "t5_2p_10": t5_2p_10,
            "s_hits_30": s_hits_30, "s_hits_10": s_hits_10,
            "b1": int(t5_now[0]["Liczba"]), "b2": int(t5_now[1]["Liczba"]), "b3": int(t5_now[2]["Liczba"]),
            "s1": float(t5_now[0]["Score"]), "s2": float(t5_now[1]["Score"]), "s3": float(t5_now[2]["Score"]),
            "p1": int(t5_now[0]["pos_nr"]), "p2": int(t5_now[1]["pos_nr"]), "p3": int(t5_now[2]["pos_nr"])
        }

    ranked_windows = sorted(all_windows, key=lambda w: win_summary[w]["power"], reverse=True)
    best_win = ranked_windows[0]
    second_win = ranked_windows[1]
    w1 = win_summary[best_win]
    w2 = win_summary[second_win]

    # =================================================================
    # KOMPAKTOWY PASEK PULSU POWTÓREK (OSTATNIE 20 GIER)
    # =================================================================
    repeats_series = [len(all_sets[i].intersection(all_sets[i + 1])) for i in range(total_draws - 1)]
    avg_global_rep = sum(repeats_series) / max(1, len(repeats_series))
    last1_rep = repeats_series[-1]
    last3_avg = sum(repeats_series[-3:]) / 3.0
    last20_reps = repeats_series[-20:]
    last20_ids = all_ids[-20:]

    pulse_html = []
    for r_v, d_id in zip(last20_reps, last20_ids):
        if r_v >= 7:
            bg, col, brd = "rgba(0,230,118,0.32)", "#00e676", "#00e676"
        elif r_v >= 5:
            bg, col, brd = "rgba(255,209,102,0.18)", "#ffd166", "#8a7535"
        else:
            bg, col, brd = "rgba(255,77,109,0.24)", "#ff6b6b", "#ff4d6d"
        pulse_html.append(
            f"<div style='display:inline-flex; flex-direction:column; align-items:center; min-width:25px; padding:2px 3px; "
            f"border:1px solid {brd}; border-radius:5px; background:{bg};'>"
            f"<span style='font-size:12px; font-weight:900; color:{col}; line-height:13px;'>{r_v}</span>"
            f"<span style='font-size:7px; color:#9da3af; line-height:8px;'>{str(d_id)[-3:]}</span></div>"
        )

    st.markdown(
        f"<div style='background:#131722; border:1.5px solid #333945; border-radius:10px; padding:10px 14px; margin-bottom:14px; font-family:sans-serif;'>"
        f"<div style='font-size:12px; color:#d0d7de; margin-bottom:6px;'>"
        f"📈 <b>Puls powtórek T ➔ T+1 (ost. 20 gier):</b> ostatnia gra: <b style='color:#ffd166;'>{last1_rep} powt.</b> | "
        f"śr. 3 gier: <b>{last3_avg:.1f}</b> (norma bazy: {avg_global_rep:.2f}) | rytm lidera (Okno {best_win}, ost. 5g): <b style='color:#00e676;'>{w1['p_rec5']}/5</b>"
        f"</div>"
        f"<div style='display:flex; flex-wrap:wrap; gap:4px;'>{''.join(pulse_html)}</div>"
        f"</div>",
        unsafe_allow_html=True
    )

    # =================================================================
    # GŁÓWNY PANEL TYPÓW V31 (ŚWIEŻA PARA #1+#2)
    # =================================================================
    c_b1, c_b2, c_b3 = consensus_cnt[w1["b1"]], consensus_cnt[w1["b2"]], consensus_cnt[w1["b3"]]
    is_3rd_ok = (w1["s_hits_30"][2] >= 10 and w1["s3"] >= 60.0 and c_b3 >= 3)

    third_html = (
        f"<div style='display:inline-flex; align-items:center; gap:10px; background:rgba(0,230,118,0.18); border:2px solid #00e676; border-radius:10px; padding:9px 14px;'>"
        f"<div><div style='font-size:13px; color:#00e676; font-weight:900;'>➕ 3. LICZBA DODATKOWA (SILNA):</div>"
        f"<div style='font-size:11px; color:#b9f6ca;'>Typ #3 (Poz.{w1['p3']:02d} | 30g: {w1['s_hits_30'][2]}/30 | w {c_b3}/8 okn.)</div></div>"
        f"<span style='font-size:28px; font-weight:900; color:#fff; background:#0077b6; padding:3px 13px; border-radius:8px; border:2px solid #00e676;'>{w1['b3']:02d}</span></div>"
        if is_3rd_ok else
        f"<div style='display:inline-flex; align-items:center; gap:10px; background:rgba(255,255,255,0.05); border:1.5px dashed #8a94a6; border-radius:10px; padding:9px 14px;'>"
        f"<div><div style='font-size:12px; color:#ffd166; font-weight:800;'>⚠️ 3. LICZBA REZERWOWA (LEPIEJ GRAJ PARĘ):</div>"
        f"<div style='font-size:11px; color:#9da3af;'>Typ #3 (Poz.{w1['p3']:02d} | 30g: {w1['s_hits_30'][2]}/30 | w {c_b3}/8 okn.)</div></div>"
        f"<span style='font-size:24px; font-weight:800; color:#d0d7de; background:#2b3548; padding:2px 11px; border-radius:7px; border:1px solid #8a94a6;'>{w1['b3']:02d}</span></div>"
    )

    sorted_cons = sorted(consensus_cnt.items(), key=lambda x: (-x[1], -consensus_score[x[0]]))[:5]
    cons_str = " &nbsp;|&nbsp; ".join(f"<b>{b:02d}</b> ({cnt}/8 okn.)" for b, cnt in sorted_cons)

    hero_v31_html = (
        f"<div style='background: linear-gradient(135deg, rgba(14, 48, 35, 0.98) 0%, rgba(9, 28, 21, 0.99) 100%); "
        f"border: 3px solid #ffd166; border-radius: 14px; padding: 16px 20px; margin-bottom: 14px; "
        f"box-shadow: 0 6px 20px rgba(255, 209, 102, 0.22); font-family: sans-serif;'>"
        f"<div style='display:flex; flex-wrap:wrap; justify-content:space-between; align-items:center; background:rgba(0,0,0,0.55); "
        f"border:2px solid #00e676; border-radius:9px; padding:10px 16px; margin-bottom:14px;'>"
        f"<div style='font-size:16px; font-weight:900; color:#00e676;'>"
        f"🎯 TYPY V31 [{mode_tag}] NA LOSOWANIE: <span style='color:#fff; background:#e63946; padding:3px 10px; border-radius:6px; font-size:18px;'>#{target_draw_id} (godz. {target_time_str})</span>"
        f"</div>"
        f"<div style='font-size:13px; color:#ffd166; font-weight:bold;'>"
        f"🏆 Lider: <b>OKNO {best_win}</b> (Para #1+#2 w 30g: <b>{w1['p_any_30']}/30 = {w1['p_any_30']/eval_long*100:.0f}%</b>, pełne 2/2: <b>{w1['p_both_30']}x</b>, śr./kulę: <b>{w1['ball_pct_30']:.1f}%</b> | 10g: <b>{w1['p_any_10']}/10</b>)"
        f"</div>"
        f"</div>"
        f"<div style='display:flex; flex-wrap:wrap; gap:14px; align-items:center; margin-bottom:12px;'>"
        f"<div style='display:inline-flex; align-items:center; gap:12px; background:rgba(0,0,0,0.65); border:3px solid #ffd166; border-radius:12px; padding:10px 18px; box-shadow:0 0 16px rgba(255,209,102,0.4);'>"
        f"<div>"
        f"<div style='font-size:14px; color:#ffd166; font-weight:900;'>👑 2 GŁÓWNE LICZBY (ŚWIEŻE #1 + #2 Z OKNA {best_win}):</div>"
        f"<div style='font-size:11px; color:#e6e6e6;'>"
        f"<b>#1: Poz.{w1['p1']:02d}</b> ({w1['s1']:.0f} pkt | 30g: {w1['s_hits_30'][0]}/30 | w {c_b1}/8 okn.) &nbsp;|&nbsp; "
        f"<b>#2: Poz.{w1['p2']:02d}</b> ({w1['s2']:.0f} pkt | 30g: {w1['s_hits_30'][1]}/30 | w {c_b2}/8 okn.)"
        f"</div>"
        f"</div>"
        f"<span style='font-size:32px; font-weight:900; color:#fff; background:#e63946; padding:3px 15px; border-radius:9px; border:2.5px solid #ffd166;'>{w1['b1']:02d}</span>"
        f"<span style='font-size:32px; font-weight:900; color:#fff; background:#e63946; padding:3px 15px; border-radius:9px; border:2.5px solid #ffd166;'>{w1['b2']:02d}</span>"
        f"</div>"
        f"{third_html}"
        f"</div>"
        f"<div style='display:flex; flex-wrap:wrap; justify-content:space-between; gap:10px; font-size:13px; color:#e6e6e6; padding-top:8px; border-top:1px solid rgba(255,255,255,0.16);'>"
        f"<div>🥈 <b>2. Miejsce (Okno {second_win} — 30g: {w2['p_any_30']}/30, 2/2: {w2['p_both_30']}x):</b> "
        f"Para: <b style='color:#00e676; font-size:16px;'>{w2['b1']:02d}, {w2['b2']:02d}</b> (+3.: <b>{w2['b3']:02d}</b>)</div>"
        f"<div>🔥 <b>Zgodność TOP 3 wszystkich okien:</b> <span style='color:#ffd166;'>{cons_str}</span></div>"
        f"</div>"
        f"</div>"
    )
    st.markdown(hero_v31_html, unsafe_allow_html=True)

    # =================================================================
    # NOWY MODUŁ: 🔄 RADAR OPÓŹNIEŃ (ECHO T+2) DLA ZWYCIĘSKIEGO OKNA
    # =================================================================
    best_sc = win_scorers[best_win]
    live_mp, live_mr = get_echo_candidates_at_t(best_sc, latest_idx)
    echo_30_tot = echo_30_hits = mix_30_any = mix_30_both = 0
    for st_i in range(eval_long):
        t_s = latest_idx - 1 - st_i
        nxt = all_sets[t_s + 1]
        mp_s, mr_s = get_echo_candidates_at_t(best_sc, t_s)
        c_now_s, _, _, _ = best_sc(t_s, return_df=False)
        for cm in mp_s:
            echo_30_tot += 1
            if cm["Liczba"] in nxt:
                echo_30_hits += 1
        all_ms = mp_s + mr_s
        e1_b = all_ms[0]["Liczba"] if len(all_ms) > 0 else c_now_s[1]["Liczba"]
        mh1, mh2 = (c_now_s[0]["Liczba"] in nxt), (e1_b in nxt)
        if mh1 or mh2: mix_30_any += 1
        if mh1 and mh2: mix_30_both += 1

    echo_30_pct = (echo_30_hits / max(1, echo_30_tot)) * 100.0
    mix_30_pct = ((mix_30_any + mix_30_both) / (eval_long * 2.0)) * 100.0
    live_all_echo = live_mp + live_mr
    top_echo_ball = live_all_echo[0]["Liczba"] if len(live_all_echo) > 0 else w1["b2"]

    if len(live_mp) > 0:
        mp_pills = " ".join(
            f"<span style='font-size:22px; font-weight:900; color:#fff; background:#7b2cbf; padding:2px 11px; border-radius:7px; border:2px solid #e0aaff;'>"
            f"{c['Liczba']:02d} <span style='font-size:10px; color:#e0aaff;'>({c['Rank']}, {c['Score']:.0f}p)</span></span>"
            for c in live_mp
        )
    else:
        mp_pills = "<span style='color:#00e676; font-weight:bold; font-size:13px;'>✅ Brak pudeł (oba typy #1 i #2 wpadły już w #" + str(last_draw_id) + "!)</span>"

    mr_pills = " ".join(
        f"<span style='font-size:14px; font-weight:800; color:#e0aaff; background:#241b35; padding:2px 8px; border-radius:6px; border:1px solid #9d4edd;'>"
        f"{c['Liczba']:02d} ({c['Rank']})</span>"
        for c in live_mr
    ) if len(live_mr) > 0 else "<span style='color:#8a94a6;'>brak</span>"

    echo_radar_html = (
        f"<div style='background: linear-gradient(135deg, rgba(35, 18, 58, 0.96) 0%, rgba(20, 12, 36, 0.99) 100%); "
        f"border: 2px solid #c77dff; border-radius: 12px; padding: 13px 18px; margin-bottom: 18px; font-family: sans-serif;'>"
        f"<div style='display:flex; flex-wrap:wrap; justify-content:space-between; align-items:center; gap:8px; margin-bottom:10px;'>"
        f"<div style='font-size:14px; font-weight:900; color:#e0aaff;'>"
        f"🔄 RADAR OPÓŹNIEŃ (ECHO T+2) NA #{target_draw_id} — Pudła z typowania na #{last_draw_id}, które mogą wpaść z 1-losowaniowym opóźnieniem (Okno {best_win}):"
        f"</div>"
        f"<div style='font-size:12px; color:#ffd166; font-weight:bold;'>"
        f"📊 Echo pudeł pary (ost. 30g): <b>{echo_30_hits}/{echo_30_tot} ({echo_30_pct:.1f}%)</b> | "
        f"MIKS #1 Świeża + #1 Echo (30g): <b>{mix_30_any}/30 ({mix_30_any/eval_long*100:.0f}%), 2/2: {mix_30_both}x, śr./kulę: {mix_30_pct:.1f}%</b>"
        f"</div>"
        f"</div>"
        f"<div style='display:flex; flex-wrap:wrap; gap:16px; align-items:center;'>"
        f"<div style='display:inline-flex; align-items:center; gap:8px; flex-wrap:wrap;'>"
        f"<span style='font-size:12px; color:#d0d7de; font-weight:bold;'>Pudła z Pary #1+#2 (główne Echo):</span> {mp_pills}"
        f"</div>"
        f"<div style='display:inline-flex; align-items:center; gap:8px; background:rgba(0,0,0,0.45); border:1.5px solid #ffd166; border-radius:9px; padding:5px 12px;'>"
        f"<span style='font-size:12px; color:#ffd166; font-weight:900;'>⚡ MIKS (#1 Świeża + #1 Echo):</span>"
        f"<span style='font-size:21px; font-weight:900; color:#fff; background:#e63946; padding:1px 9px; border-radius:6px;'>{w1['b1']:02d}</span>"
        f"<span style='font-size:14px; color:#ffd166; font-weight:bold;'>+</span>"
        f"<span style='font-size:21px; font-weight:900; color:#fff; background:#7b2cbf; padding:1px 9px; border-radius:6px; border:1px solid #e0aaff;'>{top_echo_ball:02d}</span>"
        f"</div>"
        f"<div style='font-size:12px; color:#b0b8c8;'>Pudła z #3–#5: {mr_pills}</div>"
        f"</div>"
        f"</div>"
    )
    st.markdown(echo_radar_html, unsafe_allow_html=True)

    # =================================================================
    # TABELA 1: ZESTAWIENIE 8 OKIEN (5–15)
    # =================================================================
    st.subheader(f"📊 1. Zestawienie Okien Analizy (5–15) — Skuteczność czystego #1+#2 na #{target_draw_id}")
    win_rows = []
    for r_i, w_val in enumerate(ranked_windows):
        wi = win_summary[w_val]
        t5_w = win_live_top5[w_val]
        if r_i == 0:
            tr_st = "background:rgba(255,209,102,0.16); border-left:4px solid #ffd166; border-bottom:2px solid #ffd166;"
            r_bdg = "<span style='background:#ffd166; color:#000; font-weight:900; padding:3px 8px; border-radius:6px; font-size:12px;'>🥇 1. MIEJSCE</span>"
        elif r_i == 1:
            tr_st = "background:rgba(0,230,118,0.12); border-left:4px solid #00e676; border-bottom:1.5px solid #00e676;"
            r_bdg = "<span style='background:#00e676; color:#000; font-weight:900; padding:3px 8px; border-radius:6px; font-size:12px;'>🥈 2. MIEJSCE</span>"
        else:
            tr_st = "background:#141720; border-bottom:1px solid #262a34;"
            r_bdg = f"<span style='color:#8a94a6; font-size:12px;'>#{r_i+1}</span>"

        pills = []
        for s_k, r_t5 in enumerate(t5_w):
            bv, sh = int(r_t5["Liczba"]), wi["s_hits_30"][s_k]
            if s_k < 2:
                pills.append(
                    f"<span style='display:inline-block; padding:3px 8px; margin:2px; border:2px solid #ffd166; border-radius:6px; "
                    f"background:#e63946; color:#fff; font-weight:900; font-size:13px;'>#{s_k+1}: {bv:02d} <span style='font-size:10px; color:#ffd166;'>({sh}/30)</span></span>"
                )
            else:
                pills.append(
                    f"<span style='display:inline-block; padding:3px 7px; margin:2px; border:1px solid #333945; border-radius:6px; "
                    f"background:#1c202b; color:#b0b8c8; font-size:12px;'>#{s_k+1}: <b>{bv:02d}</b> <span style='font-size:10px; color:#6c7385;'>({sh}/30)</span></span>"
                )

        win_rows.append(f"""
        <tr style='{tr_st}'>
            <td style='padding:8px 10px; white-space:nowrap;'>{r_bdg} &nbsp;<b style='font-size:14px; color:#fff;'>OKNO {w_val}</b></td>
            <td style='padding:8px 10px; text-align:center; white-space:nowrap;'>
                <span style='font-size:13px; font-weight:900; color:#00e676;'>30g: {wi['p_any_30']}/30 ({wi['p_any_30']/eval_long*100:.0f}%) | 2/2: {wi['p_both_30']}x</span><br>
                <span style='font-size:11px; color:#ffd166;'>Śr./kulę: {wi['ball_pct_30']:.1f}% | 10g: {wi['p_any_10']}/10 (2/2: {wi['p_both_10']}x)</span>
            </td>
            <td style='padding:8px 10px; text-align:center; white-space:nowrap;'>
                <span style='font-size:19px; font-weight:900; color:#fff; background:#e63946; padding:3px 10px; border-radius:7px; border:2px solid #ffd166; margin-right:4px;'>{wi['b1']:02d}</span>
                <span style='font-size:19px; font-weight:900; color:#fff; background:#e63946; padding:3px 10px; border-radius:7px; border:2px solid #ffd166; margin-right:6px;'>{wi['b2']:02d}</span>
                <span style='font-size:15px; font-weight:800; color:#00e676; background:#1c2536; padding:3px 8px; border-radius:6px; border:1.5px solid #00e676;'>+{wi['b3']:02d}</span>
            </td>
            <td style='padding:8px 10px; white-space:nowrap;'>{''.join(pills)}</td>
        </tr>
        """)

    tbl1_html = f"""
    <!DOCTYPE html><html><head><meta charset="utf-8"><style>
        body {{ margin:0; padding:0; background:#0e1117; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }}
        .tw {{ overflow-x:auto; border:1.5px solid #333945; border-radius:10px; }}
        table {{ width:100%; border-collapse:collapse; }}
        th {{ background:#161922; color:#ffd166; padding:9px 8px; font-size:12px; text-align:center; border-bottom:2px solid #333945; white-space:nowrap; }}
    </style></head><body><div class="tw"><table><thead><tr>
        <th style="text-align:left;">OKNO</th>
        <th>PARA #1+#2 (30g vs 10g)</th>
        <th>🎯 PARA #1+#2 (+#3)</th>
        <th style="text-align:left;">PEŁNE TOP 5 NA #{target_draw_id}</th>
    </tr></thead><tbody>{''.join(win_rows)}</tbody></table></div></body></html>
    """
    components.html(tbl1_html, height=430, scrolling=True)

    # =================================================================
    # TABELA 2: CZYTELNA TABELA GŁÓWNA + NOWA KOLUMNA "🔄 Echo T+2"
    # =================================================================
    st.divider()
    c_s1, c_s2 = st.columns([1.3, 0.9])
    with c_s1:
        auto_lbl = "⭐ Auto (Lider)"
        sel_w_opt = st.radio(
            f"⚙️ Okno dla Tabeli nr 2 (⭐ Auto = Okno {best_win}):",
            options=[auto_lbl] + all_windows,
            index=0, horizontal=True, key="v31_det_win"
        )
        detail_win = best_win if sel_w_opt == auto_lbl else int(sel_w_opt)
    with c_s2:
        detail_bt = st.radio(
            "🧪 Historia w Tabeli nr 2 (losowań):",
            options=[10, 15, 20, 30],
            index=2, horizontal=True, key="v31_det_bt"
        )

    det_scorer = win_scorers[detail_win]
    df_pred, latest_win_freq, latest_win_t1, latest_modes_set = det_scorer(latest_idx, return_df=True)
    top5_now = df_pred.head(5)

    def fmt_sub(k_pos, b_m):
        return f"P{k_pos:02d}" if is_no_blue else f"P{k_pos:02d}|M.{b_m:02d}"

    bt_rows = []
    slot_hits_bt = [0, 0, 0, 0, 0]
    det_mp_live, _ = get_echo_candidates_at_t(det_scorer, latest_idx)
    live_echo_cell = " ".join(
        f"<span style='padding:2px 6px; border:1.5px solid #e0aaff; border-radius:5px; background:#7b2cbf; color:#fff; font-weight:900; font-size:12px;'>{c['Liczba']:02d}</span>"
        for c in det_mp_live
    ) if len(det_mp_live) > 0 else "<span style='color:#00e676; font-size:10px;'>2/2 trafiły!</span>"

    # Wiersz 0: aktywne losowanie
    live_cells = []
    for k in range(5):
        r = top5_now.iloc[k]
        bv, kp, bm = int(r["Liczba"]), int(r["pos_nr"]), int(r["blue_m"])
        sub = fmt_sub(kp, bm)
        if k < 2:
            box = (
                f"<div style='display:inline-flex; flex-direction:column; align-items:center; justify-content:center; "
                f"width:54px; height:38px; border:2.5px solid #ffd166; border-radius:7px; background:#e63946; color:#fff; font-weight:900;'>"
                f"<span style='font-size:14px; line-height:14px;'>🎯{bv:02d}</span>"
                f"<span style='font-size:8px; color:#ffd166; line-height:9px;'>{sub}</span></div>"
            )
        elif k == 2:
            box = (
                f"<div style='display:inline-flex; flex-direction:column; align-items:center; justify-content:center; "
                f"width:54px; height:38px; border:2px dashed #00e676; border-radius:7px; background:#0077b6; color:#fff; font-weight:bold;'>"
                f"<span style='font-size:13px; line-height:13px;'>+{bv:02d}</span>"
                f"<span style='font-size:8px; color:#b9f6ca; line-height:9px;'>{sub}</span></div>"
            )
        else:
            box = (
                f"<div style='display:inline-flex; flex-direction:column; align-items:center; justify-content:center; "
                f"width:52px; height:36px; border:1px solid #3c4252; border-radius:6px; background:#1c202b;'>"
                f"<span style='font-size:13px; color:#d0d7de; line-height:14px;'>{bv:02d}</span>"
                f"<span style='font-size:8px; color:#8a94a6; line-height:9px;'>{sub}</span></div>"
            )
        live_cells.append(f"<td style='padding:5px 3px; text-align:center; border-right:1px solid #333945;'>{box}</td>")

    lb1, lb2, lb3 = int(top5_now.iloc[0]["Liczba"]), int(top5_now.iloc[1]["Liczba"]), int(top5_now.iloc[2]["Liczba"])
    lp1, lp2 = int(top5_now.iloc[0]["pos_nr"]), int(top5_now.iloc[1]["pos_nr"])
    bt_rows.append(f"""
    <tr style='background:linear-gradient(90deg, rgba(255,209,102,0.22) 0%, rgba(0,230,118,0.18) 100%); border-top:2.5px solid #ffd166; border-bottom:3px solid #ffd166;'>
        <td style='padding:7px 6px; color:#ffd166; font-weight:900; white-space:nowrap; font-size:11px;'>🔥 #{last_draw_id}<br><span style='font-size:9px; color:#fff;'>({last_time_str})</span></td>
        <td style='padding:7px 6px; font-weight:900; color:#00e676; white-space:nowrap; font-size:12px; border-right:2px solid #ffd166;'>🎯 #{target_draw_id}<br><span style='font-size:9px; color:#ffd166;'>({target_time_str})</span></td>
        <td style='padding:7px 6px; text-align:center; white-space:nowrap; border-right:2px solid #ffd166;'>
            <span style='padding:3px 6px; border:2px solid #ffd166; border-radius:6px; background:#e63946; color:#fff; font-weight:900; font-size:13px;'>{lb1:02d}(P{lp1:02d})</span>
            <span style='padding:3px 6px; border:2px solid #ffd166; border-radius:6px; background:#e63946; color:#fff; font-weight:900; font-size:13px;'>{lb2:02d}(P{lp2:02d})</span>
        </td>
        <td style='padding:7px 6px; text-align:center; white-space:nowrap; border-right:2px solid #c77dff;'>{live_echo_cell}</td>
        {''.join(live_cells)}
        <td style='padding:7px 6px; text-align:center; font-weight:900; font-size:11px; color:#ffd166; border-left:2px solid #ffd166;'>⏳ W GRZE</td>
        <td style='padding:7px 6px; text-align:center; font-weight:900; font-size:11px; color:#00e676;'>#{target_draw_id}</td>
    </tr>
    """)

    echo_bt_hits = echo_bt_tot = 0
    for st_i in range(detail_bt):
        t_s = latest_idx - 1 - st_i
        cands_s, _, _, _ = det_scorer(t_s, return_df=False)
        nxt = all_sets[t_s + 1]
        t5_s, t8_s = cands_s[:5], cands_s[:8]
        mp_s, _ = get_echo_candidates_at_t(det_scorer, t_s)

        echo_badges = []
        for cm in mp_s:
            echo_bt_tot += 1
            if cm["Liczba"] in nxt:
                echo_bt_hits += 1
                echo_badges.append(f"<span style='padding:2px 5px; border:1.5px solid #e0aaff; border-radius:4px; background:rgba(157,78,221,0.45); color:#fff; font-weight:bold;'>{cm['Liczba']:02d}🟩</span>")
            else:
                echo_badges.append(f"<span style='color:#7d8597;'>{cm['Liczba']:02d}</span>")
        echo_cell_html = " ".join(echo_badges) if echo_badges else "<span style='color:#4a5568; font-size:10px;'>— (2/2)</span>"

        row_cells = []
        for k, rp in enumerate(t5_s):
            bv, kp, bm = int(rp["Liczba"]), int(rp["pos_nr"]), int(rp["blue_m"])
            sub = fmt_sub(kp, bm)
            is_h = (bv in nxt)
            tint = "background-color:rgba(255,209,102,0.06);" if k < 2 else ""
            if is_h:
                slot_hits_bt[k] += 1
                bc = "#ffd166" if k < 2 else "#00e676"
                box = (
                    f"<div style='display:inline-flex; flex-direction:column; align-items:center; justify-content:center; "
                    f"width:52px; height:34px; border:2px solid {bc}; border-radius:6px; background:rgba(0,230,118,0.30); color:#fff; font-weight:bold;'>"
                    f"<span style='font-size:13px; line-height:13px;'>{bv:02d}</span>"
                    f"<span style='font-size:8px; color:#b9f6ca; line-height:9px;'>{sub}</span></div>"
                )
            else:
                box = (
                    f"<div style='display:inline-flex; flex-direction:column; align-items:center; justify-content:center; "
                    f"width:52px; height:34px; border:1px solid #2b303c; border-radius:6px; background:#151821;'>"
                    f"<span style='font-size:12px; color:#a8b0c0; line-height:13px;'>{bv:02d}</span>"
                    f"<span style='font-size:8px; color:#6c7385; line-height:9px;'>{sub}</span></div>"
                )
            row_cells.append(f"<td style='padding:3px 3px; text-align:center; border-right:1px solid #232731; {tint}'>{box}</td>")

        g1b, g2b = int(t5_s[0]["Liczba"]), int(t5_s[1]["Liczba"])
        g1p, g2p = int(t5_s[0]["pos_nr"]), int(t5_s[1]["pos_nr"])
        g1h, g2h = (g1b in nxt), (g2b in nxt)
        b1_html = f"<span style='padding:2px 5px; border:1.5px solid #ffd166; border-radius:4px; background:rgba(255,209,102,0.30); color:#fff; font-weight:bold;'>{g1b:02d}(P{g1p:02d})🟩</span>" if g1h else f"<span style='color:#9da3af;'>{g1b:02d}(P{g1p:02d})</span>"
        b2_html = f"<span style='padding:2px 5px; border:1.5px solid #00e676; border-radius:4px; background:rgba(0,230,118,0.28); color:#fff; font-weight:bold;'>{g2b:02d}(P{g2p:02d})🟩</span>" if g2h else f"<span style='color:#9da3af;'>{g2b:02d}(P{g2p:02d})</span>"

        h5 = sum(1 for r in t5_s if r["Liczba"] in nxt)
        h8 = sum(1 for r in t8_s if r["Liczba"] in nxt)
        h5c = "#00e676" if h5 >= 2 else ("#ffd166" if h5 == 1 else "#6c7385")
        h5bg = "rgba(0,230,118,0.16)" if h5 >= 2 else "transparent"

        bt_rows.append(f"""
        <tr style='border-bottom:1px solid #262a34;'>
            <td style='padding:5px 6px; color:#9da3af; white-space:nowrap; font-size:11px;'>#{all_ids[t_s]}<br><span style='font-size:9px; color:#6c7385;'>({all_times[t_s]})</span></td>
            <td style='padding:5px 6px; font-weight:bold; color:#fff; white-space:nowrap; font-size:11px; border-right:2px solid #333945;'>#{all_ids[t_s+1]}</td>
            <td style='padding:5px 6px; text-align:center; white-space:nowrap; font-size:11px; border-right:2px solid #333945;'>{b1_html} &nbsp; {b2_html}</td>
            <td style='padding:5px 6px; text-align:center; white-space:nowrap; font-size:11px; border-right:2px solid #333945; background:rgba(157,78,221,0.06);'>{echo_cell_html}</td>
            {''.join(row_cells)}
            <td style='padding:5px 6px; text-align:center; font-weight:bold; font-size:12px; color:{h5c}; background:{h5bg}; border-left:2px solid #333945;'>{h5} / 5</td>
            <td style='padding:5px 6px; text-align:center; font-weight:bold; font-size:12px; color:#4da6ff;'>{h8} / 8</td>
        </tr>
        """)

    st.markdown(f"### 📋 2. Tabela Główna V31 (Okno {detail_win} | **{mode_tag}**) — Czyste #1+#2 oraz **🔄 Echo T+2** na **#{target_draw_id} ({target_time_str})**")

    hdrs = []
    for k in range(5):
        hc = slot_hits_bt[k]
        if k < 2:
            hdrs.append(f"<th style='background:#4a3805; color:#ffd166; border-top:3px solid #ffd166; border-left:2px solid #ffd166; border-right:2px solid #ffd166;'>👑 TYP #{k+1}<br><span style='font-size:10px; color:#fff;'>({hc}/{detail_bt} = {hc/detail_bt*100:.0f}%)</span></th>")
        elif k == 2:
            hdrs.append(f"<th style='background:#083d25; color:#00e676; border-top:2px dashed #00e676;'>➕ TYP #3<br><span style='font-size:9px; color:#b9f6ca;'>({hc}/{detail_bt} = {hc/detail_bt*100:.0f}%)</span></th>")
        else:
            hdrs.append(f"<th style='color:#d0d7de;'>Typ #{k+1}<br><span style='font-size:9px; color:#8a94a6;'>({hc}/{detail_bt})</span></th>")

    echo_bt_pct = (echo_bt_hits / max(1, echo_bt_tot)) * 100.0
    tbl2_html = f"""
    <!DOCTYPE html><html><head><meta charset="utf-8"><style>
        body {{ margin:0; padding:0; background:#0e1117; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }}
        .tc {{ max-height:640px; overflow:auto; border:1.5px solid #ffd166; border-radius:10px; }}
        table {{ width:100%; border-collapse:collapse; }}
        thead {{ position:sticky; top:0; background:#161922; z-index:10; border-bottom:2px solid #333945; }}
        th {{ padding:7px 5px; text-align:center; color:#e6e6e6; font-size:11px; white-space:nowrap; }}
    </style></head><body><div class="tc"><table><thead><tr>
        <th style="text-align:left;">Z losowania</th>
        <th style="text-align:left; border-right:2px solid #333945;">Do (T+1)</th>
        <th style="border-right:2px solid #333945; color:#ffd166;">👑 Para #1+#2</th>
        <th style="border-right:2px solid #333945; color:#e0aaff; background:#241438;">🔄 Echo T+2<br><span style="font-size:9px; color:#c77dff;">({echo_bt_hits}/{echo_bt_tot} = {echo_bt_pct:.0f}%)</span></th>
        {''.join(hdrs)}
        <th style="border-left:2px solid #333945; color:#00e676;">TOP 5</th>
        <th style="color:#4da6ff;">TOP 8</th>
    </tr></thead><tbody>{''.join(bt_rows)}</tbody></table></div></body></html>
    """
    components.html(tbl2_html, height=660, scrolling=False)

    # =================================================================
    # TABELA 3 (RANKING 20 LICZB) + TABELA 4 (GORĄCE KULE)
    # =================================================================
    col_r3, col_r4 = st.columns([1.45, 0.95], gap="large")
    with col_r3:
        st.markdown(f"#### 📊 3. Pełny Ranking 20 liczb z #{last_draw_id} ➔ na #{target_draw_id} (Okno {detail_win} | {mode_tag})")
        drop_cols = ["pos_nr", "blue_m", "w15_hits", "pw_pct", "b_pct", "is_overheated", "bt1_win"]
        if is_no_blue:
            drop_cols.append("🟦 Kolumna M")
        df_disp = df_pred.drop(columns=drop_cols).copy()

        col_cfg = {
            "Rank": st.column_config.TextColumn("Typ #", width="small"),
            "Pozycja": st.column_config.TextColumn("Pozycja" if is_no_blue else "Poz. (🟦 M.)", width="medium"),
            "Liczba": st.column_config.NumberColumn("Kula", width="small"),
            "Score": st.column_config.ProgressColumn("Siła (Score)", format="%.1f pkt", min_value=0, max_value=100),
            "Status V31": st.column_config.TextColumn("Status V31", width="medium"),
            "⬜ Własne (okno i 15)": st.column_config.TextColumn(f"⬜ Własne ({detail_win} i 15)", width="medium"),
            "Węzeł": st.column_config.TextColumn("Węzeł", width="medium"),
            "Fala Kuli": st.column_config.TextColumn("Fala Kuli", width="medium"),
            "⭐ Najczęstsza": st.column_config.TextColumn("⭐ Najczęstsza", width="small"),
        }
        if not is_no_blue:
            col_cfg["🟦 Kolumna M"] = st.column_config.TextColumn(f"🟦 Kolumna M ({detail_win})", width="medium")

        st.dataframe(df_disp, column_config=col_cfg, hide_index=True, use_container_width=True, height=520, key="v31_rank_tbl")

    with col_r4:
        st.markdown(f"#### 🔥 4. Najczęściej losowane kule w oknie {detail_win}")
        curr_set_now = all_sets[latest_idx]
        hot_rows = []
        for b_num in range(1, 71):
            fc = latest_win_freq[b_num]
            if fc == 0:
                continue
            in_l = (b_num in curr_set_now)
            pos_l = (all_lists[latest_idx].index(b_num) + 1) if in_l else None
            hot_rows.append({
                "Kula": b_num, "f_r": fc, "t1_r": latest_win_t1[b_num], "in_r": 1 if in_l else 0,
                f"W oknie ({detail_win})": f"{fc}x ({fc/detail_win*100:.0f}%)",
                "Powtórki T+1": f"{latest_win_t1[b_num]}x" if latest_win_t1[b_num] > 0 else "0x",
                "Najczęstsza": "⭐ TAK" if b_num in latest_modes_set else "-",
                "Teraz w grze?": f"✅ Poz. {pos_l:02d}" if in_l else "⏳ Przerwa"
            })
        df_hot = pd.DataFrame(hot_rows).sort_values(
            by=["t1_r", "f_r", "in_r"], ascending=[False, False, False], kind="mergesort"
        ).head(25).drop(columns=["f_r", "t1_r", "in_r"])
        st.dataframe(df_hot, hide_index=True, use_container_width=True, height=520, key="v31_hot_tbl")

# Wywołanie modułu V31:
render_prediction_algorithm(df, default_window=10, default_blue_win=10, default_backtest=20)
