# Level 1 — Минимальный прототип: LLM-провайдеры, балансировщик и базовый мониторинг

## Архитектура

```
┌──────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Client      │────▶│  LLM Balancer    │────▶│  OpenRouter     │ :8001
│  (curl/etc)   │     │  (FastAPI)       │────▶│  vLLM           │ :8002
│               │◀────│  :8000           │◀────│  Ollama         │ :8003
└──────────────┘     │                  │     │  Cloud          │ :8004
                     │  OTel SDK        │     └─────────────────┘
                     └────────┬─────────┘
                              │
                     ┌────────▼─────────┐
                     │  OTel Collector   │ :4317
                     └────────┬─────────┘
                              │
                     ┌────────▼─────────┐
                     │  Prometheus       │ :9090
                     └────────┬─────────┘
                              │
                     ┌────────▼─────────┐
                     │  Grafana          │ :3000
                     └──────────────────┘
```

## Компоненты

| Сервис | Порт | Описание |
|--------|------|----------|
| `balancer` | 8000 | FastAPI прокси-балансировщик |
| `openrouter` | 8001 | Мок OpenRouter провайдер |
| `vllm` | 8002 | Мок vLLM провайдер |
| `ollama` | 8003 | Мок Ollama провайдер |
| `cloud` | 8004 | Мок Cloud провайдер |
| `otel-collector` | 4317 | OpenTelemetry Collector |
| `prometheus` | 9090 | Хранилище метрик |
| `grafana` | 3000 | Дашборды (admin/admin) |

## API балансировщика

### `GET /health`
Health-check. Возвращает статус и список провайдеров.

### `GET /v1/models`
Список доступных моделей.

### `POST /v1/chat/completions`
OpenAI-совместимый эндпоинт. Поддерживает `stream: true`.

**Тело запроса** (OpenAI-формат):
```json
{
  "model": "mock-model-a",
  "messages": [{"role": "user", "content": "Hello"}],
  "stream": false
}
```

**Балансировка**: по названию модели → round-robin между провайдерами с этой моделью. При `BALANCER_STRATEGY=weighted` — по статическим весам.

## Стратегии балансировки

- **round_robin** (по умолчанию): циклический перебор провайдеров для каждой модели
- **weighted**: выбор провайдера пропорционально весу (параметр `weight`)

## Метрики

| Метрика | Тип | Описание |
|---------|-----|----------|
| `llm_requests_total` | Counter | Число запросов (лейблы: provider, model) |
| `llm_request_latency_seconds` | Histogram | Латентность запросов |
| `llm_active_requests` | UpDownCounter | Активные запросы |

## Запуск

```bash
cd level1
docker compose up --build
```

## Проверка

```bash
# Health check
curl http://localhost:8000/health

# Список моделей
curl http://localhost:8000/v1/models

# Запрос (non-streaming)
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"mock-model-a","messages":[{"role":"user","content":"Hi"}]}'

# Запрос (streaming)
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"mock-model-a","messages":[{"role":"user","content":"Hi"}],"stream":true}'

# Prometheus
curl http://localhost:9090/api/v1/query?query=llm_llm_requests_total

# Grafana
open http://localhost:3000  (admin/admin)
```

## Grafana дашборды

Преднастроены два графика:
1. **Latency (p50/p95)** — гистограмма латентности
2. **Traffic by Provider** — распределение запросов по провайдерам
3. **Active Requests** — текущее число активных запросов
4. **Pie chart** — доля трафика по провайдерам
