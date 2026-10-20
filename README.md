# MedicalAssistant

Interface web pour médecins : **enregistrer une consultation**, la **transcrire** puis
faire **rédiger l'observation médicale** par une IA, à relire et valider avant de
l'intégrer au dossier du patient.

```
 Microphone ──▶ Enregistrement ──▶ Transcription ──▶ Relecture ──▶ Observation ──▶ Copier
 (navigateur)    (consentement)     Whisper, local   par le médecin  Claude Sonnet    vers le dossier
```

> **Avertissement.** MedicalAssistant est un projet en cours de développement, utilisé
> pour l'instant avec des **données fictives** uniquement. Avant tout usage avec de vrais
> patients, plusieurs exigences doivent être remplies : authentification des médecins,
> hébergement certifié HDS, cadre contractuel pour l'envoi des transcriptions à l'API
> Claude, analyse RGPD (voir [Données de santé et conformité](docs/07-donnees-de-sante-et-conformite.md)).

## En bref

| | |
|---|---|
| Transcription | **Whisper** (`small`, via faster-whisper), exécuté **dans le conteneur** : l'audio ne quitte pas le serveur |
| Rédaction | **Claude Sonnet** (`claude-sonnet-5-5`) via l'API Anthropic, avec une consigne qui interdit d'inventer |
| Format de l'observation | texte brut en six rubriques : motif, anamnèse, antécédents et traitements, examen clinique, conclusion, conduite à tenir |
| Technique | Python 3.12, FastAPI, page HTML sans framework, Docker |
| Livraison | GitHub Actions → image sur GitHub Container Registry → OpenShift, synchronisé par Argo CD |

## Démarrage rapide

Prérequis : Docker et une clé API Anthropic (détails dans
[Prérequis et installation](docs/01-prerequis-et-installation.md)).

```bash
cp .env.example .env          # puis renseigner ANTHROPIC_API_KEY
docker compose up --build
```

Ouvrir **http://localhost:8080**, cocher le consentement du patient, enregistrer, puis
générer l'observation.

## Documentation

| Document | Contenu |
|---|---|
| [01 · Prérequis et installation](docs/01-prerequis-et-installation.md) | comptes, clé API, poste de travail, lancement local, PyCharm |
| [02 · Architecture et API](docs/02-architecture-et-api.md) | composants, parcours d'une consultation, API HTTP, interface, configuration |
| [03 · Transcription (Whisper)](docs/03-transcription-whisper.md) | modèle, paramètres, performances, limites |
| [04 · Rédaction des observations (Claude)](docs/04-redaction-des-observations-claude.md) | modèle, consigne, paramètres de l'API, gestion des erreurs, limites |
| [05 · Image Docker et intégration continue](docs/05-image-docker-et-ci.md) | construction de l'image, GitHub Actions, registre GHCR |
| [06 · Déploiement OpenShift et Argo CD](docs/06-deploiement-openshift-argocd.md) | manifestes, secrets, mise en ligne, GitOps |
| [07 · Données de santé et conformité](docs/07-donnees-de-sante-et-conformite.md) | ce que fait l'application des données, prérequis réglementaires, limites |
| [08 · Dépannage](docs/08-depannage.md) | problèmes rencontrés et solutions |

## Organisation du dépôt

```
MedicalAssistant/
├── app/
│   ├── main.py               API FastAPI et page web
│   ├── transcription.py      Transcription locale avec Whisper
│   ├── observations.py       Rédaction de l'observation avec Claude
│   └── static/index.html     Interface (enregistrement, transcription, observation)
├── deploy/                   Manifestes OpenShift (Kustomize), suivis par Argo CD
├── .github/workflows/        Construction et publication de l'image
├── docs/                     Cette documentation
├── Dockerfile, compose.yaml  Image et lancement local
└── pyproject.toml, uv.lock   Dépendances
```

## Historique

L'application a un temps contenu un onglet **SkinDetector** (score de malignité d'une
lésion cutanée), devenu une application à part entière dans son propre dépôt,
`ingrid-flogny/SkinDetector`.
