"""Etape 3.3 : diagnostic des pages extraites (lecture seule, ne modifie rien).

Usage : python scripts/inspect_pages.py
Lit data/processed/pages/*.jsonl et affiche, par document, les defauts d'extraction
qui orientent les regles de nettoyage (etape 3.4).
"""
import collections
import glob
import json
import os
import unicodedata

PAIRES_LAM_ALEF = [("علاج", "عالج"), ("الأمراض", "األمراض"), ("الإصابة", "اإلصابة"),
                   ("الأعراض", "األعراض"), ("ملائمة", "مالئمة")]


def formes_presentation(texte):
    """Lettres arabes en formes de presentation (FB50-FDFF, FE70-FEFF) : cassent la recherche."""
    return sum(1 for c in texte if 0xFB50 <= ord(c) <= 0xFDFF or 0xFE70 <= ord(c) <= 0xFEFF)


def lignes_repetees(pages, seuil=0.5):
    if len(pages) < 4:
        return []
    compteur = collections.Counter()
    for p in pages:
        lignes = [l.strip() for l in p["text"].splitlines() if l.strip()]
        compteur.update(set(lignes[:2] + lignes[-2:]))
    return [(l, n) for l, n in compteur.most_common(4) if n >= seuil * len(pages) and len(l) > 3]


def main():
    chemins = sorted(glob.glob("data/processed/pages/*.jsonl"))
    if not chemins:
        print("Aucune page extraite : lancer d'abord python -m src.ingestion.extract")
        return
    for chemin in chemins:
        doc_id = os.path.basename(chemin)[:-6]
        with open(chemin, encoding="utf-8") as f:
            pages = [json.loads(l) for l in f]
        texte = "\n".join(p["text"] for p in pages)
        nfkc = unicodedata.normalize("NFKC", texte)
        total = max(len(texte), 1)

        print(f"== {doc_id} : {len(pages)} pages, {len(texte)} caracteres")
        pres = formes_presentation(texte)
        if pres:
            print(f"   formes de presentation arabes : {pres} ({100 * pres / total:.0f} % du texte) -> NFKC necessaire")
        for nom, code in (("tatweel", "\u0640"), ("ha de l'ourdou (U+06BE)", "\u06be")):
            n = texte.count(code)
            if n:
                print(f"   {nom} : {n}")
        for bon, inverse in PAIRES_LAM_ALEF:
            n_inv, n_bon = nfkc.count(inverse), nfkc.count(bon)
            if n_inv > n_bon:
                print(f"   lam-alef inverse (apres NFKC) : {inverse} x{n_inv} contre {bon} x{n_bon}")
        tabs = texte.count("\t")
        coupures = texte.count("-\n")
        if tabs:
            print(f"   tabulations : {tabs}")
        if coupures:
            print(f"   mots ou nombres coupes en fin de ligne (-\\n) : {coupures}")
        courtes = [p["page"] for p in pages if p["n_chars"] < 200]
        if courtes:
            print(f"   pages quasi vides (<200 car.) : {courtes}")
        for ligne, n in lignes_repetees(pages):
            print(f"   en-tete / pied repete {n}/{len(pages)} pages : {ligne[:70]}")


if __name__ == "__main__":
    main()
