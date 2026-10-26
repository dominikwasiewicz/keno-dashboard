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

# Wybór okna analizy
base_ranges = [10, 15, 20, 25, 35, 50, 50, 500]
available_options = [opt for opt in base_ranges if opt <= len(df)]
if not available_options:
    available_options = [len(df)]

default_index = available_options.index(20) if 20 in available_options else 0

selected_window = st.radio(
    "Wybierz zakres analizy losowań:",
    options=available_options,
    index=default_index,
    horizontal=True
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
    st.subheader(f"📊 Analiza pozycji (Trafienia T+1)")
    
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
            "Pozycja": f"Poz. {i:02d}",
            "raw_hits": repeat_t1_count,  # Czysta liczba do bezbłędnego sortowania matematycznego
            "Trafienia T+1": f"{repeat_t1_count} ({repeat_pct:.1f}%)",
            "Ostatnia": last_draw[pos_col],
            "Najczęstsza": f"{mode_val} (x{most_common_cnt})",
            "Średnia": round(series.mean(), 1)
        })
        
    # 1. Zawsze sortujemy matematycznie malejąco (największe na górze: 11, 10, 8, 7...)
    df_pos_stats = pd.DataFrame(pos_stats).sort_values(by="raw_hits", ascending=False).drop(columns=["raw_hits"])
    
    # 2. Wyświetlamy tabelę z wąskimi kolumnami i stałym porządkiem
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
    "Dla każdego losowania skrypt bierze posortowaną kolumnę 'Ostatnia' z tabeli 'Pozycje analityczne (Trafienia T+1)' "
    "i układa liczby na pozycjach 1–20 (1. wiersz = Poz. 1, 2. wiersz = Poz. 2 itd.). "
    "Niebieski kwadrat 🟦 oznacza trafienie w następnym losowaniu."
)

col_tk1, col_tk2 = st.columns([1, 1])

with col_tk1:
    rolling_window = st.radio(
        "Wybierz zakres okna dla 'Pozycje analityczne (Trafienia T+1)':",
        options=[20, 25, 50, 100],
        horizontal=True,
        key="rolling_win_selector"
    )

with col_tk2:
    max_available_test = max(10, len(df) - rolling_window)
    test_steps = st.number_input(
        "Ile losowań (wierszy) sprawdzić i wyświetlić w tabeli:",
        min_value=10,
        max_value=max_available_test,
        value=min(20, max_available_test),
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
        # Wycinamy DOKŁADNIE takie samo okno jak df_window = df.tail(selected_window)
        # Okno kończy się na indeksie t (włącznie) i ma długość rolling_window:
        win_start = t - rolling_window + 1
        win_end = t + 1  # zakres [win_start : t+1] ma dokładnie 'rolling_window' wierszy
        
        win_sets = all_sets[win_start:win_end]
        win_lists = all_lists[win_start:win_end]
        total_trans = len(win_sets) - 1  # dokładnie (rolling_window - 1) przejść
        
        nums_t = all_lists[t]
        
        # Liczymy identycznie jak w górnej tabeli "Pozycje analityczne (Trafienia T+1)"
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
            
        # Używamy DOKŁADNIE tego samego sortowania DataFrame.sort_values(by="raw_hits", ascending=False),
        # aby kolejność przy remisach była w 100% identyczna z górną tabelą!
        df_rank_step = pd.DataFrame(pos_temp).sort_values(by="raw_hits", ascending=False)
        pos_ranking_sorted = df_rank_step.to_dict("records")
        
        is_latest_unverified = (t == total_df_rows - 1)
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
            "Kolumny **1–20** to kolejne liczby z kolumny **'Ostatnia'** tabeli *Pozycje analityczne (Trafienia T+1)* "
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
            by="raw_blue", ascending=False
        ).drop(columns=["raw_blue"])
        
        st.dataframe(
            df_roll_pos,
            column_config={
                "Pozycja w tabeli": st.column_config.TextColumn("Pozycja (1-20)", width="small"),
                "🟦 Trafienia": st.column_config.TextColumn("🟦 Niebieskie kwadraty", width="medium"),
                "Teraz w grze": st.column_config.NumberColumn("Ostatnia (Teraz)", width="small"),
                "Z pozycji": st.column_config.TextColumn("Skąd (Oryg.)", width="small"),
            },
            hide_index=True,
            use_container_width=True,
            height=640
        )







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

