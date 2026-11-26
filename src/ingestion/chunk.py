"""Étape 3.11 : découpage en passages -> data/processed/passages.jsonl

Usage (racine du projet, venv activé) :
    python -m src.ingestion.chunk [--freeze]

- Un passage ne traverse jamais une frontière de page (citation exacte de la page).
- Découpage par phrases, jusqu'à chunking.max_words mots ; chevauchement de
  chunking.overlap_words mots (en phrases entières) entre passages consécutifs d'une page.
- Une phrase plus longue que max_words est coupée par fenêtres de mots.
- Un reste de moins de MIN_NOUVEAUX mots nouveaux est ajouté au passage précédent.
- chunk_id = <doc_id>_p<page>_c<n> (n à partir de 1, par page) : déterministe.
- --freeze écrit docs/corpus_freeze.json (empreintes sha256) : preuve que le corpus est figé.
"""
import argparse
import collections
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

import yaml

MIN_NOUVEAUX = 20
RE_PHRASE = re.compile(r"(?<=[.!?؟])\s+")
RE_NUM_PAGE_AR = re.compile(r"^\d{1,3}\s+(?=[\u0600-\u06FF])")


def mots(s):
    return s.split()


def fenetres(phrase, max_w, overlap):
    w = mots(phrase)
    pas = max(1, max_w - overlap)
    return [" ".join(w[i:i + max_w]) for i in range(0, len(w), pas) if w[i:i + max_w]]


def decoupe_page(texte, max_w, overlap):
    """Retourne la liste des passages (textes) d'une page."""
    phrases = []
    for p in RE_PHRASE.split(texte.strip()):
        if not p:
            continue
        if len(mots(p)) > max_w:
            phrases.extend(fenetres(p, max_w, overlap))
        else:
            phrases.append(p)
    passages = []          # liste de (liste de phrases, nb de phrases de chevauchement)
    courant, n_mots, n_chev = [], 0, 0
    for ph in phrases:
        k = len(mots(ph))
        if courant and n_mots + k > max_w:
            passages.append((courant, n_chev))
            chev, tot = [], 0
            for q in reversed(courant):
                kq = len(mots(q))
                if tot + kq > overlap:
                    break
                chev.insert(0, q)
                tot += kq
            if tot + k > max_w:
                chev, tot = [], 0
            courant, n_mots, n_chev = list(chev), tot, len(chev)
        courant.append(ph)
        n_mots += k
    if courant:
        passages.append((courant, n_chev))
    # reste trop court : on le rattache au passage précédent
    if len(passages) > 1:
        dern, nc = passages[-1]
        nouveaux = dern[nc:]
        if sum(len(mots(x)) for x in nouveaux) < MIN_NOUVEAUX:
            prec, ncp = passages[-2]
            passages[-2:] = [(prec + nouveaux, ncp)]
    return [" ".join(ph) for ph, _ in passages]


def sha256(chemin):
    h = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/config.yaml")
    ap.add_argument("--registry", default="data/sources.csv")
    ap.add_argument("--freeze", action="store_true")
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.config, encoding="utf-8"))
    out_dir = Path(cfg["paths"]["processed"])
    max_w = cfg["chunking"]["max_words"]
    overlap = cfg["chunking"]["overlap_words"]

    chunks, num_retires = [], 0
    for l in open(out_dir / "pages.jsonl", encoding="utf-8"):
        d = json.loads(l)
        texte = d["text"]
        if d["langue"] == "ar":
            t2 = RE_NUM_PAGE_AR.sub("", texte)
            num_retires += t2 != texte
            texte = t2
        for n, t in enumerate(decoupe_page(texte, max_w, overlap), 1):
            chunks.append(dict(chunk_id=f"{d['doc_id']}_p{d['page']}_c{n}", doc_id=d["doc_id"],
                               page=d["page"], langue=d["langue"], culture=d["culture"],
                               pays=d["pays"], source=d["source"], n_words=len(mots(t)), text=t))

    ids = [c["chunk_id"] for c in chunks]
    assert len(ids) == len(set(ids)), "chunk_id en double"
    with open(out_dir / "passages.jsonl", "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    total = sum(c["n_words"] for c in chunks)
    par_doc = collections.defaultdict(list)
    for c in chunks:
        par_doc[c["doc_id"]].append(c["n_words"])
    print(f"{'doc_id':12} {'passages':>8} {'mots moy':>8} {'min':>4} {'max':>4} {'part mots':>9}")
    for did, v in par_doc.items():
        print(f"{did:12} {len(v):8} {sum(v)/len(v):8.0f} {min(v):4} {max(v):4} {sum(v)/total:9.0%}")
    for cle in ("langue", "culture", "pays"):
        cpt = collections.Counter()
        for c in chunks:
            cpt[c[cle]] += c["n_words"]
        print(cle, {k: f"{v/total:.0%}" for k, v in cpt.most_common()})
    print(f"\n{len(chunks)} passages, {total} mots, {num_retires} numéros de page arabes retirés")
    print(f"-> {out_dir/'passages.jsonl'}  sha256 {sha256(out_dir/'passages.jsonl')[:16]}...")

    if args.freeze:
        with open(args.registry, encoding="utf-8", newline="") as f:
            reg = [r for r in csv.DictReader(f) if r["fichier_local"] and r["statut"] in {"retenu", "candidat"}]
        gel = dict(
            passages_sha256=sha256(out_dir / "passages.jsonl"),
            n_passages=len(chunks),
            chunking=dict(max_words=max_w, overlap_words=overlap),
            documents={r["doc_id"]: sha256(r["fichier_local"]) for r in reg if Path(r["fichier_local"]).exists()},
        )
        Path("docs").mkdir(exist_ok=True)
        json.dump(gel, open("docs/corpus_freeze.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
        print("corpus figé -> docs/corpus_freeze.json")


if __name__ == "__main__":
    sys.exit(main())