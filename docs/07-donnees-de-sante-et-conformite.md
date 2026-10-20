# 07 · Données de santé et conformité

> Cette page résume les principes appliqués et les obligations identifiées. Elle ne
> constitue pas un avis juridique : avant tout usage avec de vrais patients, la faire
> valider par un juriste, le délégué à la protection des données (DPO) et, le cas
> échéant, une personne qualifiée en affaires réglementaires.

## 1. Quelles données passent par l'application

| Donnée | Nature | Où elle va | Durée de vie |
|---|---|---|---|
| Enregistrement audio | donnée de santé, voix (donnée biométrique potentielle) | navigateur → serveur MedicalAssistant | mémoire, le temps de la transcription |
| Transcription | donnée de santé | serveur → navigateur ; **serveur → API Anthropic** | mémoire du serveur le temps de la requête ; chez Anthropic, selon le contrat (section 3) |
| Observation | donnée de santé | API Anthropic → serveur → navigateur | idem |
| Consentement | case cochée dans la page | navigateur seulement | non enregistré |

## 2. Ce que fait l'application pour les protéger

- **Rien n'est écrit sur disque** : ni audio, ni transcription, ni observation. Il n'y a
  pas de base de données.
- **Rien n'est journalisé** : les messages d'erreur ne reprennent jamais le contenu des
  requêtes.
- **L'audio ne quitte pas le serveur** : la transcription est faite localement par
  Whisper. Seul le texte, déjà relu par le médecin, part vers l'API Claude.
- **Le texte envoyé est minimal** : la transcription et la consigne, sans identité du
  patient fournie par l'application (mais la conversation peut en contenir : nom, date
  de naissance prononcés pendant la consultation).
- **Consentement** : l'enregistrement est impossible tant que le médecin n'a pas confirmé
  l'information et le consentement du patient.
- **HTTPS** en production (Route OpenShift).
- **Secrets hors du code** : clé API dans `.env` ou dans un secret OpenShift.
- **Relecture humaine** à chaque étape, rappelée dans l'interface.
- **Pas de données réelles en développement** : uniquement des consultations fictives.

## 3. Envoi des transcriptions à Anthropic

C'est le principal point à cadrer : une transcription de consultation est une donnée de
santé, transmise à un sous-traitant situé hors de l'Union européenne.

À vérifier et à contractualiser avant tout usage réel :

- les **conditions commerciales** d'Anthropic et l'**accord de traitement des données**
  (DPA) au sens de l'article 28 du RGPD ;
- la **durée de conservation** des requêtes et l'éventuelle option de non-conservation
  (*zero data retention*), selon le contrat et le modèle utilisé ;
- l'**absence d'utilisation des données pour l'entraînement** des modèles (garantie des
  offres commerciales de l'API, à confirmer contractuellement) ;
- le **transfert hors UE** (États-Unis) et ses garanties (clauses contractuelles types,
  cadre de protection des données UE–États-Unis) ;
- l'éventuelle **pseudonymisation** de la transcription avant envoi (retirer noms,
  dates, adresses), qui réduirait l'exposition.

## 4. Avant un usage réel

| Exigence | Détail |
|---|---|
| **Authentification des médecins** | aujourd'hui, toute personne qui connaît l'adresse peut utiliser l'application. Il faut une authentification forte (par exemple Pro Santé Connect ou l'annuaire de l'établissement) |
| **Hébergement certifié HDS** | en France, héberger des données de santé pour le compte de tiers impose un hébergeur certifié HDS. Le Developer Sandbox de Red Hat ne l'est pas |
| **RGPD** | base légale (article 9 : soins), information du patient sur l'enregistrement et l'usage de l'IA, **analyse d'impact (AIPD)** obligatoire pour ce type de traitement, registre des traitements, désignation des sous-traitants |
| **Contrat avec Anthropic** | voir section 3 |
| **Statut réglementaire** | un outil qui se contente de mettre en forme ce qui a été dit, sans proposer de diagnostic ni de traitement, n'est en principe pas un dispositif médical. La consigne interdit au modèle d'ajouter une conduite à tenir ; cette limite doit être maintenue et vérifiée. Toute évolution vers de l'aide au diagnostic changerait la qualification (règlement (UE) 2017/745) |
| **Règlement européen sur l'IA** | obligations de transparence (l'utilisateur sait que le texte est généré par une IA, ce que rappelle l'interface) ; à réexaminer selon l'usage final |
| **Évaluation de la qualité** | jeu de consultations fictives annotées, relecture par des médecins, mesure des oublis et des ajouts, sur des cas variés (spécialités, accents, bruit) |
| **Journalisation de sécurité** | traçabilité des accès (qui a utilisé l'outil, quand), sans journaliser le contenu médical |
| **Disponibilité** | plusieurs réplicas, surveillance, procédure en cas d'indisponibilité de l'API Claude |

## 5. Limites à connaître des utilisateurs

- La transcription peut **mal comprendre** un nom de médicament, une posologie ou une
  négation (« pas de fièvre » / « de la fièvre »).
- Les propos du médecin et du patient **ne sont pas distingués** par la transcription.
- L'observation générée peut **omettre** une information ou la **classer** dans une
  mauvaise rubrique ; le modèle est consigné pour ne rien inventer, mais aucune consigne
  n'élimine totalement ce risque.
- Le texte « [à vérifier] » signale un doute du modèle ; son absence ne garantit pas
  l'exactitude.
- **Le médecin reste seul responsable** du contenu intégré au dossier du patient.