# Wybór okna analizy (domyślnie ustawione na 25)
base_ranges = [10, 15, 20, 25, 35, 50, 300, 500]
available_options = [opt for opt in base_ranges if opt <= len(df)]
if not available_options:
    available_options = [len(df)]

default_index = available_options.index(25) if 25 in available_options else 0

selected_window = st.radio(
    "Wybierz zakres analizy losowań:",
    options=available_options,
    index=default_index,
    horizontal=True
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
    st.subheader(f"📊 Analiza pozycji (Trafienia T+1)")
    
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
            "Pozycja": f"Poz. {i:02d}",
            "raw_hits": repeat_t1_count,  # Czysta liczba do bezbłędnego sortowania matematycznego
            "Trafienia T+1": f"{repeat_t1_count} ({repeat_pct:.1f}%)",
            "Ostatnia": last_draw[pos_col],
            "Najczęstsza": f"{mode_val} (x{most_common_cnt})",
            "Średnia": round(series.mean(), 1)
        })
        
    # 1. Zawsze sortujemy matematycznie malejąco (największe na górze: 11, 10, 8, 7...)
    df_pos_stats = pd.DataFrame(pos_stats).sort_values(by="raw_hits", ascending=False).drop(columns=["raw_hits"])
    
    # 2. Wyświetlamy tabelę z wąskimi kolumnami i stałym porządkiem
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
    "Dla każdego losowania skrypt bierze posortowaną kolumnę 'Ostatnia' z tabeli 'Pozycje analityczne (Trafienia T+1)' "
    "i układa liczby na pozycjach 1–20 (1. wiersz = Poz. 1, 2. wiersz = Poz. 2 itd.). "
    "Niebieski kwadrat 🟦 oznacza trafienie w następnym losowaniu."
)

col_tk1, col_tk2 = st.columns([1, 1])

with col_tk1:
    rolling_window = st.radio(
        "Wybierz zakres okna dla 'Pozycje analityczne (Trafienia T+1)':",
        options=[20, 25, 50, 100],
        index=1,  # Domyślnie 25
        horizontal=True,
        key="rolling_win_selector_v2"  # <-- ZMIENIONE
    )

with col_tk2:
    max_available_test = max(10, len(df) - rolling_window)
    test_steps = st.number_input(
        "Ile losowań (wierszy) sprawdzić i wyświetlić w tabeli:",
        min_value=10,
        max_value=max_available_test,
        value=min(25, max_available_test),  # Domyślnie 25
        step=5,
        key="rolling_test_steps_v2"  # <-- ZMIENIONE
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
        # Wycinamy DOKŁADNIE takie samo okno jak df_window = df.tail(selected_window)
        # Okno kończy się na indeksie t (włącznie) i ma długość rolling_window:
        win_start = t - rolling_window + 1
        win_end = t + 1  # zakres [win_start : t+1] ma dokładnie 'rolling_window' wierszy
        
        win_sets = all_sets[win_start:win_end]
        win_lists = all_lists[win_start:win_end]
        total_trans = len(win_sets) - 1  # dokładnie (rolling_window - 1) przejść
        
        nums_t = all_lists[t]
        
        # Liczymy identycznie jak w górnej tabeli "Pozycje analityczne (Trafienia T+1)"
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
            
        # Używamy DOKŁADNIE tego samego sortowania DataFrame.sort_values(by="raw_hits", ascending=False),
        # aby kolejność przy remisach była w 100% identyczna z górną tabelą!
        df_rank_step = pd.DataFrame(pos_temp).sort_values(by="raw_hits", ascending=False)
        pos_ranking_sorted = df_rank_step.to_dict("records")
        
        is_latest_unverified = (t == total_df_rows - 1)
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
            "Kolumny **1–20** to kolejne liczby z kolumny **'Ostatnia'** tabeli *Pozycje analityczne (Trafienia T+1)* "
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
            by="raw_blue", ascending=False
        ).drop(columns=["raw_blue"])
        
        st.dataframe(
            df_roll_pos,
            column_config={
                "Pozycja w tabeli": st.column_config.TextColumn("Pozycja (1-20)", width="small"),
                "🟦 Trafienia": st.column_config.TextColumn("🟦 Niebieskie kwadraty", width="medium"),
                "Teraz w grze": st.column_config.NumberColumn("Ostatnia (Teraz)", width="small"),
                "Z pozycji": st.column_config.TextColumn("Skąd (Oryg.)", width="small"),
            },
            hide_index=True,
            use_container_width=True,
            height=640
        )





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

