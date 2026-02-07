import streamlit as st
import pandas as pd
import re
from collections import Counter
import os
from datetime import datetime
import altair as alt
from textblob import Blobber
from textblob_fr import PatternTagger, PatternAnalyzer
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.decomposition import LatentDirichletAllocation
import spacy

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
DATE_BASCULE = datetime(2025, 5, 1) # Date de début de la nouvelle législature

# Utilisation de checkbox (cases à cocher) au lieu du multiselect
check_actuelle = st.sidebar.checkbox("Législature Actuelle (2025-2029)", value=True)
check_precedente = st.sidebar.checkbox("Législature Précédente (2021-2025)", value=False)

if not check_actuelle and not check_precedente:
    st.warning("Veuillez cocher au moins une législature.")
    st.stop()

# Filtrage par date
mask_leg = pd.Series([False] * len(df_full), index=df_full.index)

if check_actuelle:
    mask_leg = mask_leg | (df_full['Date_dt'] >= DATE_BASCULE)
if check_precedente:
    mask_leg = mask_leg | (df_full['Date_dt'] < DATE_BASCULE)

df = df_full[mask_leg] # df contient maintenant uniquement les données choisies

if df.empty:
    st.warning("Aucune donnée trouvée pour la période sélectionnée.")
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
legs_selected = []
if check_actuelle: legs_selected.append("2025+")
if check_precedente: legs_selected.append("2021-25")
leg_info = " & ".join(legs_selected)

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

# ==========================================
# 7. ANALYSE SÉMANTIQUE (CASES À COCHER + SPACY)
# ==========================================
import spacy
from collections import Counter


@st.cache_resource
def load_spacy_model():
    try:
        if not spacy.util.is_package("fr_core_news_sm"):
            spacy.cli.download("fr_core_news_sm")
        return spacy.load("fr_core_news_sm")
    except Exception as e:
        return None


# TA LISTE NOIRE (Ajoute des mots ici pour les cacher)
CUSTOM_STOP_WORDS = {
    'monsieur', 'madame', 'président', 'présidente', 'député', 'députée',
    'conseiller', 'conseillère', 'état', 'grand', 'conseil', 'parole',
    'merci', 'voix', 'vote', 'voter', 'année', 'années', 'fois', 'jour',
    'aujourd', 'hui', 'chose', 'question', 'réponse', 'projet', 'loi',
    'rapport', 'commission', 'groupe', 'nom', 'objet', 'alinéa', 'article',
    'chers', 'chères', 'collègues', 'canton', 'république', 'neuchâtel'
}

if not df_filtered.empty:
    nlp = load_spacy_model()

    st.subheader("📊 Analyse du vocabulaire")

    col1, col2 = st.columns(2)

    # --- COLONNE GAUCHE : LES FRÉQUENCES ---
    with col1:
        st.write("### 🏆 Top des Mots")

        # SÉLECTEUR AVEC CASES À COCHER (CHECKBOX)
        st.caption("Quels types de mots inclure ?")
        c_chk1, c_chk2, c_chk3, c_chk4 = st.columns(4)

        check_noun = c_chk1.checkbox("Noms", value=True)
        check_adj = c_chk2.checkbox("Adj.", value=True)
        check_verb = c_chk3.checkbox("Verbes", value=False)
        check_propn = c_chk4.checkbox("Noms Pr.", value=False)  # Noms Propres

        # Construction de la liste des tags SpaCy
        selected_tags = []
        if check_noun: selected_tags.append("NOUN")
        if check_adj: selected_tags.append("ADJ")
        if check_verb: selected_tags.append("VERB")
        if check_propn: selected_tags.append("PROPN")

        if nlp and selected_tags:
            # On prend un échantillon du texte
            full_text = " ".join(df_filtered['Texte'].tolist())[:150000]

            with st.spinner("Analyse..."):
                doc = nlp(full_text)
                mots_propres = []

                for token in doc:
                    mot_racine = token.lemma_.lower()

                    if token.pos_ in selected_tags:
                        if not token.is_stop and not token.is_punct and len(mot_racine) > 2:
                            if mot_racine not in CUSTOM_STOP_WORDS:
                                mots_propres.append(mot_racine)

                word_counts = Counter(mots_propres).most_common(20)

            if word_counts:
                df_words = pd.DataFrame(word_counts, columns=['Mot', 'Fréquence'])

                c = alt.Chart(df_words).mark_bar().encode(
                    x='Fréquence',
                    y=alt.Y('Mot', sort='-x'),
                    tooltip=['Mot', 'Fréquence']
                )
                st.altair_chart(c, use_container_width=True)
            else:
                st.info("Aucun mot trouvé avec ces filtres.")
        else:
            st.warning("Cochez au moins une case ci-dessus.")

    # --- COLONNE DROITE : LE STYLE ---
    with col2:
        if selected_orateur == "Tous les membres":
            st.write("**Répartition par Parti :**")
            st.bar_chart(df_filtered['Parti'].value_counts())
        else:
            avg_len = df_filtered['Texte'].str.len().mean()
            st.metric("Longueur moyenne", f"{int(avg_len)} caractères")
            st.divider()

            st.write("### 🧠 Analyse du Ton")
            from textblob import Blobber
            from textblob_fr import PatternTagger, PatternAnalyzer

            tb = Blobber(pos_tagger=PatternTagger(), analyzer=PatternAnalyzer())

            blob = tb(full_text[:5000])  # On réutilise un bout du texte
            subjectivity = blob.sentiment[1]
            score_percent = int(subjectivity * 100)

            if score_percent < 15:
                label, icon = "Le Factuel", "🤖"
            elif score_percent < 30:
                label, icon = "L'Analyste", "⚖️"
            else:
                label, icon = "Le Passionné", "❤️"

            st.metric(label="Style détecté", value=f"{icon} {label}", delta=f"{score_percent}% Subjectivité")
            st.progress(min(score_percent * 2.5 / 100, 1.0))

    st.markdown("---")

