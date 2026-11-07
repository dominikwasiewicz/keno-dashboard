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
# MODUŁ ALGORYTMU PREDYKCYJNEGO V5:
# 100% SYNCHRONIZACJI Z TABELĄ NIEBIESKĄ 🟦 + ZŁOTE LOKATY BEZPOŚREDNIO Z LIDERÓW 🟦
# =====================================================================
from collections import defaultdict

def render_prediction_algorithm(df_full, default_window=15, default_backtest=100):
    st.divider()
    st.header("🧠 Algorytm Wskazujący Następne Trafienia V5 (Liderzy Tabeli Niebieskiej 🟦 + Węzły ⬜/🔴 + 'Najczęstsza')")

    pred_options = [10, 12, 15, 20, 25, 30, 50]
    bt_options = [30, 50, 100, 150, 200]

    if "pred_win_saved" not in st.session_state:
        url_val = st.query_params.get("pred_win", str(default_window))
        saved_int = int(url_val) if str(url_val).isdigit() else default_window
        st.session_state.pred_win_saved = saved_int if saved_int in pred_options else default_window

    if "bt_steps_saved" not in st.session_state:
        url_bt = st.query_params.get("bt_steps", str(default_backtest))
        saved_bt = int(url_bt) if str(url_bt).isdigit() else default_backtest
        st.session_state.bt_steps_saved = saved_bt if saved_bt in bt_options else default_backtest

    def update_pred_params():
        st.session_state.pred_win_saved = st.session_state.pred_win_radio_key
        st.session_state.bt_steps_saved = st.session_state.bt_steps_radio_key
        st.query_params["pred_win"] = str(st.session_state.pred_win_radio_key)
        st.query_params["bt_steps"] = str(st.session_state.bt_steps_radio_key)

    col_cfg1, col_cfg2 = st.columns([1.2, 1])
    with col_cfg1:
        window_size = st.radio(
            "⚙️ 1. Wybierz okno analizy dla Algorytmu (ustaw takie samo jak w Pierwszej Tabeli, np. 15):",
            options=pred_options,
            index=pred_options.index(st.session_state.pred_win_saved),
            horizontal=True,
            key="pred_win_radio_key",
            on_change=update_pred_params
        )
    with col_cfg2:
        backtest_steps = st.radio(
            "🧪 2. Liczba losowań Weryfikacji Wstecznej (domyślnie 100, pamiętane):",
            options=bt_options,
            index=bt_options.index(st.session_state.bt_steps_saved),
            horizontal=True,
            key="bt_steps_radio_key",
            on_change=update_pred_params
        )

    blue_lookback = 15  # Dokładnie 15 losowań sprawdzanych w Tabeli Niebieskiej
    max_possible_bt = max(10, len(df_full) - window_size - blue_lookback - 3)
    actual_bt_steps = min(backtest_steps, max_possible_bt)

    if len(df_full) < window_size + blue_lookback + 10:
        st.warning(f"Za mało danych w bazie ({len(df_full)}), aby wykonać pełny test.")
        return

    all_lists = df_full["numbers_list"].tolist()
    all_sets = df_full["numbers_set"].tolist()
    all_ids = df_full["draw_id"].tolist()
    all_times = df_full["draw_time"].tolist()
    total_draws = len(df_full)

    # -----------------------------------------------------------------
    # WSTĘPNE OBLICZENIE UKŁADU TABELI 1 ORAZ TABELI NIEBIESKIEJ 🟦 (1:1 Z WIDOKIEM GÓRNYM)
    # -----------------------------------------------------------------
    earliest_needed = max(window_size - 1, total_draws - 1 - actual_bt_steps - blue_lookback - 2)
    step_meta = {}
    min_mode_threshold = 3 if window_size >= 15 else 2

    for t_i in range(earliest_needed, total_draws):
        w_start = t_i - window_size + 1
        w_lists = all_lists[w_start : t_i + 1]
        w_sets = all_sets[w_start : t_i + 1]
        n_trans = len(w_lists) - 1
        curr_l = all_lists[t_i]
        next_s = all_sets[t_i + 1] if (t_i + 1 < total_draws) else set()

        pos_temp = []
        pos_modes = {}
        all_modes_set = set()

        for i in range(1, 21):
            p_idx = i - 1
            repeat_t1_count = sum(1 for k in range(n_trans) if w_lists[k][p_idx] in w_sets[k + 1])

            col_vals = [w_lists[k][p_idx] for k in range(len(w_lists))]
            s_col = pd.Series(col_vals)
            m_val = int(s_col.mode().iloc[0])
            m_cnt = int((s_col == m_val).sum())
            pos_modes[i] = (m_val, m_cnt)
            if m_cnt >= min_mode_threshold:
                all_modes_set.add(m_val)

            pos_temp.append({
                "orig_pos": i,
                "raw_hits": repeat_t1_count,
                "ball": curr_l[p_idx]
            })

        # Identyczne sortowanie mergesort jak w górnej Tabeli Niebieskiej (Tryb B)
        df_rank_step = pd.DataFrame(pos_temp).sort_values(
            by="raw_hits", ascending=False, kind="mergesort"
        ).reset_index(drop=True)

        blue_col_for_orig_pos = {}
        blue_hit_by_col = {}
        for rank_idx, r_item in df_rank_step.iterrows():
            m_col = rank_idx + 1
            o_pos = int(r_item["orig_pos"])
            b_val = int(r_item["ball"])
            w_hits = int(r_item["raw_hits"])
            blue_col_for_orig_pos[o_pos] = (m_col, w_hits)
            blue_hit_by_col[m_col] = (b_val in next_s) if (t_i + 1 < total_draws) else False

        step_meta[t_i] = {
            "blue_col_map": blue_col_for_orig_pos,
            "blue_hit_by_col": blue_hit_by_col,
            "pos_modes": pos_modes,
            "all_modes_set": all_modes_set,
        }

    # -----------------------------------------------------------------
    # GŁÓWNA FUNKCJA OCENIAJĄCA (SCORING 0-100 PKT + WYBÓR ZŁOTYCH LOKAT Z TABELI NIEBIESKIEJ)
    # -----------------------------------------------------------------
    def score_draw_at_index(t_idx):
        win_start = t_idx - window_size + 1
        win_lists = all_lists[win_start : t_idx + 1]
        win_sets = all_sets[win_start : t_idx + 1]
        trans_count = len(win_lists) - 1

        curr_nums = all_lists[t_idx]
        prev_set = all_sets[t_idx - 1] if t_idx >= 1 else set()
        prev2_set = all_sets[t_idx - 2] if t_idx >= 2 else set()

        meta_now = step_meta[t_idx]
        blue_col_map_now = meta_now["blue_col_map"]
        pos_modes_now = meta_now["pos_modes"]
        all_modes_set_now = meta_now["all_modes_set"]

        # 1. Dokładne zliczenie trafień kolumn M.1..M.20 oraz stałych trafień pozycji w oknie 15 losowań
        blue_col_hits_15 = {m: 0 for m in range(1, 21)}
        orig_pos_hits_15 = {p: 0 for p in range(1, 21)}
        blue_steps_avail = 0

        start_b = max(earliest_needed, t_idx - blue_lookback)
        for b_t in range(start_b, t_idx):
            blue_steps_avail += 1
            b_hits_map = step_meta[b_t]["blue_hit_by_col"]
            for m_c in range(1, 21):
                if b_hits_map.get(m_c, False):
                    blue_col_hits_15[m_c] += 1

            b_nums = all_lists[b_t]
            b_next_set = all_sets[b_t + 1]
            for p_i in range(20):
                if b_nums[p_i] in b_next_set:
                    orig_pos_hits_15[p_i + 1] += 1

        prev1_blue_hits = step_meta[t_idx - 1]["blue_hit_by_col"] if (t_idx - 1) in step_meta else {}
        prev2_blue_hits = step_meta[t_idx - 2]["blue_hit_by_col"] if (t_idx - 2) in step_meta else {}

        # 2. Częstotliwość kul w oknie
        win_ball_freq = {b: 0 for b in range(1, 71)}
        win_ball_t1_repeats = {b: 0 for b in range(1, 71)}
        for k_idx, d_list in enumerate(win_lists):
            for b in d_list:
                win_ball_freq[b] += 1
                if k_idx < trans_count and b in win_sets[k_idx + 1]:
                    win_ball_t1_repeats[b] += 1

        # 3. Białe kwadraty ⬜ bezpośrednio w wierszu t-1 i t-2
        sq_1_step_ago = {p: False for p in range(1, 21)}
        sq_2_steps_ago = {p: False for p in range(1, 21)}
        if t_idx >= 1:
            l_prev1 = all_lists[t_idx - 1]
            for p_i in range(20):
                if l_prev1[p_i] in all_sets[t_idx]:
                    sq_1_step_ago[p_i + 1] = True
        if t_idx >= 2:
            l_prev2 = all_lists[t_idx - 2]
            for p_i in range(20):
                if l_prev2[p_i] in all_sets[t_idx - 1]:
                    sq_2_steps_ago[p_i + 1] = True

        candidates = []
        for p_i in range(20):
            pos_nr = p_i + 1
            ball = curr_nums[p_i]

            # =================================================================
            # FILAR 1 (DO 45 PKT): TABELA NIEBIESKA 🟦 (DOKŁADNE TRAFIENIA KOLUMNY M + STAŁE TRAF. POZYCJI)
            # =================================================================
            m_col, pos_white_hits = blue_col_map_now[pos_nr]
            b_hits_cnt = blue_col_hits_15[m_col]
            b_hit_rate = b_hits_cnt / max(1, blue_steps_avail)
            orig_15_cnt = orig_pos_hits_15[pos_nr]
            orig_15_rate = orig_15_cnt / max(1, blue_steps_avail)

            # Punkty za skuteczność kolumny M w Tabeli Niebieskiej (0 - 25 pkt)
            pts_blue_col = min(25.0, (b_hit_rate / 0.50) * 25.0)

            # Punkty za stałe trafienia tej oryginalnej pozycji w ostatnich 15 grach (0 - 8 pkt)
            pts_orig_15 = min(8.0, (orig_15_rate / 0.45) * 8.0)

            # Punkty za pionową ścieżkę niebieskich kwadratów pod tym miejscem (w t-1 i t-2) (0 - 12 pkt)
            b_under_1 = prev1_blue_hits.get(m_col, False)
            b_under_2 = prev2_blue_hits.get(m_col, False)
            b_adj_1 = prev1_blue_hits.get(m_col - 1, False) or prev1_blue_hits.get(m_col + 1, False)

            if b_under_1 and b_under_2:
                pts_blue_streak = 12.0
            elif b_under_1:
                pts_blue_streak = 8.5
            elif b_adj_1:
                pts_blue_streak = 4.5
            else:
                pts_blue_streak = 0.0

            score_blue_total = round(min(45.0, pts_blue_col + pts_orig_15 + pts_blue_streak), 1)

            # =================================================================
            # FILAR 2 (DO 30 PKT): BIAŁE KWADRATY ⬜ I CZERWONE KÓŁKA 🔴 W TABELI 1
            # =================================================================
            pos_rate = pos_white_hits / trans_count if trans_count > 0 else 0
            pts_white_pos = min(12.0, (pos_rate / 0.50) * 12.0)

            sq_direct_1 = sq_1_step_ago[pos_nr]
            sq_direct_2 = sq_2_steps_ago[pos_nr]
            sq_neighbor_1 = sq_1_step_ago.get(pos_nr - 1, False) or sq_1_step_ago.get(pos_nr + 1, False)

            if sq_direct_1 and sq_direct_2:
                pts_white_ladder = 9.0
            elif sq_direct_1 and sq_neighbor_1:
                pts_white_ladder = 7.0
            elif sq_direct_1 or sq_neighbor_1:
                pts_white_ladder = 4.0
            else:
                pts_white_ladder = 0.0

            in_prev1 = (ball in prev_set)
            in_prev2 = (ball in prev2_set)
            if in_prev1 and not in_prev2:
                pts_red_circle = 9.0
                node_str = "🔴 Świeże z T-1"
            elif in_prev1 and in_prev2:
                pts_red_circle = 6.0
                node_str = "🔥🔥 Seria 3+"
            else:
                pts_red_circle = 2.0
                node_str = "⬜ Nowa"

            if sq_direct_1:
                node_str += " + ⬜ pod nią"

            score_white_red_total = round(min(30.0, pts_white_pos + pts_white_ladder + pts_red_circle), 1)

            # =================================================================
            # FILAR 3 (DO 25 PKT): KOLUMNA "NAJCZĘSTSZA" + ZŁOTY ŚRODEK CZĘSTOTLIWOŚCI
            # =================================================================
            ball_freq_in_win = win_ball_freq[ball]
            ball_t1_in_win = win_ball_t1_repeats[ball]

            mode_on_pos, mode_cnt_on_pos = pos_modes_now[pos_nr]
            near_modes = [
                pos_modes_now[p][0]
                for p in range(max(1, pos_nr - 1), min(21, pos_nr + 2))
                if pos_modes_now[p][1] >= min_mode_threshold
            ]
            is_exact_pos_mode = (ball == mode_on_pos and mode_cnt_on_pos >= min_mode_threshold)
            is_near_pos_mode = (ball in near_modes)
            is_in_any_mode_list = (ball in all_modes_set_now)

            if is_exact_pos_mode:
                pts_mode_match = 10.0
                mode_status_str = f"🎯 Lider Poz.{pos_nr:02d} (x{mode_cnt_on_pos})"
            elif is_near_pos_mode:
                pts_mode_match = 8.0
                mode_status_str = "⭐ Z 'Najczęstszej' (obok)"
            elif is_in_any_mode_list:
                pts_mode_match = 5.5
                mode_status_str = "⭐ W puli 'Najczęstsza'"
            else:
                pts_mode_match = 0.0
                mode_status_str = "-"

            ideal_min = max(3, int(window_size * 0.22))
            ideal_max = max(5, int(window_size * 0.45))
            if ideal_min <= ball_freq_in_win <= ideal_max:
                pts_freq_sweet = 10.0
            elif ball_freq_in_win > ideal_max:
                pts_freq_sweet = 6.5
            elif ball_freq_in_win == ideal_min - 1:
                pts_freq_sweet = 5.0
            else:
                pts_freq_sweet = 1.5

            pts_ball_t1 = min(5.0, ball_t1_in_win * 2.0)
            score_freq_mode_total = round(min(25.0, pts_mode_match + pts_freq_sweet + pts_ball_t1), 1)

            total_score = round(score_blue_total + score_white_red_total + score_freq_mode_total, 1)
            support_score = round(score_white_red_total + score_freq_mode_total + (orig_15_cnt * 1.5), 1)

            candidates.append({
                "pos_nr": pos_nr,
                "blue_m": m_col,
                "b_hits_cnt": b_hits_cnt,
                "b_hit_pct": round(b_hit_rate * 100.0, 1),
                "orig_15_cnt": orig_15_cnt,
                "support_score": support_score,
                "Pozycja": f"Poz. {pos_nr:02d} (🟦 M.{m_col:02d})",
                "Liczba": ball,
                "Score": total_score,
                "blue_raw": score_blue_total,
                "freq_raw": ball_freq_in_win,
                "🟦 Pkt Niebieska": f"{score_blue_total:.1f}/45 ({b_hits_cnt}/{blue_steps_avail} 🟦 | stałe:{orig_15_cnt})",
                "⬜/🔴 Pkt Tabela 1": f"{score_white_red_total:.1f}/30 ({node_str})",
                "⭐ Pula 'Najczęstsza'": mode_status_str,
                "Częstość w oknie": f"{ball_freq_in_win}x/{window_size} (powt. T+1: {ball_t1_in_win}x)",
                "Najczęstsza na Poz.": f"{mode_on_pos:02d} (x{mode_cnt_on_pos})"
            })

        # Główny ranking TOP 5 (sortowany po łącznym Score, a przy remisie po trafieniach w Tabeli Niebieskiej)
        df_cand = pd.DataFrame(candidates).sort_values(
            by=["Score", "b_hits_cnt", "pos_nr"], ascending=[False, False, True], kind="mergesort"
        ).reset_index(drop=True)

        # WYBÓR 2 ZŁOTYCH LOKAT BEZPOŚREDNIO Z LIDERÓW TABELI NIEBIESKIEJ 🟦
        # Sortujemy po liczbie trafień w Tabeli Niebieskiej (b_hits_cnt), a przy remisie (np. dwie kolumny po 6/15)
        # decyduje wyższy łączny Score (wsparcie z Tabeli 1 i częstotliwości)!
        df_blue_leaders = pd.DataFrame(candidates).sort_values(
            by=["b_hits_cnt", "Score", "orig_15_cnt"], ascending=[False, False, False], kind="mergesort"
        ).reset_index(drop=True)

        return df_cand, df_blue_leaders, win_ball_freq, win_ball_t1_repeats, all_modes_set_now

    # --- OBLICZENIE NA ŻYWO ORAZ BACKTESTU NA 100 LOSOWANIACH ---
    latest_idx = total_draws - 1
    df_predictions, df_latest_blue_leaders, latest_win_freq, latest_win_t1, latest_modes_set = score_draw_at_index(latest_idx)
    latest_curr_set = all_sets[latest_idx]

    top_5_Row = df_predictions.head(5)
    top_8_Row = df_predictions.head(8)

    # 2 Złote Lokaty wybrane bezpośrednio z liderów Tabeli Niebieskiej 🟦 (wspartych punktacją Score)
    golden_row_1 = df_latest_blue_leaders.iloc[0]
    golden_row_2 = df_latest_blue_leaders.iloc[1]

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
        df_step_pred, df_step_blue_lead, _, _, _ = score_draw_at_index(step_t)
        next_actual_set = all_sets[step_t + 1]

        top5_df = df_step_pred.head(5)
        top8_df = df_step_pred.head(8)

        top5_nums = top5_df["Liczba"].tolist()
        top8_nums = top8_df["Liczba"].tolist()

        # Sprawdzenie, jak w tym kroku trafiły 2 Złote Lokaty (Lider #1 i Lider #2 z Tabeli Niebieskiej)
        g1_ball = int(df_step_blue_lead.iloc[0]["Liczba"])
        g2_ball = int(df_step_blue_lead.iloc[1]["Liczba"])
        g1_m = int(df_step_blue_lead.iloc[0]["blue_m"])
        g2_m = int(df_step_blue_lead.iloc[1]["blue_m"])
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

        # Komórka pokazująca trafienia 2 Złotych Lokat 🟦 w danym losowaniu
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

    curr_in_modes = [b for b in all_lists[latest_idx] if b in latest_modes_set]
    curr_modes_str = ", ".join(f"{b:02d}" for b in curr_in_modes) if curr_in_modes else "brak"
    top8_balls_only = ", ".join(f"{int(r['Liczba']):02d}" for _, r in top_8_Row.iterrows())

    # =====================================================================
    # ZIELONY BLOK REKOMENDACJI Z DUŻYMI CYFRAMI (ZŁOTE LOKATY BEZPOŚREDNIO Z LIDERÓW 🟦)
    # =====================================================================
    gold_balls_set = {int(golden_row_1["Liczba"]), int(golden_row_2["Liczba"])}
    top5_badges_html = ""
    for idx_r, (_, r) in enumerate(top_5_Row.iterrows()):
        s_nr = idx_r + 1
        b_num = int(r["Liczba"])
        p_num = int(r["pos_nr"])
        m_num = int(r["blue_m"])
        b_cnt = int(r["b_hits_cnt"])
        is_gold = b_num in gold_balls_set
        border_col = "#ffd166" if is_gold else "#00e676"
        bg_col = "rgba(255, 209, 102, 0.18)" if is_gold else "rgba(0, 230, 118, 0.14)"
        top5_badges_html += (
            f"<div style='display:inline-flex; align-items:center; gap:8px; padding:6px 12px; margin:4px 6px 4px 0; "
            f"border:2px solid {border_col}; border-radius:8px; background:{bg_col};'>"
            f"<span style='font-size:13px; color:#d0d7de; font-weight:600;'>#{s_nr}:</span>"
            f"<span style='font-size:22px; font-weight:900; color:#ffffff; letter-spacing:0.5px;'>{b_num:02d}</span>"
            f"<span style='font-size:13px; font-weight:bold; color:#ffd166;'>(Poz. {p_num:02d} | 🟦 M.{m_num:02d} — {b_cnt}/15)</span>"
            f"</div>"
        )

    green_hero_html = (
        f"<div style='background: linear-gradient(135deg, rgba(16, 54, 39, 0.95) 0%, rgba(13, 38, 29, 0.95) 100%); "
        f"border: 2px solid #00e676; border-radius: 12px; padding: 16px 20px; margin-bottom: 18px; "
        f"box-shadow: 0 4px 15px rgba(0, 230, 118, 0.18); font-family: sans-serif;'>"
        f"<div style='font-size: 14px; font-weight: bold; color: #b9f6ca; margin-bottom: 12px; text-transform: uppercase; letter-spacing: 0.5px;'>"
        f"🎯 Wskazanie Algorytmu V5 (Okno {window_size}) na losowanie po #{all_ids[latest_idx]} ({all_times[latest_idx]})"
        f"</div>"
        f"<div style='margin-bottom: 14px;'>"
        f"<div style='font-size: 13px; color: #ffd166; font-weight: bold; margin-bottom: 8px;'>"
        f"🏆 ZŁOTE LOKATY (2 najsilniejsze kolumny bezpośrednio z Tabeli Pozycji Trafień 🟦 wsparte Tabelą 1):"
        f"</div>"
        f"<div style='display: flex; flex-wrap: wrap; gap: 12px; align-items: center;'>"
        f"<div style='display: inline-flex; align-items: center; gap: 10px; background: rgba(0, 0, 0, 0.45); "
        f"border: 2.5px solid #ffd166; border-radius: 10px; padding: 8px 16px; box-shadow: 0 0 10px rgba(255, 209, 102, 0.35);'>"
        f"<span style='font-size: 15px; color: #ffd166; font-weight: bold;'>Lider #1 🟦 ➔ Kula</span>"
        f"<span style='font-size: 28px; font-weight: 900; color: #ffffff; background: #e63946; padding: 2px 12px; border-radius: 8px; border: 2px solid #ffffff;'>"
        f"{int(golden_row_1['Liczba']):02d}</span>"
        f"<span style='font-size: 17px; font-weight: 800; color: #4da6ff;'>"
        f"Poz. {int(golden_row_1['pos_nr']):02d} <span style='color:#00e676;'>(🟦 M.{int(golden_row_1['blue_m']):02d})</span></span>"
        f"<span style='font-size: 14px; color: #b9f6ca; font-weight: bold;'>— w Tabeli 🟦: {int(golden_row_1['b_hits_cnt'])}/15 ({golden_row_1['b_hit_pct']:.1f}%)</span>"
        f"</div>"
        f"<div style='display: inline-flex; align-items: center; gap: 10px; background: rgba(0, 0, 0, 0.45); "
        f"border: 2.5px solid #00e676; border-radius: 10px; padding: 8px 16px; box-shadow: 0 0 10px rgba(0, 230, 118, 0.3);'>"
        f"<span style='font-size: 15px; color: #00e676; font-weight: bold;'>Lider #2 🟦 ➔ Kula</span>"
        f"<span style='font-size: 28px; font-weight: 900; color: #ffffff; background: #0077b6; padding: 2px 12px; border-radius: 8px; border: 2px solid #ffffff;'>"
        f"{int(golden_row_2['Liczba']):02d}</span>"
        f"<span style='font-size: 17px; font-weight: 800; color: #4da6ff;'>"
        f"Poz. {int(golden_row_2['pos_nr']):02d} <span style='color:#00e676;'>(🟦 M.{int(golden_row_2['blue_m']):02d})</span></span>"
        f"<span style='font-size: 14px; color: #b9f6ca; font-weight: bold;'>— w Tabeli 🟦: {int(golden_row_2['b_hits_cnt'])}/15 ({golden_row_2['b_hit_pct']:.1f}%)</span>"
        f"</div>"
        f"</div>"
        f"</div>"
        f"<div style='margin-bottom: 10px;'>"
        f"<div style='font-size: 13px; color: #e6e6e6; font-weight: bold; margin-bottom: 6px;'>🔥 Pełne TOP 5 Liczb wg łącznej siły Score (#1 – #5):</div>"
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
        st.subheader(f"📊 1. Ranking 20 liczb z #{all_ids[latest_idx]} (🟦 Niebieska 45 pkt + ⬜/🔴 30 pkt + ⭐ 25 pkt)")
        df_display_pred = df_predictions.drop(
            columns=["pos_nr", "blue_m", "b_hits_cnt", "b_hit_pct", "orig_15_cnt", "support_score", "blue_raw", "freq_raw"]
        ).copy()
        st.dataframe(
            df_display_pred,
            column_config={
                "Pozycja": st.column_config.TextColumn("Poz. (🟦 Miejsce)", width="medium"),
                "Liczba": st.column_config.NumberColumn("Kula", width="small"),
                "Score": st.column_config.ProgressColumn("Siła (Score)", format="%.1f pkt", min_value=0, max_value=100),
                "🟦 Pkt Niebieska": st.column_config.TextColumn("🟦 Tabela Niebieska (45)", width="medium"),
                "⬜/🔴 Pkt Tabela 1": st.column_config.TextColumn("⬜/🔴 Tabela 1 (30)", width="medium"),
                "⭐ Pula 'Najczęstsza'": st.column_config.TextColumn("⭐ Kol. 'Najczęstsza'", width="medium"),
                "Częstość w oknie": st.column_config.TextColumn(f"Losowana ({window_size})", width="medium"),
                "Najczęstsza na Poz.": st.column_config.TextColumn("Lider Poz.", width="small"),
            },
            hide_index=True,
            use_container_width=True,
            height=560,
            key="pred_main_ranking_tbl"
        )

    with col_hot_all:
        st.subheader(f"🔥 2. Najczęściej losowane kule w oknie {window_size} + Pula 'Najczęstsza'")
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
                "in_modes_raw": 1 if in_modes else 0,
                "in_last_raw": 1 if in_last else 0,
                f"W oknie ({window_size})": f"{f_cnt}x ({f_cnt/window_size*100:.0f}%)",
                "W kol. 'Najczęstsza'?": f"⭐ TAK (min. {min_mode_threshold}x)" if in_modes else "-",
                "Powtórki T+1": f"{latest_win_t1[b_num]}x",
                "Teraz w grze?": f"✅ TAK (Poz. {pos_in_last:02d})" if in_last else "⏳ Przerwa"
            })
        df_hot70 = pd.DataFrame(hot70_rows).sort_values(
            by=["in_modes_raw", "f_raw", "in_last_raw"], ascending=[False, False, False], kind="mergesort"
        ).head(25).drop(columns=["f_raw", "in_modes_raw", "in_last_raw"])

        st.dataframe(
            df_hot70,
            hide_index=True,
            use_container_width=True,
            height=560,
            key="hot_70_check_tbl"
        )

    # =====================================================================
    # SEKCJA 3: PODSUMOWANIE I WERYFIKACJA WSTECZNA NA 100 LOSOWAŃ
    # =====================================================================
    st.divider()
    st.subheader(f"🧪 3. Weryfikacja wsteczna algorytmu (ostatnie {actual_bt_steps} losowań przy oknie {window_size})")

    avg_top5 = (total_top5_hits / (actual_bt_steps * 5)) * 100
    avg_top8 = (total_top8_hits / (actual_bt_steps * 8)) * 100
    g1_bt_pct = (golden_1_bt_hits / actual_bt_steps) * 100
    g2_bt_pct = (golden_2_bt_hits / actual_bt_steps) * 100
    g_any_pct = (golden_at_least_one_bt / actual_bt_steps) * 100
    best_s1_pct = (top5_slot_hits[best_slot_1] / actual_bt_steps) * 100
    best_s2_pct = (top5_slot_hits[best_slot_2] / actual_bt_steps) * 100

    st.info(
        f"📈 **Podsumowanie ze {actual_bt_steps} losowań wstecz (dla okna {window_size}):**\n"
        f"- **Złote Lokaty (2 Liderzy Tabeli 🟦):** Lider #1 trafił **{golden_1_bt_hits}/{actual_bt_steps} ({g1_bt_pct:.1f}%)**, "
        f"Lider #2 trafił **{golden_2_bt_hits}/{actual_bt_steps} ({g2_bt_pct:.1f}%)** — w **{golden_at_least_one_bt}/{actual_bt_steps} ({g_any_pct:.1f}%)** gier wchodzi min. 1 Złota Lokata!\n"
        f"- **Najlepsze sloty w TOP 5:** **Typ #{best_slot_1}** trafia **{top5_slot_hits[best_slot_1]}/{actual_bt_steps} ({best_s1_pct:.1f}%)**, "
        f"a **Typ #{best_slot_2}** trafia **{top5_slot_hits[best_slot_2]}/{actual_bt_steps} ({best_s2_pct:.1f}%)**\n"
        f"- **Całe TOP 5 liczb:** łącznie **{total_top5_hits} trafień** na {actual_bt_steps*5} typów (**{avg_top5:.1f}%** skuteczności)\n"
        f"- **Całe TOP 8 liczb:** łącznie **{total_top8_hits} trafień** na {actual_bt_steps*8} typów (**{avg_top8:.1f}%** skuteczności)"
    )

    st.markdown(f"#### 🏆 A. Które miejsce wewnątrz 'Typowanie TOP 5' (Typ #1 – #5) trafia najczęściej? ({actual_bt_steps} gier)")
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
            "Pozycja i Niebieska": f"Poz. {int(curr_row_s['pos_nr']):02d} (🟦 M.{int(curr_row_s['blue_m']):02d} — {int(curr_row_s['b_hits_cnt'])}/15)",
            "Status 'Najczęstsza'": curr_row_s["⭐ Pula 'Najczęstsza'"]
        })

    df_slot_sum = pd.DataFrame(slot_summary_rows).sort_values(
        by="raw_hits", ascending=False, kind="mergesort"
    ).drop(columns=["raw_hits"])

    st.dataframe(
        df_slot_sum,
        column_config={
            "Lokata w TOP 5": st.column_config.TextColumn("Miejsce w TOP 5", width="medium"),
            "Trafienia": st.column_config.TextColumn("Trafione", width="small"),
            "Skuteczność %": st.column_config.ProgressColumn("Skuteczność %", format="%.1f%%", min_value=0, max_value=60),
            "Aktualna Kula (Teraz w grze)": st.column_config.NumberColumn("Kula Teraz", width="small"),
            "Pozycja i Niebieska": st.column_config.TextColumn("Skąd (Poz. / 🟦)", width="medium"),
            "Status 'Najczęstsza'": st.column_config.TextColumn("Kol. 'Najczęstsza'", width="medium"),
        },
        hide_index=True,
        use_container_width=True,
        key="top5_slots_summary_tbl"
    )

    st.markdown(f"#### 📊 B. Skuteczność oryginalnych Pozycji Keno (Poz. 01 – Poz. 20), gdy wejdą do TOP 5 ({actual_bt_steps} gier)")
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

    st.markdown(f"#### 📋 C. Szczegółowa historia {actual_bt_steps} losowań (Złote Lokaty 🟦 + 5 osobnych kolumn dla TOP 5 — 🟩 = Trafienie w T+1)")
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
                        <th style="border-right:2px solid #333945; color:#00aaff;">🏆 2 Złote Lokaty 🟦<br><span style="font-size:9px; color:#8a94a6;">(Lider #1 i #2 z Tab. 🟦)</span></th>
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

# Wywołanie modułu predykcyjnego V5 (domyślnie okno 15 losowań oraz weryfikacja wsteczna na 100 losowań):
render_prediction_algorithm(df, default_window=15, default_backtest=100)
