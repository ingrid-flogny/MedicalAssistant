# 06 · Déploiement OpenShift et Argo CD

> **État actuel** : les manifestes sont prêts dans `deploy/`, mais l'application n'a pas
> encore été déployée. Ce document décrit la cible et les étapes restantes.

## 1. Principe : GitOps

```
 développeur ──git push──▶ GitHub ──▶ GitHub Actions ──▶ image ghcr.io/…:sha-XXXX
                              │
                              │  deploy/kustomization.yaml (newTag: sha-XXXX)
                              ▼
                          Argo CD ──surveille le dépôt──▶ OpenShift (applique les manifestes)
```

- Le dossier `deploy/` du dépôt **décrit l'état voulu** du déploiement.
- **Argo CD** compare en permanence ce dossier à ce qui tourne dans le cluster, et
  applique les différences.
- **Déployer une nouvelle version** = changer le tag de l'image dans
  `deploy/kustomization.yaml` et pousser. **Revenir en arrière** = revenir à l'ancien tag
  (`git revert`). Tout changement passe par Git et reste tracé.

## 2. Les manifestes (`deploy/`)

| Fichier | Objet | Contenu |
|---|---|---|
| `deployment.yaml` | `Deployment` | 1 réplique ; image GHCR ; port 8080 ; clé API lue dans un secret ; sondes ; ressources |
| `service.yaml` | `Service` | expose le port 8080 des pods sous le nom `medicalassistant`, port nommé `http` |
| `route.yaml` | `Route` (OpenShift) | adresse publique en **HTTPS**, délai de 5 minutes |
| `kustomization.yaml` | Kustomize | liste les trois fichiers et fixe le **tag de l'image** déployée |

### `deployment.yaml` en détail

| Élément | Valeur | Raison |
|---|---|---|
| `imagePullSecrets` | `ghcr-pull` | nécessaire si le paquet GHCR est privé ; sans effet s'il est public |
| `ANTHROPIC_API_KEY` | lu dans le secret `medicalassistant-secrets`, clé `ANTHROPIC_API_KEY` | aucun secret dans Git |
| `readinessProbe` | `GET /healthz`, après 5 s | le trafic n'arrive qu'une fois le serveur prêt |
| `livenessProbe` | `GET /healthz`, après 15 s, toutes les 20 s | redémarrage automatique si le serveur ne répond plus |
| Ressources demandées | 250 millicœurs, 1 Gio | Whisper `small` occupe environ 1 Go une fois chargé |
| Limites | 2 cœurs, 2 Gio | plafond pour une transcription |

Le Deployment ne fixe ni utilisateur ni droits particuliers : l'image est déjà prévue
pour l'identifiant arbitraire d'OpenShift.

### `route.yaml`

- **TLS `edge`** : OpenShift termine le HTTPS et redirige le HTTP vers HTTPS. C'est
  **indispensable** : le navigateur refuse l'accès au microphone sur une page non
  sécurisée.
- **`haproxy.router.openshift.io/timeout: 5m`** : le routeur coupe par défaut les requêtes
  après 30 secondes, trop court pour transcrire une longue consultation.

### `kustomization.yaml`

```yaml
images:
  - name: ghcr.io/ingrid-flogny/medicalassistant
    newTag: sha-542d42faa3a613851c6118f3e805213a38d543f4
```

Ce tag désigne l'image construite pour le commit `542d42f` (application sans
SkinDetector, avec sa documentation). Vérifier dans l'onglet **Actions** du dépôt que ce
build a réussi avant de déployer.

## 3. Préparer le cluster

### a. Compte et connexion