# ==========================================
# 8 LA BOUSSOLE POLITIQUE (CORRIGÉE) 🧭
# ==========================================
if not df_filtered.empty:
    st.markdown("---")
    st.subheader("🧭 La Boussole Politique")
    st.caption("Positionnement relatif calculé sur le vocabulaire (centré sur la moyenne du conseil).")

    # 1. LISTES AFFINÉES (POUR ÉVITER LE BIAIS "RÉGULATEUR")
    # J'ai retiré "loi", "canton", "état", "commune" qui polluaient tout.

    # AXE X : ÉCONOMIE (Gauche vs Droite Éco)
    mots_regulateur = [
        'subvention', 'aide', 'prestation', 'social', 'protection', 'solidaire',
        'redistribution', 'taxe', 'impôt', 'contrainte', 'interdiction', 'service public',
        'salarié', 'syndicat', 'précarité', 'soutien', 'bénéficiaire'
    ]
    mots_liberale = [
        'liberté', 'privé', 'entreprise', 'pme', 'marché', 'concurrence',
        'initiative', 'baisse', 'moins', 'responsabilité', 'coût', 'efficience',
        'efficacité', 'dérégulation', 'attractivité', 'fiscalité', 'investisseur',
        'frein', 'charge', 'charges', 'dynamisme'
    ]

    # AXE Y : SOCIÉTÉ (Conservateur vs Progressiste)
    mots_progressiste = [
        'climat', 'environnement', 'durabilité', 'écologie', 'biodiversité',
        'transition', 'égalité', 'genre', 'ouverture', 'diversité', 'inclusion',
        'culture', 'innovation', 'réforme', 'monde', 'europe', 'accueil'
    ]
    mots_conservateur = [
        'sécurité', 'ordre', 'police', 'armée', 'tradition', 'patrimoine',
        'histoire', 'racines', 'famille', 'suisse', 'souveraineté', 'indépendance',
        'stabilité', 'prudence', 'rigueur', 'frontière', 'identit', 'héritage'
    ]


    # 2. FONCTION DE CALCUL (Simple compte)
    def calculate_raw_score(text):
        t = str(text).lower()
        # On utilise une petite astuce pour éviter de compter "état" dans "état civil"
        # Mais pour l'instant, le compte simple suffit si les listes sont bonnes
        c_reg = sum(t.count(w) for w in mots_regulateur)
        c_lib = sum(t.count(w) for w in mots_liberale)
        c_prog = sum(t.count(w) for w in mots_progressiste)
        c_cons = sum(t.count(w) for w in mots_conservateur)

        total = max(len(t.split()), 1)  # Évite division par 0

        # Score brut (Densité)
        raw_x = (c_lib - c_reg) / total * 10000
        raw_y = (c_prog - c_cons) / total * 10000

        return raw_x, raw_y


    # 3. CALCUL GLOBAL ET NORMALISATION (LE SECRET POUR QUE ÇA MARCHE)
    @st.cache_data
    def get_centered_positions(df_source):
        # A. On calcule les scores bruts pour tout le monde
        data = []
        grouped = df_source.groupby('Orateur')['Texte'].apply(lambda x: " ".join(x)).reset_index()

        for index, row in grouped.iterrows():
            if row['Orateur'] in ["Inconnu", "Tous les membres"]: continue
            rx, ry = calculate_raw_score(row['Texte'])

            # On récupère le parti (le plus fréquent pour cet orateur)
            partis = df_source[df_source['Orateur'] == row['Orateur']]['Parti']
            parti_top = partis.value_counts().idxmax() if not partis.empty else "Indéterminé"

            data.append({'Orateur': row['Orateur'], 'Parti': parti_top, 'Raw_X': rx, 'Raw_Y': ry})

        df_res = pd.DataFrame(data)

        if df_res.empty: return df_res

        # B. ON CENTRE LE GRAPHIQUE (Moyenne = 0)
        # Ça force les points à s'étaler autour du centre
        mean_x = df_res['Raw_X'].mean()
        mean_y = df_res['Raw_Y'].mean()

        df_res['X'] = df_res['Raw_X'] - mean_x
        df_res['Y'] = df_res['Raw_Y'] - mean_y

        return df_res


    compass_df = get_centered_positions(df)

    # 4. AFFICHAGE DU GRAPHIQUE
    if not compass_df.empty:
        # Configuration visuelle
        compass_df['Color'] = 'Autres'
        compass_df['Size'] = 60
        compass_df['Opacity'] = 0.4

        if selected_orateur != "Tous les membres":
            # Mise en évidence
            mask = compass_df['Orateur'] == selected_orateur
            compass_df.loc[mask, 'Color'] = 'Sélectionné'
            compass_df.loc[mask, 'Size'] = 200
            compass_df.loc[mask, 'Opacity'] = 1.0

        # Tooltip riche
        tooltip_info = [
            alt.Tooltip('Orateur', title='Nom'),
            alt.Tooltip('Parti', title='Parti'),
            alt.Tooltip('X', format='.1f', title='Score Eco'),
            alt.Tooltip('Y', format='.1f', title='Score Soc')
        ]

        # Chart principal
        points = alt.Chart(compass_df).mark_circle().encode(
            x=alt.X('X', title='← Régulateur | Libéral →'),
            y=alt.Y('Y', title='↓ Conservateur | Progressiste ↑'),
            color=alt.Color('Color', scale=alt.Scale(domain=['Autres', 'Sélectionné'], range=['gray', 'red']),
                            legend=None),
            size=alt.Size('Size', legend=None),
            opacity=alt.Opacity('Opacity', legend=None),
            tooltip=tooltip_info
        )

        # Lignes médianes (Zéro)
        rules = alt.Chart(pd.DataFrame({'z': [0]})).mark_rule(color='black', strokeDash=[2, 2], opacity=0.3)
        rule_x = rules.encode(x='z')
        rule_y = rules.encode(y='z')

        # Texte des Partis (Optionnel : affiche le nom du parti au centre de gravité du parti)
        # On peut l'ajouter si tu veux, mais ça charge le graph.

        final_chart = (points + rule_x + rule_y).properties(
            height=500,
            title="Positionnement relatif (Centré)"
        ).interactive()

        st.altair_chart(final_chart, use_container_width=True)

        # Légende explicative
        st.info("""
        💡 **Comment lire ce graphique ?**
        Le point (0,0) représente la **moyenne** du Grand Conseil.
        - Un point à **droite** signifie "Plus libéral que la moyenne".
        - Un point en **haut** signifie "Plus progressiste que la moyenne".
        """)

