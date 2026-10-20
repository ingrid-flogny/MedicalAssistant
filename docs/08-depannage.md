# 08 · Dépannage

## Application

| Symptôme | Cause | Solution |
|---|---|---|
| Le bouton « Démarrer l'enregistrement » reste grisé | la case de consentement n'est pas cochée | cocher la case |
| « Accès au microphone refusé ou indisponible » | autorisation refusée dans le navigateur, aucun micro, ou page non sécurisée | autoriser le micro (icône dans la barre d'adresse) ; en production, utiliser l'adresse **https://** |
| « Aucune parole détectée dans l'enregistrement » | silence, micro coupé ou mauvais micro sélectionné | vérifier le micro choisi dans le navigateur et le système |
| « Audio illisible ou format non pris en charge » | fichier corrompu ou format inconnu | réenregistrer ; avec `curl`, envoyer un webm, wav, mp3 ou m4a |
| La transcription est très longue puis échoue en production | consultation longue, délai du routeur dépassé (5 min) | voir [Transcription](03-transcription-whisper.md#4-performances) |
| « Clé API Anthropic non configurée (ANTHROPIC_API_KEY) » | variable absente | renseigner `.env` (local) ou le secret `medicalassistant-secrets` (OpenShift), puis redémarrer |
| « Clé API Anthropic absente ou invalide » | clé révoquée, mal copiée (espace, guillemets) | recréer la clé dans la console Anthropic |
| « Impossible de joindre l'API Claude » | réseau, pare-feu, ou certificat inconnu (HTTPS inspecté) | en local sur un poste avec antivirus HTTPS : `compose.override.yaml` (voir [Installation](01-prerequis-et-installation.md#poste-dont-le-https-est-inspecté)) |
| « Limite de requêtes atteinte » | trop de requêtes en peu de temps, ou crédit épuisé | patienter ; vérifier la facturation dans la console Anthropic |
| « Le modèle a refusé de traiter cette transcription » | refus du modèle et du modèle de repli | relire la transcription ; signaler le cas s'il s'agit d'une consultation ordinaire |
| « Compte rendu tronqué » | réponse au-delà de 16 000 jetons | consultation exceptionnellement longue : la découper |
| La page s'affiche sans style ou avec une ancienne version | cache du navigateur | rechargement forcé (Ctrl+F5) |

## Docker

### Le build échoue sur `uv sync` ou au téléchargement de Whisper

`invalid peer certificate: UnknownIssuer` ou `CERTIFICATE_VERIFY_FAILED` : le HTTPS est
inspecté (antivirus, proxy). Exporter le certificat racine dans `.certs/local-ca.pem` et
construire avec le secret `extra_ca` (automatique avec `compose.override.yaml`).

### `av.open() got an unexpected keyword argument 'metadata_errors'`

Incompatibilité entre faster-whisper et PyAV 19. Le projet impose `av<19` dans
`pyproject.toml` ; ne pas retirer cette contrainte sans tester.

### Docker Desktop ne répond plus

`request returned 500 Internal Server Error … dockerDesktopLinuxEngine`, ou commandes
`docker` qui ne rendent pas la main :

```powershell
Get-Process | Where-Object { $_.Name -match '^(Docker Desktop|com\.docker\..*|docker)$' } | Stop-Process -Force
wsl --shutdown
Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
```

Si Kubernetes est activé dans Docker Desktop sans être utilisé (« Waiting for node to be
ready » en boucle), le désactiver (**Settings → Kubernetes**).

### Le port 8080 est déjà utilisé

Changer le port publié dans `compose.yaml` (`"8090:8080"`) ou arrêter l'autre
application.

## Windows (poste de développement)

### `DLL load failed … stratégie de contrôle d'application`

Smart App Control bloque la DLL de PyAV. Protection voulue : ne pas la désactiver ;
lancer l'application dans Docker.

### `uv` : `invalid peer certificate: UnknownIssuer`

Ajouter `--native-tls` : uv utilise alors le magasin de certificats de Windows.

### `.env` mal lu

Un fichier enregistré avec un BOM (par exemple par `Set-Content -Encoding utf8` dans
Windows PowerShell) fait ignorer la première variable. L'enregistrer en UTF-8 **sans**
BOM.

### Git ne peut pas pousser en HTTPS

`failed to load library 'libcurl-4.dll'` : Smart App Control bloque le libcurl de Git.
Le dépôt utilise SSH avec le client OpenSSH de Windows :

```powershell
git config core.sshCommand "C:/Windows/System32/OpenSSH/ssh.exe -i C:/Users/<vous>/.ssh/id_ed25519_github -o IdentitiesOnly=yes"
git remote set-url origin git@github.com:ingrid-flogny/MedicalAssistant.git
```

La clé publique doit être ajoutée dans **GitHub → Settings → SSH and GPG keys**.

### Commandes `docker run` cassées dans Git Bash

Git Bash convertit les arguments qui ressemblent à des chemins Unix (`/app`). Utiliser
PowerShell, ou préfixer la commande par `MSYS_NO_PATHCONV=1`.

### Caractères accentués refusés par l'API dans un test `curl`

`There was an error parsing the body` : le terminal n'a pas envoyé le JSON en UTF-8.
Tester avec un texte sans accents, ou passer le corps depuis un fichier UTF-8
(`curl -d @corps.json`).

## OpenShift

| Symptôme | Cause | Solution |
|---|---|---|
| pod en `ImagePullBackOff` | secret `ghcr-pull` absent ou jeton sans `read:packages` | recréer le secret, ou rendre le paquet public |
| pod en `CreateContainerConfigError` | secret `medicalassistant-secrets` absent | le créer (voir [Déploiement](06-deploiement-openshift-argocd.md#b-secrets-créés-à-la-main-jamais-dans-git)) |
| pod redémarré, `OOMKilled` | mémoire insuffisante pendant une transcription | augmenter `limits.memory`, ou utiliser un modèle Whisper plus petit |
| page accessible mais micro refusé | adresse en `http://` | utiliser `https://` (la Route redirige normalement) |
| `504 Gateway Timeout` pendant une transcription | délai du routeur dépassé | augmenter l'annotation `timeout` de la Route, ou raccourcir les enregistrements |
| `exec format error` au démarrage du pod | image construite pour ARM64 (poste local) | n'utiliser que les images construites par la CI (amd64) |
