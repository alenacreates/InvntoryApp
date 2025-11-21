import streamlit as st
import pandas as pd
from io import StringIO

# ---------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------

@st.cache_data
def load_inventory(csv_path: str = "Inventory.csv") -> pd.DataFrame:
    """
    Lädt die Inventar-CSV robust, versucht verschiedene Trennzeichen
    und nutzt bei Bedarf die automatische Erkennung von pandas.
    """
    potential_seps = [None, ";", ",", "\t", "|"]
    last_error = None

    for sep in potential_seps:
        try:
            if sep is None:
                # automatische Trennzeichenerkennung
                df = pd.read_csv(csv_path, sep=None, engine="python")
            else:
                df = pd.read_csv(csv_path, sep=sep, engine="python")

            # Einfache Plausibilitätsprüfung
            if df.shape[1] >= 1:
                return df
        except Exception as e:
            last_error = e
            continue

    raise RuntimeError(
        f"Die Datei '{csv_path}' konnte nicht gelesen werden. "
        f"Letzte Fehlermeldung: {last_error}"
    )


def guess_column(columns, candidates):
    """
    Versucht eine Spalte anhand typischer Namen zu raten.
    candidates: Liste von (Teil-)Strings, z.B. ['artikel', 'produkt', 'name']
    """
    cols_lower = {c.lower(): c for c in columns}
    for cand in candidates:
        cand = cand.lower()
        for col_lower, original in cols_lower.items():
            if cand in col_lower:
                return original
    # Fallback: erste Spalte
    return columns[0] if columns else None


def filter_search(df: pd.DataFrame, term: str, search_columns):
    """Einfache Volltextsuche über die angegebenen Spalten."""
    if not term:
        return df

    term = term.strip()
    if term == "":
        return df

    mask = False
    for col in search_columns:
        mask = mask | df[col].astype(str).str.contains(term, case=False, na=False)

    return df[mask]


def ensure_picklist_state():
    """Initialisiert die Pickliste im Session State."""
    if "picklist" not in st.session_state:
        st.session_state["picklist"] = []  # Liste von Dicts


def add_to_picklist(df, product_col, location_col, selected_products, quantities):
    """Fügt die ausgewählten Produkte mit Mengen zur Pickliste hinzu."""
    ensure_picklist_state()

    for prod in selected_products:
        qty = quantities.get(prod, 0)
        if qty <= 0:
            continue

        # Erste passende Zeile aus dem DataFrame holen
        rows = df[df[product_col].astype(str) == str(prod)]
        if rows.empty:
            continue

        row = rows.iloc[0].to_dict()
        # Menge ergänzen
        row["Menge"] = qty

        # Optional: Lagerort extra kennzeichnen (bleibt aber im normalen Spalten-Set)
        if location_col and location_col in row:
            row["Lagerort_Anzeige"] = row[location_col]

        # Falls das Produkt schon in der Pickliste ist -> Menge addieren
        merged = False
        for existing in st.session_state["picklist"]:
            if existing.get(product_col) == row.get(product_col):
                existing["Menge"] = existing.get("Menge", 0) + qty
                merged = True
                break
        if not merged:
            st.session_state["picklist"].append(row)


# ---------------------------------------------------------
# Streamlit App
# ---------------------------------------------------------

st.set_page_config(
    page_title="Inventarverwaltung",
    layout="wide",
)

st.title("📦 Einfache Inventar-App")

st.markdown(
    """
Diese App liest eine `Inventory.csv` ein und ermöglicht dir:

- 📋 **Gesamte Produktliste anzeigen**  
- 🔎 **Produkte suchen**  
- 📍 **Lagerort einsehen** (über die gewählte Spalte)  
- 🧾 **Pickliste** erstellen und als CSV exportieren  
"""
)

# ---------------------------------------------------------
# Daten laden
# ---------------------------------------------------------

try:
    df = load_inventory("Inventory.csv")
except Exception as e:
    st.error(
        "Die Datei `Inventory.csv` konnte nicht geladen werden.\n\n"
        "Bitte stelle sicher, dass sie im selben Ordner wie `app.py` liegt."
    )
    st.exception(e)
    st.stop()

if df.empty:
    st.warning("Die Inventar-Tabelle ist leer.")
    st.stop()

# ---------------------------------------------------------
# Sidebar-Konfiguration
# ---------------------------------------------------------

st.sidebar.header("⚙️ Einstellungen")

st.sidebar.write("**Spaltenzuordnung**")

all_columns = list(df.columns)

# Produktspalte raten
product_col_guess = guess_column(
    all_columns,
    ["artikel", "produkt", "product", "name", "bezeichnung", "item"]
)
product_col = st.sidebar.selectbox(
    "Produktsäule (Name / Artikelbezeichnung)",
    options=all_columns,
    index=all_columns.index(product_col_guess) if product_col_guess in all_columns else 0,
)

# Lagerortspalte raten
location_col_guess = guess_column(
    all_columns,
    ["lager", "lagerort", "location", "warehouse", "regal", "fach", "bin"]
)
location_col = st.sidebar.selectbox(
    "Lagerort-Spalte",
    options=["<keine>"] + all_columns,
    index=(all_columns.index(location_col_guess) + 1)
    if location_col_guess in all_columns
    else 0,
)
if location_col == "<keine>":
    location_col = None

