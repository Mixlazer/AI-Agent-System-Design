# Level 2 — Реестры агентов и умная маршрутизация

## Архитектура

```
┌──────────┐   ┌────────────────┐   ┌──────────────────┐
│  Client   │──▶│  LLM Balancer  │──▶│  OpenRouter :8001│
│           │◀──│  V2 :8000      │──▶│  vLLM      :8002│
│           │   │  (smart route) │──▶│  Ollama    :8003│
└──────────┘   └───────┬────────┘──▶│  Cloud     :8004│
                       │            └──────────────────┘
               ┌───────▼────────┐
               │  Registry :8010│
               │  (Agents +     │
               │   LLM Providers│
               │   dynamic reg) │
               └───────┬────────┘
                       │
           ┌───────────┼───────────┐
           ▼           ▼           ▼
    ┌────────────┐ ┌─────────┐ ┌────────┐
    │OTel Collect│ │  MLFlow │ │Prom/Gra│
    │  :4317     │ │  :5000  │ │:9090/   │
    └────────────┘ └─────────┘ │:3000   │
                               └────────┘
```

## Новые компоненты (по сравнению с Level 1)

| Сервис | Порт | Описание |
|--------|------|----------|
| `registry` | 8010 | A2A Agent Registry + LLM Provider Registry |
| `mlflow` | 5000 | MLFlow Tracking Server для трассировки |

## API Registry

### A2A Agent Registry

- `POST /a2a/agents` — зарегистрировать агента (Agent Card)
- `GET /a2a/agents` — список всех агентов
- `GET /a2a/agents/{name}` — карточка конкретного агента
- `DELETE /a2a/agents/{name}` — удалить агента

**Agent Card:**
```json
{
  "name": "assistant-agent",
  "description": "General-purpose assistant",
  "methods": ["chat", "stream"],
  "url": "http://balancer:8000",
  "models": ["mock-model-a"]
}
```

### LLM Provider Registry (динамическая регистрация)

- `POST /llm/providers` — зарегистрировать провайдера
- `GET /llm/providers` — список всех провайдеров
- `GET /llm/providers/{name}` — информация о провайдере
- `GET /llm/providers/healthy` — только здоровые провайдеры
- `DELETE /llm/providers/{name}` — удалить провайдера
- `POST /llm/providers/{name}/restore` — восстановить unhealthy провайдера

**Регистрация провайдера:**
```json
{
  "name": "openrouter",
  "url": "http://openrouter:8001",
  "models": ["mock-model-a", "mock-model-b"],
  "price_per_token_input": 0.00001,
  "price_per_token_output": 0.00003,
  "rate_limit": 60,
  "priority": 1,
  "weight": 1.0
}
```

## Стратегии маршрутизации

Выбор стратегии через query-параметр `?strategy=`:

| Стратегия | Описание |
|-----------|----------|
| `round_robin` | Круговой перебор провайдеров |
| `weighted` | Выбор по статическим весам |
| `latency` | **(по умолчанию)** Приоритет быстрому провайдеру (EMA latency) |
| `health` | Health-aware: приоритет по (healthy, priority, -consecutive_errors, latency) |

При 3+ последовательных ошибках провайдер автоматически помечается как unhealthy и исключается из пула.

## Новые метрики

| Метрика | Тип | Описание |
|---------|-----|----------|
| `llm_ttft_seconds` | Histogram | Time-to-First-Token |
| `llm_tpot_seconds` | Histogram | Time-per-Output-Token |
| `llm_input_tokens_total` | Counter | Входные токены |
| `llm_output_tokens_total` | Counter | Выходные токены |
| `llm_request_cost_total` | Counter | Стоимость запросов |

## MLFlow трассировка

Каждый LLM-запрос логируется в MLFlow как span с атрибутами:
- provider, model, latency, ttft, input_tokens, output_tokens, cost, success, strategy

## Запуск

```bash
cd level2
docker compose up --build
```

## Проверка

```bash
# Registry health
curl http://localhost:8010/health

# Список провайдеров (после init)
curl http://localhost:8010/llm/providers

# Список агентов
curl http://localhost:8010/a2a/agents

# Запрос с latency-маршрутизацией (default)
curl -X POST "http://localhost:8000/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{"model":"mock-model-a","messages":[{"role":"user","content":"Hi"}]}'

# Запрос с health-aware маршрутизацией
curl -X POST "http://localhost:8000/v1/chat/completions?strategy=health" \
  -H "Content-Type: application/json" \
  -d '{"model":"mock-model-a","messages":[{"role":"user","content":"Hi"}]}'

# Balancer provider states
curl http://localhost:8000/balancer/providers

# MLFlow UI
open http://localhost:5000

# Grafana
open http://localhost:3000  (admin/admin)
```
