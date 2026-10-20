# 01 · Prérequis et installation

## 1. Comptes et accès

### Anthropic (obligatoire)

La rédaction des observations appelle l'API Claude.

1. Créer un compte sur https://console.anthropic.com et y configurer la facturation.
2. Créer une clé API dans **Settings → API Keys**.
3. Copier `.env.example` en `.env` et y coller la clé : `ANTHROPIC_API_KEY=sk-ant-…`.

Le fichier `.env` est exclu de Git. La clé ne doit jamais être commitée, affichée dans
un terminal partagé ni collée dans une conversation. Sans clé, l'application démarre et
transcrit, mais la génération répond « Clé API Anthropic non configurée ».

### GitHub (pour la livraison)

| Élément | Valeur |
|---|---|
| Dépôt | `ingrid-flogny/MedicalAssistant` (privé) |
| Image | `ghcr.io/ingrid-flogny/medicalassistant` (privée) |
| Accès Git | SSH (voir [Dépannage](08-depannage.md#git-ne-peut-pas-pousser-en-https)) |

### Red Hat OpenShift et Argo CD (pour le déploiement)

Un compte **Red Hat Developer Sandbox** (gratuit) fournit un cluster OpenShift. Voir
[Déploiement](06-deploiement-openshift-argocd.md).

## 2. Poste de travail

| Élément | Minimum | Utilisé pour le développement |
|---|---|---|
| Système | Windows, macOS ou Linux | Windows 11, processeur ARM64 |
| Docker | Docker Desktop récent, avec BuildKit | Docker Desktop 29.5 |
| Mémoire allouée à Docker | 3 Go | 15,4 Go |
| Disque | 4 Go (image de 2,8 Go) | |
| Navigateur | récent, avec accès au microphone | |
| Python (facultatif) | 3.12, pour l'éditeur | CPython 3.12 via uv |
| uv (facultatif) | 0.9 ou plus | |

L'application **s'exécute dans Docker**. Python installé sur le poste ne sert qu'à
l'éditeur (complétion, navigation dans le code).

### Particularités du poste de développement

- **Antivirus avec inspection HTTPS (Avast)** : les outils qui ne font pas confiance au
  magasin de certificats de Windows échouent (`UnknownIssuer`). D'où `uv … --native-tls`,
  le certificat racine exporté dans `.certs/local-ca.pem` (non versionné), transmis aux
  builds comme secret BuildKit `extra_ca`, et le fichier `compose.override.yaml` (non
  versionné).
- **Smart App Control** bloque des DLL non signées, dont celle de PyAV (décodage audio de
  Whisper) et le `libcurl` de Git. On ne contourne pas cette protection : l'application
  tourne dans Docker et Git passe par SSH. C'est aussi pourquoi Whisper est importé
  tardivement dans `app/transcription.py` : le reste de l'application démarre même là
  où il ne peut pas se charger.

## 3. Lancer l'application en local

```bash
git clone git@github.com:ingrid-flogny/MedicalAssistant.git
cd MedicalAssistant
cp .env.example .env                  # renseigner ANTHROPIC_API_KEY
docker compose up --build             # ou -d pour lancer en arrière-plan
```

- Premier lancement : quelques minutes (dépendances et modèle Whisper, embarqué dans
  l'image).
- Lancements suivants : quelques secondes.
- Adresse : **http://localhost:8080**. Le navigateur autorise le microphone sur
  `localhost` même sans HTTPS.
- Arrêter : `docker compose down`.

Après une modification du code : `docker compose up -d --build`.

### Poste dont le HTTPS est inspecté

Placer le certificat racine dans `.certs/local-ca.pem` et créer `compose.override.yaml`,
fusionné automatiquement avec `compose.yaml` :

```yaml
services:
  app:
    build:
      secrets:
        - extra_ca
    volumes:
      - ./.certs/local-ca.pem:/local-ca.pem:ro
    command: >
      sh -c "cat /etc/ssl/certs/ca-certificates.crt /local-ca.pem > /tmp/ca.pem
      && SSL_CERT_FILE=/tmp/ca.pem exec uvicorn app.main:app --host 0.0.0.0 --port 8080"

secrets:
  extra_ca:
    file: ./.certs/local-ca.pem
```

Au build, le certificat permet de télécharger les dépendances et Whisper ; à
l'exécution, il permet de joindre l'API Claude.

## 4. Ouvrir le projet dans PyCharm

1. **File → Open**, choisir le dossier `MedicalAssistant`.
2. Créer l'environnement local (une fois) : `uv sync --native-tls`.
3. **Settings → Project → Python Interpreter → Add Interpreter → Existing**, choisir
   `.venv\Scripts\python.exe`.

Lancer l'application depuis PyCharm n'est pas possible sur le poste de développement
(Smart App Control bloque PyAV) : utiliser Docker.

## 5. Variables d'environnement

| Variable | Défaut | Rôle |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | clé de l'API Claude (obligatoire pour la rédaction) |
| `CLAUDE_MODEL` | `claude-sonnet-5-5` | modèle de rédaction |
| `WHISPER_MODEL` | `small` | modèle Whisper ; à fixer **au build** (`--build-arg WHISPER_MODEL=…`), car le modèle est embarqué dans l'image |
| `WHISPER_LANGUAGE` | `fr` | langue de la consultation |
