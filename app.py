import streamlit as st
import pandas as pd
import re
from collections import Counter
import os
from datetime import datetime
import altair as alt

# 1. CONFIGURATION DE LA PAGE
st.set_page_config(page_title="Grand Conseil Explorer", page_icon="🏛️", layout="wide")

# --- OUTILS DE GESTION DES DATES ---
MOIS_MAP = {
    "janvier": 1, "février": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "août": 8, "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12
}


def convert_date(date_str):
    """Transforme 'Septembre 2025' ou '01.09.2025' en objet datetime pour le tri."""
    s = str(date_str).lower()

    # 1. Recherche d'une année (2020-2030)
    match_year = re.search(r'20\d{2}', s)
    if not match_year: return datetime(2000, 1, 1)
    annee = int(match_year.group(0))

    # 2. Détection du mois
    mois = 1
    if 'jan' in s:
        mois = 1
    elif 'f' in s and 'v' in s:
        mois = 2
    elif 'mar' in s:
        mois = 3
    elif 'avr' in s:
        mois = 4
    elif 'mai' in s:
        mois = 5
    elif 'juin' in s:
        mois = 6
    elif 'juil' in s:
        mois = 7
    elif 'ao' in s:
        mois = 8
    elif 'sep' in s:
        mois = 9
    elif 'oct' in s:
        mois = 10
    elif 'nov' in s:
        mois = 11
    elif 'déc' in s or 'dec' in s:
        mois = 12

    return datetime(annee, mois, 1)


# 2. CHARGEMENT DES DONNÉES
@st.cache_data
def load_data():
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(current_dir, "discours_grand_conseil_complet.csv")

        # Lecture tolérante (accepte virgules ou points-virgules, ignore les lignes cassées)
        df = pd.read_csv(
            file_path,
            sep=None,
            engine='python',
            dtype={'Objet': str},
            on_bad_lines='skip',
            encoding='utf-8-sig'
        )

        df['Texte'] = df['Texte'].fillna("").astype(str)
        if 'Date' not in df.columns: df['Date'] = "Janvier 2000"
        if 'Parti' not in df.columns: df['Parti'] = "Indéterminé"
        if 'Orateur' not in df.columns: df['Orateur'] = "Inconnu"

        # Nettoyage
        df['Parti'] = df['Parti'].astype(str).str.strip()
        df['Orateur'] = df['Orateur'].astype(str).str.strip()
        df['Objet'] = df['Objet'].astype(str).str.strip()

        # Création de la colonne de date technique pour le tri
        df['Date_dt'] = df['Date'].apply(convert_date)
        df = df.sort_values(by='Date_dt', ascending=False)

        return df

    except Exception as e:
        st.error(f"❌ Erreur critique de lecture du CSV : {e}")
        return pd.DataFrame()


# Chargement initial
df_full = load_data()

if df_full.empty:
    st.warning("Le fichier CSV est vide.")
    st.stop()

# 3. FILTRES (SIDEBAR)
st.sidebar.header("🔍 Filtres")

# --- A. SÉLECTEUR DE LÉGISLATURE ---
st.sidebar.subheader("📅 Période")
DATE_BASCULE = datetime(2025, 5, 1)  # Date de début de la nouvelle législature

choix_leg = st.sidebar.multiselect(
    "Choisir la législature :",
    ["Législature Actuelle (2025-2029)", "Législature Précédente (2021-2025)"],
    default=["Législature Actuelle (2025-2029)"]
)

if not choix_leg:
    st.warning("Veuillez sélectionner une législature.")
    st.stop()

# Filtrage par date (On crée un df réduit 'df' qu'on utilisera ensuite partout)
mask_leg = pd.Series([False] * len(df_full), index=df_full.index)
if "Législature Actuelle (2025-2029)" in choix_leg:
    mask_leg = mask_leg | (df_full['Date_dt'] >= DATE_BASCULE)
if "Législature Précédente (2021-2025)" in choix_leg:
    mask_leg = mask_leg | (df_full['Date_dt'] < DATE_BASCULE)

df = df_full[mask_leg]  # df contient maintenant uniquement les données de la période choisie