#8 : LISTE INTERVENTIONS
st.markdown("---")
st.header("📝 Liste des interventions")

if search_query:
    # CAS 1 : RECHERCHE ACTIVE
    # On affiche tout directement pour voir les résultats
    st.subheader(f"Résultats trouvés : {len(df_filtered)}")

    for index, row in df_filtered.iterrows():
        titre = f"📅 {row['Date']} | {row['Orateur']} | 📂 {row['Objet']}"
        with st.expander(titre):
            # Surlignage du mot-clé trouvé
            flags = 0 if case_sensitive else re.IGNORECASE
            # On échappe la query pour éviter les erreurs regex s'il y a des parenthèses
            safe_query = re.escape(search_query)
            texte_surligne = re.sub(f"({safe_query})", r"**\1**", row['Texte'], flags=flags)

            st.markdown(f"**Parti :** {row['Parti']}")
            st.markdown(texte_surligne)

else:
    # CAS 2 : NAVIGATION NORMALE
    # On met une case à cocher pour ne pas polluer l'écran si on veut juste voir les stats
    objets_uniques = df_filtered['Objet'].unique()

    label_checkbox = f"📂 Afficher le détail des textes ({len(df_filtered)} interventions)"
    show_details = st.checkbox(label_checkbox, value=False)

    if show_details:
        # On regroupe par Objet pour que ce soit plus propre
        for objet in objets_uniques:
            subset = df_filtered[df_filtered['Objet'] == objet]
            # On trie les interventions par date/ordre d'apparition
            subset = subset.sort_index()

            titre_dossier = f"📂 {objet} ({len(subset)} interventions)"

            with st.expander(titre_dossier):
                for _, row in subset.iterrows():
                    st.markdown(f"**📅 {row['Date']} | 👤 {row['Orateur']} ({row['Parti']})**")
                    st.write(row['Texte'])
                    st.divider()
