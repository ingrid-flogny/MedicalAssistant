"""Rédaction des observations médicales à partir de la transcription, via l'API Claude."""

import os

import anthropic

CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")

SYSTEM_PROMPT = """\
Tu assistes un médecin en rédigeant le compte rendu d'observation d'une consultation \
à partir de sa transcription audio. Le médecin relira, corrigera et validera ton texte \
avant de l'intégrer au dossier du patient : il reste seul responsable du contenu.

La transcription est produite automatiquement. Elle ne distingue pas les locuteurs et \
peut contenir des erreurs, notamment sur les noms de médicaments et les posologies. \
Déduis du contexte qui parle. Si un terme semble mal transcrit, écris ta meilleure \
lecture suivie de « [à vérifier] » plutôt que de trancher en silence.

Rapporte uniquement ce qui a été dit pendant la consultation. N'ajoute aucun symptôme, \
résultat d'examen, diagnostic ou traitement qui n'y figure pas, et ne propose pas ta \
propre conduite à tenir : une information inventée dans un dossier médical est plus \
dangereuse qu'une information manquante.

Rédige en français, dans le style télégraphique habituel des observations médicales, \
en texte brut sans mise en forme Markdown, avec ces rubriques dans cet ordre :

MOTIF DE CONSULTATION
ANAMNÈSE
ANTÉCÉDENTS ET TRAITEMENTS EN COURS
EXAMEN CLINIQUE
CONCLUSION
CONDUITE À TENIR

Sous une rubrique dont rien n'a été dit, écris « Non abordé ». Réponds uniquement avec \
le compte rendu, sans introduction ni commentaire."""


class ObservationError(Exception):
    """Erreur présentable telle quelle à l'utilisateur."""


_client = anthropic.AsyncAnthropic()


async def generate_observations(transcript: str) -> str:
    if not (_client.api_key or _client.auth_token):
        raise ObservationError("Clé API Anthropic non configurée (ANTHROPIC_API_KEY).")
    try:
        async with _client.beta.messages.stream(
            model=CLAUDE_MODEL,
            max_tokens=16000,
            output_config={"effort": "medium"},
            # En cas de refus par un filtre de sécurité, l'API relance sur un autre modèle.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"<transcription>\n{transcript}\n</transcription>",
                }
            ],
        ) as stream:
            message = await stream.get_final_message()
    except anthropic.AuthenticationError as e:
        raise ObservationError("Clé API Anthropic absente ou invalide.") from e
    except anthropic.RateLimitError as e:
        raise ObservationError("Limite de requêtes atteinte, réessayez dans un instant.") from e
    except anthropic.APIStatusError as e:
        raise ObservationError(f"Erreur de l'API Claude ({e.status_code}).") from e
    except anthropic.APIConnectionError as e:
        raise ObservationError("Impossible de joindre l'API Claude.") from e

    if message.stop_reason == "refusal":
        raise ObservationError("Le modèle a refusé de traiter cette transcription.")
    if message.stop_reason == "max_tokens":
        raise ObservationError("Compte rendu tronqué : la consultation est trop longue.")

    return "".join(block.text for block in message.content if block.type == "text").strip()