st.sidebar.write("---")

st.sidebar.write("**Such-Einstellungen**")
search_only_product = st.sidebar.checkbox(
    "Nur in der Produktspalte suchen", value=False
)

if search_only_product:
    search_columns = [product_col]
else:
    search_columns = all_columns

st.sidebar.write("---")
st.sidebar.caption("Tipp: Passen Sie die Spalten im Sidebar an Ihre CSV an.")

# ---------------------------------------------------------
# Tabs
# ---------------------------------------------------------

tab_list, tab_search, tab_pick = st.tabs(
    ["📋 Gesamte Liste", "🔎 Suche", "🧾 Pickliste"]
)

# ---------------------------------------------------------
# Tab: Gesamte Liste
# ---------------------------------------------------------

with tab_list:
    st.subheader("Gesamte Produktliste")

    info_cols = []
    if product_col:
        info_cols.append(product_col)
    if location_col and location_col not in info_cols:
        info_cols.append(location_col)

    st.markdown(
        f"**Anzahl Produkte:** {len(df)}"
        + (f"  – Produktspalte: `{product_col}`" if product_col else "")
        + (f", Lagerort-Spalte: `{location_col}`" if location_col else "")
    )

    st.dataframe(df, use_container_width=True)


# ---------------------------------------------------------
# Tab: Suche
# ---------------------------------------------------------

with tab_search:
    st.subheader("Produktsuche")

    search_term = st.text_input("Suchbegriff (Teilstring)")

    filtered_df = filter_search(df, search_term, search_columns)

    st.markdown(
        f"**Gefundene Produkte:** {len(filtered_df)} "
        f"(von insgesamt {len(df)})"
    )

    if location_col and location_col in filtered_df.columns:
        st.markdown(f"*Lagerort-Spalte: `{location_col}`*")

    st.dataframe(filtered_df, use_container_width=True)


# ---------------------------------------------------------
# Tab: Pickliste
# ---------------------------------------------------------

with tab_pick:
    st.subheader("Pickliste erstellen")

    st.markdown(
        """
Wähle Produkte aus und gib eine Menge an.  
Beim Hinzufügen werden identische Produkte in der Pickliste automatisch zusammengefasst.
"""
    )

    ensure_picklist_state()

    # Basis für Auswahl ist die komplette Liste; du kannst aber auch filtern:
    st.markdown("**1. Produkte auswählen**")
    base_for_pick = st.radio(
        "Basis für die Auswahl",
        options=["Gesamte Liste", "Ergebnis der Suche"],
        horizontal=True,
    )

    if base_for_pick == "Ergebnis der Suche":
        base_df = filter_search(df, st.session_state.get("last_search_term", ""), search_columns) \
            if "last_search_term" in st.session_state else df
    else:
        base_df = df

    # Damit die Suche im Pick-Tab mit der Suche im Such-Tab harmoniert,
    # speichern wir den Suchbegriff (falls im Such-Tab verwendet).
    # (Kein Muss für Funktionalität – nur Komfort)

    # Auswahl der Produkte
    available_products = (
        base_df[product_col].astype(str).dropna().unique().tolist()
        if product_col in base_df.columns
        else []
    )

    if not available_products:
        st.warning("Keine Produkte verfügbar, um eine Pickliste zu erstellen.")
    else:
        selected_products = st.multiselect(
            f"Produkte nach `{product_col}` auswählen",
            options=available_products,
        )

        st.markdown("**2. Mengen angeben**")
        quantities = {}
        for prod in selected_products:
            quantities[prod] = st.number_input(
                f"Menge für: {prod}",
                min_value=0,
                step=1,
                value=1,
                key=f"qty_{prod}",
            )

        if st.button("➕ Zur Pickliste hinzufügen"):
            add_to_picklist(df, product_col, location_col, selected_products, quantities)
            st.success("Produkte wurden zur Pickliste hinzugefügt.")

    st.markdown("---")
    st.markdown("### Aktuelle Pickliste")

    if not st.session_state["picklist"]:
        st.info("Die Pickliste ist noch leer.")
    else:
        pick_df = pd.DataFrame(st.session_state["picklist"])

        # Spalten ein wenig sortieren: Produkt, Lagerort, Menge zuerst
        cols = list(pick_df.columns)
        ordered_cols = []

        for c in [product_col, "Lagerort_Anzeige", "Menge"]:
            if c in cols and c not in ordered_cols:
                ordered_cols.append(c)

        for c in cols:
            if c not in ordered_cols:
                ordered_cols.append(c)

        pick_df = pick_df[ordered_cols]

        st.dataframe(pick_df, use_container_width=True)

        # Download als CSV
        csv_buffer = StringIO()
        pick_df.to_csv(csv_buffer, index=False)
        csv_data = csv_buffer.getvalue().encode("utf-8-sig")

        st.download_button(
            label="⬇️ Pickliste als CSV herunterladen",
            data=csv_data,
            file_name="Pickliste.csv",
            mime="text/csv",
        )

        # Option, die Pickliste zu leeren
        if st.button("🗑️ Pickliste leeren"):
            st.session_state["picklist"] = []
            st.success("Pickliste wurde geleert.")