# ==========================================
# 9. CHRONOLOGIE : L'ÉVOLUTION COMPARÉE 📈
# ==========================================
if not df_filtered.empty:
    st.markdown("---")
    st.subheader("📈 Chronologie des débats")
    st.caption("Comparez l'utilisation de deux termes dans le temps.")

    # 1. SÉLECTEURS DE MOTS (COTE A COTE)
    col_search_1, col_search_2 = st.columns(2)

    # Suggestions intelligentes
    all_words = " ".join(df_filtered['Texte'].tolist()).lower().split()
    suggestions = [m for m in all_words if len(m) > 4]
    top_suggestions = [m[0] for m in Counter(suggestions).most_common(5)]
    default_word = top_suggestions[0] if top_suggestions else "budget"

    with col_search_1:
        mot1 = st.text_input("Mot 1 (Ligne Bleue)", value=default_word)
    with col_search_2:
        mot2 = st.text_input("Mot 2 (Ligne Orange - Optionnel)", placeholder="Ex: dépense")

    if mot1:
        # 2. PRÉPARATION DES DONNÉES
        df_chrono = df_filtered.copy()

        # Groupement par mois
        df_chrono['Mois'] = df_chrono['Date_dt'].dt.to_period('M').astype(str)

        # Comptage du Mot 1
        df_chrono[mot1] = df_chrono['Texte'].str.lower().str.count(re.escape(mot1.lower()))

        # Comptage du Mot 2 (si présent)
        cols_to_keep = ['Mois', mot1]
        if mot2:
            df_chrono[mot2] = df_chrono['Texte'].str.lower().str.count(re.escape(mot2.lower()))
            cols_to_keep.append(mot2)

        # On fait la somme par mois
        evolution = df_chrono.groupby('Mois')[cols_to_keep[1:]].sum().reset_index()

        # 3. TRANSFORMATION POUR ALTAIR (Format "Long")
        # Altair a besoin que les colonnes soient "fondues" pour faire des couleurs automatiques
        evolution_melted = evolution.melt('Mois', var_name='Mot', value_name='Mentions')

        # 4. VISUALISATION
        if not evolution_melted.empty:
            chart = alt.Chart(evolution_melted).mark_line(point=True).encode(
                x=alt.X('Mois', title='Temps', axis=alt.Axis(labelAngle=-45)),
                y=alt.Y('Mentions', title='Nombre d\'occurrences'),
                color=alt.Color('Mot', title='Termes'),  # Légende automatique
                tooltip=['Mois', 'Mot', 'Mentions']
            ).properties(
                height=400,
                title=f"Comparaison : {mot1} vs {mot2}" if mot2 else f"Évolution de {mot1}"
            ).interactive()

            st.altair_chart(chart, use_container_width=True)
        else:
            st.warning("Aucune donnée pour cette période.")