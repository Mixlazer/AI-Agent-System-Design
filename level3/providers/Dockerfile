FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY mock_provider.py .

EXPOSE 8001

ENV PROVIDER_NAME=mock

CMD ["python", "mock_provider.py", "8001"]
