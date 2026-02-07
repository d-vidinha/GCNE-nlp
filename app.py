import streamlit as st
import pandas as pd
import re
from collections import Counter

# 1. CONFIGURATION DE LA PAGE
st.set_page_config(page_title="Grand Conseil Explorer", page_icon="🏛️", layout="wide")


# 2. CHARGEMENT DES DONNÉES (ROBUSTE)
@st.cache_data
def load_data():
    try:
        # On force la lecture de l'Objet en Texte (str) pour garder les zéros (ex: 25.200)
        df = pd.read_csv("discours_grand_conseil_complet.csv", dtype={'Objet': str})

        # Nettoyage et sécurisation
        df['Texte'] = df['Texte'].fillna("").astype(str)
        if 'Date' not in df.columns: df['Date'] = "Date inconnue"
        if 'Parti' not in df.columns: df['Parti'] = "Indéterminé"
        if 'Orateur' not in df.columns: df['Orateur'] = "Inconnu"

        # Suppression des espaces parasites
        df['Parti'] = df['Parti'].astype(str).str.strip()
        df['Orateur'] = df['Orateur'].astype(str).str.strip()
        df['Objet'] = df['Objet'].astype(str).str.strip()

        return df

    except Exception as e:
        st.error(f"❌ Erreur critique de lecture du CSV : {e}")
        return pd.DataFrame()


# Chargement initial
df = load_data()

if df.empty:
    st.warning("Le fichier CSV est vide ou introuvable.")
    st.stop()

# 3. BARRE LATÉRALE (FILTRES)
st.sidebar.header("🔍 Filtres")

# --- A. FILTRE ORATEUR ---
liste_orateurs = ["Tous les membres"] + sorted(df['Orateur'].unique())
selected_orateur = st.sidebar.selectbox("👤 Choisir un orateur", liste_orateurs)

# --- B. FILTRE OBJET (NOUVEAU !) ---
# On crée la liste des objets triés
liste_objets = ["Tous les objets"] + sorted(df['Objet'].unique())
selected_objet = st.sidebar.selectbox("📂 Choisir un objet", liste_objets)

# --- C. BARRE DE RECHERCHE ---
st.sidebar.markdown("---")
search_query = st.sidebar.text_input("🔎 Rechercher un mot-clé")
case_sensitive = st.sidebar.checkbox("Respecter la casse", value=False)

# 4. APPLICATION DES FILTRES (LOGIQUE EN CASCADE)
df_filtered = df.copy()

# Étape 1 : Filtrer par Orateur
if selected_orateur != "Tous les membres":
    df_filtered = df_filtered[df_filtered['Orateur'] == selected_orateur]
else:
    # Si on regarde tout le monde, on cache le bruit procédural du Président
    # (Sauf si on cherche spécifiquement "Présidence" dans la recherche textuelle, mais restons simples)
    df_filtered = df_filtered[df_filtered['Parti'] != 'Présidence']

# Étape 2 : Filtrer par Objet
if selected_objet != "Tous les objets":
    df_filtered = df_filtered[df_filtered['Objet'] == selected_objet]

# Étape 3 : Filtrer par Mot-clé (Recherche textuelle)
if search_query:
    if case_sensitive:
        mask = df_filtered['Texte'].str.contains(search_query, regex=False)
    else:
        mask = df_filtered['Texte'].str.contains(search_query, case=False, regex=False)
    df_filtered = df_filtered[mask]

# 5. INFO SIDEBAR (Mise à jour dynamique)
st.sidebar.markdown("---")
st.sidebar.markdown(f"**Interventions trouvées :** {len(df_filtered)}")

if selected_orateur != "Tous les membres" and not df_filtered.empty:
    parti = df_filtered['Parti'].iloc[0]  # On prend le premier trouvé
    st.sidebar.markdown(f"**Parti :** {parti}")

# 6. TITRE DE LA PAGE
if selected_orateur == "Tous les membres" and selected_objet == "Tous les objets":
    titre_page = "🏛️ Recherche Globale"
elif selected_objet != "Tous les objets":
    titre_page = f"📂 Débat sur l'objet {selected_objet}"
    if selected_orateur != "Tous les membres":
        titre_page += f" ({selected_orateur})"
else:
    titre_page = f"👤 Interventions de {selected_orateur}"

st.title(titre_page)

# 7. AFFICHAGE DES RÉSULTATS
if df_filtered.empty:
    st.warning("Aucune intervention ne correspond à vos critères.")
