import streamlit as st
from st_supabase_connection import SupabaseConnection

# Konfiguracja strony
st.set_page_config(page_title="Zarządzanie Sklepem", layout="wide")

# Inicjalizacja połączenia z Supabase
# Dane uwierzytelniające należy dodać w .streamlit/secrets.toml lub w Settings na Streamlit Cloud
conn = st.connection("supabase", type=SupabaseConnection)

st.title("📦 System Zarządzania Produktami")

tabs = st.tabs(["Produkty", "Kategorie"])

# --- TAB: KATEGORIE ---
with tabs[1]:
    st.header("Zarządzanie Kategoriami")
    
    # Formularz dodawania kategorii
    with st.expander("➕ Dodaj nową kategorię"):
        with st.form("add_category"):
            nazwa_kat = st.text_input("Nazwa kategorii")
            opis_kat = st.text_area("Opis")
            submit_kat = st.form_submit_button("Zapisz kategorię")
            
            if submit_kat and nazwa_kat:
                conn.table("kategorie").insert({"nazwa": nazwa_kat, "opis": opis_kat}).execute()
                st.success(f"Dodano kategorię: {nazwa_kat}")
                st.rerun()

    # Wyświetlanie i usuwanie kategorii
    kat_data = conn.table("kategorie").select("*").execute()
    if kat_data.data:
        for kat in kat_data.data:
            col1, col2 = st.columns([4, 1])
            col1.write(f"**{kat['nazwa']}** - {kat['opis']}")
            if col2.button("Usuń", key=f"del_kat_{kat['id']}"):
                conn.table("kategorie").delete().eq("id", kat['id']).execute()
                st.rerun()
    else:
        st.info("Brak kategorii w bazie.")

# --- TAB: PRODUKTY ---
with tabs[0]:
    st.header("Zarządzanie Produktami")

    # Pobranie list kategorii do selectboxa
    kat_list = conn.table("kategorie").select("id, nazwa").execute()
    kat_options = {k['nazwa']: k['id'] for k in kat_list.data} if kat_list.data else {}

    # Formularz dodawania produktu
    with st.expander("➕ Dodaj nowy produkt"):
        if not kat_options:
            st.warning("Najpierw dodaj przynajmniej jedną kategorię!")
        else:
            with st.form("add_product"):
                nazwa_prod = st.text_input("Nazwa produktu")
                liczba_prod = st.number_input("Liczba", min_value=0, step=1)
                cena_prod = st.number_input("Cena", min_value=0.0, format="%.2f")
                kat_wybrana = st.selectbox("Kategoria", options=list(kat_options.keys()))
                
                submit_prod = st.form_submit_button("Zapisz produkt")
                
                if submit_prod and nazwa_prod:
                    new_prod = {
                        "nazwa": nazwa_prod,
                        "liczba": liczba_prod,
                        "cena": cena_prod,
                        "kategoria_id": kat_options[kat_wybrana]
                    }
                    conn.table("produkty").insert(new_prod).execute()
                    st.success(f"Dodano produkt: {nazwa_prod}")
                    st.rerun()

    # Wyświetlanie i usuwanie produktów
    # Join z tabelą kategorie, aby wyświetlić nazwę zamiast ID
    prod_data = conn.table("produkty").select("*, kategorie(nazwa)").execute()
    
    if prod_data.data:
        st.subheader("Lista produktów")
        for p in prod_data.data:
            col1, col2, col3, col4, col5 = st.columns([3, 1, 1, 2, 1])
            col1.write(f"**{p['nazwa']}**")
            col2.write(f"Ilość: {p['liczba']}")
            col3.write(f"{p['cena']} zł")
            col4.write(f"📁 {p['kategorie']['nazwa'] if p['kategorie'] else 'Brak'}")
            
            if col5.button("Usuń", key=f"del_prod_{p['id']}"):
                conn.table("produkty").delete().eq("id", p['id']).execute()
                st.rerun()
    else:
        st.info("Brak produktów w bazie.")
