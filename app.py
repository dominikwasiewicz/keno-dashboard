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
# MODUŁ ALGORYTMU PREDYKCYJNEGO: CZĘSTOTLIWOŚĆ + PARY + BACKTEST (30 LOS.)
# =====================================================================
def render_prediction_algorithm(df_full, window_size=20, backtest_steps=30):
    st.divider()
    st.header("🧠 Algorytm Wskazujący Następne Trafienia (Węzły T+1 + Częstotliwość + Pary)")
    st.caption(
        f"Model wieloczynnikowy (0–100 pkt): 1) Skuteczność pozycji T+1, 2) Częstotliwość losowania kuli (w oknie {window_size} i całej bazie) + "
        f"zgodność z 'Najczęstszą' na pozycji, 3) Podwójny Węzeł (🔴+⬜), 4) Gorące sąsiedztwo, 5) Siła par przechodzących wspólnie do T+1. "
        f"Weryfikacja wsteczna: **{backtest_steps} losowań**."
    )

    if len(df_full) < window_size + backtest_steps + 2:
        st.warning(f"Za mało danych w bazie ({len(df_full)}), aby wykonać test dla okna {window_size} i {backtest_steps} kroków wstecz.")
        return

    all_lists = df_full["numbers_list"].tolist()
    all_sets = df_full["numbers_set"].tolist()
    all_ids = df_full["draw_id"].tolist()
    all_times = df_full["draw_time"].tolist()
    total_draws = len(df_full)

    # 1. Globalne statystyki liczb (częstotliwość ogólna i powtórki T+1) oraz macierze par
    num_appearances = {n: 0 for n in range(1, 71)}
    num_repeats_t1 = {n: 0 for n in range(1, 71)}
    pair_appearances_global = defaultdict(int)
    pair_repeats_t1_global = defaultdict(int)

    for idx in range(total_draws - 1):
        curr_list = all_lists[idx]
        curr_s = all_sets[idx]
        next_s = all_sets[idx + 1]
        
        for num in curr_list:
            num_appearances[num] += 1
            if num in next_s:
                num_repeats_t1[num] += 1

        # Zliczanie wspólnych przejść par (dwójek) z losowania T do T+1
        surviving_nums = [n for n in curr_list if n in next_s]
        for p in combinations(curr_list, 2):
            pair_appearances_global[p] += 1
        for p_surv in combinations(surviving_nums, 2):
            pair_repeats_t1_global[p_surv] += 1

    # Dodajemy też ostatnie losowanie do ogólnej liczby wystąpień
    for num in all_lists[-1]:
        num_appearances[num] += 1

    global_repeat_rate = {
        n: (num_repeats_t1[n] / max(1, num_appearances[n] - 1)) if num_appearances[n] > 1 else 0.285
        for n in range(1, 71)
    }

    # Funkcja oceniająca 20 liczb oraz pary dla dowolnego losowania t_idx
    def score_draw_at_index(t_idx):
        win_start = t_idx - window_size + 1
        win_lists = all_lists[win_start : t_idx + 1]
        win_sets = all_sets[win_start : t_idx + 1]
        trans_count = len(win_lists) - 1

        curr_nums = all_lists[t_idx]
        prev_set = all_sets[t_idx - 1] if t_idx >= 1 else set()
        prev2_set = all_sets[t_idx - 2] if t_idx >= 2 else set()

        # Częstotliwość występowania każdej liczby w badanym oknie (np. ostatnich 20 losowań)
        win_ball_freq = defaultdict(int)
        for d_list in win_lists:
            for b in d_list:
                win_ball_freq[b] += 1
        max_win_freq = max([win_ball_freq[b] for b in curr_nums] + [1])

        # Wspólne wystąpienia i powtórki T+1 dla par w badanym oknie + w ostatnich 120 losowaniach
        local_hist_start = max(0, t_idx - 120)
        local_lists = all_lists[local_hist_start : t_idx + 1]
        local_sets = all_sets[local_hist_start : t_idx + 1]
        
        pair_win_cooc = defaultdict(int)
        pair_win_t1 = defaultdict(int)
        pair_loc_t1 = defaultdict(int)

        # W oknie głównym (np. 20 losowań)
        for k in range(len(win_lists)):
            for p in combinations(win_lists[k], 2):
                pair_win_cooc[p] += 1
            if k < trans_count:
                surv = [n for n in win_lists[k] if n in win_sets[k + 1]]
                for p_s in combinations(surv, 2):
                    pair_win_t1[p_s] += 1

        # W szerszym oknie lokalnym (ostatnie 120 losowań do momentu t_idx)
        for k in range(len(local_lists) - 1):
            surv = [n for n in local_lists[k] if n in local_sets[k + 1]]
            for p_s in combinations(surv, 2):
                pair_loc_t1[p_s] += 1

        # Ocena wszystkich 190 par z bieżącego losowania t_idx
        pairs_ranked = []
        ball_pair_bonus = defaultdict(float)

        for a, b in combinations(curr_nums, 2):
            p_key = (a, b)
            w_cooc = pair_win_cooc[p_key]
            w_t1 = pair_win_t1[p_key]
            l_t1 = pair_loc_t1[p_key]
            g_t1 = pair_repeats_t1_global[p_key]
            g_app = max(1, pair_appearances_global[p_key])
            g_rate = (g_t1 / g_app) * 100.0

            both_in_prev = (a in prev_set) and (b in prev_set)
            adj_bonus = 4.0 if abs(curr_nums.index(a) - curr_nums.index(b)) == 1 else 0.0
            prev_pair_bonus = 8.0 if both_in_prev else 0.0

            pair_score = round(
                (w_t1 * 12.0) + (w_cooc * 3.0) + (l_t1 * 2.5) + (g_rate * 0.8) + adj_bonus + prev_pair_bonus, 1
            )

            pairs_ranked.append({
                "Para": f"{a:02d} - {b:02d}",
                "b1": a,
                "b2": b,
                "PairScore": pair_score,
                "Razem w oknie": f"{w_cooc}x",
                "Przejścia T+1 (Okno)": f"{w_t1}x",
                "Przejścia T+1 (120 los.)": f"{l_t1}x",
                "Przejścia T+1 (Cała baza)": f"{g_t1}x ({g_rate:.1f}%)",
                "Status Pary": "🔴🔴 Obie z T-1" if both_in_prev else ("🔗 Sąsiednie Poz." if adj_bonus > 0 else "Standard")
            })

        df_pairs = pd.DataFrame(pairs_ranked).sort_values(
            by=["PairScore", "b1", "b2"], ascending=[False, True, True], kind="mergesort"
        ).reset_index(drop=True)

        # Bonus dla pojedynczych liczb z 10 najsilniejszych par
        for rank_i, p_row in df_pairs.head(10).iterrows():
            weight = max(1.0, 10.0 - rank_i * 0.9)
            ball_pair_bonus[int(p_row["b1"])] = max(ball_pair_bonus[int(p_row["b1"])], weight)
            ball_pair_bonus[int(p_row["b2"])] = max(ball_pair_bonus[int(p_row["b2"])], weight)

        # Białe kwadraty w ostatnich 3 przejściach (aktywność sąsiedztwa)
        recent_squares_by_pos = {p: 0 for p in range(1, 21)}
        for lookback in range(1, min(4, trans_count + 1)):
            lb_idx = t_idx - lookback
            lb_nums = all_lists[lb_idx]
            lb_next_set = all_sets[lb_idx + 1]
            for p_i in range(20):
                if lb_nums[p_i] in lb_next_set:
                    recent_squares_by_pos[p_i + 1] += 1

        candidates = []
        for p_i in range(20):
            pos_nr = p_i + 1
            ball = curr_nums[p_i]

            # 1. Skuteczność pozycji T+1 w oknie (0 - 25 pkt)
            pos_hits = sum(1 for k in range(trans_count) if win_lists[k][p_i] in win_sets[k + 1])
            pos_rate = pos_hits / trans_count if trans_count > 0 else 0
            score_pos = min(25.0, (pos_rate / 0.55) * 25.0)

            # 2. NOWOŚĆ: Najczęstsze losowanie liczby (w oknie + na konkretnej pozycji + globalnie) (0 - 25 pkt)
            ball_freq_in_win = win_ball_freq[ball]
            freq_ratio = ball_freq_in_win / max_win_freq

            # Sprawdzamy najczęstszą liczbę na tej konkretnej pozycji (kolumnie) w oknie
            pos_col_vals = [win_lists[k][p_i] for k in range(len(win_lists))]
            pos_series = pd.Series(pos_col_vals)
            mode_on_pos = int(pos_series.mode().iloc[0])
            mode_count_on_pos = int((pos_series == mode_on_pos).sum())
            is_pos_leader = (ball == mode_on_pos and mode_count_on_pos >= 2)

            score_freq = (freq_ratio * 17.0) + (8.0 if is_pos_leader else 0.0)
            score_freq = min(25.0, score_freq)

            # 3. Impuls Węzła (Czerwone Kółko 🔴 / Seria) (0 - 20 pkt)
            in_prev1 = (ball in prev_set)
            in_prev2 = (ball in prev2_set)
            if in_prev1 and in_prev2:
                score_momentum = 20.0
                streak_label = "🔥🔥 Seria 3+"
            elif in_prev1:
                score_momentum = 14.0
                streak_label = "🔴 Trafiona z T-1"
            else:
                score_momentum = 3.0
                streak_label = "Nowa"

            if is_pos_leader:
                streak_label += " | ⭐ Lider Poz."

            # 4. Gorąca strefa sąsiedztwa + historyczna powtarzalność kuli (0 - 20 pkt)
            neighbor_positions = [pos for pos in [pos_nr - 1, pos_nr, pos_nr + 1] if 1 <= pos <= 20]
            recent_cluster_hits = sum(recent_squares_by_pos[np] for np in neighbor_positions)
            score_cluster = min(10.0, recent_cluster_hits * 2.5)

            ball_rep_rate = global_repeat_rate.get(ball, 0.285)
            score_ball_hist = min(10.0, max(0.0, ((ball_rep_rate - 0.20) / 0.18) * 10.0))

            # 5. Bonus z Algorytmu Par (0 - 10 pkt)
            score_pair = ball_pair_bonus.get(ball, 0.0)

            total_score = round(score_pos + score_freq + score_momentum + score_cluster + score_ball_hist + score_pair, 1)

            candidates.append({
                "pos_nr": pos_nr,
                "Pozycja": f"Poz. {pos_nr:02d}",
                "Liczba": ball,
                "Score": total_score,
                "Częstotliwość (Okno)": f"{ball_freq_in_win}x / {window_size}",
                "Najczęstsza na Poz.": f"{mode_on_pos:02d} (x{mode_count_on_pos})",
                "Status Węzła": streak_label,
                "Trafienia Poz. T+1": f"{pos_hits}/{trans_count} ({pos_rate*100:.1f}%)",
                "Bonus z Par": f"+{score_pair:.1f} pkt",
                "Częstotliwość (Baza)": f"{num_appearances[ball]}x ({ball_rep_rate*100:.1f}% powt.)"
            })

        df_cand = pd.DataFrame(candidates).sort_values(
            by=["Score", "pos_nr"], ascending=[False, True], kind="mergesort"
        ).reset_index(drop=True)

        return df_cand, df_pairs

    # --- WYLICZENIE DLA NAJNOWSZEGO LOSOWANIA (NA ŻYWO) ---
    latest_idx = total_draws - 1
    df_predictions, df_top_pairs = score_draw_at_index(latest_idx)

    top_5_Row = df_predictions.head(5)
    top_8_Row = df_predictions.head(8)
    best_3_pairs = df_top_pairs.head(3)

    top5_balls_str = ", ".join(f"**{int(r['Liczba']):02d}** *(Poz. {int(r['pos_nr']):02d} | {r['Częstotliwość (Okno)']})*" for _, r in top_5_Row.iterrows())
    top8_balls_only = ", ".join(f"{int(r['Liczba']):02d}" for _, r in top_8_Row.iterrows())
    top_pairs_str = "  |  ".join(f"**[{r['Para']}]** *(w oknie: {r['Razem w oknie']}, T+1: {r['Przejścia T+1 (Okno)']})*" for _, r in best_3_pairs.iterrows())

    st.success(
        f"🎯 **WSKAZANIE ALGORYTMU NA NASTĘPNE LOSOWANIE (po #{all_ids[latest_idx]} z godz. {all_times[latest_idx]}):**\n\n"
        f"🔥 **TOP 5 Najmocniejszych Liczb (Węzły + Częstotliwość):** {top5_balls_str}\n\n"
        f"🔗 **TOP 3 Najsilniejsze Pary (Dwójki przechodzące do T+1):** {top_pairs_str}\n\n"
        f"📌 **Szerszy koszyk TOP 8 liczb:** `{top8_balls_only}`"
    )

    col_pred_table, col_pairs_table = st.columns([1.35, 1.05], gap="large")

    with col_pred_table:
        st.subheader(f"📊 Ranking 20 liczb z losowania #{all_ids[latest_idx]} (z Częstotliwością)")
        df_display_pred = df_predictions.drop(columns=["pos_nr"]).copy()
        st.dataframe(
            df_display_pred,
            column_config={
                "Pozycja": st.column_config.TextColumn("Pozycja", width="small"),
                "Liczba": st.column_config.NumberColumn("Kula", width="small"),
                "Score": st.column_config.ProgressColumn("Siła (Score)", format="%.1f pkt", min_value=0, max_value=100),
                "Częstotliwość (Okno)": st.column_config.TextColumn("Częstość (Okno)", width="small"),
                "Najczęstsza na Poz.": st.column_config.TextColumn("Lider Pozycji", width="small"),
                "Status Węzła": st.column_config.TextColumn("Status Węzła", width="medium"),
                "Trafienia Poz. T+1": st.column_config.TextColumn("Poz. T+1", width="small"),
                "Bonus z Par": st.column_config.TextColumn("Siła Par", width="small"),
                "Częstotliwość (Baza)": st.column_config.TextColumn("Ogółem w bazie", width="medium"),
            },
            hide_index=True,
            use_container_width=True,
            height=560,
            key="pred_main_ranking_tbl"
        )

    with col_pairs_table:
        st.subheader(f"🔗 Filtrowanie Par: TOP 15 Dwójek z losowania #{all_ids[latest_idx]}")
        st.caption("Pary spośród aktualnych 20 liczb, które najczęściej chodzą razem i wspólnie przechodzą do następnego losowania (T+1).")
        df_display_pairs = df_top_pairs.head(15).drop(columns=["b1", "b2"]).copy()
        st.dataframe(
            df_display_pairs,
            column_config={
                "Para": st.column_config.TextColumn("Para (Dwójka)", width="small"),
                "PairScore": st.column_config.ProgressColumn("Siła Pary", format="%.1f pkt", min_value=0, max_value=100),
                "Razem w oknie": st.column_config.TextColumn("Razem (Okno)", width="small"),
                "Przejścia T+1 (Okno)": st.column_config.TextColumn("T+1 (Okno)", width="small"),
                "Przejścia T+1 (120 los.)": st.column_config.TextColumn("T+1 (120 los.)", width="small"),
                "Przejścia T+1 (Cała baza)": st.column_config.TextColumn("T+1 (Baza)", width="medium"),
                "Status Pary": st.column_config.TextColumn("Status", width="small"),
            },
            hide_index=True,
            use_container_width=True,
            height=560,
            key="pred_pairs_ranking_tbl"
        )

    # --- BACKTEST NA 30 LOSOWANIACH WSTECZ ---
    st.divider()
    st.subheader(f"🧪 Weryfikacja wsteczna algorytmu (ostatnie {backtest_steps} losowań)")
    st.caption(
        f"Sprawdzenie krok po kroku na dystansie **{backtest_steps} losowań**, jak trafiały wytypowane przez algorytm koszyki "
        f"**TOP 5**, **TOP 8** oraz wskazana **Para Nr 1**."
    )

    bt_rows = []
    total_top5_hits = 0
    total_top8_hits = 0
    pair_at_least_one_hits = 0
    pair_full_2of2_hits = 0

    for step_t in range(latest_idx - 1, latest_idx - 1 - backtest_steps, -1):
        df_step_pred, df_step_pairs = score_draw_at_index(step_t)
        next_actual_set = all_sets[step_t + 1]

        top5_nums = df_step_pred.head(5)["Liczba"].tolist()
        top8_nums = df_step_pred.head(8)["Liczba"].tolist()

        hits_5 = [n for n in top5_nums if n in next_actual_set]
        hits_8 = [n for n in top8_nums if n in next_actual_set]

        total_top5_hits += len(hits_5)
        total_top8_hits += len(hits_8)

        # Sprawdzenie najlepszej pary (TOP 1 para) z danego kroku
        top1_pair_row = df_step_pairs.iloc[0]
        p_b1, p_b2 = int(top1_pair_row["b1"]), int(top1_pair_row["b2"])
        p_hits = (1 if p_b1 in next_actual_set else 0) + (1 if p_b2 in next_actual_set else 0)
        if p_hits >= 1:
            pair_at_least_one_hits += 1
        if p_hits == 2:
            pair_full_2of2_hits += 1

        formatted_top5 = " ".join(
            f"[{n:02d}]🟩" if n in next_actual_set else f"{n:02d}"
            for n in top5_nums
        )
        formatted_pair = (
            f"[{p_b1:02d}]🟩 - [{p_b2:02d}]🟩 (2/2!)" if p_hits == 2 else
            (f"[{p_b1:02d}]🟩 - {p_b2:02d} (1/2)" if p_b1 in next_actual_set else
             (f"{p_b1:02d} - [{p_b2:02d}]🟩 (1/2)" if p_b2 in next_actual_set else f"{p_b1:02d} - {p_b2:02d} (0/2)"))
        )

        bt_rows.append({
            "Z losowania": f"#{all_ids[step_t]} ({all_times[step_t]})",
            "Do losowania (T+1)": f"#{all_ids[step_t + 1]}",
            "Wytypowane TOP 5 (🟩=Trafione)": formatted_top5,
            "Trafienia TOP 5": f"{len(hits_5)} / 5",
            "Trafienia TOP 8": f"{len(hits_8)} / 8",
            "Najmocniejsza Para (TOP 1)": formatted_pair
        })

    avg_top5 = (total_top5_hits / (backtest_steps * 5)) * 100
    avg_top8 = (total_top8_hits / (backtest_steps * 8)) * 100
    pair_1plus_pct = (pair_at_least_one_hits / backtest_steps) * 100

    st.info(
        f"📈 **Podsumowanie z {backtest_steps} losowań wstecz:**\n"
        f"- **TOP 5 liczb:** łącznie **{total_top5_hits} trafień** na {backtest_steps*5} typów (**{avg_top5:.1f}%** skuteczności)\n"
        f"- **TOP 8 liczb:** łącznie **{total_top8_hits} trafień** na {backtest_steps*8} typów (**{avg_top8:.1f}%** skuteczności)\n"
        f"- **Para Nr 1:** w **{pair_at_least_one_hits}/{backtest_steps}** losowań ({pair_1plus_pct:.1f}%) weszła przynajmniej 1 liczba z pary, "
        f"a pełna dwójka (2/2) powtórzyła się **{pair_full_2of2_hits}x** *(losowe tło Keno to 28.6% dla pojedynczej kuli i ~8.0% dla pełnej dwójki)*."
    )

    st.dataframe(
        pd.DataFrame(bt_rows),
        hide_index=True,
        use_container_width=True,
        height=620,
        key="pred_backtest_30_tbl"
    )

