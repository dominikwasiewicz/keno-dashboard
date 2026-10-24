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
base_ranges = [5, 7, 12, 15, 20, 25, 50, 500]
available_options = [opt for opt in base_ranges if opt <= len(df)]
if not available_options:
    available_options = [len(df)]

default_index = available_options.index(15) if 20 in available_options else 0

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








