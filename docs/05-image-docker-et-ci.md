# 05 · Image Docker et intégration continue

## 1. L'image (`Dockerfile`)

Base `python:3.12-slim`. Étapes, dans l'ordre choisi pour profiter du cache de Docker
(les étapes coûteuses et rarement modifiées d'abord) :

| Étape | Détail |
|---|---|
| 1. uv | copié depuis l'image officielle `ghcr.io/astral-sh/uv:0.9.15` |
| 2. Dépendances | `uv sync --frozen --no-dev --no-install-project` : versions exactes de `uv.lock`, environnement dans `/app/.venv` |
| 3. Whisper | le modèle (`small` par défaut, argument de build `WHISPER_MODEL`) est téléchargé et embarqué dans `/opt/hf` |
| 4. Hors ligne | `HF_HUB_OFFLINE=1` : plus aucun téléchargement à l'exécution |
| 5. Code | `COPY app ./app` : une modification du code ne refait que cette étape |
| 6. OpenShift | `/app` et `/opt/hf` appartiennent au groupe 0 avec les mêmes droits que leur propriétaire : OpenShift lance les conteneurs avec un identifiant d'utilisateur arbitraire membre de ce groupe |
| 7. Utilisateur | `USER 1001` : jamais root |
| 8. Démarrage | `uvicorn app.main:app --host 0.0.0.0 --port 8080` |

Taille : environ **2,8 Go** (PyAV, CTranslate2, modèle Whisper).

### Le secret `extra_ca`

Sur un poste dont le HTTPS est inspecté (antivirus, proxy d'entreprise), les étapes 2 et
3 échouent faute de reconnaître le certificat. Le build accepte un **secret BuildKit
facultatif** `extra_ca` : une autorité de certification ajoutée pendant ces étapes
seulement, jamais copiée dans l'image.

```bash
docker build --secret id=extra_ca,src=.certs/local-ca.pem -t medicalassistant:dev .
```

La CI n'en a pas besoin ; `compose.override.yaml` le fournit automatiquement en local.

### Fichiers exclus (`.dockerignore`)

`.venv/`, `.idea/`, `.git/`, `.env`, `.certs/`, `__pycache__/` : ni secrets, ni
environnement local, ni historique Git dans l'image.

## 2. Intégration continue (`.github/workflows/build.yml`)

```
push sur main ──▶ GitHub Actions ──▶ build linux/amd64 ──▶ ghcr.io/ingrid-flogny/medicalassistant
                                                          ├─ sha-<SHA complet du commit>
                                                          └─ latest
pull request  ──▶ GitHub Actions ──▶ build seul (vérifie que l'image se construit, sans publier)
```

| Étape | Action |
|---|---|
| Récupération du code | `actions/checkout@v4` |
| Buildx | `docker/setup-buildx-action@v3` |
| Connexion à GHCR | `docker/login-action@v3`, avec le `GITHUB_TOKEN` du dépôt, seulement sur un push |
| Tags | `docker/metadata-action@v5` : `sha-<SHA long>` et `latest` (branche principale) |
| Build et publication | `docker/build-push-action@v6`, plateforme `linux/amd64`, cache GitHub Actions |

Points notables :

- **amd64** : les serveurs d'OpenShift sont en x86_64, alors que le poste de développement
  est en ARM64. L'image construite localement ne convient donc pas au cluster : c'est la
  CI qui produit l'image déployée.
- **Tag par commit** : chaque image est rattachée au commit exact qui l'a produite. Les
  manifestes de déploiement référencent ce tag, jamais `latest`, pour savoir précisément
  ce qui tourne et pouvoir revenir en arrière.
- **Permissions minimales** : le job ne peut que lire le code et écrire dans le registre
  du dépôt (`contents: read`, `packages: write`).
- **Cache** : les couches inchangées (dépendances, Whisper) sont réutilisées d'un build
  à l'autre.

## 3. Le registre (GitHub Container Registry)

- Image : `ghcr.io/ingrid-flogny/medicalassistant`, **privée** comme le dépôt.
- Consultation : page du dépôt → **Packages**.
- Pour que le cluster puisse la télécharger : secret `ghcr-pull` (voir
  [Déploiement](06-deploiement-openshift-argocd.md#3-préparer-le-cluster)), ou rendre
  le paquet public.

## 4. Tester une image de la CI en local

```bash
docker pull ghcr.io/ingrid-flogny/medicalassistant:sha-<SHA>   # après docker login ghcr.io
docker run --rm -p 8080:8080 --env-file .env ghcr.io/ingrid-flogny/medicalassistant:sha-<SHA>
```

Sur un poste ARM64, l'image amd64 tourne en émulation, nettement plus lentement.
