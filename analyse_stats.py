import pandas as pd
import matplotlib.pyplot as plt

# 1. Chargement des données
df = pd.read_csv("discours_grand_conseil_complet.csv")

print(f"--- STATISTIQUES GLOBALES ---")
print(f"Nombre total d'interventions : {len(df)}")
print(f"Nombre d'orateurs uniques : {df['Orateur'].nunique()}")

# 2. Qui parle le plus ? (Top 5 Orateurs)
# On compte le nombre d'interventions par orateur
top_orateurs = df['Orateur'].value_counts().head(5)
print("\n--- TOP 5 DES BAVARDS (Nombre d'interventions) ---")
print(top_orateurs)

# 3. Quel parti parle le plus ? (Répartition politique)
# On compte les interventions par Parti
top_partis = df['Parti'].value_counts()
print("\n--- RÉPARTITION PAR PARTI ---")
print(top_partis)

# 4. (Bonus Maths) : Longueur moyenne des interventions
# On crée une nouvelle colonne 'Longueur' (nombre de caractères)
df['Longueur'] = df['Texte'].str.len()
moyenne = df['Longueur'].mean()
print(f"\n--- LONGUEUR MOYENNE ---")
print(f"Une intervention fait en moyenne {int(moyenne)} caractères.")

# 5. Visualisation rapide (Graphique)
# On crée un graphique à barres des partis
plt.figure(figsize=(10, 6))
top_partis.plot(kind='bar', color='skyblue')
plt.title('Nombre d\'interventions par Parti politique')
plt.xlabel('Parti')
plt.ylabel('Nombre d\'interventions')
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()