FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.9.15 /uv /bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    HF_HOME=/opt/hf \
    PATH="/app/.venv/bin:$PATH"

# Secret optionnel `extra_ca` : autorité de certification supplémentaire pour les postes
# dont le trafic HTTPS est inspecté (antivirus, proxy). Utilisé pendant le build
# uniquement, jamais copié dans l'image ; la CI s'en passe.
COPY pyproject.toml uv.lock ./
RUN --mount=type=secret,id=extra_ca,required=false \
    if [ -f /run/secrets/extra_ca ]; then \
        cat /etc/ssl/certs/ca-certificates.crt /run/secrets/extra_ca > /tmp/ca.pem; \
        export SSL_CERT_FILE=/tmp/ca.pem; \
    fi; \
    uv sync --frozen --no-dev --no-install-project && rm -f /tmp/ca.pem

# Le modèle Whisper est embarqué dans l'image : aucun téléchargement au démarrage du pod.
ARG WHISPER_MODEL=small
ENV WHISPER_MODEL=${WHISPER_MODEL}
RUN --mount=type=secret,id=extra_ca,required=false \
    if [ -f /run/secrets/extra_ca ]; then \
        cat /etc/ssl/certs/ca-certificates.crt /run/secrets/extra_ca > /tmp/ca.pem; \
        export SSL_CERT_FILE=/tmp/ca.pem REQUESTS_CA_BUNDLE=/tmp/ca.pem; \
    fi; \
    python -c "from faster_whisper import WhisperModel; WhisperModel('${WHISPER_MODEL}', device='cpu', compute_type='int8')" \
    && rm -f /tmp/ca.pem
ENV HF_HUB_OFFLINE=1

COPY app ./app

# OpenShift lance le conteneur avec un UID arbitraire appartenant au groupe 0.
RUN chgrp -R 0 /app /opt/hf && chmod -R g=u /app /opt/hf
USER 1001

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
