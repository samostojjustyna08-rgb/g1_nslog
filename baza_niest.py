import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
import altair as alt

# Konfiguracja strony
st.set_page_config(page_title="Baza Danych Produktów", layout="wide")

# Inicjalizacja połączenia z Supabase
conn = st.connection("supabase", type=SupabaseConnection)

# Funkcja pomocnicza do mapowania kolorów kategorii
def get_category_color(cat_name):
    colors = {
        "mleko": "#1E90FF",      # Niebieski
        "elektronika": "#2E8B57", # Zielony
        "owoce": "#FF4500",      # Pomarańczowy/Czerwony
        "warzywa": "#32CD32",    # Limonkowy
        "nabiał": "#F0E68C"       # Żółty/Khaki
    }
    # Zwróć kolor z mapy lub szary dla nieznanych
    return colors.get(cat_name.lower(), "#808080")

st.title("📊 Baza Danych Produktów")

tabs = st.tabs(["📈 Statystyki i Wykresy", "📦 Produkty", "📁 Kategorie"])

# Pobranie danych do cache'owania w ramach sesji (ułatwia rysowanie wykresów)
prod_query = conn.table("produkty").select("*, kategorie(nazwa)").execute()
kat_query = conn.table("kategorie").select("*").execute()

df_prod = pd.DataFrame(prod_query.data) if prod_query.data else pd.DataFrame()
df_kat = pd.DataFrame(kat_query.data) if kat_query.data else pd.DataFrame()

# Przetworzenie danych dla czytelności (rozbicie zagnieżdżonego słownika kategorii)
if not df_prod.empty:
    df_prod['kategoria_nazwa'] = df_prod['kategorie'].apply(lambda x: x['nazwa'] if x else "Brak")
    df_prod['kolor'] = df_prod['kategoria_nazwa'].apply(get_category_color)

# --- TAB: STATYSTYKI ---
with tabs[0]:
    st.header("Stan magazynowy produktów")
    if not df_prod.empty:
        # Tworzenie wykresu Altair
        chart = alt.Chart(df_prod).mark_bar().encode(
            x=alt.X('nazwa:N', sort='-y', title='Produkt'),
            y=alt.Y('liczba:Q', title='Ilość sztuk'),
            color=alt.Color('kategoria_nazwa:N', 
                            scale=alt.Scale(domain=list(df_prod['kategoria_nazwa'].unique()),
                                          range=[get_category_color(c) for c in df_prod['kategoria_nazwa'].unique()]),
                            title='Kategoria'),
            tooltip=['nazwa', 'liczba', 'kategoria_nazwa', 'cena']
        ).properties(height=400).interactive()
        
        st.altair_chart(chart, use_container_width=True)
        
        # Kluczowe wskaźniki (Metrics)
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Suma produktów", int(df_prod['liczba'].sum()))
        col_m2.metric("Liczba asortymentu", len(df_prod))
        col_m3.metric("Najdroższy produkt", f"{df_prod['cena'].max()} zł")
    else:
        st.info("Dodaj produkty, aby zobaczyć wykresy.")

# --- TAB: PRODUKTY ---
with tabs[1]:
    st.header("Lista i Dodawanie Produktów")
    
    with st.expander("➕ Dodaj nowy produkt"):
        if df_kat.empty:
            st.warning("Najpierw dodaj kategorię!")
        else:
            with st.form("add_product"):
                n = st.text_input("Nazwa")
                l = st.number_input("Ilość", min_value=0)
                c = st.number_input("Cena", min_value=0.0)
                k = st.selectbox("Kategoria", options=df_kat['nazwa'].tolist())
                
                if st.form_submit_button("Zapisz"):
                    kat_id = int(df_kat[df_kat['nazwa'] == k]['id'].values[0])
                    conn.table("produkty").insert({"nazwa": n, "liczba": l, "cena": c, "kategoria_id": kat_id}).execute()
                    st.rerun()

    if not df_prod.empty:
        for _, row in df_prod.iterrows():
            with st.container():
                c1, c2, c3, c4, c5 = st.columns([3, 1, 1, 2, 1])
                c1.write(f"**{row['nazwa']}**")
                c2.write(f"{row['liczba']} szt.")
                c3.write(f"{row['cena']} zł")
                
                # Kolorowa etykieta kategorii
                bg_color = row['kolor']
                c4.markdown(f'<span style="background-color:{bg_color}; color:white; padding:2px 8px; border-radius:10px; font-size:12px;">{row["kategoria_nazwa"]}</span>', unsafe_allow_html=True)
                
                if c5.button("Usuń", key=f"del_p_{row['id']}"):
                    conn.table("produkty").delete().eq("id", row['id']).execute()
                    st.rerun()
                st.divider()

# --- TAB: KATEGORIE ---
with tabs[2]:
    st.header("Zarządzanie Kategoriami")
    with st.form("add_cat"):
        nk = st.text_input("Nazwa kategorii (np. Mleko, Elektronika)")
        ok = st.text_area("Opis")
        if st.form_submit_button("Dodaj kategorię"):
            conn.table("kategorie").insert({"nazwa": nk, "opis": ok}).execute()
