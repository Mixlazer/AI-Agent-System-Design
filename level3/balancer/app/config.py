import os

REGISTRY_URL = os.getenv("REGISTRY_URL", "http://registry:8010")
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
GUARDRAILS_URL = os.getenv("GUARDRAILS_URL", "http://guardrails:8020")
AUTH_URL = os.getenv("AUTH_URL", "http://auth:8030")
PROVIDER_TIMEOUT = float(os.getenv("PROVIDER_TIMEOUT", "120"))