if df.empty:
    st.warning("Aucune donnée pour cette législature.")
    st.stop()

# --- B. SÉLECTEUR ORATEUR & OBJET ---
# On recalcule les listes pour ne montrer que ce qui existe dans la période choisie
liste_orateurs = ["Tous les membres"] + sorted(df['Orateur'].unique())
selected_orateur = st.sidebar.selectbox("👤 Choisir un orateur", liste_orateurs)

liste_objets = ["Tous les objets"] + sorted(df['Objet'].unique())
selected_objet = st.sidebar.selectbox("📂 Choisir un objet", liste_objets)

st.sidebar.markdown("---")
search_query = st.sidebar.text_input("🔎 Rechercher un mot-clé")
case_sensitive = st.sidebar.checkbox("Respecter la casse", value=False)

# 4. LOGIQUE DE FILTRAGE
df_filtered = df.copy()

if selected_objet != "Tous les objets":
    df_filtered = df_filtered[df_filtered['Objet'] == selected_objet]

if selected_orateur != "Tous les membres":
    df_filtered = df_filtered[df_filtered['Orateur'] == selected_orateur]
else:
    df_filtered = df_filtered[df_filtered['Parti'] != 'Présidence']

if search_query:
    # --- CORRECTION ICI ---
    # On utilise explicitement l'argument 'case' de Pandas.
    # Si case_sensitive est False (non coché) -> case=False (insensible à la casse)
    # Si case_sensitive est True (coché) -> case=True (sensible)
    mask = df_filtered['Texte'].str.contains(search_query, case=case_sensitive, regex=False)
    df_filtered = df_filtered[mask]

# 5. SIDEBAR STATS
if selected_orateur != "Tous les membres" and not df_filtered.empty:
    st.sidebar.markdown("---")
    st.sidebar.subheader("📊 Statistiques")
    st.sidebar.markdown(f"**Total interventions :** {len(df_filtered)}")

    top_sessions = df_filtered['Date'].value_counts()
    if not top_sessions.empty:
        st.sidebar.markdown(f"**Session record :**\n{top_sessions.idxmax()} ({top_sessions.max()} inter.)")

    st.sidebar.markdown(f"**Parti :** {df_filtered['Parti'].iloc[0]}")

# 6. TITRE
leg_info = " & ".join(["2025+" if "Actuelle" in c else "2021-25" for c in choix_leg])

if selected_orateur == "Tous les membres" and selected_objet == "Tous les objets":
    titre_page = f"🏛️ Recherche Globale ({leg_info})"
elif selected_objet != "Tous les objets":
    titre_page = f"📂 Débat sur l'objet {selected_objet}"
else:
    titre_page = f"👤 Interventions de {selected_orateur}"

st.title(titre_page)

if df_filtered.empty:
    st.warning("Aucune intervention ne correspond à vos critères.")
    st.stop()

