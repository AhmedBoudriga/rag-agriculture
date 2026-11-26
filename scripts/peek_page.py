"""Affiche le texte brut d'une page : python scripts/peek_page.py <doc_id> <page>"""
import json
import sys

doc_id, page = sys.argv[1], int(sys.argv[2])
with open(f"data/processed/pages/{doc_id}.jsonl", encoding="utf-8") as f:
    for ligne in f:
        r = json.loads(ligne)
        if r["page"] == page:
            print(r["text"])
            break
    else:
        print("page introuvable")
