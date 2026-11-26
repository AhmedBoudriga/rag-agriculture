# État du projet RAG agricole (à coller au début d'une nouvelle conversation)

## Sujet
Projet semestriel NLP 2026-2027 (5DS2), projet individuel.
Assistant agricole fondé sur la génération augmentée par la recherche (RAG) pour répondre aux questions des agriculteurs tunisiens en français et en arabe.
- Périmètre : olivier et blé. Hors périmètre : le système refuse de répondre au lieu d'inventer.
- Statut de la proposition : [à confirmer : validée le ... / en attente]

## Objectifs de la proposition
1. Corpus documenté (provenance, langue, licence).
2. Jeu de test de 50 à 100 questions avec passages de référence (développement / test séparés, test utilisé une seule fois).
3. Comparer BM25, embeddings multilingues (E5) et hybride avec Recall@k, MRR, nDCG@k.
4. Évaluer les réponses générées (exactitude, fidélité aux sources, refus correct) face à un LLM seul : évaluation humaine sur environ 30 questions, trois exécutions par configuration.
Baselines : LLM seul, BM25 seul. Ablation : embeddings seuls contre hybride. Jalons : 3 corpus/test/baselines, 4 pipeline, 5 expériences et rapport, 6-7 livrables et démo.

## Pipeline (étapes)
0 cadrage : fait | 1 dépôt : fait | 2 corpus : quasi terminée | 3 extraction, normalisation, découpage : À FAIRE | 4 jeu de test | 5 recherche | 6 génération | 7 évaluation humaine | 8 évaluation finale | 9 livrables.
Méthode de travail : une étape à la fois, commandes complètes à copier, confirmation entre les étapes.

## Dépôt
~/rag-agriculture (Python 3.12, venv .venv à activer avant tout), registre data/sources.csv, PDF dans data/raw/ (non versionnés), config dans configs/config.yaml, journal dans docs/journal_methode.md.
Contrôle : python scripts/check_corpus.py (skill rag-corpus-construction).

## Corpus (10 documents retenus ou candidats)
- oli_fr_001 AFIDOL 2016 (France) : pages 1-3 et 6-10 à exclure [proposé, à confirmer]
- oli_fr_002 Manuel d'irrigation olivier, Institut de l'Olivier (Tunisie, 206 p., 49 % du texte total)
- oli_fr_003 PNTTA n°183 ravageurs olivier (Maroc)
- oli_ar_001 Fiche n°9 maladies olivier, Institut de l'Olivier (Tunisie, arabe)
- ble_fr_002 Guide INRA/INRAT protection phytosanitaire (Maroc) : scan 92 p., OCR français à faire, licence CC-BY-SA vérifiée
- ble_fr_003 Cahiers Agricultures 2020 blé dur irrigué (Tunisie), CC BY-NC vérifiée
- ble_fr_004 PNTTA n°77 maladies du blé (Maroc)
- ble_fr_005 ITGC irrigation d'appoint du blé (Algérie)
- ble_ar_001 Nasraoui Bouzid 2008 maladies des céréales (Tunisie, arabe) : exclure taxonomie (livre p. 197-229) et légumineuses (p. 261-276), étiqueter orge et avoine
- ble_ar_002 Directives céréales pluviales (Tunisie, arabe) : supprimer l'en-tête répété
Exclus (voir registre) : BSV PACA (reproduction interdite), mémoire Constantine, cours Bagdad, cours Anbar. Non obtenu : ICARDA ble_fr_001.
Équilibre avant OCR : blé 33 % / olivier 67 % ; arabe 24 % ; Tunisie 79 % (dû surtout au manuel d'irrigation).

## Décisions prises
- Corpus figé avant d'annoter : tout ajout oblige à refaire extraction, annotation et évaluation.
- Pomme de terre : hors périmètre, à utiliser comme questions de refus ou travail futur.
- Une seule édition par guide (pas de doublons).
- Normalisation de l'arabe à prévoir : supprimer tatweel (ـ), remplacer ھ par ه, corriger les ligatures lam-alef inversées, sans supprimer les diacritiques.
- Questions échantillonnées par document et par culture, pas au prorata de la taille.
- Documents avec doses de produits : le système cite sa source et renvoie vers un technicien.

## Points ouverts
- Licences à demander (non vérifiées) : Institut de l'Olivier, PNTTA, ITGC, ONAGRI, auteur Nasraoui, AFIDOL.
- Validation du sujet par l'encadrant : [à confirmer].
- OCR de ble_fr_002 et recalcul de l'équilibre.

## Prochaine étape : 3
Extraction (texte natif + OCR de ble_fr_002), normalisation de l'arabe, nettoyage des en-têtes, application des skip_pages, découpage en passages d'environ 200 mots avec chevauchement, chunk_id stables au format <doc_id>_p<page>_c<n>, sortie data/processed/passages.jsonl, puis gel du corpus. Ensuite étape 4 : jeu de test.
