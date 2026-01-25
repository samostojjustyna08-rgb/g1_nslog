import streamlit as st
from supabase import create_client, Client
import pandas as pd
import plotly.express as px

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="Magazyn Produktów", layout="wide")

# --- POŁĄCZENIE Z BAZĄ DANYCH ---
# Funkcja łączy się z Supabase używając sekretów ze Streamlit Cloud
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_connection()

# --- FUNKCJE POBIERAJĄCE DANE ---
def get_data():
    # Pobieramy produkty wraz z nazwą kategorii (dzięki relacji w bazie)
    # Uwaga: Zakładam, że kolumna w bazie nazywa się 'minimalny_stan' lub 'minimalny stan'
    # W Pythonie najlepiej używać nazw bez spacji.
    response = supabase.table('produkty').select('*, kategorie(nazwa)').execute()
    return response.data

def get_categories():
    response = supabase.table('kategorie').select('id, nazwa').execute()
    return response.data

# --- GŁÓWNY WIDOK APLIKACJI ---
st.title("📦 System Zarządzania Stanami Magazynowymi")

# 1. Pobranie danych
data = get_data()
categories = get_categories()

if data:
    # Konwersja do Pandas DataFrame dla łatwiejszej obróbki
    df = pd.json_normalize(data)
    
    # Przemianowanie kolumn dla czytelności (dopasuj do swoich nazw w bazie)
    # Jeśli w bazie masz "minimalny stan" ze spacją, tutaj to obsłużymy
    rename_map = {
        'nazwa': 'Produkt',
        'liczba': 'Ilość',
        'cena': 'Cena',
        'kategorie.nazwa': 'Kategoria',
        'minimalny_stan': 'Min. Stan', 
        'minimalny stan': 'Min. Stan' # Zabezpieczenie na wypadek spacji w nazwie kolumny
    }
    df = df.rename(columns=rename_map)
    
    # Jeśli po normalizacji brakuje kolumny 'Kategoria' (bo np. produkt nie ma kategorii), wypełnij braki
    if 'Kategoria' not in df.columns:
        df['Kategoria'] = 'Brak'

    # --- KPI (Kluczowe Wskaźniki) ---
    col1, col2, col3 = st.columns(3)
    total_products = len(df)
    total_stock = df['Ilość'].sum()
    low_stock_count = df[df['Ilość'] <= df['Min. Stan']].shape[0]

    col1.metric("Liczba produktów (rodzaje)", total_products)
    col2.metric("Łącznie sztuk w magazynie", total_stock)
    col3.metric("⚠️ Produkty poniżej minimum", low_stock_count, delta_color="inverse")

    # --- WYKRES (Dopasowujący się do stanów) ---
    st.subheader("📊 Aktualne stany magazynowe")
    
    # Wykres słupkowy: Oś X to produkty, Oś Y to Ilość, Kolor to Kategoria
    fig = px.bar(
        df, 
        x='Produkt', 
        y='Ilość', 
        color='Kategoria',
        text='Ilość',
        title="Ilość produktów w podziale na kategorie",
        color_discrete_sequence=px.colors.qualitative.Pastel
    )
    # Dodanie linii poziomej oznaczającej ogólny poziom ostrzegawczy (opcjonalnie)
    fig.update_traces(textposition='outside')
    st.plotly_chart(fig, use_container_width=True)

    # --- TABELA DANYCH ---
    st.subheader("Szczegółowa lista produktów")
    
    # Podświetlenie wierszy gdzie ilość jest niska
    def highlight_low_stock(row):
        # Sprawdzamy czy kolumna Min. Stan istnieje w DataFrame
        if 'Min. Stan' in row and row['Ilość'] <= row['Min. Stan']:
            return ['background-color: #ffcccc'] * len(row)
        return [''] * len(row)

    # Wyświetlamy tylko potrzebne kolumny
    display_cols = ['Produkt', 'Kategoria', 'Cena', 'Ilość', 'Min. Stan']
    # Filtrujemy tylko te kolumny, które faktycznie istnieją w df
    available_cols = [c for c in display_cols if c in df.columns]
    
    st.dataframe(
        df[available_cols].style.apply(highlight_low_stock, axis=1),
        use_container_width=True
    )

else:
    st.info("Baza produktów jest pusta. Dodaj pierwszy produkt poniżej.")

# --- FORMULARZ DODAWANIA ---
st.divider()
st.subheader("➕ Dodaj nowy produkt")

with st.form("add_product_form", clear_on_submit=True):
    col_a, col_b = st.columns(2)
    
    with col_a:
        new_name = st.text_input("Nazwa produktu")
        # Tworzymy słownik {Nazwa Kategorii: ID Kategorii} do wyboru
        cat_dict = {item['nazwa']: item['id'] for item in categories} if categories else {}
        selected_cat_name = st.selectbox("Wybierz kategorię", list(cat_dict.keys()))
        
    with col_b:
        new_price = st.number_input("Cena (PLN)", min_value=0.01, step=0.01)
        new_qty = st.number_input("Ilość początkowa", min_value=1, step=1)
        new_min_stock = st.number_input("Stan minimalny (alarm)", min_value=1, value=5)

    submitted = st.form_submit_button("Zapisz produkt w bazie")

    if submitted:
        if new_name and selected_cat_name:
            try:
                # Przygotowanie danych do wysłania
                # Używamy ID kategorii pobranego ze słownika
                payload = {
                    "nazwa": new_name,
                    "cena": new_price,
                    "liczba": new_qty,
                    "minimalny_stan": new_min_stock, # Upewnij się, że w bazie masz 'minimalny_stan' lub 'minimalny stan'
                    "kategoria_id": cat_dict[selected_cat_name]
                }
                
                # Wysłanie do Supabase
                supabase.table('produkty').insert(payload).execute()
                st.success(f"Dodano produkt: {new_name}!")
                st.rerun() # Odświeżenie strony żeby pokazać nowe dane
            except Exception as e:
                st.error(f"Wystąpił błąd podczas dodawania: {e}")
        else:
            st.warning("Uzupełnij nazwę i wybierz kategorię.")
