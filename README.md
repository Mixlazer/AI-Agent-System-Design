# LLM Balancer with Smart Complexity-Based Routing

Домашнее задание по бонус-треку LLM (ИТМО, магистратура AI, 2025-2026).

| Параметр | Значение |
|----------|----------|
| **Трек** | Инфраструктурный — Разработка LLM Balancer |
| **Автор** | Лазарчик Михаил |
| **Сроки** | 13.04.2026 - 13.04.2026 |
| **Уровень** | Level 1 — Минимальный прототип (10 баллов) |

## Описание

API-шлюз для LLM-запросов с интеллектуальной балансировкой нагрузки по сложности запроса, системой очереди с приоритетами и полным стеком мониторинга.

Платформа предоставляет OpenAI-совместимый эндпоинт `/v1/chat/completions`, за которым стоит пул из 3 LLM-провайдеров (OpenRouter, Ollama, vLLM) с маршрутизацией по сложности запроса.

## Возможности

- 🧠 **Smart Routing** — маршрутизация по сложности: LOW → vLLM, MEDIUM → Ollama, HIGH → OpenRouter
- 📊 **Queue Management** — очередь запросов с приоритетами и emergency mode (queue ≥ 10)
- 🔄 **Fallback Logic** — автоматический fallback при загруженности провайдеров
- 📈 **Monitoring** — OpenTelemetry → Prometheus → Grafana
- ⚖️ **Стратегии** — Round-robin, Weighted
- 🌊 **Streaming** — SSE-стриминг без разрыва соединений
- 🔍 **Complexity Detection** — автоматическое определение сложности по длине и ключевым словам

---

## Архитектура

```
                    ┌─────────────────────────────────────┐
                    │           HTTP Request              │
                    └──────────────┬──────────────────────┘
                                   │
                         ┌─────────▼─────────┐
                         │  Balancer :8000    │
                         │  - Complexity     │
                         │    detection      │
                         │  - Smart routing  │
                         │  - Queue mgmt     │
                         └─────────┬─────────┘
                                   │
         ┌──────────────────┬──────┴──────┬──────────────────┐
         │                  │             │                  │
    ┌────▼────┐       ┌────▼────┐   ┌────▼────┐       ┌────▼────┐
    │OpenRouter│       │  Ollama  │   │  vLLM   │       │ Fallback │
    │ :8001   │       │  :8003   │   │  :8002  │       │  Queue   │
    │ Priority│       │ Priority │   │ Priority│       │          │
    │    0    │       │    1     │   │    2    │       │          │
    └─────────┘       └──────────┘   └─────────┘       └──────────┘

    ┌─────────┐    ┌──────────┐    ┌────────┐
    │Prometheus│   │ Grafana  │    │ OTel   │
    │  :9090  │    │  :3000   │    │:4317   │
    └─────────┘    └──────────┘    └────────┘
```

Подробные диаграммы потока запросов и логики маршрутизации: [docs/architecture.md](docs/architecture.md)

---

## Быстрый старт

### Требования
- Docker + Docker Compose
- API-ключ OpenRouter (для cloud-провайдера)
- HuggingFace токен (для загрузки моделей vLLM)

### Запуск

```bash
# 1. Клонировать репозиторий
git clone https://github.com/YOUR_USERNAME/llm-balancer.git && cd llm-balancer

# 2. Создать .env
cp level1/.env.example level1/.env
# Вписать OPENROUTER_API_KEY и HF_TOKEN в .env

# 3. Запустить все сервисы
cd level1
docker compose up --build -d

# 4. Смотреть логи загрузки моделей (5-15 минут)
docker compose logs -f vllm ollama
```

После запуска доступны:

| Сервис | URL | Логин |
|--------|-----|-------|
| **API (балансер)** | http://localhost:8000 | — |
| **Prometheus** | http://localhost:9090 | — |
| **Grafana** | http://localhost:3000 | admin/admin |
| **OTel Collector** | http://localhost:4317 | — |
| **vLLM** | http://localhost:8002 | — |
| **Ollama** | http://localhost:8003 | — |

### Проверка работоспособности

```bash
# Health-check
curl http://localhost:8000/health

# Тестовый запрос к LLM
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "minimax/minimax-m2.5:free",
    "messages": [{"role": "user", "content": "Hello!"}],
    "stream": false,
    "max_tokens": 100
  }'
```

---

## API Reference

### POST /v1/chat/completions

