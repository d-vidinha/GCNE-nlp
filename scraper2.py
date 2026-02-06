import pdfplumber
import re
import pandas as pd

PDF_PATH = "bulletin_test.pdf"


def extract_speeches(pdf_path):
    print(f"🔍 Analyse du fichier : {pdf_path}")
    data = []

    current_speaker = None
    current_party = None

    # --- REGEX STRICTE CORRIGÉE ---
    # 1. (?:^|\n) -> Début de ligne
    # 2. (M\.|Mme|...) -> Le Titre
    # 3. \s* -> Espaces optionnels
    # 4. ([^\n:]*) -> LE NOM (Note l'étoile * au lieu du +)
    #    Cela veut dire : "Prends le nom s'il y en a un, sinon prends rien (vide)"
    #    C'est ça qui permet de capter "Le président :" tout seul !
    regex_strict = r'(?:^|\n)(M\.|Mme|Le président|La présidente|Le rapporteur|La rapporteur)\s*([^\n:]*)\s*:\s*[–-]?\s+'

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages[1:]):

                # --- ROGNAGE ---
                height = page.height
                width = page.width
                bbox = (0, 50, width, height - 50)
                cropped_page = page.crop(bbox)
                text = cropped_page.extract_text()

                if not text: continue

                # --- 1. SUPER-COLLE (Pour les noms coupés sur 2 lignes) ---
                # On recolle les titres suivis de texte, saut de ligne, texte, deux points
                text_clean = re.sub(r'(?m)^(M\.|Mme|Le|La)\s+([^:\n]+)\n\s*([^:\n]+):', r'\1 \2 \3:', text)

                # --- 2. Correctif virgule ---
                text_clean = re.sub(r',\s*\n\s*', ', ', text_clean)
                # -----------------------------

                matches = list(re.finditer(regex_strict, text_clean))

                if not matches:
                    if current_speaker:
                        append_entry(data, current_speaker, current_party, text)
                    continue

                cursor = 0
                for match in matches:
                    start_pos = match.start()
                    end_pos = match.end()

                    # TEXTE AVANT
                    text_before = text_clean[cursor:start_pos].strip()
                    if text_before and current_speaker:
                        # Sécurité anti-bruit ("occupe le siège", "La séance est levée", etc.)
                        if len(text_before) < 100 and (
                                "occupe le siège" in text_before.lower() or "séance est levée" in text_before.lower()):
                            pass
                        else:
                            append_entry(data, current_speaker, current_party, text_before)

                    # NOUVEAU SPEAKER
                    titre = match.group(1)
                    raw_identity = match.group(2).strip()  # Peut être vide maintenant !

                    # On vérifie qu'on n'a pas capté un truc vide bizarre genre "M. :"
                    if raw_identity == "" and "M." in titre:
                        # Faux positif probable, on ignore et on traite comme du texte normal
                        continue

                    current_speaker, current_party = parse_identity(titre, raw_identity)
                    cursor = end_pos

                # TEXTE APRÈS
                text_after = text_clean[cursor:].strip()
                if text_after and current_speaker:
                    append_entry(data, current_speaker, current_party, text_after)

        # --- FUSION FINALE ---
        df_raw = pd.DataFrame(data)
        if df_raw.empty: return df_raw

        df_raw['groupe_id'] = (df_raw['Orateur'] != df_raw['Orateur'].shift()).cumsum()
        df_final = df_raw.groupby(['groupe_id', 'Orateur', 'Parti'])['Texte'].apply(lambda x: " ".join(x)).reset_index()
        df_final['Texte'] = df_final['Texte'].str.replace('\n', ' ', regex=False)

        return df_final.drop(columns=['groupe_id'])

    except Exception as e:
        print(f"❌ Erreur : {e}")
        return pd.DataFrame()


# --- FONCTION D'ANALYSE MISE À JOUR ---
def parse_identity(titre, raw_identity):
    # Nettoyage
    identity = raw_identity.replace('\n', ' ').strip()
    identity_lower = identity.lower()

    # 1. CAS PRÉSIDENT DU GRAND CONSEIL (Le président de séance)
    # Si le titre est juste "Le président" ou "La présidente" (sans nom après souvent)
    if "président" in titre.lower() or "rapporteur" in titre.lower():
        if not identity:
            return titre, "Présidence"
        else:
            return f"{titre} {identity}", "Présidence"

    # 2. CAS CONSEIL D'ÉTAT (Présence d'une virgule)
    if "," in identity:
        parts = identity.split(',', 1)
        nom = parts[0].strip()
        suite = parts[1].strip()  # Ex: "conseiller d'État, chef du Département..."
        suite_lower = suite.lower()

        speaker = f"{titre} {nom}"

        # --- NOUVELLE LOGIQUE DE PRIORITÉ ---

        # A. D'abord on cherche un DÉPARTEMENT (C'est le plus précis pour les stats)
        if "département" in suite_lower:
            # On cherche tout ce qui commence par "Département..."
            m = re.search(r'(département.*)', suite, re.IGNORECASE)
            # Si on trouve, on prend. Sinon on garde la suite entière.
            party = m.group(1) if m else suite

        # B. Ensuite la CHANCELLERIE
        elif "chancell" in suite_lower:
            party = "Chancellerie d'État"

        # C. Ensuite la PRÉSIDENCE CE (Seulement si pas de département !)
        # On fait attention d'exclure "vice-président" pour ne pas faux-positiver
        elif "président du Conseil" or "présidente du Conseil" in suite_lower and "vice" not in suite_lower:
            party = "Présidence CE"

        # D. Sinon : CONSEIL D'ÉTAT (Générique)
        else:
            party = "Conseil d'État"

        return speaker, party

    # 3. CAS DÉPUTÉ (Parenthèses)
    if "(" in identity and ")" in identity:
        m = re.match(r'(.+?)\s*\((.+?)\)', identity)
        if m:
            return f"{titre} {m.group(1).strip()}", m.group(2).strip()

    # 4. CAS PAR DÉFAUT
    return f"{titre} {identity}", "Indéterminé"


# --- FONCTION D'AJOUT SIMPLE ---
def append_entry(data, speaker, party, text):
    # Filtre anti-bruit
    if len(text) < 3 or "Vote n°" in text or "Résultat du vote" in text:
        return
    if text.isupper() and len(text) < 50:  # Titres majuscules
        return

    data.append({
        'Orateur': speaker,
        'Parti': party,
        'Texte': text
    })


# --- EXECUTION ---
if __name__ == "__main__":
    df = extract_speeches(PDF_PATH)

    if not df.empty:
        # --- CORRECTION EXCEL : On remplace les sauts de ligne par des espaces ---
        df['Texte'] = df['Texte'].str.replace('\n', ' ', regex=False)
        # -------------------------------------------------------------------------

        # On sauvegarde
        output_file = "discours_grand_conseil.csv"
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"💾 Sauvegardé dans '{output_file}' (Format optimisé pour Excel)")
    else:
        print("⚠️ Aucune donnée extraite.")