---
name: rag-corpus-construction
description: Guide pas à pas pour constituer, vérifier et documenter le corpus documentaire d'un projet RAG (assistant de questions-réponses sur des PDF), jusqu'au gel du corpus avant l'extraction. Utiliser dès que l'utilisateur cherche des sources pour un corpus, évalue un lien ou un PDF candidat, parle de registre de sources, de licences, de doublons, de scans à passer en OCR, d'équilibre entre cultures, langues ou pays, ou veut savoir si un document peut entrer dans son corpus, même s'il ne dit pas « corpus » ni « skill ». Couvre aussi le contrôle des PDF arabes (tatweel, ligatures inversées, vocabulaire régional).
---

# Constitution du corpus pour un projet RAG

Cette étape produit un corpus **documenté, vérifié et figé**, prêt pour l'extraction et le découpage en passages. Elle précède l'écriture des questions d'évaluation : les identifiants de passages doivent être stables avant d'annoter, donc le corpus doit l'être aussi.

## Principes

1. **Qualité avant quantité.** 15 à 30 documents propres valent mieux qu'une centaine de documents douteux.
2. **Chaque document est ouvert avant d'être jugé.** Un titre ou une URL ne suffisent pas : lire le texte réellement extrait.
3. **Licence : rien n'est « vérifié » sans preuve.** Découper un document en passages revient à le reproduire partiellement. Une mention « gratuit » ou « téléchargeable » n'est pas une licence.
4. **Tout est tracé.** Les exclusions aussi : le registre garde les documents écartés avec leur raison.
5. **Une étape à la fois, avec confirmation.** Donner des commandes complètes à copier, attendre la sortie de l'utilisateur, puis avancer.

## Le registre `data/sources.csv`

Colonnes, dans cet ordre :

`doc_id, titre, organisme, langue, culture, pays, annee, url, licence, licence_verifiee, fichier_local, statut, notes`

- `doc_id` : `<culture>_<langue>_<numéro>` (ex. `oli_ar_001`). Unique. **Le nom du fichier dans `data/raw/` est le même.**
- `licence_verifiee` : `oui` seulement si la licence est écrite dans le document ou sur la page officielle. Sinon `non`.
- `statut` : `candidat`, `retenu`, `a_telecharger`, `non_obtenu`, `exclu`.
- `pays` : pays de l'auteur ou de l'organisme, pas de l'hébergeur. Le contexte géographique doit être déclaré dans le rapport.
- Les valeurs contenant une virgule sont entre guillemets. Une ligne avec plus de colonnes que l'en-tête est une erreur.

## Procédure

### 1. Chercher
Pistes : organismes publics de recherche et de vulgarisation agricole, instituts techniques, revues en libre accès, entrepôts institutionnels (FAO, CIHEAM, ICARDA, CORE), sites de ministères. Une recherche par thème (maladies, irrigation, fertilisation, calendrier) et par langue.

### 2. Juger un candidat
Ouvrir le document et répondre à ces questions :

| question | exclure si |
|---|---|
| Le contenu répond-il à des questions réelles d'utilisateurs ? | brochure grand public, actualité, histoire, recettes |
| Est-il dans le périmètre (cultures, thèmes) ? | cultures ou sujets hors périmètre |
| Le texte est-il exploitable ? | scan sans texte, chiffres corrompus, diapositives en fragments |
| La licence autorise-t-elle la reproduction partielle ? | « reproduction partielle interdite » |
| Est-ce une source primaire ? | document qui reprend un autre document déjà retenu (mémoire étudiant, cours dérivé) |
| Est-ce un doublon d'édition ? | autre édition du même guide : n'en garder qu'une |
| Les conseils sont-ils sûrs et actuels ? | substance retirée du marché, produit très toxique, doses d'un autre contexte réglementaire |
| Le contexte est-il compatible avec le public visé ? | produits, réglementation ou vocabulaire d'un autre pays |

Verdicts possibles : **retenir**, **retenir en partie** (pages à exclure, notées dans `notes` puis dans la config sous `skip_pages`), **exclure**.

### 3. Télécharger et valider
```bash
curl -L -A "Mozilla/5.0 (X11; Linux x86_64)" -o data/raw/<doc_id>.pdf "<url>"
file data/raw/<doc_id>.pdf
```
- `PDF document` : bon. `HTML document` : le site bloque le téléchargement automatique. Télécharger **à la main** dans le navigateur et placer le fichier dans `data/raw/`.
- Un PDF valide peut être un scan : le test de texte (étape 5) le détecte.
- L'en-tête d'un PDF peut annoncer un mauvais nombre de pages : se fier au comptage de la bibliothèque, pas à `file`.

### 4. Enregistrer
Ajouter la ligne au registre, **y compris pour les documents exclus ou non obtenus** (`fichier_local` vide, `statut` `exclu` ou `non_obtenu`, raison dans `notes`).