1. Créer un compte **Red Hat Developer Sandbox** (https://developers.redhat.com/developer-sandbox) :
   cluster OpenShift gratuit, avec un projet (namespace) attribué et des quotas de
   ressources limités. L'accès est à renouveler périodiquement.
2. Installer le client `oc`, l'outil en ligne de commande d'OpenShift (équivalent de
   `kubectl`, avec des commandes propres à OpenShift).
3. Dans la console web : menu du compte → **Copy login command** → `oc login --token=… --server=…`.
   Le jeton est un secret : le saisir directement dans le terminal, jamais dans un
   document ou une conversation.

### b. Secrets (créés à la main, jamais dans Git)

```bash
# Clé API Anthropic
oc create secret generic medicalassistant-secrets \
  --from-literal=ANTHROPIC_API_KEY=<clé>

# Seulement si le paquet GHCR est privé : jeton GitHub (classic) avec le droit read:packages
oc create secret docker-registry ghcr-pull \
  --docker-server=ghcr.io \
  --docker-username=ingrid-flogny \
  --docker-password=<jeton GitHub>
```

Le dépôt est public, mais le paquet GHCR garde sa propre visibilité (privé par défaut).
Si on le rend public (page du paquet → **Package settings → Change visibility**), le
second secret est inutile : le pod démarre même si `ghcr-pull` n'existe pas.

### c. Quotas

Vérifier que le quota de mémoire du projet accepte 2 Gio de limite :
`oc describe quota` (ou `oc get resourcequota`).

## 4. Déployer

### Sans Argo CD (premier essai)

```bash
oc apply -k deploy/
oc rollout status deployment/medicalassistant
oc get route medicalassistant -o jsonpath='{.spec.host}'
```

Ouvrir l'adresse affichée en `https://`.

### Avec Argo CD

Argo CD a besoin de droits étendus sur le cluster pour s'installer (opérateur
*OpenShift GitOps*), que le Developer Sandbox n'accorde pas à ses utilisateurs.
Deux possibilités :

- faire tourner Argo CD **hors du Sandbox** (par exemple sur un petit cluster local) et
  lui déclarer le cluster du Sandbox comme destination, avec le jeton de connexion ;
- utiliser un cluster OpenShift où l'on a les droits d'administration.

Déclaration de l'application dans Argo CD :

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: medicalassistant
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/ingrid-flogny/MedicalAssistant.git
    targetRevision: main
    path: deploy
  destination:
    server: <URL de l'API du cluster>
    namespace: <projet OpenShift>
  syncPolicy:
    automated:
      prune: true      # supprime ce qui a disparu de deploy/
      selfHeal: true   # annule les modifications faites à la main dans le cluster
```

Le dépôt étant public, Argo CD le lit en HTTPS sans identifiants : rien à déclarer dans
ses paramètres de dépôts. Les secrets de l'application
(`medicalassistant-secrets`, `ghcr-pull`) restent créés à la main : Argo CD ne les gère
pas, puisqu'ils ne sont pas dans Git.

## 5. Mettre à jour la version déployée

1. Pousser le code sur `main` ; attendre le build vert dans **Actions**.
2. Copier le tag `sha-<SHA>` de la nouvelle image.
3. Le mettre dans `deploy/kustomization.yaml`, commiter, pousser.
4. Argo CD détecte le changement et déploie (ou `oc apply -k deploy/` sans Argo CD).

Cette mise à jour du tag pourra être automatisée plus tard (étape de la CI, ou Argo CD
Image Updater).

## 6. Exploitation

| Besoin | Commande |
|---|---|
| état des pods | `oc get pods -l app=medicalassistant` |
| journaux | `oc logs deployment/medicalassistant` |
| redémarrer | `oc rollout restart deployment/medicalassistant` |
| historique des versions | `oc rollout history deployment/medicalassistant` |
| consommation | `oc adm top pods` (si les métriques sont disponibles) |

Les journaux ne contiennent jamais d'audio, de transcription ni d'observation.

## 7. Limites de cette cible

- **Une seule réplique**, sans file d'attente : deux transcriptions simultanées se
  partagent les 2 cœurs. Pour plusieurs médecins, augmenter les répliques et les
  ressources.
- **Developer Sandbox** : environnement d'apprentissage, sans garantie de service ni
  certification pour des données de santé. Il ne convient qu'aux données fictives.