OpenAI-совместимый эндпоинт для генерации ответов LLM с интеллектуальной маршрутизацией.

**Параметры запроса:**

| Параметр | Тип | Обязательный | Описание |
|----------|-----|--------------|----------|
| model | string | да | Идентификатор модели |
| messages | array | да | Массив сообщений {role, content} |
| stream | bool | нет | SSE-стриминг (по умолчанию: false) |
| max_tokens | int | нет | Максимум токенов в ответе |
| temperature | float | нет | Температура генерации |

**Логика маршрутизации:**
- Сложность определяется автоматически по длине промпта и ключевым словам
- **LOW** (<100 chars, простые вопросы) → vLLM (priority 2)
- **MEDIUM** (>100 chars, код, SQL) → Ollama (priority 1)
- **HIGH** (>500 chars, архитектура, анализ) → OpenRouter (priority 0)
- Если целевой провайдер занят → fallback к следующему по приоритету
- Если queue ≥ 10 → emergency mode (любой провайдер может ответить)

**Запрос (non-streaming):**
```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "minimax/minimax-m2.5:free",
    "messages": [{"role": "user", "content": "Напиши SQL запрос для поиска дубликатов"}],
    "stream": false,
    "max_tokens": 200
  }'
```

**Запрос (streaming):**
```bash
curl -N -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "minimax/minimax-m2.5:free",
    "messages": [{"role": "user", "content": "Hello!"}],
    "stream": true
  }'
```

### GET /health

Проверка здоровья сервиса с информацией о провайдерах и очереди.

```bash
curl http://localhost:8000/health
```

**Ответ:**
```json
{
  "status": "ok",
  "providers": ["openrouter", "ollama", "vllm"],
  "queue_stats": {
    "queue_size": 0,
    "active_requests": {},
    "total_pending": 0
  },
  "strategy": "weighted"
}
```

### GET /queue/stats

Детальная статистика очереди запросов.

```bash
curl http://localhost:8000/queue/stats
```

### GET /v1/models

Список доступных моделей от всех провайдеров.

```bash
curl http://localhost:8000/v1/models
```

---

## Балансировка нагрузки

### Round Robin

Циклический перебор провайдеров. Используется для равномерного распределения нагрузки.

```bash
BALANCER_STRATEGY=round_robin
```

### Weighted

Выбор провайдера пропорционально весу. Веса настраиваются через `PROVIDER_*_WEIGHT` в `.env`.

```bash
BALANCER_STRATEGY=weighted
```

**Пример конфигурации:**
```env
PROVIDER_0_WEIGHT=2.0  # OpenRouter — высокий вес (мощный)
PROVIDER_1_WEIGHT=1.5  # Ollama — средний вес
PROVIDER_2_WEIGHT=1.0  # vLLM — низкий вес (простой)
```

### Complexity-based Routing

Основная логика маршрутизации Level 1:

| Сложность | Критерии | Провайдер | Fallback |
|-----------|----------|-----------|----------|
| **LOW** | <100 chars, привет, шутка, 2+2 | vLLM (priority 2) | — |
| **MEDIUM** | >100 chars, SQL, код, объяснение | Ollama (priority 1) | vLLM |
| **HIGH** | >500 chars, архитектура, анализ, ML | OpenRouter (priority 0) | Ollama → vLLM (emergency) |

**Emergency Mode:** При queue ≥ 10 запросов, любой провайдер может ответить на любой запрос для предотвращения деградации.

---

## Queue Management

### Очередь запросов

- Фоновый процессор очереди (`_process_queue`)
- Отслеживание активных запросов по провайдерам
- Приоритет при освобождении провайдера (сложные запросы первыми)

### Эндпоинты мониторинга очереди

```bash
# Статистика очереди
curl http://localhost:8000/queue/stats

# В health check
curl http://localhost:8000/health | jq .queue_stats
```

---

## Наблюдаемость

### Метрики (Prometheus + Grafana)

Платформа экспортирует метрики через `/metrics` в формате Prometheus:

| Метрика | Тип | Описание | Лейблы |
|---------|-----|----------|--------|
| `llm_requests_total` | Counter | Запросы по провайдеру/модели | provider, model, complexity |
| `llm_request_latency_seconds` | Histogram | Латентность (end-to-end) | provider, model, complexity |
| `llm_active_requests` | UpDownCounter | Активные запросы | provider |

**PromQL запросы:**

