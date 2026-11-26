"""Étape 3.7 : extraction du texte page par page -> data/processed/pages.jsonl

Usage (racine du projet, venv activé) :
    python -m src.ingestion.extract [--docs oli_fr_002,ble_ar_001] [--no-vocab]

Pour chaque document du registre (statut retenu ou candidat, fichier présent) :
  - applique skip_pages, ocr, ocr_pages, nfkc, header_regex de configs/config.yaml ;
  - texte natif (PyMuPDF) ou OCR Tesseract (cache dans data/processed/ocr_cache) ;
  - supprime les en-têtes / pieds de page répétés et les numéros de page ;
  - arabe : NFKC, tatweel, ھ -> ه, réparation des ligatures lam-alef par vocabulaire OCR
    (diacritiques conservés) ;
  - écarte les pages sous extraction.min_chars_page caractères.
"""
import argparse
import collections
import csv
import io
import itertools
import json
import re
import sys
import unicodedata
from pathlib import Path

import pymupdf
import yaml

STATUTS_OK = {"retenu", "candidat"}
INV = {"ال": "لا", "أل": "لأ", "إل": "لإ", "آل": "لآ"}
RE_DIAC = re.compile(r"[\u064B-\u0652\u0670]")
RE_MOT_AR = re.compile(r"[\u0621-\u064A\u064B-\u0652\u0670]+")


def sans_diac(w):
    return RE_DIAC.sub("", w)


def mots_vocab(t):
    """Mots arabes (sans diacritiques, >= 2 lettres) d'un texte OCR normalisé."""
    return {sans_diac(w) for w in RE_MOT_AR.findall(norm_arabe(t)) if len(sans_diac(w)) >= 2}
LANG_OCR = {"fr": "fra", "ar": "ara"}


# ---------- normalisation ----------
LIGATURES = {chr(c): unicodedata.normalize("NFKC", chr(c)) for c in range(0xFB00, 0xFB07)}
RE_CESURE = re.compile(r"([^\W\d_]{2,})- ([a-zàâçéèêëîïôûùüÿœ][^\W\d_]*)")
RE_MOT_LAT = re.compile(r"[^\W\d_]+")


def norm_commun(t):
    """Ligatures latines (ﬁ, ﬂ...) -> lettres ; trait d'union conditionnel supprimé."""
    for k, v in LIGATURES.items():
        t = t.replace(k, v)
    return t.replace("\u00ad", "")


def corrige_cesures(textes):
    """Recolle les mots coupés en fin de ligne (« préoccu- pant »).
    Règle : on recolle si le mot recollé existe ailleurs dans le corpus, ou si le
    premier fragment n'est pas un mot ; sinon on garde le trait d'union (« plantes-hôtes »).
    Retourne (textes corrigés, nombre de recollages par texte)."""
    freq = collections.Counter()
    for t in textes:
        freq.update(w.lower() for w in RE_MOT_LAT.findall(RE_CESURE.sub(" ", t)))
    compte = [0] * len(textes)

    def corrige(i, t):
        def f(m):
            a, b = m.group(1), m.group(2)
            if freq[(a + b).lower()] >= 1 or freq[a.lower()] == 0:
                compte[i] += 1
                return a + b
            return a + "-" + b
        return RE_CESURE.sub(f, t)
    return [corrige(i, t) for i, t in enumerate(textes)], compte


def norm_arabe(t):
    t = unicodedata.normalize("NFKC", t)
    t = t.replace("\u0640", "").replace("\u06BE", "\u0647")
    return t


def candidats(w):
    pos = [(i, w[i:i + 2]) for i in range(len(w) - 1) if w[i:i + 2] in INV]
    out = set()
    for r in range(1, min(len(pos), 3) + 1):
        for sub in itertools.combinations(pos, r):
            if any(b[0] - a[0] < 2 for a, b in zip(sub, sub[1:])):
                continue
            s = w
            for i, k in reversed(sub):
                s = s[:i] + INV[k] + s[i + 2:]
            out.add(s)
    return out


def repare_mot(w, vocab):
    """Corrige un mot seulement si sa version réparée est dans le vocabulaire
    et que le mot d'origine n'y est pas (évite de casser l'article « ال »)."""
    if w in vocab or RE_DIAC.search(w):
        return w
    trouves = [c for c in candidats(w) if c in vocab]
    return trouves[0] if len(trouves) == 1 else w


def repare_texte_stats(t, vocab):
    n = 0

    def f(m):
        nonlocal n
        r = repare_mot(m.group(0), vocab)
        if r != m.group(0):
            n += 1
        return r
    return RE_MOT_AR.sub(f, t), n


