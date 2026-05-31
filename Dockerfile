FROM python:3.12-slim-bookworm

ARG INSTALL_MSSQL=true

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        pkg-config \
        default-libmysqlclient-dev \
    && if [ "$INSTALL_MSSQL" = "true" ]; then \
        apt-get install -y --no-install-recommends \
            curl \
            gnupg \
            unixodbc \
            unixodbc-dev \
        && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
            | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
        && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" \
            > /etc/apt/sources.list.d/microsoft-prod.list \
        && apt-get update \
        && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 \
        ; fi \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/projects', timeout=3)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
