# Level 1 - Smart LLM Balancer (Полное Решение)

## Сводка Требований и Выполнения

### ✅ Задача 1: Окружение и деплой (Docker Compose)

**Требование:** Используйте Docker Compose для развёртывания всех компонентов.

**Реализация:**
- `docker-compose.yml` — единый файл для всех сервисов
- Провайдеры: OpenRouter (cloud), Ollama (local), vLLM (local)
- Настраиваемые модели через `.env` (без жёстких имён моделей в compose)
- Модели конфигурируются динамически:
  ```env
  PROVIDER_0_MODELS=minimax/minimax-m2.5:free
  PROVIDER_1_MODELS=gemma4:31b-cloud,rnj-1:8b-cloud
  PROVIDER_2_MODELS=google/gemma-4-E2B-it
  ```

**Запуск:**
```bash
docker compose up --build
```

---

### ✅ Задача 2: Несколько LLM-провайдеров

**Требование:** Сконфигурируйте несколько тестовых LLM-провайдеров.

**Реализация:**

| Провайдер | Тип | Модели | Приоритет |
|-----------|-----|--------|-----------|
| **OpenRouter** | Cloud API | `minimax/minimax-m2.5:free` | 0 (мощный) |
| **Ollama** | Local GPU/CPU | `gemma4:31b-cloud`, `rnj-1:8b-cloud` | 1 (средний) |
| **vLLM** | Local GPU | `google/gemma-4-E2B-it` | 2 (простой) |

---

### ✅ Задача 3: Простейший LLM-балансировщик с расширенной логикой

**Требование:** Прокси, распределяющий запросы между провайдерами по названию моделей.

**Базовая реализация:**
- ✅ Round-robin балансировка
- ✅ Weighted балансировка (настраиваемые веса)
- ✅ Поточное чтение (streaming) без разрыва соединений

**Расширенная логика (сверх требований):**

#### 🧠 Интеллектуальная маршрутизация по сложности

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  HIGH (сложные) │────→│  Priority 0     │────→│  OpenRouter     │
│  >500 chars     │     │  (мощный)       │     │  minimax-m2.5   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
         │                      │
         ▼                      ▼ (fallback)
┌─────────────────┐     ┌─────────────────┐
│  MEDIUM         │────→│  Priority 1     │────→│  Ollama         │
│  >100 chars     │     │  (средний)      │     │  gemma4:31b     │
└─────────────────┘     └─────────────────┘     └─────────────────┘
         │                      │
         ▼                      ▼ (fallback)
┌─────────────────┐     ┌─────────────────┐
│  LOW (простые)  │────→│  Priority 2     │────→│  vLLM           │
│  <100 chars     │     │  (простой)      │     │  gemma-E2B      │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

#### 🔄 Логика fallback

1. **Сложные запросы** → Priority 0 (OpenRouter)
   - Если занят → Priority 1 (Ollama)
   - Если занят → Priority 2 (vLLM) только если **queue >= 10**

2. **Средние запросы** → Priority 1 (Ollama)
   - Если занят → Priority 2 (vLLM)

3. **Простые запросы** → Priority 2 (vLLM)

4. **Emergency mode** (queue >= 10):
   - Любой провайдер может отвечать на любой запрос
   - Выбирается наиболее мощный доступный

#### 📊 Queue Management

```python
QUEUE_THRESHOLD = 10  # Экстренный режим при >= 10 запросов в очереди

class QueuedRequest:
    id: str
    model: str
    complexity: str  # low/medium/high
    payload: dict
    future: asyncio.Future
    enqueue_time: float
```

**Очередь обрабатывается в фоне:**
- При освобождении мощного провайдера → сложные запросы
- При освобождении среднего → средние запросы
- При освобождении простого → простые запросы

---

### ✅ Задача 4: Минимальный мониторинг

#### 4.1 OpenTelemetry метрики

| Метрика | Тип | Описание |
|---------|-----|----------|
| `llm_requests_total` | Counter | Общее количество запросов |
| `llm_request_latency_seconds` | Histogram | Латентность запросов |
| `llm_active_requests` | UpDownCounter | Активные запросы |

**Лейблы:**
- `provider` — имя провайдера
- `model` — имя модели
- `complexity` — сложность запроса (low/medium/high)

#### 4.2 Prometheus интеграция

```yaml
# prometheus.yml
scrape_configs:
  - job_name: "otel-collector"
    targets: ["otel-collector:8889"]
  - job_name: "balancer-prometheus"
    targets: ["balancer:9464"]
```

#### 4.3 Grafana дашборды

**URL:** http://localhost:3000 (admin/admin)