def recolle_fragments(texte, vocab):
    """Recolle une lettre isolée à son voisin (« وجو د » -> « وجود ») seulement si le mot
    obtenu est dans le vocabulaire OCR et qu'un seul des deux côtés convient."""
    toks = texte.split(" ")
    out, n, i = [], 0, 0
    est_ar = lambda t: RE_MOT_AR.fullmatch(t) is not None
    while i < len(toks):
        t = toks[i]
        if len(t) == 1 and est_ar(t):
            g = out[-1] if out else None
            d = toks[i + 1] if i + 1 < len(toks) else None
            cg = repare_mot(g + t, vocab) if g and est_ar(g) else None
            cd = repare_mot(t + d, vocab) if d and est_ar(d) else None
            ok_g, ok_d = cg in vocab, cd in vocab
            if ok_d and not ok_g:
                out.append(cd); i += 2; n += 1
                continue
            if ok_g and not ok_d:
                out[-1] = cg; i += 1; n += 1
                continue
        out.append(t); i += 1
    return " ".join(out), n


# ---------- en-têtes ----------
def cle_ligne(l):
    return re.sub(r"\d+", "#", " ".join(l.split()))


def bords(lignes, k=2):
    """Indices (dans la liste filtrée des lignes non vides) des k premières et k dernières lignes."""
    n = len(lignes)
    return set(range(min(k, n))) | set(range(max(0, n - k), n))


def lignes_repetees(pages_lignes, seuil=0.5, min_pages=6):
    """Lignes de bord de page (chiffres masqués) présentes sur >= seuil des pages."""
    if len(pages_lignes) < min_pages:
        return set()
    cpt = collections.Counter()
    for lignes in pages_lignes:
        ne = [l for l in lignes if l.strip()]
        cpt.update({cle_ligne(ne[i]) for i in bords(ne)})
    n = len(pages_lignes)
    return {k for k, c in cpt.items() if c / n >= seuil and len(k) > 1}


def nettoie_lignes(lignes, repetees, regex):
    ne = [l.strip() for l in lignes if l.strip()]
    b = bords(ne)
    out, retirees = [], 0
    for i, s in enumerate(ne):
        if re.fullmatch(r"\d{1,4}", s) and i in b:
            retirees += 1
            continue
        if i in b and cle_ligne(s) in repetees:
            retirees += 1
            continue
        if regex:
            s2 = re.sub(regex, "", s).strip()
            if s2 != s:
                retirees += 1
                s = s2
                if not s:
                    continue
        out.append(s)
    return out, retirees


def joindre(lignes):
    t = " ".join(lignes)
    return " ".join(t.split())


# ---------- OCR ----------
def ocr_page(page, lang, dpi, cache):
    if cache.exists():
        return cache.read_text(encoding="utf-8")
    import pytesseract
    from PIL import Image
    pix = page.get_pixmap(dpi=dpi)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    t = pytesseract.image_to_string(img, lang=lang)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(t, encoding="utf-8")
    return t


