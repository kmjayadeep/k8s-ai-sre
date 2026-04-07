FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && curl -fsSL https://dl.k8s.io/release/v1.32.0/bin/linux/amd64/kubectl -o /usr/local/bin/kubectl \
    && chmod +x /usr/local/bin/kubectl \
    && rm -rf /var/lib/apt/lists/*

COPY . .

RUN pip install uv && uv sync --frozen

ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

EXPOSE 8080

CMD ["uv", "run", "main.py"]
