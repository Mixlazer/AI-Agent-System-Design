FROM python:3.11-slim

WORKDIR /app
RUN pip install --no-cache-dir httpx
COPY init_providers.py .

CMD ["python", "init_providers.py", "http://registry:8010"]
