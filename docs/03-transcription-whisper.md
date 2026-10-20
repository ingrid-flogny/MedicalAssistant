# 03 · Transcription (Whisper)

## 1. Le modèle

| | |
|---|---|
| Modèle | **Whisper `small`** (OpenAI), environ 244 millions de paramètres, multilingue |
| Bibliothèque | **faster-whisper** : réimplémentation de Whisper sur CTranslate2, plus rapide et plus économe en mémoire que l'implémentation d'origine |
| Exécution | **CPU**, poids quantifiés en **int8** |
| Langue | français, imposé (`WHISPER_LANGUAGE=fr`) |
| Décodage audio | PyAV (FFmpeg), version inférieure à 19 |
| Emplacement | téléchargé depuis Hugging Face **pendant la construction de l'image**, puis embarqué ; `HF_HUB_OFFLINE=1` interdit tout téléchargement à l'exécution |

## 2. Fonctionnement (`app/transcription.py`)

```python
WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
segments, _ = model.transcribe(audio, language=WHISPER_LANGUAGE, vad_filter=True)
text = " ".join(segment.text.strip() for segment in segments)
```

- **Chargement unique** : le modèle est chargé à la première transcription, puis gardé en
  mémoire (`lru_cache`).
- **Import différé** : `faster_whisper` n'est importé qu'à ce moment-là. Le reste de
  l'application démarre même sur un poste où ses bibliothèques natives sont bloquées.
- **Langue imposée** : évite une mauvaise détection sur un début d'enregistrement court ou
  bruité, et accélère le traitement.
- **Filtre de détection de voix** (`vad_filter=True`) : les silences sont retirés avant la
  transcription. Cela réduit le temps de calcul et évite que Whisper « invente » du texte
  sur les passages silencieux, un défaut connu du modèle.
- **En mémoire uniquement** : le flux audio reçu est passé directement à Whisper, sans
  fichier temporaire.

## 3. Pourquoi ce choix

| Option | Avantages | Inconvénients | Choix |
|---|---|---|---|
| **Whisper local** | l'audio ne quitte pas le serveur ; pas de coût par minute ; fonctionne hors ligne | consomme le CPU et la mémoire du serveur ; plus lent qu'un service spécialisé | **retenu** |
| Service de transcription en ligne | rapide, souvent plus précis, séparation des locuteurs | l'audio d'une consultation part chez un tiers : contrat, hébergement HDS, consentement | écarté |

### Pourquoi `small`

| Modèle | Paramètres | Commentaire |
|---|---|---|
| `tiny`, `base` | 39 M, 74 M | trop d'erreurs sur le vocabulaire médical |
| **`small`** | **244 M** | **compromis retenu** : environ 1 Go de mémoire, temps raisonnable sur CPU |
| `medium` | 769 M | meilleure précision, mais 2 à 3 fois plus lent et plus gourmand |
| `large-v3` | 1,55 G | le plus précis ; demande un GPU pour un usage interactif |

Pour changer de modèle : `docker compose build --build-arg WHISPER_MODEL=medium`, puis
augmenter la mémoire du déploiement en conséquence.

## 4. Performances

- Échantillon de français synthétisé : transcription correcte en **3,6 s** dans Docker.
- Une consultation réelle de 15 minutes prendra plusieurs minutes sur CPU. La Route
  OpenShift accepte des requêtes jusqu'à **5 minutes** (annotation `timeout: 5m`) : au-delà,
  il faudra un modèle plus léger, plus de CPU, ou un traitement asynchrone.
- Mémoire : environ **1 Go** une fois le modèle chargé (limite du déploiement : 2 Go).

## 5. Limites connues

- **Un seul flux, sans distinction des locuteurs** : la transcription ne dit pas qui du
  médecin ou du patient parle. Claude le déduit du contexte (consigne explicite).
- **Noms de médicaments et posologies** : principale source d'erreurs. La consigne de
  Claude demande de marquer les termes douteux « [à vérifier] » ; la relecture par le
  médecin reste indispensable.
- **Bruit, voix lointaines, chevauchements** : dégradent fortement la qualité. Un micro
  proche des deux interlocuteurs est préférable.
- **Hallucinations de Whisper** : sur des passages bruités, Whisper peut produire des
  phrases qui n'ont pas été dites. Le filtre de voix les limite sans les supprimer.
- **Consultations longues** : temps de traitement proportionnel à la durée (voir section 4).
