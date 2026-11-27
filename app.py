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
# MODUŁ ALGORYTMU PREDYKCYJNEGO V29:
# 1) DOMYŚLNY TRYB "⬜ BEZ TABELI NIEBIESKIEJ" (ZWYCIĘZCA TESTU A/B NA 1241 GRACH)
# 2) BLOKADA SŁABYCH SLOTÓW #4/#5: WYBÓR PARY TYLKO W TOP 3 Z PROGIEM MIN. 3x PEŁNE 2/2 (+ OPCJA SZTYWNE #1+#2)
# 3) WYGŁADZONA PUNKTACJA (OCHRONA GORĄCYCH KUL Z >=3x POWT. T+1 PRZED SPADKIEM NA #9-#11)
# 4) ROZSZERZONY TEST A/B (WALK-FORWARD): SZTYWNE #1+#2 vs SKANER TOP 3 vs STARY #1-#5 + SKANER 8 OKIEN
# =====================================================================
from collections import defaultdict, Counter
from itertools import combinations
from datetime import datetime, timedelta

def render_prediction_algorithm(df_full, default_window=10, default_blue_win=10, default_backtest=10):
    st.divider()

    all_windows = [5, 6, 7, 8, 9, 10, 12, 15]
    all_bt_horizons = [10, 15, 20, 30]
    matrix_bt_steps = 30
    recent_rank_steps = 10
    meta_bt_max = 20
    elite_models_total = len(all_bt_horizons) * 3  # 12 elitarnych modeli

    if len(df_full) < 45 + matrix_bt_steps + meta_bt_max:
        st.warning(f"Za mało danych w bazie ({len(df_full)}), aby wykonać pełną analizę i test A/B.")
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

    st.header(f"🧠 Algorytm V29 — Tryb Bez Niebieskiej + Blokada TOP 3 + Test A/B na #{target_draw_id} (godz. {target_time_str})")

    # =================================================================
    # PRZEŁĄCZNIKI: TRYB SILNIKA (DOMYŚLNIE BEZ NIEBIESKIEJ) + STRATEGIA PARY
    # =================================================================
    mode_labels = {
        "⬜ Bez Tabeli Niebieskiej (Tabela 1 + Kule)": "no_blue",
        "🔄 Hybryda (Tabela 1 + Niebieska 🟦)": "hybrid",
        "🟦 Tylko Tabela Niebieska (bez Tabeli 1)": "only_blue",
    }
    pair_strat_labels = {
        "⚙️ Skaner w TOP 3 (z progiem 2/2)": "top3_guard",
        "🎯 Sztywna Para #1 + #2 (czysty szczyt)": "fixed_12",
    }

    col_m1, col_m2 = st.columns([1.35, 1.0])
    with col_m1:
        selected_mode_label = st.radio(
            "🎛️ Tryb pracy silnika (domyślnie zwycięski Bez Niebieskiej):",
            options=list(mode_labels.keys()),
            index=0,
            horizontal=True,
            key="v29_engine_mode_radio"
        )
    with col_m2:
        selected_strat_label = st.radio(
            "🎯 Strategia wyboru 2 Głównych Liczb (blokada słabych #4/#5):",
            options=list(pair_strat_labels.keys()),
            index=0,
            horizontal=True,
            key="v29_pair_strat_radio"
        )

    active_engine_mode = mode_labels[selected_mode_label]
    active_pair_strategy = pair_strat_labels[selected_strat_label]

    # =================================================================
    # SZYBKI SILNIK V29 (WYGŁADZONA PUNKTACJA + OCHRONA GORĄCYCH KUL >=3x)
    # =================================================================
    def run_engine_v29(w_size, b_lookback, steps_needed_back, engine_mode="no_blue"):
        earliest_needed = max(max(w_size, b_lookback, 15) - 1, total_draws - 1 - steps_needed_back - max(b_lookback, 15) - 4)
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

            b_start = t_i - b_lookback + 1
            b_lists = all_lists[b_start : t_i + 1]
            b_sets = all_sets[b_start : t_i + 1]
            b_trans = max(1, len(b_lists) - 1)

            pos_modes = {}
            all_modes_set = set()
            white_hits_w = {}
            white_hits_15 = {}
            pos_temp_blue = []

            for i in range(1, 21):
                p_idx = i - 1
                rep_w = sum(1 for k in range(n_trans) if w_lists[k][p_idx] in w_sets[k + 1])
                white_hits_w[i] = rep_w
                white_hits_15[i] = sum(1 for k in range(n15_trans) if w15_lists[k][p_idx] in w15_sets[k + 1])

                cnts = Counter(w_lists[k][p_idx] for k in range(len(w_lists)))
                m_cnt = max(cnts.values())
                m_val = min(k for k, v in cnts.items() if v == m_cnt)
                pos_modes[i] = (m_val, m_cnt)
                if m_cnt >= min_mode_thr:
                    all_modes_set.add(m_val)

                rep_b = sum(1 for k in range(b_trans) if b_lists[k][p_idx] in b_sets[k + 1])
                pos_temp_blue.append((rep_b, i, curr_l[p_idx]))

            pos_temp_blue.sort(key=lambda x: (-x[0], x[1]))

            blue_col_for_orig_pos = {}
            blue_hit_by_col = {}
            for rank_idx, (_, o_pos, b_val) in enumerate(pos_temp_blue):
                m_col = rank_idx + 1
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

        score_cache = {}

        def score_at_t(t_idx, return_df=False):
            if t_idx in score_cache and not return_df:
                return score_cache[t_idx]

            win_start = t_idx - w_size + 1
            win_lists = all_lists[win_start : t_idx + 1]
            win_sets = all_sets[win_start : t_idx + 1]
            trans_count = max(1, len(win_lists) - 1)

            curr_nums = all_lists[t_idx]
            prev_list = all_lists[t_idx - 1] if t_idx >= 1 else []
            prev_set = all_sets[t_idx - 1] if t_idx >= 1 else set()

            meta_now = local_meta[t_idx]
            blue_col_map_now = meta_now["blue_col_map"]
            white_hits_15_now = meta_now["white_hits_15"]
            n15_trans_now = meta_now["n15_trans"]
            pos_modes_now = meta_now["pos_modes"]
            all_modes_set_now = meta_now["all_modes_set"]
            min_thr = meta_now["min_mode_thr"]

            max_w15_in_draw = max(white_hits_15_now.values()) if white_hits_15_now else 5

            blue_col_hits = [0] * 21
            blue_col_rec2 = [0] * 21
            blue_col_rec3 = [0] * 21
            orig_pos_hits_bwin = [0] * 21
            orig_pos_rec2 = [0] * 21
            orig_pos_rec3 = [0] * 21
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
                        p_nr_tmp = p_i + 1
                        orig_pos_hits_bwin[p_nr_tmp] += 1
                        if is_r2:
                            orig_pos_rec2[p_nr_tmp] += 1
                        if is_r3:
                            orig_pos_rec3[p_nr_tmp] += 1

            prev1_blue_hits = local_meta[t_idx - 1]["blue_hit_by_col"] if (t_idx - 1) in local_meta else {}
            prev2_blue_hits = local_meta[t_idx - 2]["blue_hit_by_col"] if (t_idx - 2) in local_meta else {}

            w15_start_idx = max(0, t_idx - 14)
            w15_lists_slice = all_lists[w15_start_idx : t_idx + 1]
            w15_sets_slice = all_sets[w15_start_idx : t_idx + 1]

            win_ball_freq = [0] * 71
            win_ball_t1_repeats = [0] * 71
            for k_idx, d_list in enumerate(win_lists):
                nxt_w_s = win_sets[k_idx + 1] if k_idx < trans_count else None
                for b in d_list:
                    win_ball_freq[b] += 1
                    if nxt_w_s is not None and b in nxt_w_s:
                        win_ball_t1_repeats[b] += 1

            ball_15_freq = [0] * 71
            ball_15_t1_repeats = [0] * 71
            w15_last_k = len(w15_lists_slice) - 1
            for k_idx, d15_l in enumerate(w15_lists_slice):
                nxt_15_s = w15_sets_slice[k_idx + 1] if k_idx < w15_last_k else None
                for b in d15_l:
                    ball_15_freq[b] += 1
                    if nxt_15_s is not None and b in nxt_15_s:
                        ball_15_t1_repeats[b] += 1

            sq_1_ago = [False] * 21
            sq_2_ago = [False] * 21
            if t_idx >= 1:
                curr_s_now = all_sets[t_idx]
                prev_l_1 = all_lists[t_idx - 1]
                for p_i in range(20):
                    if prev_l_1[p_i] in curr_s_now:
                        sq_1_ago[p_i + 1] = True
            if t_idx >= 2:
                prev_s_1 = all_sets[t_idx - 1]
                prev_l_2 = all_lists[t_idx - 2]
                for p_i in range(20):
                    if prev_l_2[p_i] in prev_s_1:
                        sq_2_ago[p_i + 1] = True

            min_strong_white_hits = max(2, int(round(trans_count * 0.30)))
            denom_b = max(1, blue_steps_avail)

            candidates = []
            for p_i in range(20):
                pos_nr = p_i + 1
                ball = curr_nums[p_i]

                m_col, pos_white_hits = blue_col_map_now[pos_nr]
                b_hits_cnt = blue_col_hits[m_col]
                b_hit_rate = b_hits_cnt / denom_b
                b_r2 = blue_col_rec2[m_col]
                b_r3 = blue_col_rec3[m_col]

                pos_white_rate = pos_white_hits / trans_count
                w15_hits = white_hits_15_now[pos_nr]

                orig_bwin_cnt = orig_pos_hits_bwin[pos_nr]
                orig_bwin_rate = orig_bwin_cnt / denom_b
                o_r2 = orig_pos_rec2[pos_nr]
                o_r3 = orig_pos_rec3[pos_nr]

                in_prev1 = (ball in prev_set)
                exact_same_pos_in_t1 = (t_idx >= 1 and prev_list[p_i] == ball)

                sq_d1 = sq_1_ago[pos_nr]
                sq_d2 = sq_2_ago[pos_nr]
                sq_n1 = (pos_nr > 1 and sq_1_ago[pos_nr - 1]) or (pos_nr < 20 and sq_1_ago[pos_nr + 1])

                b_u1 = prev1_blue_hits.get(m_col, False)
                b_u2 = prev2_blue_hits.get(m_col, False)
                b_adj1 = prev1_blue_hits.get(m_col - 1, False) or prev1_blue_hits.get(m_col + 1, False)

                ball_freq_in_win = win_ball_freq[ball]
                ball_freq_rate = ball_freq_in_win / max(1, w_size)
                ball_t1_in_win = win_ball_t1_repeats[ball]
                ball_t1_15 = ball_15_t1_repeats[ball]
                ball_f_15 = ball_15_freq[ball]

                mode_on_pos, mode_cnt_on_pos = pos_modes_now[pos_nr]
                is_exact_mode = (ball == mode_on_pos and mode_cnt_on_pos >= min_thr)
                mode_str = f"🎯 Lider Poz.{pos_nr:02d} (x{mode_cnt_on_pos})" if is_exact_mode else ("⭐ W 'Najczęstszej'" if ball in all_modes_set_now else "-")

                is_top_w15_leader = (w15_hits >= max(4, max_w15_in_draw - 1))
                is_blue_table_leader = (b_hit_rate >= 0.40 and b_r3 >= 1)
                # WZMOCNIONA OCHRONA GORĄCYCH KUL (np. 54 z 4x powt. T+1 oraz 11 z 3x powt. T+1!)
                is_super_hot_ball = (
                    (ball_freq_rate >= 0.45 and ball_t1_in_win >= 3)
                    or (ball_t1_in_win >= 4)
                    or (ball_f_15 >= 7 and ball_t1_15 >= 4)
                )
                is_sweet_spot_ball = (0.33 <= ball_freq_rate <= 0.58 and (ball_t1_in_win >= 2 or ball_t1_15 >= 2))
                is_hot_repeater = is_super_hot_ball or (ball_t1_in_win >= 3 or (ball_t1_in_win >= 2 and ball in all_modes_set_now))
                is_overheated_ball = (ball_freq_rate > 0.68 and ball_t1_in_win <= 1 and not (in_prev1 and sq_d1))

                source_pos = None
                is_transfer_from_strong_pos = False
                if in_prev1 and prev_list:
                    source_pos = prev_list.index(ball) + 1
                    _, source_white_hits = blue_col_map_now[source_pos]
                    rec_cond = (o_r2 >= 1) if engine_mode == "no_blue" else (o_r2 >= 1 or b_r2 >= 1)
                    if (
                        source_pos != pos_nr
                        and abs(source_pos - pos_nr) <= 1
                        and rec_cond
                        and (ball_t1_in_win >= 2 or ball_t1_15 >= 2)
                        and source_white_hits >= min_strong_white_hits
                    ):
                        is_transfer_from_strong_pos = True

                if engine_mode == "no_blue":
                    # --- TRYB ⬜ BEZ TABELI NIEBIESKIEJ (V29: WYGŁADZONA PRZEPAŚĆ #5/#6 + OCHRONA >=3x POWT.) ---
                    has_direct_t1_square = sq_d1
                    eff_blue_leader_flag = 0

                    if sq_d1 and sq_d2:
                        pts_node = 18.0
                        path_str = "⬜⬜ Seria białych kwadratów (T-1 & T-2)!"
                    elif sq_d1:
                        pts_node = 16.0
                        path_str = "⬜ Biały kwadrat w T-1!"
                    elif is_transfer_from_strong_pos:
                        pts_node = 13.5
                        path_str = f"🔄🔴 Transfer z Poz.{source_pos:02d}"
                    elif sq_d2:
                        pts_node = 10.5
                        path_str = f"⬜ Biały kwadrat w t-2 ({o_r2}x)"
                    elif sq_n1:
                        pts_node = 5.5
                        path_str = "⬜ Kwadrat tuż obok"
                    else:
                        pts_node = 0.0
                        path_str = "Brak ⬜ w 2 ost."

                    if 0.33 <= pos_white_rate <= 0.62:
                        pts_white_pos = 19.0
                    elif pos_white_rate > 0.62:
                        pts_white_pos = 16.5
                    else:
                        pts_white_pos = round(min(15.5, (pos_white_rate / 0.33) * 15.5), 1)

                    w15_rel_ratio = w15_hits / max(1.0, float(max_w15_in_draw))
                    pts_w15_stability = round(min(18.0, w15_rel_ratio * 18.0), 1) if w15_hits >= 3 else round(w15_rel_ratio * 8.5, 1)

                    pts_mode = 6.0 if is_exact_mode else (3.5 if ball in all_modes_set_now else 0.0)
                    ball_bonus = 11.0 if is_super_hot_ball else (8.0 if is_hot_repeater else (5.0 if is_sweet_spot_ball else (-3.5 if is_overheated_ball else 0.0)))
                    pts_ball_t1 = min(28.0, max(0.0, (ball_t1_in_win * 5.0) + (ball_t1_15 * 2.4) + ball_bonus))
                    score_ball = round(min(34.0, pts_mode + pts_ball_t1), 1)

                    series_bonus = 0.0
                    if in_prev1 and (sq_d1 or exact_same_pos_in_t1 or is_transfer_from_strong_pos) and (ball_t1_in_win >= 2 or ball_t1_15 >= 2):
                        series_bonus = 5.5
                        path_str += " | 👑 Seria"
                    elif in_prev1 and (sq_d1 or is_transfer_from_strong_pos):
                        series_bonus = 2.5
                        path_str += " | 🔴 z T-1"

                    soft_penalty = 0.0
                    if ball_t1_in_win == 0 and not in_prev1:
                        soft_penalty += 4.5
                    # Pełna ochrona przed karą o_r3 dla gorących kul mających >=3x powt. T+1!
                    if not sq_d1 and not is_transfer_from_strong_pos and not is_super_hot_ball and ball_t1_in_win < 3:
                        if not is_hot_repeater and not is_top_w15_leader:
                            soft_penalty += 4.5
                        if o_r3 == 0:
                            soft_penalty += 9.5
                        elif o_r2 == 0 and not is_top_w15_leader:
                            soft_penalty += 5.5
                    if w15_hits <= 1 and n15_trans_now >= 12 and not sq_d1 and not is_super_hot_ball and ball_t1_in_win < 3:
                        soft_penalty += 10.0

                    raw_score = pts_node + pts_white_pos + pts_w15_stability + score_ball + series_bonus - soft_penalty
                    final_score = round(min(99.0, max(5.0, raw_score)), 1)

                    if in_prev1 and (sq_d1 or exact_same_pos_in_t1 or is_transfer_from_strong_pos) and (ball_t1_in_win >= 2 or ball_t1_15 >= 2):
                        verdict_str = "👑 POTWIERDZONA SERIA (🔴+⬜)"
                    elif is_super_hot_ball:
                        verdict_str = f"🌋 SUPER-GORĄCA KULA ({ball_t1_in_win}x powt.)"
                    elif sq_d1:
                        verdict_str = f"⬜ Żywy Kwadrat Poz.{pos_nr:02d} ({w15_hits}/14)"
                    elif is_top_w15_leader:
                        verdict_str = f"🏆 Lider Tabeli 15 ({w15_hits}/{n15_trans_now} ⬜)"
                    elif is_hot_repeater:
                        verdict_str = f"🔥 Gorąca Kula ({ball_t1_in_win}x powt.)"
                    elif soft_penalty >= 10.0:
                        verdict_str = f"❄️ Chłodna Poz.{pos_nr:02d}"
                    else:
                        verdict_str = "⏳ Aktywna w t-2"

                elif engine_mode == "only_blue":
                    # --- TRYB 🟦 TYLKO TABELA NIEBIESKA ---
                    has_direct_t1_square = b_u1
                    eff_blue_leader_flag = 1 if is_blue_table_leader else 0

                    pts_blue_rate = round(min(48.0, (b_hit_rate / 0.55) * 48.0), 1)
                    if b_u1 and b_u2:
                        pts_b_node = 28.0
                        path_str = "🟦🟦 Podwójny niebieski kwadrat (T-1 & T-2)!"
                    elif b_u1:
                        pts_b_node = 23.0
                        path_str = "🟦 Niebieski kwadrat w T-1!"
                    elif b_u2:
                        pts_b_node = 14.0
                        path_str = f"🟦 Niebieski kwadrat w t-2 ({b_r2}x)"
                    elif b_adj1:
                        pts_b_node = 6.0
                        path_str = "🟦 Kwadrat na sąsiednim M"
                    else:
                        pts_b_node = 0.0
                        path_str = "Brak 🟦 w 2 ost."

                    pts_zone = 12.0 if (m_col <= 6 and b_hit_rate >= 0.30) else (6.0 if (m_col <= 10 and b_hit_rate >= 0.30) else 0.0)
                    pts_orig = round(min(12.0, (orig_bwin_rate / 0.50) * 12.0), 1)

                    soft_penalty = 0.0
                    if b_r3 == 0:
                        soft_penalty += 15.0
                    elif b_r2 == 0 and not is_blue_table_leader:
                        soft_penalty += 8.0
                    if b_hit_rate <= 0.22:
                        soft_penalty += 10.0

                    raw_score = pts_blue_rate + pts_b_node + pts_zone + pts_orig - soft_penalty
                    final_score = round(min(99.0, max(5.0, raw_score)), 1)

                    if is_blue_table_leader and b_u1:
                        verdict_str = f"🟦👑 Lider + Kwadrat M.{m_col:02d} ({b_hits_cnt}/{blue_steps_avail})"
                    elif is_blue_table_leader:
                        verdict_str = f"🟦👑 Lider Tab.🟦 M.{m_col:02d} ({b_hits_cnt}/{blue_steps_avail})"
                    elif b_u1:
                        verdict_str = f"🟦 Żywy Kwadrat M.{m_col:02d} ({b_hits_cnt}/{blue_steps_avail})"
                    elif soft_penalty >= 12.0:
                        verdict_str = f"❄️ Chłodna M.{m_col:02d}"
                    else:
                        verdict_str = f"🟦 Aktywna M.{m_col:02d} ({b_hits_cnt}/{blue_steps_avail})"

                else:
                    # --- TRYB 🔄 HYBRYDA ---
                    has_direct_t1_square = (sq_d1 or b_u1)
                    eff_blue_leader_flag = 1 if is_blue_table_leader else 0

                    if sq_d1 and b_u1:
                        pts_node = 18.0
                        path_str = "⬜+🟦 Podwójny kwadrat w T-1!"
                    elif sq_d1:
                        pts_node = 15.5
                        path_str = "⬜ Biały kwadrat w T-1!"
                    elif b_u1:
                        pts_node = 14.0
                        path_str = "🟦 Niebieski kwadrat w T-1!"
                    elif is_blue_table_leader and (sq_d2 or b_u2):
                        pts_node = 13.5
                        path_str = f"🟦👑 Lider M.{m_col:02d} ({b_hits_cnt}/{blue_steps_avail}) + kwadrat w t-2!"
                    elif sq_d2 and b_u2:
                        pts_node = 11.5
                        path_str = "⬜+🟦 Podwójny kwadrat w t-2"
                    elif is_transfer_from_strong_pos:
                        pts_node = 12.0
                        path_str = f"🔄🔴 Transfer z Poz.{source_pos:02d}"
                    elif sq_d2 or b_u2:
                        pts_node = 8.5
                        path_str = f"Aktywna w t-2 (⬜:{o_r2}x, 🟦:{b_r2}x)"
                    elif sq_n1 or b_adj1:
                        pts_node = 4.0
                        path_str = "Kwadrat tuż obok"
                    else:
                        pts_node = 0.0
                        path_str = "Brak kwadratu w 2 ost."

                    if 0.33 <= pos_white_rate <= 0.62:
                        pts_white_pos = 14.5
                    elif pos_white_rate > 0.62:
                        pts_white_pos = 12.5
                    else:
                        pts_white_pos = round(min(11.5, (pos_white_rate / 0.33) * 11.5), 1)

                    w15_rel_ratio = w15_hits / max(1.0, float(max_w15_in_draw))
                    pts_w15_stability = round(min(12.5, w15_rel_ratio * 12.5), 1) if w15_hits >= 3 else round(w15_rel_ratio * 6.0, 1)

                    pts_blue_rate = round(min(17.5, (b_hit_rate / 0.50) * 17.5), 1)
                    pts_blue_leader_bonus = 3.5 if is_blue_table_leader else (2.0 if (m_col <= 6 and b_hit_rate >= 0.30) else 0.0)
                    pts_orig_bwin = round(min(3.0, (orig_bwin_rate / 0.45) * 3.0), 1)
                    score_blue = min(24.0, pts_blue_rate + pts_blue_leader_bonus + pts_orig_bwin)

                    pts_mode = 5.0 if is_exact_mode else (3.0 if ball in all_modes_set_now else 0.0)
                    ball_bonus = 9.5 if is_super_hot_ball else (6.5 if is_hot_repeater else (4.5 if is_sweet_spot_ball else (-3.5 if is_overheated_ball else 0.0)))
                    pts_ball_t1 = min(23.0, max(0.0, (ball_t1_in_win * 4.4) + (ball_t1_15 * 2.0) + ball_bonus))
                    score_ball = round(min(28.0, pts_mode + pts_ball_t1), 1)

                    series_bonus = 0.0
                    if in_prev1 and (sq_d1 or exact_same_pos_in_t1 or is_transfer_from_strong_pos) and (ball_t1_in_win >= 2 or ball_t1_15 >= 2):
                        series_bonus = 5.5
                        path_str += " | 👑 Seria"
                    elif in_prev1 and (has_direct_t1_square or is_transfer_from_strong_pos):
                        series_bonus = 2.5
                        path_str += " | 🔴 z T-1"

                    soft_penalty = 0.0
                    if b_hit_rate <= 0.22 and b_hits_cnt <= 3 and not is_super_hot_ball:
                        soft_penalty += 6.0
                    if ball_t1_in_win == 0 and not in_prev1:
                        soft_penalty += 4.0
                    if not has_direct_t1_square and not is_blue_table_leader and not is_transfer_from_strong_pos and not is_super_hot_ball and ball_t1_in_win < 3:
                        if not is_hot_repeater and not is_top_w15_leader:
                            soft_penalty += 4.5
                        if o_r3 == 0 and b_r3 == 0:
                            soft_penalty += 9.5
                        elif o_r2 == 0 and b_r2 == 0 and not is_top_w15_leader:
                            soft_penalty += 6.0
                    if w15_hits <= 1 and n15_trans_now >= 12 and not has_direct_t1_square and not is_blue_table_leader and not is_super_hot_ball:
                        soft_penalty += 10.0

                    raw_score = pts_node + pts_white_pos + pts_w15_stability + score_blue + score_ball + series_bonus - soft_penalty
                    final_score = round(min(99.0, max(5.0, raw_score)), 1)

                    if in_prev1 and (sq_d1 or exact_same_pos_in_t1 or is_transfer_from_strong_pos) and (ball_t1_in_win >= 2 or ball_t1_15 >= 2):
                        verdict_str = "👑 POTWIERDZONA SERIA (🔴+⬜)"
                    elif is_super_hot_ball:
                        verdict_str = f"🌋 SUPER-GORĄCA KULA ({ball_t1_in_win}x powt.)"
                    elif is_hot_repeater and (has_direct_t1_square or is_transfer_from_strong_pos or b_hit_rate >= 0.35):
                        verdict_str = f"🔥 Gorąca Kula ({ball_t1_in_win}x powt. T+1)"
                    elif is_blue_table_leader:
                        verdict_str = f"🟦👑 Lider Tab.🟦 M.{m_col:02d} ({b_hits_cnt}/{blue_steps_avail})"
                    elif sq_d1 and b_u1:
                        verdict_str = "💎 PODWÓJNY KWADRAT (⬜+🟦)"
                    elif sq_d1:
                        verdict_str = f"⬜ Żywy Kwadrat Poz.{pos_nr:02d} ({w15_hits}/14)"
                    elif b_u1:
                        verdict_str = f"🟦 Żywy Kwadrat M.{m_col:02d} ({b_hits_cnt}/{blue_steps_avail})"
                    elif is_top_w15_leader:
                        verdict_str = f"🏆 Lider Tabeli 15 ({w15_hits}/{n15_trans_now} ⬜)"
                    elif soft_penalty >= 10.0:
                        verdict_str = f"❄️ Chłodna Poz.{pos_nr:02d}"
                    else:
                        verdict_str = "⏳ Aktywna w t-2"

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
                    "is_blue_leader": eff_blue_leader_flag,
                    "is_super_hot": 1 if is_super_hot_ball else 0,
                    "ball_t1_win": ball_t1_in_win,
                    "ball_t1_total": ball_t1_in_win + ball_t1_15,
                    "Pozycja": f"Poz. {pos_nr:02d} (🟦 M.{m_col:02d})",
                    "Liczba": ball,
                    "Score": final_score,
                    "Status V29": verdict_str,
                    "⬜ Własne Poz. (i z 15)": f"{pos_white_hits}/{trans_count} ({pos_white_rate*100:.0f}%) | z 15: {w15_hits}/14",
                    "🟦 Kolumna M (i Stałe)": f"M.{m_col:02d}: {b_hits_cnt}/{blue_steps_avail} | Stałe: {orig_bwin_cnt}/{blue_steps_avail}",
                    "Pod pozycją (Węzeł)": path_str,
                    "Powtórki Kuli T+1": f"{ball_t1_in_win}x (z 15: {ball_t1_15}x na {ball_f_15})",
                    "⭐ 'Najczęstsza'": mode_str
                })

            if engine_mode == "no_blue":
                candidates.sort(key=lambda x: (-x["Score"], -x["ball_t1_total"], -x["w15_hits"], -x["pos_white_pct"]))
            elif engine_mode == "only_blue":
                candidates.sort(key=lambda x: (-x["Score"], -x["b_hit_pct"], -x["has_t1_sq"], x["blue_m"]))
            else:
                candidates.sort(key=lambda x: (-x["Score"], -x["ball_t1_total"], -x["b_hit_pct"], -x["w15_hits"]))

            for idx_c, c_item in enumerate(candidates):
                c_item["Rank"] = f"#{idx_c+1}"

            res_tuple = (candidates, win_ball_freq, win_ball_t1_repeats, all_modes_set_now, min_thr)
            score_cache[t_idx] = res_tuple

            if return_df:
                df_c = pd.DataFrame(candidates)
                cols_order = ["Rank"] + [col for col in df_c.columns if col != "Rank"]
                return df_c[cols_order], win_ball_freq, win_ball_t1_repeats, all_modes_set_now, min_thr
            return res_tuple

        return score_at_t

    # =================================================================
    # WSPÓLNA FUNKCJA WYBORU PARY W TOP 3 (Z BLOKADĄ PRZECIW PUŁAPCE 0x 2/2!)
    # =================================================================
    top3_pair_combos = [(0, 1), (0, 2), (1, 2)]
    all_pair_combos = list(combinations(range(5), 2))

    def select_top3_pair_with_guard(pair_any_long, pair_both_long, pair_any_short, pair_both_short, pair_rec5, slot_hits_long, long_len, short_len, min_both_req, strategy="top3_guard"):
        if strategy == "fixed_12":
            return (0, 1)

        def q_score(c):
            r_any_l = pair_any_long[c] / max(1, long_len)
            r_both_l = pair_both_long[c] / max(1, long_len)
            r_any_s = pair_any_short[c] / max(1, short_len)
            r_both_s = pair_both_short[c] / max(1, short_len)
            r_rec5 = pair_rec5[c] / 5.0
            r_slots = (slot_hits_long[c[0]] + slot_hits_long[c[1]]) / (2.0 * max(1, long_len))
            stab = (r_any_l * 45.0) + (r_both_l * 75.0) + (r_slots * 30.0)
            mom = (r_any_s * 35.0) + (r_both_s * 60.0) + (r_rec5 * 20.0)
            return (stab * 0.60) + (mom * 0.40)

        q_01 = q_score((0, 1))
        best_c = (0, 1)
        best_q = q_01

        for c in [(0, 2), (1, 2)]:
            # Alternatywa w TOP 3 musi mieć min. wymaganą liczbę pełnych dubletów 2/2 i wyraźnie bić #1+#2!
            if pair_both_long[c] >= min_both_req:
                qc = q_score(c)
                if qc > best_q * 1.04:
                    best_q = qc
                    best_c = c
        return best_c

    # =================================================================
    # 🔬 ROZSZERZONY TEST A/B (WALK-FORWARD NA CAŁEJ BAZIE):
    # 1) TRYBY SILNIKA + STRATEGIE PARY (#1+#2 vs TOP 3 vs STARY #1-#5)
    # 2) SKANER WSZYSTKICH 8 OKIEN (5–15) NA CAŁEJ BAZIE!
    # =================================================================
    with st.expander(f"🔬 ROZSZERZONY TEST A/B (Walk-Forward na bazie do {max(50, total_draws - 65)} gier: Strategie Pary + Wszystkie Okna!)", expanded=False):
        st.caption(
            "Test wykonuje 100% uczciwą symulację krok po kroku (bez podglądania przyszłości) i pokazuje **realną trafność pary na 1 kulę (%)**, "
            "porównując sztywne `#1+#2`, nowy Skaner w TOP 3 oraz dawny Skaner `#1–#5` na tych samych losowaniach."
        )
        ab_max_draws = max(50, total_draws - 65)
        ab_size_opts = [x for x in [100, 250, 500] if x < ab_max_draws] + [ab_max_draws]

        col_ab1, col_ab2, col_ab3 = st.columns([1.0, 0.9, 1.3])
        with col_ab1:
            ab_test_len = st.radio(
                "📊 Liczba losowań w teście:",
                options=ab_size_opts,
                index=len(ab_size_opts) - 1,
                format_func=lambda x: f"Cała baza ({x})" if x == ab_max_draws else f"{x} gier",
                horizontal=True,
                key="v29_ab_len_radio"
            )
        with col_ab2:
            ab_win_size = st.radio(
                "⚙️ Okno do Testu 1:",
                options=[6, 8, 10, 15],
                index=2,
                horizontal=True,
                key="v29_ab_win_radio"
            )
        with col_ab3:
            st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)
            c_b1, c_b2 = st.columns(2)
            with c_b1:
                run_ab_btn = st.button(
                    f"🚀 Test 1: Tryby & Strategie ({ab_test_len}g)",
                    type="primary",
                    use_container_width=True,
                    key="v29_run_ab_btn"
                )
            with c_b2:
                run_allwin_btn = st.button(
                    f"📊 Test 2: Wszystkie 8 Okien ({ab_test_len}g)",
                    use_container_width=True,
                    key="v29_run_allwin_btn"
                )

        # Funkcja pomocnicza: szybki walk-forward z sumami prefiksowymi (zero wycieku przyszłości!)
        def eval_mode_walkforward(w_sz, e_mode, n_eval):
            sc_ab = run_engine_v29(w_sz, w_sz, n_eval + 34, engine_mode=e_mode)
            t_start = latest_idx - n_eval
            t_pre_start = t_start - 30
            n_pre_tot = latest_idx - t_pre_start

            h_matrix = []
            for offset_p in range(n_pre_tot):
                t_c = t_pre_start + offset_p
                cands_c, _, _, _, _ = sc_ab(t_c, return_df=False)
                nxt_c = all_sets[t_c + 1]
                h_matrix.append([cands_c[k]["Liczba"] in nxt_c for k in range(5)])

            # Sumy prefiksowe dla slotów i wszystkich 10 par
            pref_slot = [[0] * (n_pre_tot + 1) for _ in range(5)]
            pref_p_any = {c: [0] * (n_pre_tot + 1) for c in all_pair_combos}
            pref_p_both = {c: [0] * (n_pre_tot + 1) for c in all_pair_combos}

            for i_p in range(n_pre_tot):
                hf = h_matrix[i_p]
                for s_k in range(5):
                    pref_slot[s_k][i_p + 1] = pref_slot[s_k][i_p] + (1 if hf[s_k] else 0)
                for c in all_pair_combos:
                    ch = (1 if hf[c[0]] else 0) + (1 if hf[c[1]] else 0)
                    pref_p_any[c][i_p + 1] = pref_p_any[c][i_p] + (1 if ch >= 1 else 0)
                    pref_p_both[c][i_p + 1] = pref_p_both[c][i_p] + (1 if ch == 2 else 0)

            res_by_strat = {
                "fixed_12": {"p_any": 0, "p_both": 0, "t5_hits": 0, "t5_2p": 0, "t5_3p": 0},
                "top3_guard": {"p_any": 0, "p_both": 0, "t5_hits": 0, "t5_2p": 0, "t5_3p": 0},
                "old_all5": {"p_any": 0, "p_both": 0, "t5_hits": 0, "t5_2p": 0, "t5_3p": 0},
            }

            for pos in range(30, n_pre_tot):
                hf_now = h_matrix[pos]
                hc_now = sum(1 for x in hf_now if x)

                # Statystyki z ostatnich 30, 10 i 5 kroków PRZED pos
                sl_30 = [pref_slot[s][pos] - pref_slot[s][pos - 30] for s in range(5)]
                pa_30 = {c: pref_p_any[c][pos] - pref_p_any[c][pos - 30] for c in all_pair_combos}
                pb_30 = {c: pref_p_both[c][pos] - pref_p_both[c][pos - 30] for c in all_pair_combos}
                pa_10 = {c: pref_p_any[c][pos] - pref_p_any[c][pos - 10] for c in all_pair_combos}
                pb_10 = {c: pref_p_both[c][pos] - pref_p_both[c][pos - 10] for c in all_pair_combos}
                pa_5 = {c: pref_p_any[c][pos] - pref_p_any[c][pos - 5] for c in all_pair_combos}

                # 1) Sztywne #1+#2
                c_fix = (0, 1)
                # 2) Nowy Skaner w TOP 3 z progiem min. 3x 2/2
                c_t3 = select_top3_pair_with_guard(pa_30, pb_30, pa_10, pb_10, pa_5, sl_30, 30, 10, 3, strategy="top3_guard")
                # 3) Dawny Skaner po wszystkich 10 parach (#1–#5)
                c_old = max(
                    all_pair_combos,
                    key=lambda c: (
                        ((pa_30[c] / 30.0) * 50.0 + (pb_30[c] / 30.0) * 65.0 + ((sl_30[c[0]] + sl_30[c[1]]) / 60.0) * 30.0) * 0.55
                        + ((pa_10[c] / 10.0) * 40.0 + (pb_10[c] / 10.0) * 50.0 + (pa_5[c] / 5.0) * 25.0) * 0.45
                    )
                )

                for st_key, chosen_c in [("fixed_12", c_fix), ("top3_guard", c_t3), ("old_all5", c_old)]:
                    ph = (1 if hf_now[chosen_c[0]] else 0) + (1 if hf_now[chosen_c[1]] else 0)
                    d_r = res_by_strat[st_key]
                    if ph >= 1:
                        d_r["p_any"] += 1
                    if ph == 2:
                        d_r["p_both"] += 1
                    d_r["t5_hits"] += hc_now
                    if hc_now >= 2:
                        d_r["t5_2p"] += 1
                    if hc_now >= 3:
                        d_r["t5_3p"] += 1

            return res_by_strat

        if run_ab_btn:
            prog_ab = st.progress(0, text=f"Wykonuję uczciwy test walk-forward na {ab_test_len} losowaniach (Okno {ab_win_size})...")
            res_nb = eval_mode_walkforward(ab_win_size, "no_blue", ab_test_len)
            prog_ab.progress(0.40)
            res_hy = eval_mode_walkforward(ab_win_size, "hybrid", ab_test_len)
            prog_ab.progress(0.75)
            res_ob = eval_mode_walkforward(ab_win_size, "only_blue", ab_test_len)
            prog_ab.progress(1.0)
            prog_ab.empty()

            ab_entries = [
                ("⬜ Bez Niebieskiej — Sztywna Para #1+#2", res_nb["fixed_12"]),
                ("⬜ Bez Niebieskiej — Nowy Skaner TOP 3 (próg 2/2)", res_nb["top3_guard"]),
                ("⬜ Bez Niebieskiej — Dawny Skaner #1–#5", res_nb["old_all5"]),
                ("🔄 Hybryda — Sztywna Para #1+#2", res_hy["fixed_12"]),
                ("🟦 Tylko Niebieska — Sztywna Para #1+#2", res_ob["fixed_12"]),
            ]

            ab_rows = []
            for label_e, d_e in ab_entries:
                pair_balls_hits = d_e["p_any"] + d_e["p_both"]
                pair_per_ball_pct = (pair_balls_hits / (ab_test_len * 2.0)) * 100.0
                p_any_pct = (d_e["p_any"] / ab_test_len) * 100.0
                p_both_pct = (d_e["p_both"] / ab_test_len) * 100.0
                t5_avg_pct = (d_e["t5_hits"] / (ab_test_len * 5.0)) * 100.0
                t5_2p_pct = (d_e["t5_2p"] / ab_test_len) * 100.0
                t5_3p_pct = (d_e["t5_3p"] / ab_test_len) * 100.0

                ab_rows.append({
                    "Tryb & Strategia Pary": label_e,
                    "raw_pair_ball": pair_per_ball_pct,
                    "raw_p_any": p_any_pct,
                    "raw_t5": t5_avg_pct,
                    "Trafność Pary na 1 kulę": f"{pair_per_ball_pct:.2f}% ({pair_balls_hits}/{ab_test_len*2})",
                    "Para: min. 1 traf.": f"{p_any_pct:.1f}% ({d_e['p_any']}/{ab_test_len})",
                    "Para: pełne 2/2": f"{p_both_pct:.2f}% ({d_e['p_both']}x)",
                    "Śr. TOP 5 (kula)": f"{t5_avg_pct:.2f}% ({d_e['t5_hits']}/{ab_test_len*5})",
                    "TOP 5: 2+ traf.": f"{t5_2p_pct:.1f}% ({d_e['t5_2p']})",
                    "TOP 5: 3+ traf.": f"{t5_3p_pct:.1f}% ({d_e['t5_3p']})"
                })

            best_ab = max(ab_rows, key=lambda r: (r["raw_pair_ball"], r["raw_p_any"], r["raw_t5"]))
            diff_pair_rand = best_ab["raw_pair_ball"] - 28.57

            ab_rows.append({
                "Tryb & Strategia Pary": "🎲 Losowy wybór (teoria Keno 20/70)",
                "raw_pair_ball": 28.57, "raw_p_any": 49.28, "raw_t5": 28.57,
                "Trafność Pary na 1 kulę": "28.57% (baza losowa)",
                "Para: min. 1 traf.": "49.28% (baza losowa)",
                "Para: pełne 2/2": "7.87% (baza losowa)",
                "Śr. TOP 5 (kula)": "28.57% (baza losowa)",
                "TOP 5: 2+ traf.": "44.44% (baza losowa)",
                "TOP 5: 3+ traf.": "13.67% (baza losowa)"
            })

            st.session_state["v29_ab_df"] = pd.DataFrame(ab_rows).drop(columns=["raw_pair_ball", "raw_p_any", "raw_t5"])
            st.session_state["v29_ab_verdict"] = (
                f"🏆 **ZWYCIĘZCA TESTU 1 ({ab_test_len} gier, Okno {ab_win_size}):** **{best_ab['Tryb & Strategia Pary']}** — "
                f"Trafność pary na 1 kulę: **{best_ab['Trafność Pary na 1 kulę']}** ({diff_pair_rand:+.2f} pkt proc. vs losowe `28.57%`) | "
                f"Min. 1 z pary: **{best_ab['Para: min. 1 traf.']}** | Pełne 2/2: **{best_ab['Para: pełne 2/2']}**."
            )

        if run_allwin_btn:
            prog_w = st.progress(0, text=f"Skanuję wszystkie 8 okien (5–15) w trybie Bez Niebieskiej na {ab_test_len} grach...")
            allw_rows = []
            for idx_w, w_test in enumerate(all_windows):
                r_w = eval_mode_walkforward(w_test, "no_blue", ab_test_len)
                d12 = r_w["fixed_12"]
                dt3 = r_w["top3_guard"]
                pb12 = ((d12["p_any"] + d12["p_both"]) / (ab_test_len * 2.0)) * 100.0
                pbt3 = ((dt3["p_any"] + dt3["p_both"]) / (ab_test_len * 2.0)) * 100.0
                allw_rows.append({
                    "Okno (⬜ Bez Nieb.)": f"Okno {w_test}",
                    "raw_pb12": pb12,
                    "Para #1+#2 (na 1 kulę)": f"{pb12:.2f}% ({d12['p_any']+d12['p_both']}/{ab_test_len*2})",
                    "#1+#2: min. 1 / pełne 2/2": f"{d12['p_any']/ab_test_len*100:.1f}% | 2/2: {d12['p_both']}x ({d12['p_both']/ab_test_len*100:.2f}%)",
                    "Skaner TOP 3 (na 1 kulę)": f"{pbt3:.2f}% | 2/2: {dt3['p_both']}x",
                    "Śr. TOP 5": f"{d12['t5_hits']/(ab_test_len*5.0)*100:.2f}%",
                    "TOP 5: 2+ traf.": f"{d12['t5_2p']/ab_test_len*100:.1f}% ({d12['t5_2p']})"
                })
                prog_w.progress((idx_w + 1) / len(all_windows))
            prog_w.empty()
            allw_rows.sort(key=lambda x: -x["raw_pb12"])
            best_w_row = allw_rows[0]
            st.session_state["v29_allwin_df"] = pd.DataFrame(allw_rows).drop(columns=["raw_pb12"])
            st.session_state["v29_allwin_msg"] = (
                f"🏆 **NAJLEPSZE OKNO NA {ab_test_len} GRACH (⬜ Bez Niebieskiej):** **{best_w_row['Okno (⬜ Bez Nieb.)']}** — "
                f"Para #1+#2 na 1 kulę: **{best_w_row['Para #1+#2 (na 1 kulę)']}** | **{best_w_row['#1+#2: min. 1 / pełne 2/2']}**."
            )

        if "v29_ab_verdict" in st.session_state:
            st.success(st.session_state["v29_ab_verdict"])
        if "v29_ab_df" in st.session_state:
            st.dataframe(st.session_state["v29_ab_df"], hide_index=True, use_container_width=True)
        if "v29_allwin_msg" in st.session_state:
            st.info(st.session_state["v29_allwin_msg"])
        if "v29_allwin_df" in st.session_state:
            st.dataframe(st.session_state["v29_allwin_df"], hide_index=True, use_container_width=True)

    # =================================================================
    # MODUŁ 0: EMPIRYCZNA ANALIZA FAZ POWTÓREK NA CAŁEJ BAZIE
    # =================================================================
    repeats_series = [len(all_sets[i].intersection(all_sets[i + 1])) for i in range(total_draws - 1)]
    global_avg_rep = sum(repeats_series) / max(1, len(repeats_series))
    global_6plus_pct = (sum(1 for x in repeats_series if x >= 6) / max(1, len(repeats_series))) * 100.0

    phase_buckets = {
        "🔥 Faza Gorąca (śr. 3 ost. gier ≥ 6.5)": [],
        "⚖️ Faza Normalna (śr. 3 ost. gier 5.0–6.4)": [],
        "❄️ Faza Chłodna (śr. 3 ost. gier < 5.0)": [],
        "📉 Po Głębokim Dołku (ostatnia gra ≤ 3 powt.)": []
    }
    for k_p in range(3, len(repeats_series)):
        prev3_avg = (repeats_series[k_p - 1] + repeats_series[k_p - 2] + repeats_series[k_p - 3]) / 3.0
        prev1_val = repeats_series[k_p - 1]
        nxt_val = repeats_series[k_p]
        if prev3_avg >= 6.5:
            phase_buckets["🔥 Faza Gorąca (śr. 3 ost. gier ≥ 6.5)"].append(nxt_val)
        elif prev3_avg >= 5.0:
            phase_buckets["⚖️ Faza Normalna (śr. 3 ost. gier 5.0–6.4)"].append(nxt_val)
        else:
            phase_buckets["❄️ Faza Chłodna (śr. 3 ost. gier < 5.0)"].append(nxt_val)
        if prev1_val <= 3:
            phase_buckets["📉 Po Głębokim Dołku (ostatnia gra ≤ 3 powt.)"].append(nxt_val)

    last1_rep = repeats_series[-1]
    prev1_rep = repeats_series[-2] if len(repeats_series) >= 2 else last1_rep
    last3_rep_avg = sum(repeats_series[-3:]) / 3.0
    last5_rep_avg = sum(repeats_series[-5:]) / 5.0
    last20_reps = repeats_series[-20:]
    last20_ids = all_ids[-20:]

    post_spike_cooldown = (prev1_rep >= 9 and last1_rep <= 5) or (prev1_rep >= 8 and (prev1_rep - last1_rep) >= 4)

    if post_spike_cooldown:
        curr_phase_name = f"📉 SCHŁODZENIE PO SZCZYCIE ({prev1_rep} ➔ {last1_rep} powt. — ostrożnie!)"
        curr_phase_color = "#ffd166"
        phase_rep_score = 16
    elif last3_rep_avg >= 6.3 and last1_rep >= 6:
        curr_phase_name = "🔥 FAZA GORĄCA (Aktywna fala powtórek!)"
        curr_phase_color = "#00e676"
        phase_rep_score = 26
    elif last1_rep <= 3:
        curr_phase_name = "📈 DOŁEK POWTÓREK (Możliwe odbicie do średniej ~5.7)"
        curr_phase_color = "#ffd166"
        phase_rep_score = 17
    elif last3_rep_avg >= 5.2:
        curr_phase_name = "⚖️ FAZA NORMALNA (Stabilne powtórki)"
        curr_phase_color = "#4da6ff"
        phase_rep_score = 20
    else:
        curr_phase_name = "❄️ FAZA CHŁODNA (Mało powtórek w ostatnich grach)"
        curr_phase_color = "#ff6b6b"
        phase_rep_score = 10

    # =====================================================================
    # PREKALKULACJA 8 OKIEN (5–15) W WYBRANYM TRYBIE SILNIKA
    # =====================================================================
    total_precomp_steps = matrix_bt_steps + meta_bt_max + 2
    win_scorers = {}
    win_top5_cache = {w: {} for w in all_windows}
    win_hits_cache = {w: {} for w in all_windows}

    for w_val in all_windows:
        sc_fn = run_engine_v29(w_val, w_val, total_precomp_steps, engine_mode=active_engine_mode)
        win_scorers[w_val] = sc_fn
        start_pre = latest_idx - (matrix_bt_steps + meta_bt_max)
        for t_s in range(start_pre, latest_idx + 1):
            cands_t, _, _, _, _ = sc_fn(t_s, return_df=False)
            t5_t = cands_t[:5]
            win_top5_cache[w_val][t_s] = t5_t
            if t_s < latest_idx:
                nxt_s = all_sets[t_s + 1]
                win_hits_cache[w_val][t_s] = [t5_t[k]["Liczba"] in nxt_s for k in range(5)]

    # =====================================================================
    # ELITARNY META-SELEKTOR (TOP 3 OKNA × 4 HORYZONTY = 12 MODELI, WYBÓR PARY TYLKO W TOP 3!)
    # =====================================================================
    def compute_elite_meta_at_t(t_eval):
        ball_meta_points = defaultdict(float)
        ball_model_votes = defaultdict(int)
        ball_windows_set = defaultdict(set)
        ball_horizons_set = defaultdict(set)
        ball_best_pos = {}
        horizon_best_model = {}

        for h_len in all_bt_horizons:
            horizon_candidates = []
            short_h = min(10, h_len)
            min_b_req = 1 if h_len <= 10 else (2 if h_len <= 20 else 3)

            for w_val in all_windows:
                slot_h = [0, 0, 0, 0, 0]
                pair_any_l = {c: 0 for c in top3_pair_combos}
                pair_both_l = {c: 0 for c in top3_pair_combos}
                pair_any_s = {c: 0 for c in top3_pair_combos}
                pair_both_s = {c: 0 for c in top3_pair_combos}
                pair_rec5 = {c: 0 for c in top3_pair_combos}

                for off in range(1, h_len + 1):
                    h_fl = win_hits_cache[w_val][t_eval - off]
                    for s_i in range(5):
                        if h_fl[s_i]:
                            slot_h[s_i] += 1
                    for c in top3_pair_combos:
                        ch = (1 if h_fl[c[0]] else 0) + (1 if h_fl[c[1]] else 0)
                        if ch >= 1:
                            pair_any_l[c] += 1
                            if off <= short_h:
                                pair_any_s[c] += 1
                            if off <= 5:
                                pair_rec5[c] += 1
                        if ch == 2:
                            pair_both_l[c] += 1
                            if off <= short_h:
                                pair_both_s[c] += 1

                best_c = select_top3_pair_with_guard(
                    pair_any_l, pair_both_l, pair_any_s, pair_both_s, pair_rec5,
                    slot_h, h_len, short_h, min_b_req, strategy=active_pair_strategy
                )
                as1, as2 = best_c
                as3 = [s for s in range(3) if s not in best_c][0]

                t5_now = win_top5_cache[w_val][t_eval]
                p_any_rate = pair_any_l[best_c] / h_len
                p_both_rate = pair_both_l[best_c] / h_len
                model_quality = (p_any_rate * 48.0) + (p_both_rate * 75.0) + (pair_rec5[best_c] / 5.0) * 18.0 + ((slot_h[as1] + slot_h[as2]) / (2.0 * h_len)) * 18.0

                horizon_candidates.append({
                    "quality": model_quality, "h_len": h_len, "w_val": w_val,
                    "any_cnt": pair_any_l[best_c], "both_cnt": pair_both_l[best_c],
                    "s1": as1, "s2": as2, "s3": as3,
                    "s1_r": slot_h[as1] / h_len, "s2_r": slot_h[as2] / h_len, "s3_r": slot_h[as3] / h_len,
                    "r1": t5_now[as1], "r2": t5_now[as2], "r3": t5_now[as3],
                    "b1": int(t5_now[as1]["Liczba"]), "b2": int(t5_now[as2]["Liczba"]), "b3": int(t5_now[as3]["Liczba"])
                })

            horizon_candidates.sort(key=lambda x: -x["quality"])
            horizon_best_model[h_len] = horizon_candidates[0]

            podium_weights = [3.0, 2.0, 1.0]
            for rank_h, hc in enumerate(horizon_candidates[:3]):
                p_w = podium_weights[rank_h]
                q_mult = max(0.6, hc["quality"] / 45.0)
                for b_v, slot_r, r_obj, base_mult in [
                    (hc["b1"], hc["s1_r"], hc["r1"], 1.15),
                    (hc["b2"], hc["s2_r"], hc["r2"], 1.00),
                    (hc["b3"], hc["s3_r"], hc["r3"], 0.45),
                ]:
                    own_rep_boost = 1.0 if active_engine_mode == "only_blue" else (1.25 if int(r_obj["ball_t1_win"]) >= 2 else (1.0 if int(r_obj["ball_t1_win"]) == 1 else 0.78))
                    pts_add = p_w * q_mult * base_mult * own_rep_boost * (0.9 + slot_r * 0.9 + float(r_obj["Score"]) / 160.0)
                    ball_meta_points[b_v] += pts_add
                    if base_mult >= 1.0:
                        ball_model_votes[b_v] += 1
                        ball_windows_set[b_v].add(hc["w_val"])
                        ball_horizons_set[b_v].add(h_len)
                    if b_v not in ball_best_pos or float(r_obj["Score"]) > ball_best_pos[b_v][2]:
                        ball_best_pos[b_v] = (int(r_obj["pos_nr"]), int(r_obj["blue_m"]), float(r_obj["Score"]), int(r_obj["ball_t1_win"]))

        meta_ranked = []
        for b_v, m_pts in ball_meta_points.items():
            p_nr, m_col, sc_val, bt1_w = ball_best_pos[b_v]
            meta_ranked.append({
                "Liczba": b_v, "meta_pts": round(m_pts, 1),
                "models_cnt": ball_model_votes[b_v], "win_cnt": len(ball_windows_set[b_v]),
                "hor_cnt": len(ball_horizons_set[b_v]), "pos_nr": p_nr,
                "blue_m": m_col, "score_ref": sc_val, "bt1_w": bt1_w
            })

        meta_ranked.sort(key=lambda x: (-x["meta_pts"], -x["models_cnt"], -x["bt1_w"], -x["score_ref"]))
        if len(meta_ranked) < 5:
            seen_m = {x["Liczba"] for x in meta_ranked}
            fallback_w = horizon_best_model[30]["w_val"]
            for fb_r in win_top5_cache[fallback_w][t_eval]:
                fb_b = int(fb_r["Liczba"])
                if fb_b not in seen_m:
                    meta_ranked.append({
                        "Liczba": fb_b, "meta_pts": 1.0, "models_cnt": 0, "win_cnt": 1, "hor_cnt": 1,
                        "pos_nr": int(fb_r["pos_nr"]), "blue_m": int(fb_r["blue_m"]),
                        "score_ref": float(fb_r["Score"]), "bt1_w": int(fb_r["ball_t1_win"])
                    })
                    seen_m.add(fb_b)
                if len(meta_ranked) >= 5:
                    break

        return meta_ranked, horizon_best_model

    live_meta_ranked, live_horizon_best = compute_elite_meta_at_t(latest_idx)

    meta_hist_rows = []
    meta_slot_hits_20 = [0, 0, 0, 0, 0]
    meta_slot_hits_10 = [0, 0, 0, 0, 0]
    meta_pa_20 = {c: 0 for c in top3_pair_combos}
    meta_pb_20 = {c: 0 for c in top3_pair_combos}
    meta_pa_10 = {c: 0 for c in top3_pair_combos}
    meta_pb_10 = {c: 0 for c in top3_pair_combos}
    meta_pa_5 = {c: 0 for c in top3_pair_combos}
    meta_top5_2plus_20 = 0

    for step_i in range(meta_bt_max):
        t_step = latest_idx - 1 - step_i
        m_rank_step, _ = compute_elite_meta_at_t(t_step)
        nxt_s = all_sets[t_step + 1]
        m_top5 = m_rank_step[:5]
        h_fl = [m_top5[k]["Liczba"] in nxt_s for k in range(5)]
        t5_h = sum(1 for f in h_fl if f)

        if t5_h >= 2:
            meta_top5_2plus_20 += 1

        for k in range(5):
            if h_fl[k]:
                meta_slot_hits_20[k] += 1
                if step_i < 10:
                    meta_slot_hits_10[k] += 1

        for c in top3_pair_combos:
            ch = (1 if h_fl[c[0]] else 0) + (1 if h_fl[c[1]] else 0)
            if ch >= 1:
                meta_pa_20[c] += 1
                if step_i < 10:
                    meta_pa_10[c] += 1
                if step_i < 5:
                    meta_pa_5[c] += 1
            if ch == 2:
                meta_pb_20[c] += 1
                if step_i < 10:
                    meta_pb_10[c] += 1

        meta_hist_rows.append({"t_step": t_step, "m_top5": m_top5, "h_fl": h_fl, "t5_h": t5_h})

    # NAPRAWA V29: Meta-Selektor wybiera parę WYŁĄCZNIE z TOP 3 (Meta #1, #2, #3) z progiem min. 2x 2/2!
    best_meta_pair_c = select_top3_pair_with_guard(
        meta_pa_20, meta_pb_20, meta_pa_10, meta_pb_10, meta_pa_5,
        meta_slot_hits_20, meta_bt_max, 10, 2, strategy=active_pair_strategy
    )
    ms1, ms2 = best_meta_pair_c
    ms3 = [s for s in range(3) if s not in best_meta_pair_c][0]

    meta_pair_any_20 = meta_pa_20[best_meta_pair_c]
    meta_pair_both_20 = meta_pb_20[best_meta_pair_c]
    meta_pair_any_10 = meta_pa_10[best_meta_pair_c]
    meta_pair_rec5 = meta_pa_5[best_meta_pair_c]
    last_meta_pair_hit = meta_hist_rows[0]["h_fl"][ms1] or meta_hist_rows[0]["h_fl"][ms2]

    # =====================================================================
    # STANDARDOWY SKANER 8 OKIEN (5–15) — WYBÓR PARY WYŁĄCZNIE W TOP 3!
    # =====================================================================
    win_live_top5 = {}
    win_summary_data = {}
    consensus_ball_windows = defaultdict(list)
    consensus_ball_scores = defaultdict(float)

    for w_val in all_windows:
        live_t5 = win_top5_cache[w_val][latest_idx]
        win_live_top5[w_val] = live_t5

        for idx_5, r_row in enumerate(live_t5[:3]):
            b_num = int(r_row["Liczba"])
            consensus_ball_windows[b_num].append(w_val)
            consensus_ball_scores[b_num] += float(r_row["Score"]) * (1.25 if idx_5 < 2 else 0.95)

        slot_hits_10 = {s: 0 for s in range(5)}
        slot_hits_30 = {s: 0 for s in range(5)}
        top5_2plus_10 = 0
        top5_2plus_30 = 0

        pa_30 = {c: 0 for c in top3_pair_combos}
        pb_30 = {c: 0 for c in top3_pair_combos}
        pa_10 = {c: 0 for c in top3_pair_combos}
        pb_10 = {c: 0 for c in top3_pair_combos}
        pa_5 = {c: 0 for c in top3_pair_combos}
        last1_map = {c: False for c in top3_pair_combos}

        for step_i in range(matrix_bt_steps):
            step_t = latest_idx - 1 - step_i
            h_flags = win_hits_cache[w_val][step_t]
            h_cnt = sum(1 for f in h_flags if f)
            if h_cnt >= 2:
                top5_2plus_30 += 1
                if step_i < recent_rank_steps:
                    top5_2plus_10 += 1
            for s_i in range(5):
                if h_flags[s_i]:
                    slot_hits_30[s_i] += 1
                    if step_i < recent_rank_steps:
                        slot_hits_10[s_i] += 1
            for c in top3_pair_combos:
                ch = (1 if h_flags[c[0]] else 0) + (1 if h_flags[c[1]] else 0)
                if step_i == 0 and ch >= 1:
                    last1_map[c] = True
                if ch >= 1:
                    pa_30[c] += 1
                    if step_i < recent_rank_steps:
                        pa_10[c] += 1
                    if step_i < 5:
                        pa_5[c] += 1
                if ch == 2:
                    pb_30[c] += 1
                    if step_i < recent_rank_steps:
                        pb_10[c] += 1

        best_pair_c = select_top3_pair_with_guard(
            pa_30, pb_30, pa_10, pb_10, pa_5,
            slot_hits_30, matrix_bt_steps, recent_rank_steps, 3, strategy=active_pair_strategy
        )
        act_s1, act_s2 = best_pair_c
        best_s3 = [s for s in range(3) if s not in best_pair_c][0]

        pair_per_ball_30 = (pa_30[best_pair_c] + pb_30[best_pair_c]) / (2.0 * matrix_bt_steps)
        pair_per_ball_10 = (pa_10[best_pair_c] + pb_10[best_pair_c]) / (2.0 * recent_rank_steps)
        win_power_score = (
            (pair_per_ball_30 * 95.0)
            + ((pb_30[best_pair_c] / matrix_bt_steps) * 50.0)
            + (pair_per_ball_10 * 55.0)
            + ((pa_5[best_pair_c] / 5.0) * 15.0)
            + ((top5_2plus_30 / matrix_bt_steps) * 18.0)
        )

        win_summary_data[w_val] = {
            "w_val": w_val, "power": win_power_score,
            "best_s1": act_s1, "best_s2": act_s2, "best_s3": best_s3,
            "last1_hit": last1_map[best_pair_c],
            "s1_hits10": slot_hits_10[act_s1], "s2_hits10": slot_hits_10[act_s2], "s3_hits10": slot_hits_10[best_s3],
            "s1_hits30": slot_hits_30[act_s1], "s2_hits30": slot_hits_30[act_s2], "s3_hits30": slot_hits_30[best_s3],
            "pair_any_10": pa_10[best_pair_c], "pair_both_10": pb_10[best_pair_c],
            "pair_rec5": pa_5[best_pair_c],
            "pair_any_30": pa_30[best_pair_c], "pair_both_30": pb_30[best_pair_c],
            "pair_ball_pct30": pair_per_ball_30 * 100.0,
            "top5_2plus_10": top5_2plus_10, "top5_2plus_30": top5_2plus_30,
            "b1": int(live_t5[act_s1]["Liczba"]), "b2": int(live_t5[act_s2]["Liczba"]), "b3": int(live_t5[best_s3]["Liczba"]),
            "b1_score": float(live_t5[act_s1]["Score"]), "b2_score": float(live_t5[act_s2]["Score"]), "b3_score": float(live_t5[best_s3]["Score"]),
            "b1_t1": int(live_t5[act_s1]["ball_t1_win"]), "b2_t1": int(live_t5[act_s2]["ball_t1_win"]),
            "slot_hits_10": slot_hits_10, "slot_hits_30": slot_hits_30
        }

    for w_val in all_windows:
        wi = win_summary_data[w_val]
        wi["c_b1"] = len(consensus_ball_windows[wi["b1"]])
        wi["c_b2"] = len(consensus_ball_windows[wi["b2"]])
        wi["c_b3"] = len(consensus_ball_windows[wi["b3"]])
        wi["power"] += (wi["c_b1"] + wi["c_b2"]) * 1.1

    ranked_windows = sorted(all_windows, key=lambda w: win_summary_data[w]["power"], reverse=True)
    first_place_win = ranked_windows[0]
    second_place_win = ranked_windows[1]
    w1_info = win_summary_data[first_place_win]
    w2_info = win_summary_data[second_place_win]

    # =====================================================================
    # SYGNALIZATOR FAZY I GOTOWOŚCI (0 – 100 PKT)
    # =====================================================================
    best_rec5 = max(w1_info["pair_rec5"], meta_pair_rec5)
    algo_rhythm_score = min(28, int(round((best_rec5 / 5.0) * 28)))
    best_stab_rate = max(w1_info["pair_any_30"] / matrix_bt_steps, meta_pair_any_20 / meta_bt_max)
    stab_score = min(24, int(round(max(0.0, (best_stab_rate - 0.35) / 0.40) * 24)))

    meta_pair_set = {live_meta_ranked[ms1]["Liczba"], live_meta_ranked[ms2]["Liczba"]}
    win1_pair_set = {w1_info["b1"], w1_info["b2"]}
    overlap_cnt = len(meta_pair_set.intersection(win1_pair_set))
    quality_score = (
        (8 if overlap_cnt >= 1 else 0)
        + (6 if overlap_cnt == 2 else 0)
        + (4 if (w1_info["b1_t1"] >= 2 or w1_info["b2_t1"] >= 2) else (2 if (w1_info["b1_t1"] + w1_info["b2_t1"]) >= 1 else 0))
        + (4 if (w1_info["b1_score"] + w1_info["b2_score"]) / 2.0 >= 68.0 else 1)
    )
    caution_adj = -8 if (not w1_info["last1_hit"] and not last_meta_pair_hit) else 0
    total_readiness = max(5, min(100, phase_rep_score + algo_rhythm_score + stab_score + quality_score + caution_adj))

    if total_readiness >= 74:
        light_emoji = "🟢 ZIELONE ŚWIATŁO — FAZA AKTYWNA (DOBRY MOMENT DO GRY!)"
        light_border = "#00e676"
        light_bg = "linear-gradient(135deg, rgba(10, 58, 36, 0.96) 0%, rgba(7, 36, 22, 0.99) 100%)"
        light_hint = "Powtórki i trafność algorytmu są w dobrej fazie, a Elitarny Meta-Selektor i Zwycięskie Okno są spójne."
    elif total_readiness >= 54:
        light_emoji = "🟡 ŻÓŁTE ŚWIATŁO — FAZA PRZEJŚCIOWA (GRAJ OSTROŻNIE / TYLKO 2 LICZBY)"
        light_border = "#ffd166"
        light_bg = "linear-gradient(135deg, rgba(64, 48, 10, 0.96) 0%, rgba(36, 27, 6, 0.99) 100%)"
        light_hint = "Schłodzenie po szczycie lub mieszany rytm — jeśli grasz, trzymaj się ściśle 2 najsilniejszych liczb."
    else:
        light_emoji = "🔴 CZERWONE ŚWIATŁO — FAZA CHŁODNA (LEPIEJ PRZECZEKAĆ 1–2 LOSOWANIA)"
        light_border = "#ff4d6d"
        light_bg = "linear-gradient(135deg, rgba(68, 14, 24, 0.96) 0%, rgba(38, 8, 14, 0.99) 100%)"
        light_hint = "Mała liczba powtórek w ostatnich grach lub słabsza seria algorytmu — warto poczekać na powrót fali."

    pulse_bars_html = []
    for r_val, d_id_p in zip(last20_reps, last20_ids):
        if r_val >= 7:
            p_bg, p_col, p_brd = "rgba(0, 230, 118, 0.35)", "#00e676", "#00e676"
        elif r_val >= 5:
            p_bg, p_col, p_brd = "rgba(255, 209, 102, 0.20)", "#ffd166", "#8a7535"
        else:
            p_bg, p_col, p_brd = "rgba(255, 77, 109, 0.25)", "#ff6b6b", "#ff4d6d"
        pulse_bars_html.append(
            f"<div style='display:inline-flex; flex-direction:column; align-items:center; min-width:26px; padding:2px 3px; "
            f"border:1px solid {p_brd}; border-radius:5px; background:{p_bg};'>"
            f"<span style='font-size:12px; font-weight:900; color:{p_col}; line-height:13px;'>{r_val}</span>"
            f"<span style='font-size:7px; color:#9da3af; line-height:8px;'>{str(d_id_p)[-3:]}</span>"
            f"</div>"
        )

    phase_banner_html = (
        f"<div style='background: {light_bg}; border: 2.5px solid {light_border}; border-radius: 14px; "
        f"padding: 14px 18px; margin-bottom: 16px; font-family: sans-serif; box-shadow: 0 4px 18px rgba(0,0,0,0.35);'>"
        f"<div style='display:flex; flex-wrap:wrap; justify-content:space-between; align-items:center; gap:10px; margin-bottom:10px;'>"
        f"<div style='font-size:16px; font-weight:900; color:{light_border};'>{light_emoji}</div>"
        f"<div style='font-size:14px; font-weight:900; color:#ffffff; background:rgba(0,0,0,0.5); padding:4px 12px; border-radius:8px; border:1.5px solid {light_border};'>"
        f"Indeks Fazy & Pewności: <span style='color:{light_border}; font-size:17px;'>{total_readiness} / 100 pkt</span>"
        f"</div>"
        f"</div>"
        f"<div style='font-size:12px; color:#e6e6e6; margin-bottom:10px;'>"
        f"🌊 <b>Aktualna faza powtórek:</b> <span style='color:{curr_phase_color}; font-weight:bold;'>{curr_phase_name}</span> &nbsp;|&nbsp; "
        f"Ost. gra: <b>{last1_rep} powt.</b> &nbsp;|&nbsp; Śr. 3 gier: <b>{last3_rep_avg:.1f}</b> &nbsp;|&nbsp; Śr. 5 gier: <b>{last5_rep_avg:.1f}</b> "
        f"(Norma Keno: <b>{global_avg_rep:.2f}</b>) &nbsp;|&nbsp; Rytm algorytmu (ost. 5g): <b>{best_rec5}/5</b>"
        f"<br><span style='color:#b0b8c8;'>💡 {light_hint}</span>"
        f"</div>"
        f"<div style='font-size:11px; color:#9da3af; margin-bottom:4px; font-weight:bold;'>"
        f"📈 Puls liczby powtórek T ➔ T+1 w ostatnich 20 losowaniach (od lewej starsze, z prawej najnowsze #{last_draw_id} | 🟩 ≥7, 🟨 5–6, 🟥 ≤4):"
        f"</div>"
        f"<div style='display:flex; flex-wrap:wrap; gap:4px;'>{''.join(pulse_bars_html)}</div>"
        f"</div>"
    )
    st.markdown(phase_banner_html, unsafe_allow_html=True)

    with st.expander(f"🧪 Empiryczna Weryfikacja Teorii Faz na całej bazie ({len(repeats_series)} losowań Keno — sprawdź twarde dane!)", expanded=False):
        st.caption(
            f"Średnia w całej Twojej bazie ({len(repeats_series)} losowań): **{global_avg_rep:.2f} powtórek na losowanie** "
            f"(teoria Keno = 5.71), w **{global_6plus_pct:.1f}%** gier wpada ≥6 powtórek."
        )
        phase_test_rows = []
        for p_label, p_vals in phase_buckets.items():
            cnt_p = len(p_vals)
            avg_p = (sum(p_vals) / cnt_p) if cnt_p > 0 else 0.0
            pct6_p = (sum(1 for x in p_vals if x >= 6) / cnt_p * 100.0) if cnt_p > 0 else 0.0
            pct7_p = (sum(1 for x in p_vals if x >= 7) / cnt_p * 100.0) if cnt_p > 0 else 0.0
            diff_p = avg_p - global_avg_rep
            phase_test_rows.append({
                "Faza przed losowaniem T+1": p_label,
                "Liczba wystąpień w bazie": f"{cnt_p} gier",
                "Śr. powtórek w kolejnej grze (T+1)": f"{avg_p:.2f} ({diff_p:+.2f})",
                "Szansa na ≥6 powt. w T+1": f"{pct6_p:.1f}%",
                "Szansa na ≥7 powt. w T+1": f"{pct7_p:.1f}%"
            })
        st.dataframe(pd.DataFrame(phase_test_rows), hide_index=True, use_container_width=True)

    # =====================================================================
    # RENDER MODUŁU 1: 🌐 ELITARNY META-SELEKTOR (WYBÓR PARY TYLKO W TOP 3!)
    # =====================================================================
    m1, m2, m3 = live_meta_ranked[ms1], live_meta_ranked[ms2], live_meta_ranked[ms3]
    meta_p20_pct = (meta_pair_any_20 / meta_bt_max) * 100.0
    meta_3rd_strong = (meta_slot_hits_20[ms3] >= 8) and (meta_slot_hits_10[ms3] >= 4 or (m3["models_cnt"] >= 4 and m3["bt1_w"] >= 2))

    meta_3rd_box = (
        f"<div style='display: inline-flex; align-items: center; gap: 10px; background: rgba(0, 230, 118, 0.20); "
        f"border: 2.5px solid #00e676; border-radius: 10px; padding: 9px 15px;'>"
        f"<div>"
        f"<div style='font-size: 13px; color: #00e676; font-weight: 900;'>➕ 3. META-LICZBA (Meta #{ms3+1}: {meta_slot_hits_20[ms3]}/{meta_bt_max} — SILNA!):</div>"
        f"<div style='font-size: 11px; color: #b9f6ca;'>Wybrana w <b>{m3['models_cnt']}/{elite_models_total}</b> elit. modelach | Poz.{m3['pos_nr']:02d}</div>"
        f"</div>"
        f"<span style='font-size: 28px; font-weight: 900; color: #fff; background: #0077b6; padding: 3px 13px; border-radius: 8px; border: 2px solid #00e676;'>{m3['Liczba']:02d}</span>"
        f"</div>"
        if meta_3rd_strong else
        f"<div style='display: inline-flex; align-items: center; gap: 10px; background: rgba(255, 255, 255, 0.06); "
        f"border: 1.5px dashed #8a94a6; border-radius: 10px; padding: 9px 15px;'>"
        f"<div>"
        f"<div style='font-size: 12px; color: #ffd166; font-weight: 800;'>⚠️ 3. META-LICZBA (Meta #{ms3+1}: {meta_slot_hits_20[ms3]}/{meta_bt_max} — REZERWA):</div>"
        f"<div style='font-size: 11px; color: #9da3af;'>Poparcie: {m3['models_cnt']}/{elite_models_total} elit. modeli | Poz.{m3['pos_nr']:02d}</div>"
        f"</div>"
        f"<span style='font-size: 24px; font-weight: 800; color: #d0d7de; background: #2b3548; padding: 2px 11px; border-radius: 7px; border: 1px solid #8a94a6;'>{m3['Liczba']:02d}</span>"
        f"</div>"
    )

    hor_pills = []
    for h_len in all_bt_horizons:
        hr = live_horizon_best[h_len]
        hor_pills.append(
            f"<div style='background:rgba(0,0,0,0.45); border:1px solid #3c4a5e; border-radius:8px; padding:6px 10px; font-size:11px;'>"
            f"<span style='color:#4da6ff; font-weight:900;'>Badanie {h_len} gier</span> "
            f"<span style='color:#9da3af;'>(🥇 Okno {hr['w_val']}: {hr['any_cnt']}/{h_len}, 2z2: {hr['both_cnt']}x) ➔</span> "
            f"<b style='color:#ffd166; font-size:13px;'>{hr['b1']:02d}, {hr['b2']:02d}</b> "
            f"<span style='color:#00e676;'>+{hr['b3']:02d}</span>"
            f"</div>"
        )

    mode_short_tag = "⬜ BEZ NIEBIESKIEJ" if active_engine_mode == "no_blue" else ("🔄 HYBRYDA" if active_engine_mode == "hybrid" else "🟦 TYLKO NIEBIESKA")
    strat_short_tag = "SZTYWNE #1+#2" if active_pair_strategy == "fixed_12" else "TOP 3 (PRÓG 2/2)"
    meta_hero_html = (
        f"<div style='background: linear-gradient(135deg, rgba(16, 36, 64, 0.98) 0%, rgba(11, 22, 42, 0.99) 100%); "
        f"border: 3px solid #00b4d8; border-radius: 14px; padding: 16px 20px; margin-bottom: 18px; "
        f"box-shadow: 0 6px 22px rgba(0, 180, 216, 0.25); font-family: sans-serif;'>"
        f"<div style='display:flex; flex-wrap:wrap; justify-content:space-between; align-items:center; background:rgba(0,0,0,0.55); "
        f"border:2px solid #00b4d8; border-radius:9px; padding:10px 16px; margin-bottom:14px;'>"
        f"<div style='font-size:16px; font-weight:900; color:#90e0ef;'>"
        f"🌐 ELITARNY META-SELEKTOR [{mode_short_tag} | {strat_short_tag}] NA <span style='color:#ffffff; background:#e63946; padding:3px 10px; border-radius:6px; font-size:18px;'>#{target_draw_id} (godz. {target_time_str})</span>"
        f"</div>"
        f"<div style='font-size:12px; color:#ffd166; font-weight:bold;'>"
        f"📊 Skuteczność Meta-Pary (#{ms1+1}+#{ms2+1} w 20g): <b>{meta_pair_any_20}/{meta_bt_max} ({meta_p20_pct:.0f}%)</b>, pełne 2z2: <b>{meta_pair_both_20}x</b> | "
        f"Ost. 10g: <b>{meta_pair_any_10}/10 ({meta_pair_any_10*10}%)</b> | Meta-TOP5 (2+): <b>{meta_top5_2plus_20}/{meta_bt_max}</b>"
        f"</div>"
        f"</div>"
        f"<div style='display: flex; flex-wrap: wrap; gap: 14px; align-items: center; margin-bottom: 14px;'>"
        f"<div style='display: inline-flex; align-items: center; gap: 12px; background: rgba(0, 0, 0, 0.65); "
        f"border: 3px solid #ffd166; border-radius: 12px; padding: 10px 18px; box-shadow: 0 0 16px rgba(255, 209, 102, 0.4);'>"
        f"<div>"
        f"<div style='font-size: 14px; color: #ffd166; font-weight: 900;'>🌐 META-PARA (Z TOP 3: Meta #{ms1+1} + Meta #{ms2+1}):</div>"
        f"<div style='font-size: 11px; color: #e6e6e6;'>"
        f"1. <b>Meta #{ms1+1} ({meta_slot_hits_20[ms1]}/{meta_bt_max})</b>: Poz.{m1['pos_nr']:02d} ({m1['models_cnt']}/{elite_models_total}m) &nbsp;|&nbsp; "
        f"2. <b>Meta #{ms2+1} ({meta_slot_hits_20[ms2]}/{meta_bt_max})</b>: Poz.{m2['pos_nr']:02d} ({m2['models_cnt']}/{elite_models_total}m)"
        f"</div>"
        f"</div>"
        f"<span style='font-size: 32px; font-weight: 900; color: #fff; background: #e63946; padding: 3px 15px; border-radius: 9px; border: 2.5px solid #ffd166;'>{m1['Liczba']:02d}</span>"
        f"<span style='font-size: 32px; font-weight: 900; color: #fff; background: #e63946; padding: 3px 15px; border-radius: 9px; border: 2.5px solid #ffd166;'>{m2['Liczba']:02d}</span>"
        f"</div>"
        f"{meta_3rd_box}"
        f"</div>"
        f"<div style='font-size: 12px; color: #90e0ef; font-weight: bold; margin-bottom: 6px;'>"
        f"🔍 Liderzy z poszczególnych długości badania (10, 15, 20, 30 gier — tylko TOP 3 okna głosują!):"
        f"</div>"
        f"<div style='display:flex; flex-wrap:wrap; gap:8px;'>{''.join(hor_pills)}</div>"
        f"</div>"
    )
    st.markdown(meta_hero_html, unsafe_allow_html=True)

    with st.expander(f"📋 Weryfikacja Historii Elitarnego Meta-Selektora (Ostatnie {meta_bt_max} gier — Meta #{ms1+1}+#{ms2+1} = {meta_pair_any_20}/{meta_bt_max} [{meta_p20_pct:.0f}%], pełne 2z2: {meta_pair_both_20}x)", expanded=True):
        meta_tbl_rows = []
        live_m_cells = []
        for idx_m, m_it in enumerate(live_meta_ranked[:5]):
            if idx_m in (ms1, ms2):
                m_box = (
                    f"<div style='display:inline-flex; flex-direction:column; align-items:center; justify-content:center; "
                    f"width:58px; height:38px; border:2.5px solid #ffd166; border-radius:7px; background:#e63946; color:#fff; font-weight:900;'>"
                    f"<span style='font-size:15px; line-height:15px;'>🎯{m_it['Liczba']:02d}</span>"
                    f"<span style='font-size:8px; color:#ffd166; line-height:9px;'>{m_it['models_cnt']}/{elite_models_total}m</span></div>"
                )
            elif idx_m == ms3:
                m_box = (
                    f"<div style='display:inline-flex; flex-direction:column; align-items:center; justify-content:center; "
                    f"width:58px; height:38px; border:2px dashed #00e676; border-radius:7px; background:#0077b6; color:#fff; font-weight:bold;'>"
                    f"<span style='font-size:14px; line-height:14px;'>+{m_it['Liczba']:02d}</span>"
                    f"<span style='font-size:8px; color:#b9f6ca; line-height:9px;'>{m_it['models_cnt']}/{elite_models_total}m</span></div>"
                )
            else:
                m_box = (
                    f"<div style='display:inline-flex; flex-direction:column; align-items:center; justify-content:center; "
                    f"width:54px; height:36px; border:1px solid #3c4252; border-radius:6px; background:#1c202b;'>"
                    f"<span style='font-size:13px; color:#d0d7de; line-height:14px;'>{m_it['Liczba']:02d}</span>"
                    f"<span style='font-size:8px; color:#8a94a6; line-height:9px;'>{m_it['models_cnt']}/{elite_models_total}m</span></div>"
                )
            live_m_cells.append(f"<td style='padding:5px 3px; text-align:center; border-right:1px solid #333945;'>{m_box}</td>")

        meta_tbl_rows.append(f"""
        <tr style='background: linear-gradient(90deg, rgba(0, 180, 216, 0.25) 0%, rgba(255, 209, 102, 0.20) 100%); border-top: 2.5px solid #00b4d8; border-bottom: 3px solid #00b4d8;'>
            <td style='padding: 6px 6px; color: #90e0ef; font-weight:900; white-space: nowrap; font-size: 11px;'>🔥 #{last_draw_id}<br><span style='font-size:9px; color:#fff;'>({last_time_str})</span></td>
            <td style='padding: 6px 6px; font-weight:900; color:#00e676; white-space: nowrap; font-size: 12px; border-right:2px solid #00b4d8;'>🎯 #{target_draw_id}<br><span style='font-size:9px; color:#ffd166;'>({target_time_str})</span></td>
            <td style='padding: 6px 6px; text-align:center; white-space:nowrap; border-right:2px solid #00b4d8;'>
                <span style='padding:3px 7px; border:2px solid #ffd166; border-radius:6px; background:#e63946; color:#fff; font-weight:900; font-size:13px;'>{m1['Liczba']:02d}</span>
                <span style='padding:3px 7px; border:2px solid #ffd166; border-radius:6px; background:#e63946; color:#fff; font-weight:900; font-size:13px;'>{m2['Liczba']:02d}</span>
                <span style='padding:2px 5px; border:1.5px dashed #00e676; border-radius:5px; background:#0077b6; color:#fff; font-weight:bold; font-size:11px;'>+{m3['Liczba']:02d}</span>
            </td>
            {''.join(live_m_cells)}
            <td style='padding: 6px 6px; text-align:center; font-weight:900; font-size:11px; color:#ffd166; border-left:2px solid #00b4d8;'>⏳ W GRZE</td>
        </tr>
        """)

        for mh in meta_hist_rows:
            ts, mt5, hfl = mh["t_step"], mh["m_top5"], mh["h_fl"]
            m_cells = []
            for k in range(5):
                bv, mcnt = mt5[k]["Liczba"], mt5[k]["models_cnt"]
                is_p = k in (ms1, ms2)
                tint = "background-color:rgba(255, 209, 102, 0.07);" if is_p else ""
                if hfl[k]:
                    bc = "#ffd166" if is_p else "#00e676"
                    cbox = (
                        f"<div style='display:inline-flex; flex-direction:column; align-items:center; justify-content:center; "
                        f"width:54px; height:34px; border:2px solid {bc}; border-radius:6px; background:rgba(0,230,118,0.32); color:#fff; font-weight:bold;'>"
                        f"<span style='font-size:13px; line-height:13px;'>{bv:02d}</span>"
                        f"<span style='font-size:8px; color:#b9f6ca; line-height:9px;'>{mcnt}/{elite_models_total}m</span></div>"
                    )
                else:
                    cbox = (
                        f"<div style='display:inline-flex; flex-direction:column; align-items:center; justify-content:center; "
                        f"width:54px; height:34px; border:1px solid #2b303c; border-radius:6px; background:#151821;'>"
                        f"<span style='font-size:12px; color:#a8b0c0; line-height:13px;'>{bv:02d}</span>"
                        f"<span style='font-size:8px; color:#6c7385; line-height:9px;'>{mcnt}/{elite_models_total}m</span></div>"
                    )
                m_cells.append(f"<td style='padding:3px 3px; text-align:center; border-right:1px solid #232731; {tint}'>{cbox}</td>")

            mb1 = f"<span style='padding:2px 5px; border:1.5px solid #ffd166; border-radius:4px; background:rgba(255,209,102,0.32); color:#fff; font-weight:bold;'>{mt5[ms1]['Liczba']:02d}🟩</span>" if hfl[ms1] else f"<span style='color:#9da3af;'>{mt5[ms1]['Liczba']:02d}</span>"
            mb2 = f"<span style='padding:2px 5px; border:1.5px solid #00e676; border-radius:4px; background:rgba(0,230,118,0.28); color:#fff; font-weight:bold;'>{mt5[ms2]['Liczba']:02d}🟩</span>" if hfl[ms2] else f"<span style='color:#9da3af;'>{mt5[ms2]['Liczba']:02d}</span>"
            t5c = "#00e676" if mh["t5_h"] >= 2 else ("#ffd166" if mh["t5_h"] == 1 else "#6c7385")
            t5bg = "rgba(0, 230, 118, 0.16)" if mh["t5_h"] >= 2 else "transparent"
            meta_tbl_rows.append(f"""
            <tr style='border-bottom: 1px solid #262a34;'>
                <td style='padding: 4px 6px; color: #9da3af; white-space: nowrap; font-size: 11px;'>#{all_ids[ts]}<br><span style='font-size:9px; color:#6c7385;'>({all_times[ts]})</span></td>
                <td style='padding: 4px 6px; font-weight: bold; color: #fff; white-space: nowrap; font-size: 11px; border-right:2px solid #333945;'>#{all_ids[ts + 1]}</td>
                <td style='padding: 4px 6px; text-align:center; white-space:nowrap; font-size:11px; border-right:2px solid #333945;'>{mb1} &nbsp; {mb2}</td>
                {''.join(m_cells)}
                <td style='padding: 4px 6px; text-align:center; font-weight:bold; font-size:12px; color:{t5c}; background:{t5bg}; border-left:2px solid #333945;'>{mh['t5_h']} / 5</td>
            </tr>
            """)

        meta_headers = []
        for k in range(5):
            hc = meta_slot_hits_20[k]
            if k in (ms1, ms2):
                meta_headers.append(
                    f"<th style='background:#4a3805; color:#ffd166; border-top:3px solid #ffd166; border-left:2px solid #ffd166; border-right:2px solid #ffd166;'>"
                    f"👑 GRAJ META #{k+1}<br><span style='font-size:10px; color:#fff;'>({hc}/{meta_bt_max} = {hc/meta_bt_max*100:.0f}%)</span></th>"
                )
            elif k == ms3:
                meta_headers.append(
                    f"<th style='background:#083d25; color:#00e676; border-top:2px dashed #00e676;'>"
                    f"➕ 3. META (#{k+1})<br><span style='font-size:9px; color:#b9f6ca;'>({hc}/{meta_bt_max} = {hc/meta_bt_max*100:.0f}%)</span></th>"
                )
            else:
                meta_headers.append(f"<th>Meta #{k+1}<br><span style='font-size:9px; color:#8a94a6;'>({hc}/{meta_bt_max})</span></th>")

        meta_matrix_html = f"""
        <!DOCTYPE html>
        <html><head><meta charset="utf-8"><style>
            body {{ margin:0; padding:0; background:#0e1117; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }}
            .mc {{ max-height:460px; overflow:auto; border:1.5px solid #00b4d8; border-radius:10px; }}
            table {{ width:100%; border-collapse:collapse; }}
            thead {{ position:sticky; top:0; background:#161922; z-index:10; border-bottom:2px solid #333945; }}
            th {{ padding:7px 5px; text-align:center; color:#e6e6e6; font-size:11px; white-space:nowrap; }}
        </style></head><body><div class="mc"><table><thead><tr>
            <th style="text-align:left;">Z losowania</th>
            <th style="text-align:left; border-right:2px solid #333945;">Do (T+1)</th>
            <th style="border-right:2px solid #333945; color:#ffd166;">🌐 Para (#{ms1+1}+#{ms2+1}: {meta_pair_any_20}/{meta_bt_max})</th>
            {''.join(meta_headers)}
            <th style="border-left:2px solid #333945; color:#00e676;">META TOP 5</th>
        </tr></thead><tbody>{''.join(meta_tbl_rows)}</tbody></table></div></body></html>
        """
        components.html(meta_matrix_html, height=480, scrolling=False)

    # =====================================================================
    # ZWYCIĘSKIE POJEDYNCZE OKNO + TABELA 1 + TABELA 2
    # =====================================================================
    main_ball_1, main_ball_2, cand_ball_3 = w1_info["b1"], w1_info["b2"], w1_info["b3"]
    c3_win_count = w1_info["c_b3"]
    c3_slot_pct30 = (w1_info["s3_hits30"] / matrix_bt_steps) * 100.0
    c3_score = w1_info["b3_score"]
    c3_has_sq = int(win_live_top5[first_place_win][w1_info["best_s3"]]["has_t1_sq"]) == 1

    is_3rd_ball_strong = (
        (w1_info["s3_hits30"] >= 11 and w1_info["s3_hits10"] >= 4 and c3_win_count >= 3)
        or (w1_info["s3_hits30"] >= 13 and c3_score >= 64.0 and c3_has_sq)
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

    p30_pct = (w1_info["pair_any_30"] / matrix_bt_steps) * 100.0
    hero_v29_html = (
        f"<div style='background: linear-gradient(135deg, rgba(14, 48, 35, 0.98) 0%, rgba(9, 28, 21, 0.99) 100%); "
        f"border: 3px solid #ffd166; border-radius: 14px; padding: 16px 20px; margin-bottom: 18px; "
        f"box-shadow: 0 6px 20px rgba(255, 209, 102, 0.25); font-family: sans-serif;'>"
        f"<div style='display:flex; flex-wrap:wrap; justify-content:space-between; align-items:center; background:rgba(0,0,0,0.55); "
        f"border:2px solid #00e676; border-radius:9px; padding:10px 16px; margin-bottom:14px;'>"
        f"<div style='font-size:16px; font-weight:900; color:#00e676;'>"
        f"🎯 ZWYCIĘSKIE POJEDYNCZE OKNO [{mode_short_tag}] NA: <span style='color:#ffffff; background:#e63946; padding:3px 10px; border-radius:6px; font-size:18px;'>#{target_draw_id} (godz. {target_time_str})</span>"
        f"</div>"
        f"<div style='font-size:13px; color:#ffd166; font-weight:bold;'>"
        f"🏆 Wybrano (TOP 3): <b>OKNO {first_place_win}</b> — <b>Typ #{w1_info['best_s1']+1} + Typ #{w1_info['best_s2']+1}</b> "
        f"(30g: <b>{w1_info['pair_any_30']}/30 = {p30_pct:.0f}%</b>, pełne 2z2: <b>{w1_info['pair_both_30']}x</b>, śr./kulę: <b>{w1_info['pair_ball_pct30']:.1f}%</b> | 10g: <b>{w1_info['pair_any_10']}/10</b>)"
        f"</div>"
        f"</div>"
        f"<div style='display: flex; flex-wrap: wrap; gap: 16px; align-items: center; margin-bottom: 14px;'>"
        f"<div style='display: inline-flex; align-items: center; gap: 12px; background: rgba(0, 0, 0, 0.65); "
        f"border: 3px solid #ffd166; border-radius: 12px; padding: 10px 18px; box-shadow: 0 0 16px rgba(255, 209, 102, 0.45);'>"
        f"<div>"
        f"<div style='font-size: 14px; color: #ffd166; font-weight: 900;'>👑 2 GŁÓWNE LICZBY Z OKNA {first_place_win}:</div>"
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
        f"<div>🔥 <b>Zgodność TOP 3 wszystkich okien (5–15):</b> <span style='color:#ffd166;'>{consensus_html}</span></div>"
        f"</div>"
        f"</div>"
    )
    st.markdown(hero_v29_html, unsafe_allow_html=True)

    # TABELA 1: ZESTAWIENIE OKIEN ANALIZY (5–15)
    st.subheader(f"📊 1. Zestawienie Okien Analizy (5–15) — Stabilność 30 gier + Forma 10 gier na #{target_draw_id}")
    win_rows_html = []
    for rank_i, w_val in enumerate(ranked_windows):
        wi = win_summary_data[w_val]
        t5_w = win_live_top5[w_val]
        is_1st, is_2nd = (rank_i == 0), (rank_i == 1)

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
            if s_idx in (wi["best_s1"], wi["best_s2"]):
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
        win_rows_html.append(f"""
        <tr style='{tr_style}'>
            <td style='padding: 8px 10px; white-space: nowrap;'>{rank_badge}<br><b style='font-size:15px; color:#fff;'>OKNO {w_val} LOSOWAŃ</b></td>
            <td style='padding: 8px 10px; text-align: center; white-space: nowrap;'>
                <span style='font-size:14px; font-weight:900; color:#00e676;'>30g: {wi['pair_any_30']}/30 ({p30_w_pct:.0f}%) | 2z2: {wi['pair_both_30']}x</span><br>
                <span style='font-size:11px; color:#ffd166;'>Śr./kulę: {wi['pair_ball_pct30']:.1f}% | Ost. 10g: {wi['pair_any_10']}/10 (2z2: {wi['pair_both_10']}x)</span>
            </td>
            <td style='padding: 8px 10px; text-align: center; white-space: nowrap;'>
                <b style='color:#ffd166; font-size:13px;'>Typ #{wi['best_s1']+1} ({wi['s1_hits30']}/30) + Typ #{wi['best_s2']+1} ({wi['s2_hits30']}/30)</b><br>
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
    <html><head><meta charset="utf-8"><style>
        body {{ margin:0; padding:0; background:#0e1117; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }}
        .tbl-wrap {{ overflow-x:auto; border:1.5px solid #333945; border-radius:10px; }}
        table {{ width:100%; border-collapse:collapse; }}
        th {{ background:#161922; color:#ffd166; padding:10px 8px; font-size:12px; text-align:center; border-bottom:2px solid #333945; white-space:nowrap; }}
    </style></head><body><div class="tbl-wrap"><table><thead><tr>
        <th style="text-align:left;">OKNO ANALIZY</th>
        <th>SKUTECZNOŚĆ PARY (30 GIER vs 10 GIER)</th>
        <th>WYBRANE KOLUMNY (Z TOP 3)</th>
        <th>🎯 2 GŁÓWNE LICZBY (+3. DODATKOWA)</th>
        <th style="text-align:left;">WSZYSTKIE 5 KOLUMN NA #{target_draw_id} (Złote = Wybrane do Pary)</th>
    </tr></thead><tbody>{''.join(win_rows_html)}</tbody></table></div></body></html>
    """
    components.html(clean_windows_table_html, height=480, scrolling=True)

    # TABELA NR 2 — CZYTELNA TABELA GŁÓWNA + AUTO-SYNC
    st.divider()
    col_s1, col_s2 = st.columns([1.3, 0.9])
    with col_s1:
        auto_opt_label = "⭐ Auto (Zwycięskie)"
        win_radio_opts = [auto_opt_label] + all_windows
        selected_win_opt = st.radio(
            f"⚙️ Okno dla Tabeli nr 2 (⭐ Auto = aktualnie Okno {first_place_win}):",
            options=win_radio_opts, index=0, horizontal=True, key="v29_detail_win_radio"
        )
        detail_win = first_place_win if selected_win_opt == auto_opt_label else int(selected_win_opt)
    with col_s2:
        detail_bt = st.radio(
            "🧪 Liczba wierszy historii w Tabeli nr 2:",
            options=[10, 15, 20, 30], index=2, horizontal=True, key="v29_detail_bt_radio"
        )

    active_scorer = win_scorers[detail_win]
    df_predictions, latest_win_freq, latest_win_t1, latest_modes_set, _ = active_scorer(latest_idx, return_df=True)
    latest_curr_set = all_sets[latest_idx]
    det_info = win_summary_data[detail_win]
    sel_s1, sel_s2, sel_s3 = det_info["best_s1"], det_info["best_s2"], det_info["best_s3"]

    top_5_Row = df_predictions.head(5)
    bt_html_rows = []
    top5_slot_hits = {slot: 0 for slot in range(1, 6)}

    live_g1_ball = int(top_5_Row.iloc[sel_s1]["Liczba"])
    live_g2_ball = int(top_5_Row.iloc[sel_s2]["Liczba"])
    live_g3_ball = int(top_5_Row.iloc[sel_s3]["Liczba"])
    live_g1_p = int(top_5_Row.iloc[sel_s1]["pos_nr"])
    live_g2_p = int(top_5_Row.iloc[sel_s2]["pos_nr"])

    live_slot_cells_html = []
    for slot_idx, (_, r_pred) in enumerate(top_5_Row.iterrows()):
        b_val, k_pos, b_m = int(r_pred["Liczba"]), int(r_pred["pos_nr"]), int(r_pred["blue_m"])
        if slot_idx in (sel_s1, sel_s2):
            cell_box = (
                f"<div style='display:inline-flex; flex-direction:column; align-items:center; justify-content:center; "
                f"width:56px; height:38px; border:2.5px solid #ffd166; border-radius:7px; "
                f"background:#e63946; color:#ffffff; font-weight:900; box-shadow:0 0 8px rgba(255,209,102,0.6);'>"
                f"<span style='font-size:15px; line-height:15px;'>🎯{b_val:02d}</span>"
                f"<span style='font-size:8px; color:#ffd166; line-height:9px;'>P{k_pos:02d}|M.{b_m:02d}</span></div>"
            )
        elif slot_idx == sel_s3:
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
        f"{live_g1_ball:02d}(P{live_g1_p:02d})</span> "
        f"<span style='padding:3px 7px; border:2px solid #ffd166; border-radius:6px; background:#e63946; color:#fff; font-weight:900; font-size:13px;'>"
        f"{live_g2_ball:02d}(P{live_g2_p:02d})</span> "
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
        cands_step, _, _, _, _ = active_scorer(step_t, return_df=False)
        next_actual_set = all_sets[step_t + 1]
        top5_list, top8_list = cands_step[:5], cands_step[:8]

        g1_ball, g2_ball = int(top5_list[sel_s1]["Liczba"]), int(top5_list[sel_s2]["Liczba"])
        g1_p, g2_p = int(top5_list[sel_s1]["pos_nr"]), int(top5_list[sel_s2]["pos_nr"])
        g1_hit, g2_hit = (g1_ball in next_actual_set), (g2_ball in next_actual_set)

        slot_cells_html = []
        for slot_idx, r_pred in enumerate(top5_list):
            slot_nr = slot_idx + 1
            b_val, k_pos, b_m = int(r_pred["Liczba"]), int(r_pred["pos_nr"]), int(r_pred["blue_m"])
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

        g1_badge = f"<span style='padding:2px 5px; border:1.5px solid #ffd166; border-radius:4px; background:rgba(255,209,102,0.30); color:#fff; font-weight:bold;'>{g1_ball:02d}(P{g1_p:02d})🟩</span>" if g1_hit else f"<span style='color:#9da3af;'>{g1_ball:02d}(P{g1_p:02d})</span>"
        g2_badge = f"<span style='padding:2px 5px; border:1.5px solid #00e676; border-radius:4px; background:rgba(0,230,118,0.28); color:#fff; font-weight:bold;'>{g2_ball:02d}(P{g2_p:02d})🟩</span>" if g2_hit else f"<span style='color:#9da3af;'>{g2_ball:02d}(P{g2_p:02d})</span>"

        hits_5_cnt = sum(1 for r_x in top5_list if r_x["Liczba"] in next_actual_set)
        hits_8_cnt = sum(1 for r_x in top8_list if r_x["Liczba"] in next_actual_set)
        h5_color = "#00e676" if hits_5_cnt >= 2 else ("#ffd166" if hits_5_cnt == 1 else "#6c7385")
        h5_bg = "rgba(0, 230, 118, 0.16)" if hits_5_cnt >= 2 else "transparent"

        bt_html_rows.append(f"""
        <tr style='border-bottom: 1px solid #262a34;'>
            <td style='padding: 5px 6px; color: #9da3af; white-space: nowrap; font-size: 11px;'>#{all_ids[step_t]}<br><span style='font-size:9px; color:#6c7385;'>({all_times[step_t]})</span></td>
            <td style='padding: 5px 6px; font-weight: bold; color: #ffffff; white-space: nowrap; font-size: 11px; border-right:2px solid #333945;'>#{all_ids[step_t + 1]}</td>
            <td style='padding: 5px 6px; text-align: center; white-space: nowrap; font-size: 11px; border-right:2px solid #333945;'>{g1_badge} &nbsp; {g2_badge}</td>
            {''.join(slot_cells_html)}
            <td style='padding: 5px 6px; text-align: center; font-weight: bold; font-size: 12px; color: {h5_color}; background-color: {h5_bg}; border-left:2px solid #333945;'>{hits_5_cnt} / 5</td>
            <td style='padding: 5px 6px; text-align: center; font-weight: bold; font-size: 12px; color: #4da6ff;'>{hits_8_cnt} / 8</td>
        </tr>
        """)

    st.markdown(
        f"### 📋 2. Czytelna Tabela Główna (Okno {detail_win}, tryb: **{mode_short_tag}**) — Pierwszy wiersz u góry to Twoje typy na **#{target_draw_id} ({target_time_str})**"
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
            col_headers_t5.append(f"<th style='color:#d0d7de;'>Typ #{s_nr}<br><span style='font-size:9px; color:#8a94a6;'>({h_cnt}/{detail_bt})</span></th>")

    bt_matrix_html = f"""
    <!DOCTYPE html>
    <html><head><meta charset="utf-8"><style>
        body {{ margin:0; padding:0; background:#0e1117; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }}
        .table-container {{ max-height:640px; overflow:auto; border:1.5px solid #ffd166; border-radius:10px; }}
        table {{ width:100%; border-collapse:collapse; }}
        thead {{ position:sticky; top:0; background:#161922; z-index:10; border-bottom:2px solid #333945; }}
        th {{ padding:7px 5px; text-align:center; color:#e6e6e6; font-size:11px; white-space:nowrap; }}
    </style></head><body><div class="table-container"><table><thead><tr>
        <th style="text-align:left;">Z losowania</th>
        <th style="text-align:left; border-right:2px solid #333945;">Do (T+1)</th>
        <th style="border-right:2px solid #333945; color:#ffd166;">👑 2 Główne (Typ #{sel_s1+1}+#{sel_s2+1})</th>
        {''.join(col_headers_t5)}
        <th style="border-left:2px solid #333945; color:#00e676;">TOP 5</th>
        <th style="color:#4da6ff;">TOP 8</th>
    </tr></thead><tbody>{''.join(bt_html_rows)}</tbody></table></div></body></html>
    """
    components.html(bt_matrix_html, height=660, scrolling=False)

    # SPÓJNY RANKING 20 LICZB I GORĄCE KULE
    col_pred_table, col_hot_all = st.columns([1.45, 0.95], gap="large")
    with col_pred_table:
        st.markdown(f"#### 📊 3. Pełny Ranking 20 liczb z #{last_draw_id} ➔ na #{target_draw_id} (Okno = {detail_win} | {mode_short_tag})")
        df_display_pred = df_predictions.drop(
            columns=["pos_nr", "blue_m", "pos_white_hits", "trans_count", "pos_white_pct", "w15_hits", "b_hits_cnt", "orig_bwin_cnt", "b_steps", "b_hit_pct", "has_t1_sq", "is_blue_leader", "is_super_hot", "ball_t1_win", "ball_t1_total"]
        ).copy()
        st.dataframe(
            df_display_pred,
            column_config={
                "Rank": st.column_config.TextColumn("Typ #", width="small"),
                "Pozycja": st.column_config.TextColumn("Poz. (🟦 Miejsce)", width="medium"),
                "Liczba": st.column_config.NumberColumn("Kula", width="small"),
                "Score": st.column_config.ProgressColumn("Siła (Score)", format="%.1f pkt", min_value=0, max_value=100),
                "Status V29": st.column_config.TextColumn("Status Weryfikacji", width="medium"),
                "⬜ Własne Poz. (i z 15)": st.column_config.TextColumn(f"⬜ Własne ({detail_win} i 15)", width="medium"),
                "🟦 Kolumna M (i Stałe)": st.column_config.TextColumn(f"🟦 Kolumna M ({detail_win})", width="medium"),
                "Pod pozycją (Węzeł)": st.column_config.TextColumn("Pod pozycją", width="medium"),
                "Powtórki Kuli T+1": st.column_config.TextColumn("Powt. Kuli", width="small"),
                "⭐ 'Najczęstsza'": st.column_config.TextColumn("⭐ 'Najczęstsza'", width="small"),
            },
            hide_index=True, use_container_width=True, height=520, key="pred_main_ranking_tbl_v29"
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

        st.dataframe(df_hot70, hide_index=True, use_container_width=True, height=520, key="hot_70_check_tbl_v29")

# Wywołanie modułu V29 (domyślnie tryb Bez Tabeli Niebieskiej i blokada słabych slotów #4/#5):
render_prediction_algorithm(df, default_window=10, default_blue_win=10, default_backtest=10)
