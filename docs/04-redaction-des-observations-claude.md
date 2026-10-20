# 04 · Rédaction des observations (Claude)

## 1. Le modèle

| | |
|---|---|
| Modèle | **Claude Sonnet 5.5** (`claude-sonnet-5-5`), réglable par `CLAUDE_MODEL` |
| Fournisseur | Anthropic, API Messages (`https://api.anthropic.com`) |
| Bibliothèque | SDK Python officiel `anthropic` (1.x), client asynchrone `AsyncAnthropic` |
| Authentification | variable `ANTHROPIC_API_KEY` |
| Tarif indicatif | 2 $ par million de jetons en entrée, 10 $ par million en sortie (tarif public Anthropic, octobre 2026) |

### Pourquoi Sonnet

Sonnet est le modèle intermédiaire de la gamme Claude : très bon en rédaction et en
synthèse, plus rapide et deux fois moins cher qu'Opus. Rédiger une observation à partir
d'une transcription est une tâche de synthèse fidèle, pas de raisonnement difficile :
Sonnet suffit, et sa rapidité compte pour un médecin qui attend le résultat. Le choix a
été fait explicitement pour ce projet ; il peut être changé par `CLAUDE_MODEL` sans
toucher au code.

### Coût par consultation (estimation)

Une consultation de 15 minutes produit environ 2 000 à 2 500 mots de transcription, soit
de l'ordre de 4 000 à 5 000 jetons en entrée avec la consigne, et 1 000 à 2 000 jetons en
sortie (observation et raisonnement du modèle). Ordre de grandeur : **2 à 3 centimes de
dollar par observation**. À confirmer sur des consultations réelles, avec les compteurs
de la console Anthropic.

## 2. La consigne (`SYSTEM_PROMPT`)

La consigne système, en français, fixe le rôle, les règles et le format. Ses principes :

| Règle | Formulation (résumé) | Raison |
|---|---|---|
| Responsabilité | le médecin relira, corrigera et validera ; il reste seul responsable | situe le modèle comme assistant de rédaction, pas comme décideur |
| Transcription imparfaite | pas de distinction des locuteurs, erreurs possibles sur les médicaments et posologies ; déduire du contexte qui parle | prévient le modèle des défauts connus de Whisper |
| Termes douteux | écrire la meilleure lecture suivie de **« [à vérifier] »** plutôt que trancher en silence | une erreur signalée se corrige ; une erreur silencieuse passe dans le dossier |
| **Ne rien inventer** | rapporter uniquement ce qui a été dit ; aucun symptôme, résultat, diagnostic ou traitement absent ; pas de conduite à tenir proposée par le modèle | « une information inventée dans un dossier médical est plus dangereuse qu'une information manquante » : la raison est donnée au modèle, pas seulement l'interdiction |
| Format | français, style télégraphique des observations, **texte brut sans Markdown** | collé tel quel dans un logiciel de dossier patient |
| Rubriques | six rubriques dans un ordre fixe | structure habituelle d'une observation, toujours la même |
| Rubrique vide | écrire **« Non abordé »** | distingue « rien de dit » de « oublié par le modèle » |
| Réponse | uniquement le compte rendu, sans introduction ni commentaire | pas de texte à retirer avant de copier |

Les six rubriques :

```
MOTIF DE CONSULTATION
ANAMNÈSE
ANTÉCÉDENTS ET TRAITEMENTS EN COURS
EXAMEN CLINIQUE
CONCLUSION
CONDUITE À TENIR
```

La transcription est transmise dans le message utilisateur, entourée de balises
`<transcription>…</transcription>` : le modèle sépare ainsi clairement les données à
traiter des consignes, et une phrase prononcée pendant la consultation (« ignore ce qui
précède… ») reste une donnée.

## 3. L'appel à l'API (`app/observations.py`)

```python
async with client.beta.messages.stream(
    model=CLAUDE_MODEL,                       # claude-sonnet-5-5
    max_tokens=16000,
    output_config={"effort": "medium"},
    betas=["server-side-fallback-2026-07-01"],
    fallbacks="default",
    system=SYSTEM_PROMPT,
    messages=[{"role": "user", "content": f"<transcription>\n{transcript}\n</transcription>"}],
) as stream:
    message = await stream.get_final_message()
```

