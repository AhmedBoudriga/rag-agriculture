"""Etape 3.1 : extraction du texte natif, page par page, sans aucun nettoyage.

Sortie : data/processed/pages/<doc_id>.jsonl (une ligne JSON par page).
Les scans (peu de texte) sont signales : ils passent par l'OCR (etape 3.2).
"""
import csv
import json
import os

import yaml

try:
    import pymupdf as fitz
except ImportError:  # anciennes versions
    import fitz

SEUIL_SCAN = 200      # caracteres par page en dessous desquels on suspecte un scan
SEUIL_VIDE = 20       # une page avec moins de caracteres est comptee comme vide
EXCLUS = {"exclu", "non_obtenu"}


def charger_config(chemin="configs/config.yaml"):
    with open(chemin, encoding="utf-8") as f:
        return yaml.safe_load(f)


def main():
    cfg = charger_config()
    sortie = os.path.join(cfg["paths"]["processed"], "pages")
    os.makedirs(sortie, exist_ok=True)

    with open("data/sources.csv", encoding="utf-8", newline="") as f:
        docs = list(csv.DictReader(f))

    print(f"{'doc_id':12} {'pages':>5} {'caracteres':>10} {'vides':>5}  resultat")
    for d in docs:
        if d["statut"] in EXCLUS or not d["fichier_local"]:
            continue
        doc_id = d["doc_id"]
        try:
            pdf = fitz.open(d["fichier_local"])
            textes = [page.get_text() for page in pdf]
            pdf.close()
        except Exception as e:
            print(f"{doc_id:12} ERREUR de lecture : {e}")
            continue

        total = sum(len(t) for t in textes)
        vides = sum(1 for t in textes if len(t.strip()) < SEUIL_VIDE)
        if total < SEUIL_SCAN * max(len(textes), 1):
            print(f"{doc_id:12} {len(textes):5} {total:10} {vides:5}  SCAN : OCR requis (3.2)")
            continue

        with open(os.path.join(sortie, f"{doc_id}.jsonl"), "w", encoding="utf-8") as out:
            for numero, texte in enumerate(textes, start=1):
                ligne = {"doc_id": doc_id, "page": numero, "n_chars": len(texte), "text": texte}
                out.write(json.dumps(ligne, ensure_ascii=False) + "\n")
        print(f"{doc_id:12} {len(textes):5} {total:10} {vides:5}  ok")


if __name__ == "__main__":
    main()
