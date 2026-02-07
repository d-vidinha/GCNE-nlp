import streamlit as st
import pandas as pd
import re
from collections import Counter
import os

# 1. CONFIGURATION DE LA PAGE
st.set_page_config(page_title="Grand Conseil Explorer", page_icon="🏛️", layout="wide")


# 2. CHARGEMENT DES DONNÉES
@st.cache_data
def load_data():
    try:
        # On construit le chemin absolu vers le fichier, peu importe où tourne le serveur
        current_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(current_dir, "discours_grand_conseil_complet.csv")

        # On charge avec ce chemin précis
        df = pd.read_csv(file_path, dtype={'Objet': str})

        df['Texte'] = df['Texte'].fillna("").astype(str)
        if 'Date' not in df.columns: df['Date'] = "Date inconnue"
        if 'Parti' not in df.columns: df['Parti'] = "Indéterminé"
        if 'Orateur' not in df.columns: df['Orateur'] = "Inconnu"

        # Nettoyage
        df['Parti'] = df['Parti'].astype(str).str.strip()
        df['Orateur'] = df['Orateur'].astype(str).str.strip()
        df['Objet'] = df['Objet'].astype(str).str.strip()

        return df

    except Exception as e:
        st.error(f"❌ Erreur critique de lecture du CSV : {e}")
        return pd.DataFrame()


df = load_data()
if df.empty:
    st.warning("Le fichier CSV est vide.")
    st.stop()

# 3. FILTRES (SIDEBAR)
st.sidebar.header("🔍 Filtres")

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
    flags = 0 if case_sensitive else re.IGNORECASE
    mask = df_filtered['Texte'].str.contains(search_query, flags=flags, regex=False)
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
if selected_orateur == "Tous les membres" and selected_objet == "Tous les objets":
    titre_page = "🏛️ Recherche Globale"
elif selected_objet != "Tous les objets":
    titre_page = f"📂 Débat sur l'objet {selected_objet}"
else:
    titre_page = f"👤 Interventions de {selected_orateur}"

st.title(titre_page)

if df_filtered.empty:
    st.warning("Aucune intervention ne correspond à vos critères.")
    st.stop()

# 7. ANALYSE SÉMANTIQUE (PLACÉE EN HAUT)
# On affiche les stats AVANT la liste pour répondre à ta demande
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
        'cette', 'notre', 'votre', 'leur', 'leurs', 'entre', 'encore', 'alors', 'après', 'avant'
    ])

    col1, col2 = st.columns(2)

    with col1:
        all_text = " ".join(df_filtered['Texte'].tolist()).lower()
        words = re.findall(r'\b[a-zàâçéèêëîïôûùüÿñ]{4,}\b', all_text)
        meaningful_words = [w for w in words if w not in STOP_WORDS]
        word_counts = Counter(meaningful_words).most_common(20)

        if word_counts:
            df_words = pd.DataFrame(word_counts, columns=['Mot', 'Fréquence']).set_index('Mot')
            st.write("**Top 20 des mots les plus utilisés :**")
            st.bar_chart(df_words.sort_values('Fréquence', ascending=False), horizontal=True)
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

# 8. LISTE DES INTERVENTIONS (AVEC TOGGLE)
# Si recherche active : on affiche tout direct
if search_query:
    st.subheader(f"Résultats de recherche ({len(df_filtered)})")
    for index, row in df_filtered.iterrows():
        titre = f"📅 {row['Date']} | {row['Orateur']} | 📂 {row['Objet']}"
        with st.expander(titre):
            flags = 0 if case_sensitive else re.IGNORECASE
            texte = re.sub(f"({re.escape(search_query)})", r"**\1**", row['Texte'], flags=flags)
            st.markdown(texte)

# Si mode navigation : On cache la liste derrière une case à cocher
else:
    objets_uniques = df_filtered['Objet'].unique()

    # LE "MASTER SWITCH"
    st.subheader("Historique des interventions")
    show_details = st.checkbox(
        f"📂 Afficher le détail des interventions ({len(df_filtered)} interventions sur {len(objets_uniques)} objets)")

    if show_details:
        for objet in objets_uniques:
            subset = df_filtered[df_filtered['Objet'] == objet]
            titre_dossier = f"📂 Objet {objet} ({len(subset)} interventions)"

            with st.expander(titre_dossier):
                for _, row in subset.iterrows():
                    # --- EN-TÊTE AVEC DATE ET NOM DE L'ORATEUR ---
                    st.markdown(f"**📅 {row['Date']} | 👤 {row['Orateur']} ({row['Parti']})**")
                    st.write(row['Texte'])
                    st.divider()