else:
    # Si on affiche beaucoup de résultats sans recherche précise, on limite l'affichage initial
    if search_query == "" and len(df_filtered) > 50:
        st.caption(f"⚠️ Affichage des 50 dernières interventions sur {len(df_filtered)}.")
        display_df = df_filtered.tail(50).iloc[::-1]  # Inverser pour avoir les récents en haut
    else:
        # Sinon on affiche tout (ou si c'est filtré par objet/orateur)
        display_df = df_filtered.iloc[::-1]  # Toujours du plus récent au plus ancien

    for index, row in display_df.iterrows():
        # Icône dynamique
        icon = "🏛️" if "Conseil d'État" in row['Parti'] or "Présidence CE" in row['Parti'] else "👤"

        # Titre de l'expander
        titre_expander = f"{icon} {row['Orateur']} ({row['Parti']}) | 📅 {row['Date']} | 📂 {row['Objet']}"

        with st.expander(titre_expander):
            texte_final = row['Texte']

            # Surlignage
            if search_query:
                flags = 0 if case_sensitive else re.IGNORECASE
                texte_final = re.sub(
                    f"({re.escape(search_query)})",
                    r"<mark style='background-color: yellow; color: black'>\1</mark>",
                    texte_final,
                    flags=flags
                )
                st.markdown(texte_final, unsafe_allow_html=True)
            else:
                st.write(texte_final)

# 8. STATISTIQUES SÉMANTIQUES (Analyses des mots)
if not df_filtered.empty and (selected_orateur != "Tous les membres" or selected_objet != "Tous les objets"):
    st.markdown("---")
    st.subheader("📊 Analyse du vocabulaire")

    # --- LISTE DES MOTS À EXCLURE (STOP WORDS) ---
    # Mots grammaticaux courants + Mots de politesse parlementaire
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
        # Mots parlementaires "vides" de sens politique
        'monsieur', 'madame', 'messieurs', 'mesdames', 'président', 'présidente',
        'député', 'députée', 'conseiller', 'conseillère', 'état', 'grand', 'conseil',
        'rapport', 'commission', 'projet', 'loi', 'article', 'articles', 'alinéa',
        'vote', 'voter', 'voix', 'majorité', 'minorité', 'parole', 'merci', 'chose',
        'question', 'réponse', 'dire', 'dis', 'dit', 'faut', 'fois', 'année', 'années', 'groupe',
        'décret', 'libéral', 'parti', 'socialiste', 'vertpop', "vert'libéral", 'libéral-radical',
        'UDC','centre'
    ])

    col1, col2 = st.columns(2)

    with col1:
        # A. DÉTECTION DES MOTS CLÉS
        # 1. On colle tous les textes ensemble
        all_text = " ".join(df_filtered['Texte'].tolist()).lower()

        # 2. On nettoie (on ne garde que les lettres, on vire la ponctuation)
        # On ne garde que les mots de plus de 3 lettres
        words = re.findall(r'\b[a-zàâçéèêëîïôûùüÿñ]{4,}\b', all_text)

        # 3. On filtre les stop words
        meaningful_words = [w for w in words if w not in STOP_WORDS]

        # 4. On compte
        word_counts = Counter(meaningful_words).most_common(20)  # Top 15

        # 5. On affiche
        if word_counts:
            df_words = pd.DataFrame(word_counts, columns=['Mot', 'Fréquence']).set_index('Mot')
            st.write("**Top 20 des mots les plus utilisés :**")
            # Inversion du graph pour avoir le mot le plus fréquent en haut
            st.bar_chart(df_words.sort_values('Fréquence', ascending=False), horizontal=True)
        else:
            st.info("Pas assez de données pour l'analyse sémantique.")

    with col2:
        # B. RÉPARTITION PAR PARTI (Seulement si on regarde un Objet ou Recherche globale)
        if selected_orateur == "Tous les membres":
            st.write("**Répartition des interventions par Parti :**")
            st.bar_chart(df_filtered['Parti'].value_counts())

        # C. LONGUEUR DES INTERVENTIONS (Si on regarde un Orateur)
        else:
            avg_len = df_filtered['Texte'].str.len().mean()
            st.metric("Longueur moyenne intervention", f"{int(avg_len)} caractères")

            # Bonus : Total mots
            total_words = len(meaningful_words)
            st.metric("Richesse lexicale (mots significatifs)", f"{total_words}")