# ---------- principal ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", default="")
    ap.add_argument("--no-vocab", action="store_true", help="pas de réparation lam-alef")
    ap.add_argument("--config", default="configs/config.yaml")
    ap.add_argument("--registry", default="data/sources.csv")
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.config, encoding="utf-8"))
    raw = Path(cfg["paths"]["raw"])
    out_dir = Path(cfg["paths"]["processed"])
    cache_dir = out_dir / "ocr_cache"
    dpi = cfg["ocr"]["dpi"]
    min_chars = cfg.get("extraction", {}).get("min_chars_page", 150)
    docs_cfg = cfg.get("documents") or {}
    voulus = {d for d in args.docs.split(",") if d}

    with open(args.registry, encoding="utf-8", newline="") as f:
        registre = [r for r in csv.DictReader(f)
                    if r["statut"] in STATUTS_OK and r["fichier_local"]]
    if voulus:
        registre = [r for r in registre if r["doc_id"] in voulus]

    # 1) texte brut par page
    docs = {}
    for r in registre:
        did, lang = r["doc_id"], r["langue"]
        chemin = Path(r["fichier_local"])
        if not chemin.exists():
            print(f"[ATTENTION] {did} : fichier absent ({chemin})")
            continue
        dc = docs_cfg.get(did, {})
        skip = set(dc.get("skip_pages", []))
        ocr_all = bool(dc.get("ocr", False))
        ocr_set = set(dc.get("ocr_pages", []))
        pdf = pymupdf.open(chemin)
        pages = {}
        for n in range(1, len(pdf) + 1):
            if n in skip:
                continue
            if ocr_all or n in ocr_set:
                print(f"  OCR {did} p{n}/{len(pdf)}", end="\r", flush=True)
                t = ocr_page(pdf[n - 1], LANG_OCR[lang], dpi, cache_dir / f"{did}_p{n}.txt")
                src = "ocr"
            else:
                t, src = pdf[n - 1].get_text(), "natif"
            pages[n] = (norm_commun(t), src)
        docs[did] = dict(meta=r, cfg=dc, pages=pages, total=len(pdf), skip=len(skip))
        print(f"{did}: {len(pages)} pages à traiter ({len(skip)} exclues)      ")

    # 2) vocabulaire OCR arabe (pages natives arabes uniquement)
    vocab = set()
    if not args.no_vocab:
        for did, d in docs.items():
            if d["meta"]["langue"] != "ar":
                continue
            pdf = pymupdf.open(d["meta"]["fichier_local"])
            for n, (t, src) in d["pages"].items():
                if src == "ocr" or len(t.strip()) < min_chars:
                    continue
                print(f"  OCR vocabulaire {did} p{n}", end="\r", flush=True)
                o = ocr_page(pdf[n - 1], "ara", dpi, cache_dir / f"{did}_p{n}.txt")
                vocab |= mots_vocab(o)
        print(f"vocabulaire OCR arabe : {len(vocab)} mots" + " " * 20)

    # 3) nettoyage et écriture
    out_dir.mkdir(parents=True, exist_ok=True)
    rapport, lignes_out = [], []
    for did, d in docs.items():
        lang, m = d["meta"]["langue"], d["meta"]
        brut = {n: (t.splitlines() if lang != "ar" else norm_arabe(t).splitlines())
                for n, (t, s) in d["pages"].items()}
        rep = lignes_repetees(list(brut.values()))
        regex = d["cfg"].get("header_regex")
        ecartees, retirees, repar, chars, recolles = [], 0, 0, 0, 0
        for n, lignes in brut.items():
            propres, k = nettoie_lignes(lignes, rep, regex)
            retirees += k
            texte = joindre(propres)
            if lang == "ar" and vocab and d["pages"][n][1] == "natif":
                texte, nf = recolle_fragments(texte, vocab)
                texte, nb = repare_texte_stats(texte, vocab)
                repar += nb
                recolles += nf
            if len(texte) < min_chars:
                ecartees.append(n)
                continue
            chars += len(texte)
            lignes_out.append(dict(doc_id=did, page=n, langue=lang, culture=m["culture"],
                                   pays=m["pays"], source=d["pages"][n][1], text=texte))
        rapport.append(dict(doc_id=did, pages_pdf=d["total"], exclues=d["skip"],
                            ecartees_courtes=len(ecartees), gardees=len(d["pages"]) - len(ecartees),
                            lignes_repetees=sorted(rep), lignes_retirees=retirees,
                            mots_repares=repar, fragments_recolles=recolles, caracteres=chars))

    idx = [i for i, l in enumerate(lignes_out) if l["langue"] == "fr"]
    nouveaux, comptes = corrige_cesures([lignes_out[i]["text"] for i in idx])
    cesures = collections.Counter()
    for i, t, c in zip(idx, nouveaux, comptes):
        lignes_out[i]["text"] = t
        cesures[lignes_out[i]["doc_id"]] += c
    for r in rapport:
        r["cesures_corrigees"] = cesures.get(r["doc_id"], 0)
        r["caracteres"] = sum(len(l["text"]) for l in lignes_out if l["doc_id"] == r["doc_id"])

    with open(out_dir / "pages.jsonl", "w", encoding="utf-8") as f:
        for l in lignes_out:
            f.write(json.dumps(l, ensure_ascii=False) + "\n")
    json.dump(rapport, open(out_dir / "extraction_report.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    total = sum(r["caracteres"] for r in rapport) or 1
    print(f"\n{'doc_id':12} {'pdf':>4} {'excl':>4} {'court':>5} {'gard':>4} {'répét':>5} {'répar':>6} {'recol':>5} {'car':>9} {'part':>5}")
    for r in rapport:
        print(f"{r['doc_id']:12} {r['pages_pdf']:4} {r['exclues']:4} {r['ecartees_courtes']:5} "
              f"{r['gardees']:4} {len(r['lignes_repetees']):5} {r['mots_repares']:6} "
              f"{r['fragments_recolles']:5} {r['caracteres']:9} {r['caracteres']/total:5.0%}")
    print(f"\n{len(lignes_out)} pages -> {out_dir/'pages.jsonl'}")


if __name__ == "__main__":
    sys.exit(main())