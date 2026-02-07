import pdfplumber
import re
import pandas as pd
import os
import glob
import csv  # <--- IMPORTANT : Pour gérer les guillemets

# --- CONFIGURATION ---
PDF_FOLDER = "pdfs"

MOIS = {
    "01": "Janvier", "02": "Février", "03": "Mars", "04": "Avril",
    "05": "Mai", "06": "Juin", "07": "Juillet", "08": "Août",
    "09": "Septembre", "10": "Octobre", "11": "Novembre", "12": "Décembre"
}


def get_date_from_filename(filepath):
    filename = os.path.basename(filepath)
    match = re.search(r'PV_(\d{2})(\d{2})', filename, re.IGNORECASE)
    if match:
        year_short = match.group(1)
        month_digits = match.group(2)
        full_year = f"20{year_short}"
        month_name = MOIS.get(month_digits, month_digits)
        return f"{month_name} {full_year}"
    return "Date inconnue"


def extract_speeches(pdf_path):
    print(f"🔍 Analyse du fichier : {pdf_path}")
    current_date = get_date_from_filename(pdf_path)
    print(f"   📅 Date détectée : {current_date}")

    data = []
    current_speaker = None
    current_party = None
    current_object = "Ouverture / Divers"

    regex_strict = r'(?:^|\n)(M\.|Mme|Le président|La présidente|Le rapporteur|La rapporteur)\s*([^\n:]*)\s*:\s*[–-]?\s+'

    try:
        with pdfplumber.open(pdf_path) as pdf:
            start_page = 1 if len(pdf.pages) > 1 else 0

            for i, page in enumerate(pdf.pages[start_page:]):
                width = page.width
                height = page.height

                # --- 1. OBJETS ---
                bold_objects = []
                words = page.extract_words(extra_attrs=['fontname'])
                for w in words:
                    text = w['text']
                    font = w['fontname'].lower()
                    if 'bold' in font or 'bd' in font or 'gras' in font:
                        found_ids = re.findall(r'\d{2}\.\d{3}', text)
                        for obj_id in found_ids:
                            bold_objects.append({'id': obj_id, 'top': w['top']})
                bold_objects.sort(key=lambda x: x['top'])

                # --- 2. SLICING ---
                slice_points = [50] + [obj['top'] for obj in bold_objects] + [height - 50]

                for j in range(len(slice_points) - 1):
                    y_top = slice_points[j]
                    y_bottom = slice_points[j + 1]
                    if y_bottom - y_top < 10: continue
                    if j > 0: current_object = bold_objects[j - 1]['id']

                    bbox = (0, y_top, width, y_bottom)
                    cropped_slice = page.crop(bbox)
                    text = cropped_slice.extract_text()
                    if not text: continue

                    # --- 3. ORATEURS ---
                    text_clean = re.sub(r'(?m)^(M\.|Mme|Le|La)\s+([^:\n]+)\n\s*([^:\n]+):', r'\1 \2 \3:', text)
                    text_clean = re.sub(r',\s*\n\s*', ', ', text_clean)
                    text_clean = text_clean.replace('’', "'")

                    matches = list(re.finditer(regex_strict, text_clean))

                    if not matches:
                        if current_speaker:
                            append_entry(data, current_speaker, current_party, current_object, current_date, text)
                        continue

                    cursor = 0
                    for match in matches:
                        start_pos = match.start()
                        end_pos = match.end()

                        # Avant
                        text_before = text_clean[cursor:start_pos].strip()
                        if text_before and current_speaker:
                            if len(text_before) < 100 and (
                                    "occupe le siège" in text_before.lower() or "séance est levée" in text_before.lower()):
                                pass
                            else:
                                append_entry(data, current_speaker, current_party, current_object, current_date,
                                             text_before)

                        # Nouveau
                        titre = match.group(1)
                        raw_identity = match.group(2).strip()
                        if raw_identity == "" and "M." in titre: continue

                        current_speaker, current_party = parse_identity(titre, raw_identity)
                        cursor = end_pos

                    # Après
                    text_after = text_clean[cursor:].strip()
                    if text_after and current_speaker:
                        append_entry(data, current_speaker, current_party, current_object, current_date, text_after)

        cols = ['Date', 'Objet', 'Orateur', 'Parti', 'Texte']
        if not data: return pd.DataFrame(columns=cols)
        return pd.DataFrame(data)

    except Exception as e:
        print(f"❌ Erreur sur {pdf_path} : {e}")
        return pd.DataFrame(columns=['Date', 'Objet', 'Orateur', 'Parti', 'Texte'])


