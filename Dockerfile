# SolIntel - imagen Linux ligera (opcional). docker compose up -d
FROM python:3.12-slim
RUN groupadd --system solintel && useradd --system --gid solintel --home /app solintel
WORKDIR /app
COPY --chown=root:solintel src ./src
COPY --chown=root:solintel config ./config
RUN mkdir -p data logs && chown solintel:solintel data logs && chmod 700 data
USER solintel
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8080/api/salud')"
CMD ["python", "src/backend/servidor.py", "--con-simulador"]
