# Assistant agricole RAG (olivier et blé, français et arabe)

Projet semestriel NLP 2026-2027, École Polytechnique de Sousse. Projet individuel.

Un système de génération augmentée par la recherche qui répond aux questions d'agriculteurs tunisiens à partir d'un corpus de documents techniques, avec citation des sources et refus lorsque le contexte est insuffisant.

## Avancement

| étape | statut |
|---|---|
| 1. Dépôt et configuration | fait |
| 2. Corpus et registre des sources | fait (licences à confirmer) |
| 3. Extraction, normalisation, découpage | à faire |
| 4. Jeu de test | à faire |
| 5. Recherche (BM25, E5, hybride) | à faire |
| 6. Génération avec citations | à faire |
| 7 à 9. Évaluation et livrables | à faire |

## Structure

    configs/    paramètres (config.yaml)
    data/       sources.csv (registre) ; raw/ et processed/ non versionnés
    docs/       journal de méthode, état du projet
    scripts/    outils de contrôle
    skills/     procédures documentées par étape
    src/        code du pipeline

## Données

Le corpus n'est pas redistribué : seuls le registre `data/sources.csv` (provenance, langue, licence) et les scripts sont versionnés. Chaque document est téléchargé depuis sa source d'origine.

## Reproduire

    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    python scripts/check_corpus.py

## Limites connues

Contexte surtout tunisien et marocain, un document dominant dans le volume du corpus, extraction des PDF arabes imparfaite, usage de l'IA générative déclaré dans le rapport.