| Paramètre | Rôle |
|---|---|
| `AsyncAnthropic` | client asynchrone : la route `/api/observations` est `async`, l'attente de la réponse ne bloque pas le serveur |
| `stream(...)` + `get_final_message()` | la réponse arrive en flux, mais le code attend simplement le message complet. Le flux évite les délais d'expiration HTTP sur les réponses longues ; l'interface n'affiche le texte qu'à la fin |
| `max_tokens=16000` | plafond de la réponse, raisonnement compris. Large pour ne jamais tronquer une observation ; on ne paie que ce qui est produit |
| `effort: "medium"` | profondeur de réflexion et volume de jetons du modèle. Sonnet 5.5 réfléchit par défaut (*adaptive thinking*) avant de répondre ; `medium` (le défaut est `high`) suffit pour une synthèse fidèle et réduit délai et coût |
| `fallbacks="default"` + en-tête bêta `server-side-fallback-2026-07-01` | si un filtre de sécurité d'Anthropic refuse la requête, l'API la relance automatiquement, dans le même appel, sur un autre modèle choisi selon la catégorie du refus. Un vocabulaire médical (médicaments, doses, anatomie) peut en effet déclencher un filtre à tort |
| `system` | la consigne de la section 2 |

Le raisonnement du modèle n'est pas renvoyé (affichage `omitted` par défaut) : le code
ne garde que les blocs de texte de la réponse.

## 4. Gestion des erreurs

Les erreurs sont converties en `ObservationError`, dont le message est affiché tel quel
au médecin (réponse HTTP 502) :

| Situation | Détection | Message |
|---|---|---|
| clé absente | aucune clé ni jeton dans le client, avant l'appel | « Clé API Anthropic non configurée (ANTHROPIC_API_KEY). » |
| clé refusée | `AuthenticationError` | « Clé API Anthropic absente ou invalide. » |
| trop de requêtes | `RateLimitError` | « Limite de requêtes atteinte, réessayez dans un instant. » |
| autre erreur de l'API | `APIStatusError` | « Erreur de l'API Claude (code). » |
| réseau | `APIConnectionError` | « Impossible de joindre l'API Claude. » |
| refus du modèle | `stop_reason == "refusal"` | « Le modèle a refusé de traiter cette transcription. » |
| réponse tronquée | `stop_reason == "max_tokens"` | « Compte rendu tronqué : la consultation est trop longue. » |

Précisions :

- Le SDK **réessaie automatiquement** deux fois les erreurs de réseau, 408, 409, 429 et
  5xx, avec un délai croissant, avant de lever l'exception.
- Un **refus** n'est pas une erreur HTTP : l'API répond normalement (200) avec
  `stop_reason: "refusal"`. Avec le repli activé, ce cas signifie que **toute la chaîne**
  (Sonnet puis le modèle de repli) a refusé.
- Les exceptions sont attrapées de la plus précise à la plus générale, pour distinguer
  les erreurs à réessayer (débit, réseau) de celles à corriger (clé).
- Aucun message d'erreur ne contient la transcription.

## 5. Qualité et limites

Vérifié sur une transcription courte : six rubriques, aucun élément inventé, « Non
abordé » pour les rubriques absentes, réponse en 2 à 3 secondes.

Limites connues :

- **Erreurs de transcription propagées** : si Whisper a mal compris un médicament, Claude
  ne peut le corriger qu'en signalant un doute. La relecture de la transcription avant
  génération est la meilleure protection.
- **Attribution des propos** : sans distinction des locuteurs, une phrase du patient peut
  être prise pour une constatation du médecin, et inversement.
- **Interprétation** : le modèle reformule et classe ; il peut placer une information dans
  la mauvaise rubrique ou résumer trop fort une nuance.
- **Variabilité** : deux générations sur la même transcription ne donnent pas exactement
  le même texte.
- **Pas d'évaluation systématique** : la qualité n'a été vérifiée que sur quelques
  exemples. Une évaluation sérieuse demanderait un jeu de transcriptions fictives
  annotées et une relecture par des médecins (voir
  [Conformité](07-donnees-de-sante-et-conformite.md#4-avant-un-usage-réel)).

## 6. Changer de modèle ou de consigne

- **Modèle** : `CLAUDE_MODEL=claude-opus-5-5` dans `.env` (ou le secret OpenShift), puis
  redémarrer. Le paramètre `fallbacks="default"` est accepté par les modèles actuels de
  la gamme ; vérifier la documentation d'Anthropic avant d'utiliser un modèle plus ancien.
- **Consigne** : modifier `SYSTEM_PROMPT` dans `app/observations.py`. Toute modification
  devrait être testée sur plusieurs transcriptions fictives, y compris des cas pièges
  (consultation incomplète, médicament mal transcrit, propos ambigus).