### 5. Contrôler
Environnement virtuel activé (l'invite commence par `(.venv)` ; sinon `python` ou le module sont introuvables) :
```bash
python scripts/check_corpus.py
```
Le script vérifie le registre, la cohérence fichiers/registre, la signature PDF, la présence de texte, les en-têtes répétés, les défauts de l'arabe et l'équilibre du corpus. Corriger tout message `ERREUR` avant de continuer.

## Pièges rencontrés (à vérifier systématiquement)

- Lien qui renvoie une page HTML au lieu du PDF (blocage des téléchargements automatiques).
- `doc_id` du registre différent du nom du fichier téléchargé.
- Document hébergé par un tiers : la licence se vérifie chez l'**éditeur**, pas chez l'hébergeur.
- Date incohérente (couverture et pieds de page) : retenir la couverture, le noter.
- Numérotation qui saute (point 8 absent) : section peut-être manquante, à vérifier après extraction.
- Tableaux et graphiques extraits dans le désordre : à nettoyer ou exclure, jamais réécrits à la main.
- En-têtes ou pieds de page répétés à chaque page : à supprimer avant le découpage.
- Livre ou chapitre qui mélange le périmètre et le reste (autres cultures, taxonomie) : prévoir `skip_pages` et étiqueter la culture dans les métadonnées.
- Environnement virtuel recréé ou désactivé : `ModuleNotFoundError` ne vient pas du code.

## PDF arabes : contrôles obligatoires

Tester l'extraction **avant** d'ajouter un document arabe au corpus. Défauts fréquents :

- **Tatweel** (ـ) à l'intérieur des mots (texte justifié) : à supprimer.
- **ھ (U+06BE)** à la place de **ه (U+0647)** : à remplacer.
- **Ligatures lam-alef inversées** : « علاج » devient « عالج », « الأمراض » devient « األمراض ». Une requête correcte ne retrouve alors jamais le mot. Corriger par normalisation, ou passer par une OCR arabe, et comparer sur quelques pages.
- **Noms latins inversés** (« graminis Puccinia ») et **chiffres altérés** (doses, températures) : ne pas retenir un document dont les nombres sont corrompus.
- **Vocabulaire régional** : le blé se dit « القمح » au Maghreb et « الحنطة » en Irak. Les produits et leurs doses diffèrent aussi. Un cours d'une autre région n'est pas interchangeable avec un document local.
- La normalisation ne doit pas supprimer les diacritiques si le projet s'est engagé à les conserver.

## Équilibre du corpus

Mesurer la part du texte par culture, langue, pays **et par document**. Points d'attention :
- Un document au-delà de 30 % du texte total domine la recherche : il noiera les autres sur les questions générales.
- Les parts en caractères ne sont pas les parts de questions : à l'étape suivante, échantillonner les questions **par document et par culture**, pas au prorata de la taille.
- Les scans (OCR à faire) ne sont comptés qu'après extraction : recalculer.
- Déclarer dans le rapport la répartition par pays et la limite correspondante.

## Licences et éthique

- Ne pas redistribuer le corpus : `data/raw/` et `data/processed/` sont dans `.gitignore`.
- Pour chaque document sans licence explicite : noter l'éditeur, demander l'autorisation d'usage académique (modèle ci-dessous) et garder la réponse.
- Les documents qui citent des produits et des doses sont sensibles : le système final doit citer sa source et renvoyer vers un technicien. Signaler dans `notes` les documents qui contiennent des doses ou des substances anciennes.
- Déclarer l'usage de l'IA générative dans le rapport.

Modèle de demande :

> Objet : Demande d'autorisation d'usage académique d'un document technique
> Bonjour, je suis étudiant en [formation] à [établissement]. Pour un projet de traitement automatique du langage, j'aimerais utiliser « [titre] » ([éditeur, année]) dans un corpus de recherche non redistribué, découpé en passages pour de la recherche d'information. Le document serait cité et crédité dans mon rapport. Pouvez-vous m'indiquer si cet usage est autorisé ? Cordialement, [nom]

## Journal de méthode

Dans `docs/journal_methode.md`, noter pour chaque décision la date, le choix et la raison : documents exclus, pages exclues, édition retenue, règle d'annotation. Ce journal alimente directement le rapport.

## Critères de sortie de l'étape

- [ ] `python scripts/check_corpus.py` : **0 erreur**
- [ ] Chaque document est `retenu`, `candidat` validé, `non_obtenu` ou `exclu`, avec sa raison
- [ ] Scans identifiés (OCR à faire à l'étape suivante)
- [ ] Documents partiels : `skip_pages` notés dans le registre
- [ ] Licences : liste des documents sans licence vérifiée et demandes envoyées
- [ ] Défauts d'extraction arabe notés pour l'étape de normalisation
- [ ] Répartition par culture, langue, pays et document connue et jugée acceptable
- [ ] Journal de méthode à jour
- [ ] Corpus **figé** : tout ajout ultérieur oblige à refaire extraction, annotation et évaluation

L'étape suivante est l'extraction, la normalisation et le découpage en passages (avec `chunk_id` stables).

## Comportement attendu de l'assistant

- Ouvrir chaque document avant de rendre un verdict ; dire clairement ce qui n'a pas pu être lu.
- Ne jamais écrire qu'une licence est vérifiée sans preuve ; ne jamais déduire une date ou un nombre de pages.
- Proposer un verdict motivé (retenir, partiel, exclure) avec les réserves, puis les lignes de registre prêtes à coller.
- Fournir des commandes complètes, rappeler d'activer le venv, et attendre la sortie avant de passer à la suite.
- Si l'utilisateur veut élargir le périmètre (autre culture), rappeler que cela change la proposition et le jeu de test ; suggérer de garder ces sujets comme questions hors périmètre ou comme travail futur.
