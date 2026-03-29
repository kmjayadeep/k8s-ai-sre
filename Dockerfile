FROM python:3.12-slim

WORKDIR /app

COPY . .

RUN pip install uv && uv sync --frozen

EXPOSE 8080

CMD ["uv", "run", "main.py", "serve"]