**Доступные графики:**
- Латентность по провайдерам (p50, p95, p99)
- Распределение трафика по провайдерам
- Активные запросы
- Queue size

#### 4.4 Health Check Endpoints

| Endpoint | URL | Описание |
|----------|-----|----------|
| Health | `/health` | Статус + queue stats |
| Queue Stats | `/queue/stats` | Детальная статистика очереди |
| Models | `/v1/models` | Список доступных моделей |

---

## 🚀 Запуск продвинутого тестирования

### Подготовка

```bash
# Установка зависимостей в WSL
sudo apt-get install -y python3-pip
pip3 install aiohttp
```

### Быстрый тест (5 минут)

```bash
cd ~/bonus-track-hw/load-testing
python3 quick_test.py
```

### Продвинутый тест (10 минут, синусоидальная нагрузка)

```bash
python3 advanced_load_test.py
```

**Особенности продвинутого теста:**
- ⏱️ 10 минут продолжительность
- 📈 Синусоидальная нагрузка (5-30 RPM)
- 🔴 67% сложных запросов
- 🟡 16% средних запросов
- 🟢 17% простых запросов
- 🖥️ Реал-тайм вывод ответов моделей в терминал

---

## 📊 Прометей-запросы для анализа

```promql
# Общее количество запросов по провайдерам
sum by (provider) (llm_llm_requests_total)

# RPS (запросов в секунду)
rate(llm_llm_requests_total[1m])

# Средняя латентность по провайдеру
rate(llm_llm_request_latency_seconds_sum[5m]) / 
  rate(llm_llm_request_latency_seconds_count[5m])

# 95-й перцентиль латентности
histogram_quantile(0.95, rate(llm_llm_request_latency_seconds_bucket[5m]))

# Активные запросы
llm_llm_active_requests

# Запросы по сложности
sum by (complexity) (llm_llm_requests_total)
```

---

## 🔧 Архитектура балансировщика

```
┌─────────────────────────────────────────────────────────────┐
│                    HTTP Request                             │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                 SmartLLMBalancer                            │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  1. detect_complexity(payload)                      │   │
│  │     - prompt length analysis                        │   │
│  │     - keyword detection (code, analysis, etc)       │   │
│  └─────────────────────────────────────────────────────┘   │
│                            │                               │
│                            ▼                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  2. select_provider(model, payload)                 │   │
│  │     - get_provider_for_complexity()                 │   │
│  │     - fallback logic based on queue size            │   │
│  └─────────────────────────────────────────────────────┘   │
│                            │                               │
│                            ▼                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  3. Request Queue (if provider busy)                │   │
│  │     - QueuedRequest(complexity, payload, future)  │   │
│  │     - Background queue processor                    │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            │
            ┌───────────────┼───────────────┐
            ▼               ▼               ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│  OpenRouter   │  │    Ollama     │  │     vLLM      │
│  Priority 0   │  │  Priority 1   │  │  Priority 2   │
│  (мощный)     │  │  (средний)    │  │  (простой)    │
└───────────────┘  └───────────────┘  └───────────────┘
```

---

## ✅ Проверка требований ДЗ

| Требование | Статус | Реализация |
|------------|--------|------------|
| Docker Compose | ✅ | `docker-compose.yml` |
| Несколько провайдеров | ✅ | 3 провайдера (cloud + 2 local) |
| Прокси-балансировщик | ✅ | FastAPI с routing |
| Round-robin | ✅ | `RoundRobinSelector` |
| Weighted | ✅ | `WeightedSelector` |
| Поточное чтение | ✅ | `StreamingResponse` |
| OpenTelemetry | ✅ | Метрики с лейблами |
| Prometheus | ✅ | `prometheus.yml` |
| Grafana дашборды | ✅ | Дефолтные дашборды |
| Health checks | ✅ | `/health`, `/queue/stats` |

**Сверх требований:**
- 🧠 Интеллектуальная маршрутизация по сложности
- 📊 Queue management с приоритетами
- 🔄 Smart fallback (не пускаем слабые модели на сложные задачи)
- 🚨 Emergency mode при перегрузке
- 📝 Detailed logging

---

## 🎯 Итог

Балансировщик полностью удовлетворяет требованиям Level 1 и содержит расширенные функции:

1. **Масштабируемость**: Легко добавить новых провайдеров через `.env`
2. **Умная балансировка**: Распределяет нагрузку по сложности запросов
3. **Отказоустойчивость**: Queue + fallback + emergency mode
4. **Наблюдаемость**: Полный стек OTel → Prometheus → Grafana
5. **Тестируемость**: Скрипты для разных сценариев нагрузки
