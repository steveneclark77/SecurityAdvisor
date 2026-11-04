FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN --mount=type=secret,id=pip_ca_bundle \
    if [ -f /run/secrets/pip_ca_bundle ]; then \
      PIP_CERT=/run/secrets/pip_ca_bundle pip install --no-cache-dir -r requirements.txt; \
    else pip install --no-cache-dir -r requirements.txt; fi
RUN useradd --create-home app
COPY --chown=app:app . .
USER app
EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
