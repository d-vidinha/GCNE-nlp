import pdfplumber
import re
import pandas as pd

# --- CONFIGURATION ---
# Remplace ce chemin par le vrai chemin d'un PDF que tu as téléchargé
PDF_PATH = "bulletin_test.pdf"


def extract_speeches(pdf_path):
    print(f"🔍 Analyse du fichier : {pdf_path}...")
    data = []

    current_speaker = None
    current_party = None
    current_text = []

    # --- LES 3 MOTIFS (REGEX) ---

    # CAS 1 : Député standard -> M. Nom (PARTI) :
    regex_depute = r'^(M\.|Mme)\s+(.+?)\s*\((.+?)\)\s*:\s*.?\s*(.*)'

    # CAS 2 : Présidence -> Le président : (ou La présidente)
    # On capture le texte après les deux points
    regex_president = r'^(Le président|La présidente)\s*:\s*.?\s*(.*)'

    # CAS 3 : Conseil d'État -> M. Nom, conseiller... :
    # On capture le Nom (avant la virgule) et le Titre (après la virgule)
    regex_ce = r'^(M\.|Mme)\s+([^,]+),\s+(.+?)\s*:\s*.?\s*(.*)'

    try:
        with pdfplumber.open(pdf_path) as pdf:
            # On ignore la page 1 (couverture)
            for i, page in enumerate(pdf.pages[1:]):

                # --- ROGNAGE (Crop) ---
                height = page.height
                width = page.width
                bbox = (0, 60, width, height - 50)
                cropped_page = page.crop(bbox)
                text = cropped_page.extract_text()
                # -----------------------

                if not text: continue

                lines = text.split('\n')
                i = 0
                while i < len(lines):
                    line = lines[i].strip()

                    # 1. On teste si la ligne seule matche déjà
                    match_depute = re.match(regex_depute, line)
                    match_president = re.match(regex_president, line)
                    match_ce = re.match(regex_ce, line)

                    # 2. LOGIQUE DE RÉPARATION (Si la ligne seule ne matche pas)
                    is_merged_line = False
                    if not (match_depute or match_president or match_ce) and i + 1 < len(lines):
                        # On tente de coller avec la ligne suivante
                        next_line = lines[i + 1].strip()
                        combined_line = f"{line} {next_line}"

                        # On re-teste avec la version collée
                        # On ne teste que le Conseil d'État (souvent long) et Député (parfois long)
                        if re.match(regex_ce, combined_line):
                            line = combined_line
                            match_ce = re.match(regex_ce, line)  # Mise à jour du match
                            is_merged_line = True
                        elif re.match(regex_depute, combined_line):
                            line = combined_line
                            match_depute = re.match(regex_depute, line)
                            is_merged_line = True

                    # SI C'EST UN DÉPUTÉ
                    if match_depute:
                        save_previous(data, current_speaker, current_party, current_text)

                        current_speaker = f"{match_depute.group(1)} {match_depute.group(2).strip()}"
                        current_party = match_depute.group(3).strip()
                        current_text = [match_depute.group(4)] if match_depute.group(4) else []

                    # SI C'EST LE PRÉSIDENT (Cas simple)
                    elif match_president:
                        save_previous(data, current_speaker, current_party, current_text)

                        current_speaker = match_president.group(1)  # "Le président"
                        current_party = "Présidence"  # On invente un parti pour la cohérence
                        current_text = [match_president.group(2)] if match_president.group(2) else []

                    # SI C'EST UN CONSEILLER D'ÉTAT
                    elif match_ce:
                        save_previous(data, current_speaker, current_party, current_text)

                        current_speaker = f"{match_ce.group(1)} {match_ce.group(2).strip()}"

                        # LOGIQUE DÉPARTEMENT :
                        # On récupère tout le titre (ex: "conseiller d'État, chef du Département de la santé...")
                        titre_complet = match_ce.group(3).strip()

                        if "président" in titre_complet:
                            current_party="Présidence CE"

                        # On cherche le mot "Département" pour ne garder que ça
                        elif "Département" in titre_complet:
                            # On découpe la phrase et on garde ce qui commence par "Département"
                            # Ex: "chef du Département de la santé" -> "Département de la santé"
                            try:
                                # On prend la partie après "du " ou "le " qui précède souvent Département
                                # Le plus simple : on cherche la position du mot "Département"
                                index_dept = titre_complet.find("Département")
                                current_party = titre_complet[index_dept:]  # On garde tout depuis "Département..."
                            except:
                                current_party = titre_complet  # Si ça rate, on garde le titre entier
                        else:
                            # Si aucun département n'est cité (ex: juste "Le Conseil d'État"), on garde le générique
                            current_party = "Conseil d'État"
                        current_text = [match_ce.group(4)] if match_ce.group(4) else []

                    # SINON (Suite du texte ou Bruit)
                    else:
                        if current_speaker is None: continue

                        # Filtre anti-bruit
                        is_noise = False
                        if len(line) < 3: is_noise = True
                        if "Vote n°" in line: is_noise = True
                        if "Résultat du vote" in line: is_noise = True
                        if line.isupper() and len(line) < 50: is_noise = True

                        if not is_noise:
                            current_text.append(line)

        # Sauvegarder le dernier à la fin
        save_previous(data, current_speaker, current_party, current_text)

        print(f"✅ Terminé ! {len(data)} interventions extraites.")
        return pd.DataFrame(data)

    except FileNotFoundError:
        print("❌ Fichier introuvable.")
        return pd.DataFrame()


# --- Petite fonction utilitaire pour ne pas répéter le code de sauvegarde ---
def save_previous(data, speaker, party, text_list):
    if speaker is not None and text_list:
        data.append({
            'Orateur': speaker,
            'Parti': party,
            'Texte': " ".join(text_list)
        })

# --- EXÉCUTION ---
if __name__ == "__main__":
    df = extract_speeches(PDF_PATH)

    if not df.empty:
        # On sauvegarde le résultat propre dans un fichier CSV (compatible Excel)
        output_file = "discours_grand_conseil.csv"
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"\n💾 Données sauvegardées dans '{output_file}'")