```promql
# RPS по провайдерам
rate(llm_requests_total[1m])

# Средняя латентность
rate(llm_request_latency_seconds_sum[5m]) / 
  rate(llm_request_latency_seconds_count[5m])

# 95-й перцентиль
histogram_quantile(0.95, rate(llm_request_latency_seconds_bucket[5m]))

# Распределение по сложности
sum by (complexity) (llm_requests_total)
```

Prometheus скрейпит каждые 15 секунд. Grafana подключена автоматически.

### Трассировка (OpenTelemetry)

Каждый HTTP-запрос оборачивается в OTel span с атрибутами:
- `http.method`, `http.url`, `http.status_code`
- `provider`, `model`, `complexity`
- `latency`, `queue_size`

### Дашборд Grafana

Дашборд "LLM Balancer" доступен сразу после запуска на http://localhost:3000 (admin/admin).

Панели:
- **Latency by Provider** — латентность по провайдерам (p50/p95)
- **Traffic Distribution** — распределение трафика (pie chart)
- **Requests by Complexity** — распределение по сложности
- **Queue Size** — размер очереди в реальном времени
- **Active Requests** — активные запросы по провайдерам

---

## Нагрузочное тестирование

### Тесты

| Тест | Длительность | Нагрузка | Особенности |
|------|--------------|----------|-------------|
| `quick_test.py` | 5 минут | 10 RPM | Равномерная нагрузка |
| `advanced_load_test.py` | 10 минут | 5-30 RPM | Синусоидальная нагрузка (day/night cycle) |

**Сценарии:**
- 67% HIGH сложности (архитектура, анализ)
- 16% MEDIUM сложности (SQL, код)
- 17% LOW сложности (простые вопросы)

### Запуск тестов

```bash
cd load-testing

# Быстрый тест
python3 quick_test.py

# Продвинутый тест с синусоидой
python3 advanced_load_test.py
```

**Результаты:**
- JSON-файл с детальной статистикой
- Реал-тайм вывод ответов моделей в терминал
- Метрики в Prometheus/Grafana

---

## Переменные окружения

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `PROVIDER_0_API_KEY` | "" | API-ключ OpenRouter |
| `PROVIDER_1_MODELS` | "gemma4:31b-cloud" | Модели Ollama |
| `PROVIDER_2_MODELS` | "google/gemma-4-E2B-it" | Модель vLLM |
| `BALANCER_STRATEGY` | "weighted" | Стратегия балансировки |
| `HF_TOKEN` | "" | HuggingFace токен |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | "http://otel-collector:4317" | OTel endpoint |

---

## Структура проекта

```
llm-balancer/
├── level1/
│   ├── balancer/
│   │   └── app/
│   │       ├── main.py              # FastAPI entrypoint
│   │       ├── balancer.py          # SmartLLMBalancer
│   │       ├── config.py            # Config from .env
│   │       └── telemetry.py         # OpenTelemetry
│   ├── docker-compose.yml           # Real providers
│   └── .env                         # API keys (in .gitignore)
│
├── load-testing/
│   ├── advanced_load_test.py       # 10 min sinusoidal test
│   ├── quick_test.py               # 5 min quick test
│   └── README.md
│
├── monitoring/
│   ├── prometheus.yml
│   └── grafana/
│       └── dashboards/
│
├── docs/
│   └── architecture.md              # Detailed diagrams
│
├── .gitignore
└── README.md                        # This file
```

---

## Стек технологий

| Компонент | Технология |
|-----------|------------|
| Язык | Python 3.11 |
| Web-фреймворк | FastAPI + Uvicorn |
| HTTP-клиент | httpx (async) |
| Валидация | Pydantic v2 |
| Контейнеризация | Docker + Docker Compose |
| Метрики | OpenTelemetry + Prometheus |
| Мониторинг | Grafana |
| LLM Providers | OpenRouter, Ollama, vLLM |

---

## Troubleshooting

### Модели не отвечают (mock-ответы)

Проверь что используешь **real** провайдеры:

```bash
docker compose ps
# level1-vllm-1 — должен быть vllm/vllm-openai:latest
# level1-ollama-1 — должен быть ollama/ollama:latest
```

### Out of memory

Уменьши GPU memory для vLLM:
```bash
# В docker-compose.yml
--gpu-memory-utilization 0.7  # вместо 0.85
```

### Модели не загружаются

Проверь HF_TOKEN:
```bash
docker compose logs vllm | grep "HF_TOKEN\|authentication"
```

