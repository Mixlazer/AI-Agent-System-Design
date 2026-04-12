import os

REGISTRY_URL = os.getenv("REGISTRY_URL", "http://registry:8010")
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
PROVIDER_TIMEOUT = float(os.getenv("PROVIDER_TIMEOUT", "120"))