# --- HELPERS ---
def parse_identity(titre, raw_identity):
    identity = raw_identity.replace('\n', ' ').replace('’', "'").strip()
    if ("président" in titre.lower() or "rapporteur" in titre.lower()) and not identity: return titre, "Présidence"
    if "(" in identity and ")" in identity:
        m = re.match(r'(.+?)\s*\((.+?)\)', identity)
        if m: return f"{titre} {m.group(1).strip()}", m.group(2).strip()
    if "," in identity:
        parts = identity.split(',', 1)
        nom = parts[0].strip()
        suite = parts[1].strip()
        suite_lower = suite.lower()
        speaker = f"{titre} {nom}"
        party = "Conseil d'État"
        if "département" in suite_lower:
            m = re.search(r'(département.*)', suite, re.IGNORECASE)
            party = m.group(1) if m else suite
        elif "chancell" in suite_lower:
            party = "Chancellerie d'État"
        elif "président" in suite_lower and "état" in suite_lower:
            party = "Présidence CE"
        elif "conseil" in suite_lower and "état" in suite_lower:
            party = "Conseil d'État"
        elif "président" in suite_lower:
            party = "Présidence"
        return speaker, party
    if "président" in titre.lower(): return f"{titre} {identity}", "Présidence"
    return f"{titre} {identity}", "Indéterminé"


def append_entry(data, speaker, party, objet, date, text):
    if len(text) < 3 or "Vote n°" in text or "Résultat du vote" in text: return
    if text.isupper() and len(text) < 50: return
    data.append({'Date': date, 'Objet': objet, 'Orateur': speaker, 'Parti': party, 'Texte': text})


# --- MAIN BLOCK ---
if __name__ == "__main__":
    pdf_files = glob.glob(os.path.join(PDF_FOLDER, "*.pdf"))
    if not pdf_files and os.path.exists("bulletin_test.pdf"): pdf_files = ["bulletin_test.pdf"]

    if not pdf_files:
        print("❌ Aucun fichier PDF trouvé !")
        exit()

    all_dataframes = []
    print(f"🚀 Traitement de {len(pdf_files)} fichiers...")

    for pdf_file in pdf_files:
        df_temp = extract_speeches(pdf_file)
        if not df_temp.empty:
            all_dataframes.append(df_temp)
            print(f"   ✅ {len(df_temp)} entrées.")

    if all_dataframes:
        print("\n🔄 Fusion...")
        df_total = pd.concat(all_dataframes, ignore_index=True)

        df_total['groupe_id'] = (df_total['Orateur'] != df_total['Orateur'].shift()).cumsum() + \
                                (df_total['Objet'] != df_total['Objet'].shift()).cumsum() + \
                                (df_total['Date'] != df_total['Date'].shift()).cumsum()

        df_final = df_total.groupby(['groupe_id', 'Orateur', 'Parti', 'Objet', 'Date'])['Texte'].apply(
            lambda x: " ".join(x)).reset_index()
        df_final['Texte'] = df_final['Texte'].str.replace('\n', ' ', regex=False)
        df_final = df_final.drop(columns=['groupe_id'])

        output_file = "discours_grand_conseil_complet.csv"

        # --- C'EST ICI QUE LA MAGIE OPÈRE (QUOTING) ---
        df_final.to_csv(output_file, index=False, encoding='utf-8-sig', quoting=csv.QUOTE_ALL)
        # ----------------------------------------------

        print(f"🎉 Succès ! Fichier généré : '{output_file}' ({len(df_final)} lignes)")
    else:
        print("❌ Aucune donnée.")