# 7. ANALYSE SÉMANTIQUE
if not df_filtered.empty and (selected_orateur != "Tous les membres" or selected_objet != "Tous les objets"):
    st.subheader("📊 Analyse du vocabulaire")

    STOP_WORDS = set([
        'le', 'la', 'les', 'un', 'une', 'des', 'du', 'de', 'au', 'aux',
        'et', 'ou', 'mais', 'donc', 'or', 'ni', 'car', 'que', 'qui', 'quoi', 'dont', 'où',
        'ce', 'cet', 'cette', 'ces', 'ca', 'ça', 'cela', 'ceci',
        'je', 'tu', 'il', 'elle', 'nous', 'vous', 'ils', 'elles', 'on',
        'mon', 'ton', 'son', 'ma', 'ta', 'sa', 'mes', 'tes', 'ses', 'notre', 'votre', 'leur', 'nos', 'vos', 'leurs',
        'être', 'suis', 'es', 'est', 'sommes', 'êtes', 'sont', 'été', 'étais', 'était',
        'avoir', 'ai', 'as', 'a', 'avons', 'avez', 'ont', 'eu', 'avais', 'avait',
        'faire', 'fait', 'fais', 'font', 'aller', 'vais', 'va', 'vont',
        'plus', 'moins', 'très', 'trop', 'peu', 'beaucoup', 'tout', 'toute', 'tous', 'toutes',
        'aussi', 'ici', 'là', 'bien', 'mal', 'si', 'non', 'oui', 'ne', 'pas', 'y', 'en',
        'pour', 'par', 'dans', 'sur', 'sous', 'vers', 'avec', 'sans', 'chez', 'comme',
        'monsieur', 'madame', 'messieurs', 'mesdames', 'président', 'présidente',
        'député', 'députée', 'conseiller', 'conseillère', 'état', 'grand', 'conseil',
        'rapport', 'commission', 'projet', 'loi', 'article', 'articles', 'alinéa',
        'vote', 'voter', 'voix', 'majorité', 'minorité', 'parole', 'merci', 'chose',
        'question', 'réponse', 'dire', 'dis', 'dit', 'faut', 'fois', 'année', 'années',
        'cette', 'notre', 'votre', 'leur', 'leurs', 'entre', 'encore', 'alors', 'après', 'avant',
        'chers', 'chères', 'collègues', 'groupe', 'socialiste','udc', 'libéral', 'radical', 'centre','vertpop',
        'parce','peut', 'selon', 'puis',
    ])

    col1, col2 = st.columns(2)

    with col1:
        all_text = " ".join(df_filtered['Texte'].tolist()).lower()
        words = re.findall(r'\b[a-zàâçéèêëîïôûùüÿñ]{4,}\b', all_text)
        meaningful_words = [w for w in words if w not in STOP_WORDS]
        word_counts = Counter(meaningful_words).most_common(20)

        if word_counts:
            # On crée le DataFrame (sans le mettre en index pour Altair)
            df_words = pd.DataFrame(word_counts, columns=['Mot', 'Fréquence'])

            st.write("**Top 20 des mots les plus utilisés :**")

            # --- CORRECTION DU TRI ---
            # On utilise Altair pour forcer le tri par fréquence (et non alphabétique)
            c = alt.Chart(df_words).mark_bar().encode(
                x='Fréquence',
                y=alt.Y('Mot', sort='-x')
                # sort='-x' veut dire : Trie l'axe Y selon les valeurs de X (du plus grand au plus petit)
            )

            st.altair_chart(c, use_container_width=True)
            # -------------------------

        else:
            st.info("Données insuffisantes pour l'analyse.")

    with col2:
        if selected_orateur == "Tous les membres":
            st.write("**Répartition par Parti :**")
            st.bar_chart(df_filtered['Parti'].value_counts())
        else:
            avg_len = df_filtered['Texte'].str.len().mean()
            st.metric("Longueur moyenne intervention", f"{int(avg_len)} caractères")
            st.metric("Richesse lexicale (mots clés)", f"{len(meaningful_words)}")

    st.markdown("---")

# 8. LISTE DES INTERVENTIONS
if search_query:
    st.subheader(f"Résultats de recherche ({len(df_filtered)})")
    for index, row in df_filtered.iterrows():
        titre = f"📅 {row['Date']} | {row['Orateur']} | 📂 {row['Objet']}"
        with st.expander(titre):
            # Pour le surlignage, on utilise re.IGNORECASE si la case n'est pas cochée
            flags = 0 if case_sensitive else re.IGNORECASE
            texte = re.sub(f"({re.escape(search_query)})", r"**\1**", row['Texte'], flags=flags)
            st.markdown(texte)

else:
    objets_uniques = df_filtered['Objet'].unique()

    st.subheader("Historique des interventions")
    show_details = st.checkbox(
        f"📂 Afficher le détail des interventions ({len(df_filtered)} interventions sur {len(objets_uniques)} objets)")

    if show_details:
        for objet in objets_uniques:
            subset = df_filtered[df_filtered['Objet'] == objet]
            titre_dossier = f"📂 Objet {objet} ({len(subset)} interventions)"

            with st.expander(titre_dossier):
                for _, row in subset.iterrows():
                    st.markdown(f"**📅 {row['Date']} | 👤 {row['Orateur']} ({row['Parti']})**")
                    st.write(row['Texte'])
                    st.divider()