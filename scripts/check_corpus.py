#!/usr/bin/env python3
"""Contrôle de l'étape « corpus » d'un projet RAG.

Usage (depuis la racine du projet, venv activé) :
    python scripts/check_corpus.py [--registry data/sources.csv] [--raw data/raw]

Ce que le script vérifie :
  1. le registre : colonnes attendues, doc_id uniques, lignes mal formées ;
  2. la cohérence registre <-> dossier : fichiers manquants / non enregistrés ;
  3. chaque fichier : vrai PDF (signature %PDF), texte lisible ou scan ;
  4. l'équilibre : parts par culture, langue, pays et par document ;
  5. pour l'arabe : tatweel, « ھ » (U+06BE), ligatures lam-alef inversées ;
  6. les lignes répétées sur beaucoup de pages (en-têtes / pieds de page).
"""
import argparse
import collections
import csv
import os
import sys

try:
    import pymupdf as fitz
except ImportError:  # anciennes versions
    import fitz

COLONNES = [
    "doc_id", "titre", "organisme", "langue", "culture", "pays", "annee",
    "url", "licence", "licence_verifiee", "fichier_local", "statut", "notes",
]
SEUIL_SCAN = 200          # caractères par page en dessous desquels on soupçonne un scan
SEUIL_DOMINANT = 0.30     # part du texte total au-delà de laquelle un document domine
SEUIL_REPETITION = 0.5    # une ligne présente sur >= 50 % des pages est un en-tête probable

# (forme correcte, forme inversée typique de l'extraction)
PAIRES_LAM_ALEF = [
    ("علاج", "عالج"), ("الأمراض", "األمراض"), ("الإصابة", "اإلصابة"),
    ("الأعراض", "األعراض"), ("ملائمة", "مالئمة"),
]


def lire_registre(chemin):
    with open(chemin, encoding="utf-8", newline="") as f:
        lecteur = csv.DictReader(f)
        manquantes = [c for c in COLONNES if c not in (lecteur.fieldnames or [])]
        lignes = list(lecteur)
    return lignes, manquantes


def est_pdf(chemin):
    with open(chemin, "rb") as f:
        return f.read(5).startswith(b"%PDF")


def extraire(chemin):
    doc = fitz.open(chemin)
    pages = [p.get_text() for p in doc]
    doc.close()
    return pages


def lignes_repetees(pages):
    if len(pages) < 4:
        return []
    compteur = collections.Counter()
    for texte in pages:
        lignes = [l.strip() for l in texte.splitlines() if l.strip()]
        candidates = set(lignes[:2] + lignes[-2:])
        compteur.update(candidates)
    return [(l, n) for l, n in compteur.most_common(3)
            if n >= SEUIL_REPETITION * len(pages) and len(l) > 3]


def controle_arabe(texte):
    alertes = []
    tatweel = texte.count("\u0640")
    heh = texte.count("\u06be")
    if tatweel:
        alertes.append(f"{tatweel} tatweel (ـ) à supprimer")
    if heh:
        alertes.append(f"{heh} « ھ » (U+06BE) à remplacer par « ه »")
    for bon, inverse in PAIRES_LAM_ALEF:
        nb_bon, nb_inv = texte.count(bon), texte.count(inverse)
        if nb_inv > nb_bon:
            alertes.append(f"ligature lam-alef inversée probable ({inverse} x{nb_inv} contre {bon} x{nb_bon})")
    return alertes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--registry", default="data/sources.csv")
    ap.add_argument("--raw", default="data/raw")
    args = ap.parse_args()

    erreurs, avertissements = 0, 0
    lignes, manquantes = lire_registre(args.registry)
    if manquantes:
        print(f"ERREUR registre : colonnes absentes {manquantes}")
        sys.exit(1)

    ids = [r["doc_id"] for r in lignes]
    for doublon in {i for i in ids if ids.count(i) > 1}:
        print(f"ERREUR doc_id en double : {doublon}")
        erreurs += 1
    for r in lignes:
        if None in r:
            print(f"ERREUR ligne avec trop de colonnes : {r['doc_id']}")
            erreurs += 1
    print(f"{len(lignes)} lignes dans le registre\n")

    enregistres = {r["fichier_local"] for r in lignes if r["fichier_local"]}
    for r in lignes:
        if r["fichier_local"] and not os.path.exists(r["fichier_local"]):
            print(f"ERREUR fichier manquant : {r['doc_id']} -> {r['fichier_local']}")
            erreurs += 1
    if os.path.isdir(args.raw):
        for nom in sorted(os.listdir(args.raw)):
            chemin = os.path.join(args.raw, nom)
            if chemin not in enregistres and nom.lower().endswith(".pdf"):
                print(f"AVERTISSEMENT fichier non enregistré : {chemin}")
                avertissements += 1

    totaux = collections.Counter()
    par_doc = {}
    for r in lignes:
        if r["statut"] in ("exclu", "non_obtenu") or not r["fichier_local"]:
            continue
        if not os.path.exists(r["fichier_local"]):
            continue
        ident = r["doc_id"]
        if not est_pdf(r["fichier_local"]):
            print(f"ERREUR {ident} : ce n'est pas un PDF (page HTML ou erreur de téléchargement)")
            erreurs += 1
            continue
        try:
            pages = extraire(r["fichier_local"])
        except Exception as e:  # PDF corrompu
            print(f"ERREUR {ident} : lecture impossible ({e})")
            erreurs += 1
            continue
        n = sum(len(p) for p in pages)
        if n < SEUIL_SCAN * max(len(pages), 1):
            print(f"SCAN {ident} : {len(pages)} pages, {n} caractères -> OCR nécessaire")
            continue
        par_doc[ident] = n
        for cle in ("culture", "langue", "pays"):
            totaux[(cle, r[cle])] += n
        totaux[("total", "")] += n

        texte = "\n".join(pages)
        if r["langue"] == "ar":
            for alerte in controle_arabe(texte):
                print(f"ARABE {ident} : {alerte}")
                avertissements += 1
        for ligne, nb in lignes_repetees(pages):
            print(f"EN-TÊTE probable {ident} : « {ligne[:60]} » sur {nb}/{len(pages)} pages")

    total = totaux[("total", "")]
    if not total:
        print("\nAucun document lisible : rien à comparer.")
        sys.exit(1 if erreurs else 0)

    print("\n--- Équilibre (texte natif seulement ; scans non comptés) ---")
    for (cle, val), n in sorted(totaux.items()):
        if cle != "total":
            print(f"{cle:8} {val or '(vide)':12} {n:9} caractères  {100 * n / total:3.0f} %")
    print()
    for ident, n in sorted(par_doc.items(), key=lambda x: -x[1]):
        marque = "  <-- DOMINANT" if n / total > SEUIL_DOMINANT else ""
        print(f"{ident:14} {n:9} caractères  {100 * n / total:3.0f} %{marque}")

    print(f"\n{erreurs} erreur(s), {avertissements} avertissement(s)")
    sys.exit(1 if erreurs else 0)


if __name__ == "__main__":
    main()
