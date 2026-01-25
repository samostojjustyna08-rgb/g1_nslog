import streamlit as st
from supabase import create_client, Client
import pandas as pd
import plotly.express as px

# --- 1. KONFIGURACJA STRONY ---
st.set_page_config(
    page_title="System Magazynowy",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. POŁĄCZENIE Z BAZĄ SUPABASE ---
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

try:
    supabase = init_connection()
except Exception as e:
    st.error("Błąd połączenia z bazą danych. Sprawdź plik secrets.")
    st.stop()

# --- 3. FUNKCJE POMOCNICZE ---
def get_data():
    # Pobieramy produkty wraz z nazwą kategorii
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

# --- PASEK BOCZNY (FILTRY) ---
with st.sidebar:
    st.header("📦 Magazyn")
    st.divider()
    
    # Przycisk odświeżania
    if st.button("🔄 Odśwież dane", use_container_width=True):
        st.rerun()
    
    st.subheader("Filtrowanie")

# Pobranie danych
raw_data = get_data()
categories_data = get_categories()

if raw_data:
    # Konwersja danych do tabeli (DataFrame)
    df = pd.json_normalize(raw_data)
    
    # Zmiana nazw kolumn na czytelniejsze
    rename_map = {
        'nazwa': 'Produkt',
        'liczba': 'Ilość',
        'cena': 'Cena',
        'kategorie.nazwa': 'Kategoria',
        'minimalny_stan': 'Min. Stan',
        'minimalny stan': 'Min. Stan' # Zabezpieczenie na wypadek spacji w nazwie
    }
    df = df.rename(columns=rename_map)
    
    # Uzupełnienie braków
    if 'Kategoria' not in df.columns: df['Kategoria'] = 'Inne'
    if 'Min. Stan' not in df.columns: df['Min. Stan'] = 0

    # Filtrowanie w pasku bocznym
    search_query = st.sidebar.text_input("🔍 Szukaj produktu:", placeholder="Nazwa...")
    cat_filter = st.sidebar.multiselect("Filtruj kategorię:", options=df['Kategoria'].unique())

    # Logika filtrowania
    df_filtered = df.copy()
    if search_query:
        df_filtered = df_filtered[df_filtered['Produkt'].str.contains(search_query, case=False)]
    if cat_filter:
        df_filtered = df_filtered[df_filtered['Kategoria'].isin(cat_filter)]

    # --- DASHBOARD (GÓRA STRONY) ---
    st.title("Stan Magazynowy")
    
    # Statystyki (KPI)
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    
    total_items = df_filtered['Ilość'].sum()
    total_value = (df_filtered['Ilość'] * df_filtered['Cena']).sum()
    low_stock_items = df_filtered[df_filtered['Ilość'] < df_filtered['Min. Stan']]

    kpi1.metric("📦 Liczba produktów", len(df_filtered))
    kpi2.metric("📊 Sztuk łącznie", int(total_items))
    kpi3.metric("💰 Wartość magazynu", f"{total_value:,.2f} zł".replace(",", " "))
    kpi4.metric("⚠️ Poniżej minimum", len(low_stock_items), delta_color="inverse")

    st.divider()

    # ZAKŁADKI
    tab_list, tab_ops, tab_add = st.tabs(["📋 Lista i Wykresy", "🛠️ Ruch Magazynowy", "➕ Dodaj Nowy"])

    # --- ZAKŁADKA 1: TABELA + WYKRES ---
    with tab_list:
        col_table, col_chart = st.columns([1.5, 1])
        
        with col_table:
            st.subheader("Szczegóły produktów")

            # --- LOGIKA KOLOROWANIA WIERSZY ---
            def color_stock(row):
                min_val = row.get('Min. Stan', 0)
                # Jeśli ilość jest mniejsza niż minimum -> Czerwony
                if row['Ilość'] < min_val:
                    return ['background-color: #ffcccc; color: black'] * len(row)
                # W przeciwnym razie -> Zielony
                else:
                    return ['background-color: #d4edda; color: black'] * len(row)

            # Wybór kolumn
            display_cols = ['Produkt', 'Kategoria', 'Cena', 'Ilość', 'Min. Stan']
            
            # Tworzenie stylizowanej tabeli
            # .apply -> nakłada kolory
            # .format -> naprawia "dużo zer po kropce"
            styled_df = df_filtered[display_cols].style\
                .apply(color_stock, axis=1)\
                .format({
                    "Cena": "{:.2f} zł",   # Formatowanie waluty: 12.50 zł
                    "Ilość": "{:.0f}",     # Formatowanie ilości: 100
                    "Min. Stan": "{:.0f}"
                })

            st.dataframe(
                styled_df,
                use_container_width=True,
                height=500
            )

        with col_chart:
            st.subheader("Wykres stanów")
            if not df_filtered.empty:
                # Przygotowanie danych do wykresu (dodajemy kolumnę koloru)
                df_chart = df_filtered.copy()
                df_chart['Status'] = df_chart.apply(
                    lambda x: 'Niski stan' if x['Ilość'] < x['Min. Stan'] else 'OK', axis=1
                )

                # Wykres słupkowy
                fig = px.bar(
                    df_chart, 
                    x='Produkt', 
                    y='Ilość',
                    color='Status', # Kolor zależny od statusu
                    color_discrete_map={'OK': '#28a745', 'Niski stan': '#dc3545'}, # Zielony i Czerwony
                    text='Ilość',
                    title="Ranking ilości"
                )
                fig.update_traces(textposition='outside')
                st.plotly_chart(fig, use_container_width=True)

                # Wykres kołowy (udział kategorii)
                fig2 = px.pie(df_filtered, values='Ilość', names='Kategoria', hole=0.4, title="Udział kategorii")
                st.plotly_chart(fig2, use_container_width=True)

    # --- ZAKŁADKA 2: SZYBKIE OPERACJE ---
    with tab_ops:
        st.write("### Zmień stan magazynowy")
        
        # Lista wyboru z podglądem aktualnego stanu
        product_options = {f"{row['Produkt']} | Stan: {row['Ilość']} szt.": row for index, row in df.iterrows()}
        selected_key = st.selectbox("Wybierz produkt:", list(product_options.keys()))
        
        if selected_key:
            item = product_options[selected_key]
            st.info(f"Wybrano: **{item['Produkt']}** | Cena: {item['Cena']:.2f} zł")

            col_in, col_out = st.columns(2)

            # Karta Dostawy (Zielona)
            with col_in:
                with st.container(border=True):
                    st.success("📥 **DOSTAWA (Przyjęcie)**")
                    qty_add = st.number_input("Ile dodać?", min_value=1, value=1, key="q_add")
                    
                    if st.button("Zatwierdź Dostawę", type="primary", use_container_width=True):
                        new_val = item['Ilość'] + qty_add
                        if update_stock_in_db(item['id'], new_val):
                            st.toast(f"✅ Dodano {qty_add} szt. Nowy stan: {new_val}", icon="📦")
                            st.rerun()
                        else:
                            st.error("Błąd zapisu w bazie.")

            # Karta Wydania (Czerwona)
            with col_out:
                with st.container(border=True):
                    st.error("📤 **SPRZEDAŻ (Wydanie)**")
                    qty_sub = st.number_input("Ile wydać?", min_value=1, value=1, key="q_sub")
                    
                    if st.button("Zatwierdź Wydanie", type="secondary", use_container_width=True):
                        new_val = item['Ilość'] - qty_sub
                        if new_val < 0:
                            st.warning("⚠️ Nie możesz wydać więcej niż masz!")
                        else:
                            if update_stock_in_db(item['id'], new_val):
                                st.toast(f"✅ Wydano {qty_sub} szt. Nowy stan: {new_val}", icon="💸")
                                st.rerun()
                            else:
                                st.error("Błąd zapisu w bazie.")

    # --- ZAKŁADKA 3: DODAWANIE NOWEGO PRODUKTU ---
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
                # Format %.2f zapewnia, że użytkownik wpisuje np. 12.50
                n_price = st.number_input("Cena (PLN)", min_value=0.01, step=0.01, format="%.2f")
                n_qty = st.number_input("Stan początkowy", min_value=0, step=1)
                n_min = st.number_input("Alarm niskiego stanu (szt.)", min_value=1, value=5)

            submitted = st.form_submit_button("💾 Zapisz produkt", use_container_width=True)
            
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
    st.info("Baza danych jest pusta. Dodaj pierwszy produkt w zakładce 'Dodaj Nowy'.")
