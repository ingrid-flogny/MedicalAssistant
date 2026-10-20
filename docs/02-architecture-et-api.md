# 02 · Architecture et API

## 1. Vue d'ensemble

```
┌────────────── Navigateur (app/static/index.html) ──────────────┐
│ 1. consentement  2. MediaRecorder (webm)  3. texte éditable     │
└───────┬──────────────────────────┬──────────────────────────────┘
        │ POST /api/transcriptions │ POST /api/observations
        │ (audio)                  │ (texte relu)
┌───────▼──────────────────────────▼───────── Conteneur ─────────┐
│ FastAPI (app/main.py)                                           │
│   ├─ app/transcription.py ── Whisper small, CPU, int8 (local)   │
│   └─ app/observations.py ─────────────────────────────┐         │
└───────────────────────────────────────────────────────┼─────────┘
                                                        │ HTTPS
                                              API Anthropic (Claude Sonnet)
```

Un seul conteneur sert la page, l'API et la transcription. Seul le **texte** de la
transcription quitte le serveur, vers l'API Claude ; l'audio reste dans le conteneur.

## 2. Parcours d'une consultation

1. **Consentement** : le médecin coche « Le patient a été informé de l'enregistrement et
   y a consenti ». Le bouton d'enregistrement reste désactivé tant que la case n'est pas
   cochée.
2. **Enregistrement** : le navigateur demande l'accès au microphone et enregistre avec
   l'API `MediaRecorder` (format webm/Opus en général). Un chronomètre s'affiche.
3. **Transcription** : à l'arrêt, l'audio est envoyé à `POST /api/transcriptions` ;
   Whisper le transcrit en mémoire. Le texte apparaît dans une zone **modifiable**.
4. **Relecture** : le médecin corrige la transcription si besoin. Il peut aussi coller un
   texte directement, sans enregistrement.
5. **Rédaction** : « Générer l'observation » envoie le texte à `POST /api/observations` ;
   Claude rédige l'observation en six rubriques.
6. **Validation** : l'observation apparaît dans une zone modifiable ; le médecin la relit,
   la corrige et la **copie** vers le dossier du patient.

L'application ne conserve rien : à la fermeture de la page, l'enregistrement, la
transcription et l'observation sont perdus.

## 3. API HTTP

### `POST /api/transcriptions`

Requête `multipart/form-data`, champ `audio` : un fichier audio (webm, wav, mp3, m4a…,
tout format décodable par FFmpeg via PyAV).

Réponse `200` :

```json
{ "text": "Bonjour docteur, je viens parce que je tousse depuis trois jours…" }
```

| Code | Cause |
|---|---|
| `422` « Audio illisible ou format non pris en charge. » | fichier non décodable |
| `422` « Aucune parole détectée dans l'enregistrement. » | silence uniquement (filtre de détection de voix) |

La route est déclarée en `def` (et non `async def`) : Whisper est bloquant, FastAPI
l'exécute dans un fil séparé, sans bloquer les autres requêtes.

### `POST /api/observations`

Requête JSON :

```json
{ "text": "transcription relue, non vide" }
```

Réponse `200` :

```json
{ "text": "MOTIF DE CONSULTATION\nToux depuis 3 jours…\n\nANAMNÈSE\n…" }
```

| Code | Cause (message renvoyé tel quel) |
|---|---|
| `422` | texte vide ou corps invalide |
| `502` « Clé API Anthropic non configurée (ANTHROPIC_API_KEY). » | variable absente |
| `502` « Clé API Anthropic absente ou invalide. » | clé refusée par l'API |
| `502` « Limite de requêtes atteinte, réessayez dans un instant. » | limite de débit |
| `502` « Erreur de l'API Claude (code). » | autre erreur de l'API |
| `502` « Impossible de joindre l'API Claude. » | réseau, certificat, pare-feu |
| `502` « Le modèle a refusé de traiter cette transcription. » | refus du modèle |
| `502` « Compte rendu tronqué : la consultation est trop longue. » | réponse au-delà de la limite de longueur |

`502` signale que l'erreur vient d'un service en amont (l'API Claude), pas de la requête.

### `GET /healthz`

`{"status": "ok"}`. Sondes de disponibilité et de vie d'OpenShift.

### `GET /`

La page web.

Exemples :

```bash
curl -F "audio=@consultation.webm" http://localhost:8080/api/transcriptions
curl -H "Content-Type: application/json" -d '{"text":"Patient de 40 ans, toux depuis 3 jours."}' \
     http://localhost:8080/api/observations
```

## 4. Interface

`app/static/index.html` : une seule page, HTML, CSS et JavaScript sans dépendance ni
étape de construction. Trois sections numérotées (enregistrement, transcription,
observation), des messages d'état sous chaque action, et le rappel que le texte généré
doit être relu et validé par le médecin.

L'accès au microphone exige un **contexte sécurisé** : `localhost` en développement,
**HTTPS** en production (la Route OpenShift l'impose).

## 5. Choix techniques

| Choix | Raison |
|---|---|
| Transcription locale (Whisper) plutôt qu'un service en ligne | l'audio, donnée la plus sensible, ne quitte pas le serveur |
| Modèle Whisper embarqué dans l'image | démarrage rapide, aucun téléchargement en production, fonctionnement sans accès à Hugging Face |
| Rédaction par Claude Sonnet | qualité de rédaction médicale en français, bon compromis qualité / rapidité / coût ; modèle réglable par `CLAUDE_MODEL` |
| Relecture humaine obligatoire entre chaque étape | la transcription et la rédaction peuvent se tromper ; le médecin reste responsable du contenu |
| Texte brut sans Markdown | collé tel quel dans un logiciel de dossier patient |
| Aucune persistance | rien à protéger sur disque, pas de base de données à héberger |
| Page sans framework | rien à construire ni à mettre à jour côté interface |
| Un seul conteneur | simple à construire, déployer et surveiller |

## 6. Vérifications effectuées

Il n'y a pas encore de tests automatisés. Vérifications faites de bout en bout dans
Docker :

| Vérification | Résultat |
|---|---|
| Transcription d'un échantillon de français synthétisé | texte correct en 3,6 s |
| Génération d'une observation à partir d'une transcription courte | six rubriques, rien d'inventé, « Non abordé » pour les rubriques absentes, environ 2 à 3 s |
| Démarrage sans clé API | l'application démarre ; la génération renvoie un message clair |
| Page d'accueil et `GET /healthz` | 200 |

L'interface n'a pas encore été vérifiée visuellement sur tous les navigateurs.