---

## Чек-лист Level 1

- [x] Docker Compose для всех компонентов
- [x] 3 LLM-провайдера (OpenRouter, Ollama, vLLM)
- [x] Балансировщик с Round-robin и Weighted стратегиями
- [x] Поточное чтение (streaming) без разрыва соединений
- [x] OpenTelemetry метрики
- [x] Prometheus + Grafana
- [x] Health-check endpoints
- [x] **Smart routing** по сложности (сверх требований)
- [x] **Queue management** с приоритетами (сверх требований)
- [x] **Load testing** с разными сценариями (сверх требований)

---

## Лицензия

MIT License — домашнее задание для курса по LLM инфраструктуре (ИТМО, 2025-2026).

---

**Автор:** Лазарчик Михаил  
**Курс:** LLM Infrastructure & Deployment — Bonus Track  
**Уровень:** Level 1 (10 баллов + бонусы за Smart Routing и Queue Management)

| Функция | Level 1 | Level 2 | Level 3 |
|---------|---------|---------|---------|
| **Балансировщик** | ✓ Round-robin, Weighted | ✓ + Latency-based, Health-aware | ✓ + Auth middleware |
| **Провайдеры** | 4 мока (OpenRouter, vLLM, Ollama, Cloud) | ✓ + Динамическая регистрация | ✓ |
| **Реестр** | — | ✓ Agent Registry + Provider Registry | ✓ |
| **Стриминг** | ✓ | ✓ | ✓ |
| **Мониторинг** | OpenTelemetry, Prometheus, Grafana | ✓ + TTFT, TPOT, cost | ✓ + Guardrail rejections |
| **MLFlow** | — | ✓ Tracing | ✓ |
| **Guardrails** | — | — | ✓ Prompt injection, Secret leak |
| **Authorization** | — | — | ✓ Token-based |
| **Load Testing** | — | — | ✓ Скрипт + отчёт |

---

## Порты сервисов

### Level 1
| Сервис | Порт |
|--------|------|
| Balancer | 8000 |
| OpenRouter | 8001 |
| vLLM | 8002 |
| Ollama | 8003 |
| Cloud | 8004 |
| Prometheus | 9090 |
| Grafana | 3000 |
| OTel Collector | 4317 |

### Level 2 (+ к Level 1)
| Сервис | Порт |
|--------|------|
| Registry | 8010 |
| MLFlow | 5000 |

### Level 3 (+ к Level 2)
| Сервис | Порт |
|--------|------|
| Guardrails | 8020 |
| Auth | 8030 |

---

## Быстрый старт

### Level 1
```bash
cd level1
docker compose up --build

# Проверка
curl http://localhost:8000/health
curl http://localhost:8000/v1/models
```

### Level 2
```bash
cd level2
docker compose up --build

# Проверка
curl http://localhost:8010/health
curl http://localhost:8010/a2a/agents
curl http://localhost:8000/balancer/providers
```

### Level 3
```bash
cd level3
docker compose up --build

# Получить admin токен
ADMIN_TOKEN=$(docker logs level3-auth-1 2>&1 | grep "Admin token:" | tail -1 | awk '{print $NF}')

# Создать токен приложения
APP_TOKEN=$(curl -s -X POST http://localhost:8030/tokens \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"app","scopes":["llm:write"]}' | python -c "import sys,json; print(json.load(sys.stdin)[''])")

# Проверка с авторизацией
curl -H "Authorization: Bearer $APP_TOKEN" http://localhost:8000/v1/models

# Нагрузочное тестирование
python loadtest/load_test.py http://localhost:8000 "$APP_TOKEN"
```

---

## Архитектура Level 3 (полная)

```
                    ┌─────────────────────────────────────┐
                    │           Clients                   │
                    └──────────────┬──────────────────────┘
                                   │
                         ┌─────────▼─────────┐
                         │  Balancer V3      │
                         │  :8000            │
                         │  - Auth check     │
                         │  - Guardrails     │
                         │  - Smart routing  │
                         └─────────┬─────────┘
                                   │
         ┌──────────────┬──────────┼──────────┬──────────────┐
         │              │          │          │              │
    ┌────▼────┐   ┌────▼────┐ ┌────▼────┐ ┌────▼────┐   ┌────▼────┐
    │OpenRouter│   │  vLLM   │ │ Ollama  │ │  Cloud  │   │  ...    │
    │  :8001   │   │  :8002  │ │ :8003   │ │ :8004   │   │         │
    └─────────┘   └─────────┘ └─────────┘ └─────────┘   └─────────┘

    ┌─────────┐    ┌──────────┐    ┌────────┐
    │ Registry│    │Guardrails│    │  Auth  │
    │  :8010  │    │  :8020   │    │ :8030  │
    └─────────┘    └──────────┘    └────────┘

    ┌─────────┐    ┌──────────┐    ┌─────────┐
    │  MLFlow │    │Prometheus│    │ Grafana │
    │  :5000  │    │  :9090   │    │ :3000   │
    └─────────┘    └──────────┘    └─────────┘
```

