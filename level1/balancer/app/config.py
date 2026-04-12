import os
from dataclasses import dataclass, field
from typing import List, Dict


@dataclass
class ProviderConfig:
    name: str
    url: str
    api_key: str = ""
    models: List[str] = field(default_factory=list)
    weight: float = 1.0
    priority: int = 0


@dataclass
class Settings:
    providers: List[ProviderConfig] = field(default_factory=list)
    balancer_strategy: str = "round_robin"  # round_robin | weighted
    otel_endpoint: str = "http://otel-collector:4317"
    prometheus_port: int = 9090

    @classmethod
    def from_env(cls) -> "Settings":
        providers = []
        
        # Try new PROVIDER_{N}_* format first
        provider_index = 0
        while True:
            name = os.getenv(f"PROVIDER_{provider_index}_NAME")
            if name is None:
                # Fallback to legacy format
                legacy = cls._parse_legacy_providers()
                if legacy:
                    providers = legacy
                break
            
            url = os.getenv(f"PROVIDER_{provider_index}_URL", "")
            api_key = os.getenv(f"PROVIDER_{provider_index}_API_KEY", "")
            models_str = os.getenv(f"PROVIDER_{provider_index}_MODELS", "")
            models = [m.strip() for m in models_str.split(",") if m.strip()]
            weight = float(os.getenv(f"PROVIDER_{provider_index}_WEIGHT", "1.0"))
            priority = int(os.getenv(f"PROVIDER_{provider_index}_PRIORITY", "0"))
            
            providers.append(ProviderConfig(
                name=name, url=url, api_key=api_key,
                models=models, weight=weight, priority=priority
            ))
            provider_index += 1
        
        return cls(
            providers=providers,
            balancer_strategy=os.getenv("BALANCER_STRATEGY", "round_robin"),
            otel_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317"),
        )
    
    @classmethod
    def _parse_legacy_providers(cls) -> List[ProviderConfig]:
        """Parse legacy PROVIDERS format (pipe-separated)"""
        providers = []
        provider_defs = os.getenv("PROVIDERS", "").split(",")
        for pdef in provider_defs:
            pdef = pdef.strip()
            if not pdef:
                continue
            parts = pdef.split("|")
            name = parts[0] if len(parts) > 0 else ""
            url = parts[1] if len(parts) > 1 else ""
            api_key = parts[2] if len(parts) > 2 else ""
            models = parts[3].split(";") if len(parts) > 3 else []
            weight = float(parts[4]) if len(parts) > 4 else 1.0
            priority = int(parts[5]) if len(parts) > 5 else 0
            providers.append(ProviderConfig(
                name=name, url=url, api_key=api_key,
                models=models, weight=weight, priority=priority
            ))
        return providers


settings = Settings.from_env()
