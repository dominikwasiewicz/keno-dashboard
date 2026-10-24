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
    default=["Poz. 09", "Poz. 17"],
    max_selections=3,
    help="Możesz wybrać 2 pozycje (np. 9 i 17) albo dobrać trzecią pozycję.",
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