---

## Стратегии балансировки

| Стратегия | Описание | Когда использовать |
|-----------|----------|-------------------|
| **round_robin** | Циклический перебор | Равномерная нагрузка, провайдеры одинаковые |
| **weighted** | Пропорционально весу | Разные мощности, нужно задать руками |
| **latency** | Приоритет быстрому (EMA) | Автоматический выбор лучшего по времени отклика |
| **health** | Health-aware + priority | Высокая надёжность, учитывает ошибки и приоритеты |

**Пример:**
```bash
# Latency-based (default)
curl -X POST "http://localhost:8000/v1/chat/completions?strategy=latency" ...

# Health-aware
curl -X POST "http://localhost:8000/v1/chat/completions?strategy=health" ...
```

---

## Метрики

### Основные
- `llm_requests_total` — счётчик запросов
- `llm_request_latency_seconds` — гистограмма латентности
- `llm_active_requests` — gauge активных запросов

### Level 2+
- `llm_ttft_seconds` — Time-to-First-Token
- `llm_tpot_seconds` — Time-per-Output-Token
- `llm_input_tokens_total` — входные токены
- `llm_output_tokens_total` — выходные токены
- `llm_request_cost_total` — стоимость

### Level 3
- `llm_guardrail_rejections_total` — блокировки guardrails

---

## Guardrails

**Проверки:**
1. **Prompt Injection** — обнаружение попыток переопределить инструкции
2. **Secret Leak** — AWS ключи, GitHub токены, private keys, DB URLs
3. **Forbidden Content** — запрещённые темы

**Поведение:**
- При обнаружении опасного контента → HTTP 422
- При обнаружении секретов → замена на `[REDACTED]`, запрос пропускается

---

## Authorization

**Scope-based access control:**
- `llm:read` — чтение моделей
- `llm:write` — отправка запросов
- `agent:read` / `agent:write` — агенты
- `admin` — полный доступ

**Flow:**
1. Получить admin token из логов auth-сервиса
2. Создать токен с нужными scopes
3. Использовать в заголовке `Authorization: Bearer <token>`

---

## Нагрузочное тестирование (Level 3)

Сценарии:
1. **Concurrent** — 50 параллельных запросов × 3 батча
2. **Streaming** — 20 параллельных стриминговых запросов
3. **Multi-model** — распределение между моделями
4. **Strategies** — сравнение всех 4 стратегий
5. **Guardrails** — проверка блокировок

Метрики:
- Throughput (req/s)
- Latency (p50, p95, p99)
- Success rate
- Provider distribution

**Запуск:**
```bash
python level3/loadtest/load_test.py http://localhost:8000 <token>
```

---

## Grafana дашборды

- **Level 1** — базовая латентность и распределение трафика
- **Level 2** — добавлены TTFT, TPOT, cost metrics
- **Level 3** — добавлены guardrail rejections

URL: http://localhost:3000 (admin/admin)

---

## MLFlow

Все запросы логируются как traces с атрибутами:
- provider, model, latency, ttft
- input/output tokens, cost
- strategy, success/failure
- guardrail violations (Level 3)

URL: http://localhost:5000

---

## Зависимости

- Docker + Docker Compose
- Python 3.11 (для локального тестирования)

---

## Оценка выполнения

| Уровень | Баллы | Статус |
|---------|-------|--------|
| Level 1 | 10 | ✅ Выполнено |
| Level 2 | 20 | ✅ Выполнено |
| Level 3 | 25 | ✅ Выполнено |
| **Итого** | **55** | |

Для каждого уровня:
- ✅ Архитектурные диаграммы
- ✅ Описания API
- ✅ Инструкции по запуску
- ✅ Отчёты о тестировании (Level 3)
- ✅ Сравнение стратегий балансировки