# Wybór okna analizy
base_ranges = [10, 15, 20, 25, 35, 50, 50, 500]
available_options = [opt for opt in base_ranges if opt <= len(df)]
if not available_options:
    available_options = [len(df)]

default_index = available_options.index(35) if 20 in available_options else 0

selected_window = st.radio(
    "Wybierz zakres analizy losowań:",
    options=available_options,
    index=default_index,
    horizontal=True
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
    st.subheader(f"📊 Analiza pozycji (Trafienia T+1)")
    
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
            "Pozycja": f"Poz. {i:02d}",
            "raw_hits": repeat_t1_count,  # Czysta liczba do bezbłędnego sortowania matematycznego
            "Trafienia T+1": f"{repeat_t1_count} ({repeat_pct:.1f}%)",
            "Ostatnia": last_draw[pos_col],
            "Najczęstsza": f"{mode_val} (x{most_common_cnt})",
            "Średnia": round(series.mean(), 1)
        })
        
    # 1. Zawsze sortujemy matematycznie malejąco (największe na górze: 11, 10, 8, 7...)
    df_pos_stats = pd.DataFrame(pos_stats).sort_values(by="raw_hits", ascending=False).drop(columns=["raw_hits"])
    
    # 2. Wyświetlamy tabelę z wąskimi kolumnami i stałym porządkiem
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
    "Dla każdego losowania skrypt bierze posortowaną kolumnę 'Ostatnia' z tabeli 'Pozycje analityczne (Trafienia T+1)' "
    "i układa liczby na pozycjach 1–20 (1. wiersz = Poz. 1, 2. wiersz = Poz. 2 itd.). "
    "Niebieski kwadrat 🟦 oznacza trafienie w następnym losowaniu."
)

col_tk1, col_tk2 = st.columns([1, 1])

with col_tk1:
    rolling_window = st.radio(
        "Wybierz zakres okna dla 'Pozycje analityczne (Trafienia T+1)':",
        options=[20, 25, 50, 100],
        horizontal=True,
        key="rolling_win_selector"
    )

with col_tk2:
    max_available_test = max(10, len(df) - rolling_window)
    test_steps = st.number_input(
        "Ile losowań (wierszy) sprawdzić i wyświetlić w tabeli:",
        min_value=10,
        max_value=max_available_test,
        value=min(20, max_available_test),
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
        # Wycinamy DOKŁADNIE takie samo okno jak df_window = df.tail(selected_window)
        # Okno kończy się na indeksie t (włącznie) i ma długość rolling_window:
        win_start = t - rolling_window + 1
        win_end = t + 1  # zakres [win_start : t+1] ma dokładnie 'rolling_window' wierszy
        
        win_sets = all_sets[win_start:win_end]
        win_lists = all_lists[win_start:win_end]
        total_trans = len(win_sets) - 1  # dokładnie (rolling_window - 1) przejść
        
        nums_t = all_lists[t]
        
        # Liczymy identycznie jak w górnej tabeli "Pozycje analityczne (Trafienia T+1)"
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
            
        # Używamy DOKŁADNIE tego samego sortowania DataFrame.sort_values(by="raw_hits", ascending=False),
        # aby kolejność przy remisach była w 100% identyczna z górną tabelą!
        df_rank_step = pd.DataFrame(pos_temp).sort_values(by="raw_hits", ascending=False)
        pos_ranking_sorted = df_rank_step.to_dict("records")
        
        is_latest_unverified = (t == total_df_rows - 1)
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
            "Kolumny **1–20** to kolejne liczby z kolumny **'Ostatnia'** tabeli *Pozycje analityczne (Trafienia T+1)* "
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
            by="raw_blue", ascending=False
        ).drop(columns=["raw_blue"])
        
        st.dataframe(
            df_roll_pos,
            column_config={
                "Pozycja w tabeli": st.column_config.TextColumn("Pozycja (1-20)", width="small"),
                "🟦 Trafienia": st.column_config.TextColumn("🟦 Niebieskie kwadraty", width="medium"),
                "Teraz w grze": st.column_config.NumberColumn("Ostatnia (Teraz)", width="small"),
                "Z pozycji": st.column_config.TextColumn("Skąd (Oryg.)", width="small"),
            },
            hide_index=True,
            use_container_width=True,
            height=640
        )





