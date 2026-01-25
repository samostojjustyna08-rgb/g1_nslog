import streamlit as st
from supabase import create_client, Client
import pandas as pd
import plotly.express as px

# --- 1. KONFIGURACJA STRONY (Musi być na samym początku) ---
st.set_page_config(
    page_title="Magazyn Manager",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. POŁĄCZENIE Z BAZĄ ---
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

try:
    supabase = init_connection()
except Exception as e:
    st.error("Nie udało się połączyć z bazą danych. Sprawdź klucze API.")
    st.stop()

# --- 3. FUNKCJE POMOCNICZE ---
def get_data():
    # Pobieramy produkty
    response = supabase.table('produkty').select('*, kategorie(nazwa)').order('id').execute()
    return response.data

def get_categories():
    response = supabase.table('kategorie').select('id, nazwa').execute()
    return response.data

def update_stock_in_db(product_id, new_total):
    try:
        supabase.table('produkty').update({'liczba': new_total}).eq('id', product_id).execute()
        return True
    except:
        return False

# --- 4. GŁÓWNA APLIKACJA ---

# Pasek boczny (Sidebar) - LOGO I FILTRY
with st.sidebar:
    st.header("📦 Magazyn")
    st.caption("Panel sterowania")
    st.divider()
    
    # Odświeżanie
    if st.button("🔄 Odśwież dane", use_container_width=True):
        st.rerun()
    
    st.divider()
    st.subheader("Filtrowanie")

# Pobranie danych
raw_data = get_data()
categories_data = get_categories()

if raw_data:
    # Przygotowanie DataFrame
    df = pd.json_normalize(raw_data)
    
    # Mapowanie nazw kolumn
    rename_map = {
        'nazwa': 'Produkt',
        'liczba': 'Ilość',
        'cena': 'Cena',
        'kategorie.nazwa': 'Kategoria',
        'minimalny_stan': 'Min. Stan',
        'minimalny stan': 'Min. Stan'
    }
    df = df.rename(columns=rename_map)
    if 'Kategoria' not in df.columns: df['Kategoria'] = 'Inne'

    # Wyszukiwarka w pasku bocznym
    search_query = st.sidebar.text_input("🔍 Szukaj produktu:", placeholder="Nazwa...")
    cat_filter = st.sidebar.multiselect("Filtruj kategorię:", options=df['Kategoria'].unique())

    # Logika filtrowania
    df_filtered = df.copy()
    if search_query:
        df_filtered = df_filtered[df_filtered['Produkt'].str.contains(search_query, case=False)]
    if cat_filter:
        df_filtered = df_filtered[df_filtered['Kategoria'].isin(cat_filter)]

    # --- PANEL GŁÓWNY (DASHBOARD) ---
    st.title("Przegląd Magazynu")
    
    # KPI - Karty statystyk
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    
    total_items = df_filtered['Ilość'].sum()
    total_value = (df_filtered['Ilość'] * df_filtered['Cena']).sum()
    low_stock_count = 0
    if 'Min. Stan' in df.columns:
        low_stock_count = len(df_filtered[df_filtered['Ilość'] <= df_filtered['Min. Stan']])

    kpi1.metric("📦 Liczba produktów", len(df_filtered))
    kpi2.metric("📊 Sztuk łącznie", f"{total_items}")
    kpi3.metric("💰 Wartość magazynu", f"{total_value:,.2f} zł".replace(",", " "))
    kpi4.metric("⚠️ Niskie stany", low_stock_count, delta_color="inverse")

    st.divider()

    # ZAKŁADKI
    tab_list, tab_ops, tab_add = st.tabs(["📋 Lista i Wykresy", "🛠️ Szybkie Operacje", "➕ Dodaj Nowy"])

    # --- ZAKŁADKA 1: TABELA + WYKRES ---
   with tab_list:
        col_table, col_chart = st.columns([1.5, 1])
        
        with col_table:
            st.subheader("Szczegóły produktów")
            
            # 1. Definicja funkcji kolorującej
            def color_stock(row):
                # Sprawdzamy czy kolumna Min. Stan istnieje (dla bezpieczeństwa)
                min_val = row.get('Min. Stan', 0) 
                
                if row['Ilość'] < min_val:
                    # Czerwone tło (pastelowe) dla niskiego stanu
                    return ['background-color: #ffcccc; color: black'] * len(row)
                else:
                    # Zielone tło (pastelowe) gdy stan jest OK (równy lub wyższy)
                    return ['background-color: #d4edda; color: black'] * len(row)

            # 2. Wybór kolumn do wyświetlenia
            display_cols = ['Produkt', 'Kategoria', 'Cena', 'Ilość', 'Min. Stan']
            
            # 3. Nakładanie stylów i formatowania
            # Tworzymy obiekt "Styler", który trzyma informacje o kolorach i formacie liczb
            styled_df = df_filtered[display_cols].style\
                .apply(color_stock, axis=1)\
                .format({
                    "Cena": "{:.2f} zł",   # Tu naprawiamy format ceny (np. 12.00 zł)
                    "Ilość": "{:.0f}",     # Ilość jako liczba całkowita
                    "Min. Stan": "{:.0f}"
                })

            # 4. Wyświetlenie pokolorowanej tabeli
            st.dataframe(
                styled_df,
                use_container_width=True,
                height=400,
                column_config={
                    "Produkt": st.column_config.TextColumn("Nazwa Produktu"),
                }
            )

        with col_chart:
            st.subheader("Struktura magazynu")
            if not df_filtered.empty:
                # Wykres kołowy
                fig = px.pie(df_filtered, values='Ilość', names='Kategoria', hole=0.4)
                fig.update_layout(margin=dict(t=0, b=0, l=0, r=0)) # Zmniejszenie marginesów
                st.plotly_chart(fig, use_container_width=True)
                
                # Wykres słupkowy z kolorowaniem warunkowym na wykresie
                # Dodajemy pomocniczą kolumnę koloru tylko dla wykresu
                df_chart = df_filtered.copy()
                df_chart['Status'] = df_chart.apply(lambda x: 'Niski stan' if x['Ilość'] < x.get('Min. Stan', 0) else 'OK', axis=1)
                
                fig2 = px.bar(
                    df_chart, 
                    x='Produkt', 
                    y='Ilość', 
                    color='Status', # Kolor słupka zależy od statusu
                    color_discrete_map={'OK': '#28a745', 'Niski stan': '#dc3545'}, # Zielony i Czerwony
                    title="Ranking ilości"
                )
                st.plotly_chart(fig2, use_container_width=True)
    # --- ZAKŁADKA 3: DODAWANIE ---
    with tab_add:
        st.write("### Rejestracja nowego produktu")
        with st.form("new_product_form", clear_on_submit=True):
            col_f1, col_f2 = st.columns(2)
            
            with col_f1:
                n_name = st.text_input("Nazwa produktu")
                # Pobranie słownika kategorii
                cat_dict = {c['nazwa']: c['id'] for c in categories_data} if categories_data else {}
                n_cat = st.selectbox("Kategoria", list(cat_dict.keys()))
            
            with col_f2:
                n_price = st.number_input("Cena sprzedaży (PLN)", min_value=0.01, step=0.01, format="%.2f")
                n_qty = st.number_input("Stan początkowy", min_value=0, step=1)
                n_min = st.number_input("Alarm niskiego stanu (szt.)", min_value=1, value=5)

            submitted = st.form_submit_button("💾 Zapisz produkt w bazie", use_container_width=True)
            
            if submitted:
                if n_name and n_cat:
                    try:
                        supabase.table('produkty').insert({
                            "nazwa": n_name,
                            "kategoria_id": cat_dict[n_cat],
                            "cena": n_price,
                            "liczba": n_qty,
                            "minimalny_stan": n_min
                        }).execute()
                        st.success(f"Dodano produkt: {n_name}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Wystąpił błąd: {e}")
                else:
                    st.warning("Podaj nazwę produktu.")

else:
    st.warning("Brak danych w bazie. Dodaj produkty przez Supabase lub zakładkę 'Dodaj Nowy'.")