# Wywołanie modułu predykcyjnego na dole strony (domyślnie okno 20 i backtest na 30 losowań):
render_prediction_algorithm(df, window_size=20, backtest_steps=30)










# =====================================================================
# MODUŁ ALGORYTMU PREDEKCYJNEGO: WSKAZANIE NASTĘPNYCH TRAFIEŃ (T+1)
# =====================================================================
def render_prediction_algorithm(df_full, window_size=20, backtest_steps=15):
    st.divider()
    st.header("🧠 Algorytm Wskazujący Następne Trafienia (Analiza Węzłów T+1)")
    st.caption(
        "Algorytm analizuje ostatnie losowanie i oblicza indeks siły (Score) dla każdej z 20 pozycji, "
        "łącząc skuteczność kolumny, zjawisko 'Podwójnego Węzła' (🔴+⬜), aktywność sąsiednich pozycji oraz historyczną parzystość powtórek."
    )

    if len(df_full) < window_size + backtest_steps + 2:
        st.warning("Za mało danych w bazie do uruchomienia pełnego modelu predykcyjnego.")
        return

    all_lists = df_full["numbers_list"].tolist()
    all_sets = df_full["numbers_set"].tolist()
    all_ids = df_full["draw_id"].tolist()
    all_times = df_full["draw_time"].tolist()
    total_draws = len(df_full)

    # 1. Obliczenie globalnej skłonności każdej z 70 liczb do powtarzania się w T+1 (na bazie całej historii)
    num_appearances = {n: 0 for n in range(1, 71)}
    num_repeats_t1 = {n: 0 for n in range(1, 71)}
    for idx in range(total_draws - 1):
        curr_s = all_sets[idx]
        next_s = all_sets[idx + 1]
        for num in curr_s:
            num_appearances[num] += 1
            if num in next_s:
                num_repeats_t1[num] += 1

    global_repeat_rate = {
        n: (num_repeats_t1[n] / num_appearances[n]) if num_appearances[n] > 0 else 0.285
        for n in range(1, 71)
    }

    # Funkcja wyliczająca punkty (Score) dla dowolnego losowania t_idx (używana do typowania na żywo oraz do Backtestu)
    def score_draw_at_index(t_idx):
        win_start = t_idx - window_size + 1
        win_lists = all_lists[win_start : t_idx + 1]
        win_sets = all_sets[win_start : t_idx + 1]
        trans_count = len(win_lists) - 1  # liczba przejść T -> T+1 w oknie

        curr_nums = all_lists[t_idx]
        prev_set = all_sets[t_idx - 1] if t_idx >= 1 else set()
        prev2_set = all_sets[t_idx - 2] if t_idx >= 2 else set()

        # Obliczamy, gdzie były białe kwadraty w ostatnich 3 znanych przejściach (t_idx-3 -> t_idx-2 -> t_idx-1 -> t_idx)
        recent_squares_by_pos = {p: 0 for p in range(1, 21)}
        for lookback in range(1, min(4, trans_count + 1)):
            lb_idx = t_idx - lookback
            lb_nums = all_lists[lb_idx]
            lb_next_set = all_sets[lb_idx + 1]
            for p_i in range(20):
                if lb_nums[p_i] in lb_next_set:
                    recent_squares_by_pos[p_i + 1] += 1

        candidates = []
        for p_i in range(20):
            pos_nr = p_i + 1
            ball = curr_nums[p_i]

            # Kryterium 1: Skuteczność pozycji w oknie (0 - 35 pkt)
            pos_hits = sum(1 for k in range(trans_count) if win_lists[k][p_i] in win_sets[k + 1])
            pos_rate = pos_hits / trans_count if trans_count > 0 else 0
            score_pos = min(35.0, (pos_rate / 0.55) * 35.0)

            # Kryterium 2: Zjawisko "Podwójnego Węzła" - czy liczba ma czerwone kółko 🔴 (0 - 25 pkt)
            in_prev1 = (ball in prev_set)
            in_prev2 = (ball in prev2_set)
            if in_prev1 and in_prev2:
                score_momentum = 25.0  # Silna seria (minimum 3 losowania z rzędu, jak 26 lub 27)
                streak_label = "🔥🔥 Seria 3+"
            elif in_prev1:
                score_momentum = 18.0  # Właśnie powtórzyła się z T-1 (ma czerwone kółko)
                streak_label = "🔴 Trafiona z T-1"
            else:
                score_momentum = 4.0
                streak_label = "Nowa"

            # Kryterium 3: Aktywność sąsiednich kolumn (p-1, p, p+1) w ostatnich 3 losowaniach (0 - 20 pkt)
            neighbor_positions = [pos for pos in [pos_nr - 1, pos_nr, pos_nr + 1] if 1 <= pos <= 20]
            recent_cluster_hits = sum(recent_squares_by_pos[np] for np in neighbor_positions)
            score_cluster = min(20.0, recent_cluster_hits * 4.5)

            # Kryterium 4: Historyczna skłonność tej konkretnej kuli do powtórek T+1 (0 - 20 pkt)
            ball_rep_rate = global_repeat_rate.get(ball, 0.285)
            score_ball_hist = min(20.0, max(0.0, ((ball_rep_rate - 0.20) / 0.18) * 20.0))

            total_score = round(score_pos + score_momentum + score_cluster + score_ball_hist, 1)

            candidates.append({
                "pos_nr": pos_nr,
                "Pozycja": f"Poz. {pos_nr:02d}",
                "Liczba": ball,
                "Score": total_score,
                "Status Węzła": streak_label,
                "Trafienia Poz. (Okno)": f"{pos_hits}/{trans_count} ({pos_rate*100:.1f}%)",
                "Klaster (3 los.)": f"{recent_cluster_hits} ⬜ w sąsiedztwie",
                "Hist. powtórek liczby": f"{ball_rep_rate*100:.1f}%"
            })

        # Sortujemy od najwyższego wyniku Score
        df_cand = pd.DataFrame(candidates).sort_values(
            by=["Score", "pos_nr"], ascending=[False, True], kind="mergesort"
        ).reset_index(drop=True)
        return df_cand

    # --- WYLICZENIE DLA NAJNOWSZEGO LOSOWANIA (NA ŻYWO DO NASTĘPNEJ GRY) ---
    latest_idx = total_draws - 1
    df_predictions = score_draw_at_index(latest_idx)

    top_5_Row = df_predictions.head(5)
    top_8_Row = df_predictions.head(8)

    top5_balls_str = ", ".join(f"**{int(r['Liczba']):02d}** *(Poz. {int(r['pos_nr']):02d})*" for _, r in top_5_Row.iterrows())
    top8_balls_only = ", ".join(f"{int(r['Liczba']):02d}" for _, r in top_8_Row.iterrows())

    # Wyświetlenie głównego boksu rekomendacji
    st.success(
        f"🎯 **WSKAZANIE ALGORYTMU NA NASTĘPNE LOSOWANIE (po #{all_ids[latest_idx]} z godz. {all_times[latest_idx]}):**\n\n"
        f"🔥 **TOP 5 Najmocniejszych Węzłów:** {top5_balls_str}\n\n"
        f"📌 **Szerszy koszyk TOP 8 liczb:** `{top8_balls_only}`"
    )

    col_pred_table, col_backtest = st.columns([1.3, 1.2], gap="large")

    with col_pred_table:
        st.subheader(f"📊 Ranking wszystkich 20 liczb z losowania #{all_ids[latest_idx]}")
        df_display_pred = df_predictions.drop(columns=["pos_nr"]).copy()
        st.dataframe(
            df_display_pred,
            column_config={
                "Pozycja": st.column_config.TextColumn("Pozycja", width="small"),
                "Liczba": st.column_config.NumberColumn("Kula (Typ)", width="small"),
                "Score": st.column_config.ProgressColumn("Siła (Score)", format="%.1f pkt", min_value=0, max_value=100),
                "Status Węzła": st.column_config.TextColumn("Status (🔴/⬜)", width="small"),
                "Trafienia Poz. (Okno)": st.column_config.TextColumn("Skuteczność Poz.", width="small"),
                "Klaster (3 los.)": st.column_config.TextColumn("Sąsiedztwo", width="small"),
                "Hist. powtórek liczby": st.column_config.TextColumn("Powtórki Kuli", width="small"),
            },
            hide_index=True,
            use_container_width=True,
            height=560
        )

    # --- BACKTEST: SPRAWDZENIE SKUTECZNOŚCI ALGORYTMU NA OSTATNICH N LOSOWANIACH ---
    with col_backtest:
        st.subheader(f"🧪 Weryfikacja wsteczna algorytmu (ostatnie {backtest_steps} losowań)")
        st.caption("Tabela pokazuje, które liczby algorytm wskazałby jako TOP 5 oraz TOP 8 w poprzednich losowaniach i ile z nich faktycznie trafiło (🟩).")

        bt_rows = []





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