from collections import defaultdict
from itertools import combinations

st.divider()
st.subheader("🔬 Weryfikacja powtórzeń dla 2 i 3 pozycji")

# 1. Wybór ilości analizowanych losowań
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

# 2. Przycięcie danych do wybranej liczby ostatnich losowań
available_total = len(df)
effective_limit = min(chosen_limit, available_total)
target_data = df.tail(effective_limit).reset_index(drop=True)
total_rows = len(target_data)

# 3. Wybór zestawu (2 lub 3) i pasek informacyjny
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

# 4. Przeliczanie pozycji dla Tabeli 1
combo_appearances = defaultdict(list)

for idx in range(total_rows - 1):
    curr_nums = target_data.iloc[idx]["numbers_list"]
    next_set = target_data.iloc[idx + 1]["numbers_set"]
    
    hits = [i + 1 for i, n in enumerate(curr_nums) if n in next_set]
    
    if len(hits) >= k_target:
        for combo in combinations(hits, k_target):
            combo_appearances[combo].append(idx)

# 5. Generowanie statystyk odstępów dla Tabeli 1
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
    default=["Poz. 02", "Poz. 09"],
    max_selections=3,
    help="Możesz wybrać 2 pozycje (np. 2 i 9) albo dobrać trzecią pozycję.",
    key="pos_multiselect_checker"
)

if len(selected_pos_labels) < 2:
    st.info("Wybierz co najmniej 2 pozycje, aby rozpocząć analizę.")
else:
    # Zamiana etykiet 'Poz. 09' na indeksy 1-based (np. 9)
    selected_indices = [int(p.replace("Poz. ", "")) for p in selected_pos_labels]
    
    occurrences = []
    
    # Korzystamy z tego samego target_data (zgodnego z wybranym wyżej zakresem 300/500/1000)
    for idx in range(total_rows - 1):
        curr_row = target_data.iloc[idx]
        next_set = target_data.iloc[idx + 1]["numbers_set"]
        nums = curr_row["numbers_list"]
        
        # Sprawdzamy czy WSZYSTKIE wybrane pozycje dały biały kwadrat w T+1
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
            
    # Obliczanie osi czasu i odstępów
    timeline = []
    gaps_draws = []
    
    for i in range(len(occurrences)):
        curr = occurrences[i]
        if i > 0:
            prev = occurrences[i - 1]
            gap_draws = curr["idx"] - prev["idx"]
            gaps_draws.append(gap_draws)
            gap_days = round(gap_draws / 260.0, 2)  # 260 losowań Keno na dobę
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
    
    # Obliczanie aktualnego oczekiwania od ostatniego trafienia
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
    
    # Kafelki z metrykami (5 kolumn)
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
        # Odwracamy kolejność tabeli, aby na samej górze widzieć najświeższe trafienia
        st.dataframe(df_timeline.iloc[::-1].reset_index(drop=True), use_container_width=True, hide_index=True)
    else:
        st.warning(f"Zestaw {k_name} nie trafił wspólnie ani razu w wybranym zakresie losowań.")

