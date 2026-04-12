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

### 1. Настройка

Создай `.env` файл (API ключи не попадут в git):

```bash
# OpenRouter API ключ (получить на https://openrouter.ai/keys)
PROVIDER_0_API_KEY=sk-or-v1-...

# HuggingFace токен (для скачивания моделей)
HF_TOKEN=hf_...
```

### 2. Запуск

```bash
cd level1
docker compose up --build -d

# Смотреть логи загрузки моделей (5-15 минут)
docker compose logs -f vllm ollama
```

### 3. Проверка

```bash
# Health check
 curl http://localhost:8000/health

# Должно вернуть:
# {
#   "status": "ok",
#   "providers": ["openrouter", "ollama", "vllm"],
#   "queue_stats": {...},
#   "strategy": "weighted"
# }
```

### 4. Мониторинг

| Сервис | URL | Логин |
|--------|-----|-------|
| **Prometheus** | http://localhost:9090 | — |
| **Grafana** | http://localhost:3000 | admin/admin |
| **Balancer** | http://localhost:8000 | — |

### 5. Тестирование

```bash
cd load-testing

# Быстрый тест (5 минут)
python3 quick_test.py

# Продвинутый тест (10 мин, синусоидальная нагрузка)
python3 advanced_load_test.py
```

---

## 📊 Метрики

### OpenTelemetry метрики

| Метрика | Тип | Лейблы |
|---------|-----|--------|
| `llm_requests_total` | Counter | provider, model, complexity |
| `llm_request_latency_seconds` | Histogram | provider, model, complexity |
| `llm_active_requests` | UpDownCounter | provider |

### PromQL запросы

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

---

## 🧪 Стратегии балансировки

| Стратегия | Описание | Переменная |
|-----------|----------|------------|
| **round_robin** | Циклический выбор | `BALANCER_STRATEGY=round_robin` |
| **weighted** | По весу (приоритет + нагрузка) | `BALANCER_STRATEGY=weighted` |

**Пример запроса с весами:**
```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "minimax/minimax-m2.5:free",
    "messages": [{"role": "user", "content": "Привет!"}]
  }'
```

---

## 📁 Структура проекта

```
bonus-track-hw/
├── level1/                          # Основной код
│   ├── balancer/
│   │   └── app/
│   │       ├── main.py             # FastAPI балансировщик
│   │       ├── balancer.py         # SmartLLMBalancer
│   │       ├── config.py           # Конфиг из .env
│   │       └── telemetry.py        # OpenTelemetry
│   ├── docker-compose.yml          # Real providers (vLLM, Ollama)
│   └── .env                        # API ключи (в .gitignore)
│
├── load-testing/                    # Тестирование
│   ├── advanced_load_test.py       # 10 мин с синусоидой
│   ├── quick_test.py               # 5 мин быстрый
│   └── README.md
│
├── monitoring/                      # Prometheus + Grafana
│   ├── prometheus.yml
│   └── grafana/
│
├── .gitignore                       # Исключает .env
└── README.md                        # Этот файл
```

---

## 🔍 Логика маршрутизации

### Определение сложности

```python
prompt = "Write a SQL query to find duplicates"
# Длина: 38 chars
# Ключевые слова: "SQL", "query"
→ Сложность: MEDIUM

prompt = "Design a distributed system for high-frequency trading..."
# Длина: >500 chars
# Ключевые слова: "design", "distributed", "system"
→ Сложность: HIGH
```

### Fallback правила

```
HIGH сложность:
  → OpenRouter (priority 0)
  → Если занят и queue < 10 → ждать в очереди
  → Если queue ≥ 10 → emergency mode (любой провайдер)

MEDIUM сложность:
  → Ollama (priority 1)
  → Если занят → vLLM (priority 2)

LOW сложность:
  → vLLM (priority 2)
```

### Emergency Mode

Когда в очереди ≥ 10 запросов, **любой провайдер** может ответить на **любой** запрос. Это предотвращает деградацию системы при перегрузке.

---

## 🛠️ Troubleshooting

### Модели не отвечают (mock-ответы)

Проверь что используешь **real** провайдеры, не mock:

```bash
# Должны быть запущены реальные сервисы
docker compose ps
# level1-vllm-1 — должен быть vllm/vllm-openai:latest
# level1-ollama-1 — должен быть ollama/ollama:latest
```

### Out of memory

Уменьши GPU memory для vLLM в `.env`:
```bash
PROVIDER_2_GPU_MEMORY=0.7  # вместо 0.85
```

### Модели не загружаются

Проверь HF_TOKEN:
```bash
docker compose logs vllm | grep "HF_TOKEN\|authentication"
```

---

## 📚 Документация

- [OpenRouter API](https://openrouter.ai/docs)
- [Ollama API](https://github.com/ollama/ollama/blob/main/docs/api.md)
- [vLLM OpenAI API](https://docs.vllm.ai/en/latest/serving/openai_compatible_server.html)
- [OpenTelemetry Python](https://opentelemetry.io/docs/languages/python/)

---

## ✅ Чек-лист Level 1

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

## 📝 Лицензия

MIT License — домашнее задание для курса по LLM инфраструктуре.

---

**Автор:** @mixli  
**Курс:** LLM Infrastructure & Deployment  
**Уровень:** Level 1 (10 баллов + бонусы)

---

## Сравнение уровней

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
