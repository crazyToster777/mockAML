# Production Improvements Plan

## Приоритеты

| Приоритет | Что | Почему |
|-----------|-----|--------|
| 🔴 Критично | Alembic миграции | `create_all()` сломает прод при изменении схемы |
| 🔴 Критично | Graceful shutdown | Потеря данных при деплое |
| 🔴 Критично | Dead Letter Queue | Битые сообщения молча теряются |
| 🔴 Критично | Secrets management | Пароли в env файлах — уязвимость |
| 🟡 Важно | Prometheus метрики | Без них невозможен мониторинг |
| 🟡 Важно | Healthcheck endpoint | Kubernetes не знает жив ли сервис |
| 🟡 Важно | Retry с backoff | Сервис падает при недоступности зависимостей |
| 🟡 Важно | Тесты | Без них нельзя деплоить уверенно |
| 🟠 Хорошо иметь | Schema Registry | Эволюция схемы без поломок |
| 🟠 Хорошо иметь | Blacklist из БД | Санкционные списки должны обновляться |

---

## 1. 🔴 Alembic миграции вместо `create_all()`

**Проблема:** `Base.metadata.create_all()` в `session.py` не умеет изменять существующие таблицы.
Добавил колонку в модель — в БД её нет, сервис падает.

**Решение:** Версионированные Alembic миграции.

```bash
alembic init alembic
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

Каждое изменение схемы — отдельный файл миграции который можно применить и откатить.
Миграции запускаются в CI перед деплоем.

---

## 2. 🔴 Graceful Shutdown

**Проблема:** SIGTERM убивает процесс в середине обработки транзакции — offset закоммичен,
но результат не записан в БД. Данные теряются.

**Решение:** Ловим сигналы, завершаем текущую итерацию перед выходом.

```python
import signal

class AMLVerifier:
    def __init__(self):
        self._running = True
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

    def _handle_shutdown(self, *_):
        logger.info("shutdown_requested")
        self._running = False

    def run(self):
        while self._running:
            txn = consumer.poll_one(timeout=5.0)
            if txn:
                self.process_transaction(txn)
        consumer.close()  # commit последнего offset перед выходом
```

---

## 3. 🔴 Dead Letter Queue

**Проблема:** Сообщение которое не десериализуется — молча теряется.

```python
# сейчас в consumer.py
except Exception:
    self._consumer.commit(message=msg, asynchronous=False)
    return None  # ← сообщение потеряно навсегда
```

**Решение:** Отправлять битые сообщения в отдельный DLQ топик с метаданными об ошибке.

```python
except Exception as exc:
    self._dlq_producer.produce(
        topic="aml.transactions.dlq",
        value=msg.value(),
        headers={
            "error": str(exc),
            "original_topic": msg.topic(),
            "original_partition": str(msg.partition()),
            "original_offset": str(msg.offset()),
            "failed_at": datetime.utcnow().isoformat(),
        }
    )
    self._consumer.commit(message=msg, asynchronous=False)
```

DLQ сообщения можно проанализировать и переотправить после фикса.

---

## 4. 🔴 Secrets Management

**Проблема:** Пароли хранятся в `.env` файлах — уязвимость, не подходит для продакшена.

```python
# сейчас — пароль виден в конфиге
postgres_password: str = "aml_password"
```

**Решение:** Читать секреты из внешнего хранилища.

```python
# вариант 1 — Docker/Kubernetes secrets (файлы в /run/secrets/)
class Settings(BaseSettings):
    model_config = SettingsConfigDict(secrets_dir="/run/secrets")

# вариант 2 — AWS Secrets Manager / HashiCorp Vault
import boto3

def get_secret(name: str) -> str:
    client = boto3.client("secretsmanager")
    return client.get_secret_value(SecretId=name)["SecretString"]
```

`.env` файлы — только для локальной разработки, никогда не в продакшене.

---

## 5. 🟡 Prometheus Метрики

**Проблема:** Нет метрик — невозможно мониторить сервис, настроить алерты, строить дашборды.

**Решение:** `prometheus_client` + HTTP эндпоинт `/metrics`.

```python
from prometheus_client import Counter, Histogram, Gauge, start_http_server

transactions_total = Counter(
    "aml_transactions_total", "Processed transactions", ["risk_level"]
)
processing_seconds = Histogram(
    "aml_processing_seconds", "Transaction processing duration"
)
consumer_lag = Gauge(
    "aml_consumer_lag", "Kafka consumer lag", ["partition"]
)

# в verifier.py
with processing_seconds.time():
    result = self._rule_engine.evaluate(txn, recent)

transactions_total.labels(risk_level=result.risk_level).inc()
```

Ключевые метрики для мониторинга:
- `aml_transactions_total` by risk_level — throughput и распределение рисков
- `aml_processing_seconds` — латентность обработки
- `aml_consumer_lag` — отставание от Kafka (если растёт — проблема)
- `aml_dlq_messages_total` — количество битых сообщений

---

## 6. 🟡 Healthcheck Endpoint

**Проблема:** Kubernetes не знает жив ли сервис — нет liveness и readiness проб.

**Решение:** Лёгкий HTTP сервер в отдельном потоке.

```python
# health.py
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            # liveness: процесс жив
            self._respond(200, {"status": "ok"})

        elif self.path == "/ready":
            # readiness: Kafka и БД доступны
            try:
                check_kafka_connection()
                check_db_connection()
                self._respond(200, {"status": "ready"})
            except Exception as e:
                self._respond(503, {"status": "not ready", "error": str(e)})

def start_health_server(port: int = 8080):
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
```

```yaml
# kubernetes deployment
livenessProbe:
  httpGet:
    path: /health
    port: 8080
readinessProbe:
  httpGet:
    path: /ready
    port: 8080
```

---

## 7. 🟡 Retry с Exponential Backoff

**Проблема:** Если Kafka или PostgreSQL недоступны при старте — сервис сразу падает.
При деплое сервис поднимается раньше чем успевают стартовать зависимости.

**Решение:** `tenacity` уже в `requirements.txt` — нужно использовать.

```python
from tenacity import retry, stop_after_attempt, wait_exponential, before_log

@retry(
    stop=stop_after_attempt(10),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    before=before_log(logger, logging.WARNING),
)
def create_kafka_producer(cfg: Settings) -> ConfluentProducer:
    producer = ConfluentProducer({"bootstrap.servers": cfg.kafka_bootstrap_servers})
    # проверяем что брокер доступен
    producer.list_topics(timeout=5)
    return producer

@retry(
    stop=stop_after_attempt(10),
    wait=wait_exponential(multiplier=1, min=2, max=60),
)
def create_db_engine(cfg: Settings):
    engine = create_engine(cfg.postgres_dsn)
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return engine
```

---

## 8. 🟡 Тесты (pytest + Allure + testcontainers)

**Проблема:** Без тестов нельзя деплоить уверенно — любое изменение может сломать пайплайн.

**Структура:**

```
tests/
├── conftest.py                  # testcontainers fixtures (Kafka + Postgres)
├── factories.py                 # Faker-based генерация данных
├── unit/
│   └── test_aml_rules.py        # правила — без Docker, мгновенно
├── integration/
│   ├── test_kafka_flow.py       # producer/consumer round-trip
│   └── test_db_repository.py   # CRUD, idempotent upserts
├── e2e/
│   └── test_aml_pipeline.py    # полный пайплайн produce→consume→verify→DB
└── data_quality/
    └── test_reconciliation.py  # reconciliation healthy/unhealthy
```

**Ключевые паттерны:**
- `session.begin_nested()` — SAVEPOINT rollback между тестами (<1ms vs 500ms DROP/CREATE)
- Уникальный `group_id` для каждого тест-консьюмера — изоляция offset'ов
- `testcontainers` — реальные Kafka и Postgres, не моки

```bash
pytest -m unit                   # без Docker
pytest -m "integration or e2e"   # с Docker
pytest --alluredir=allure-results
allure serve allure-results
```

---

## 9. 🟠 Schema Registry + Avro/Protobuf

**Проблема:** JSON без контракта — producer и consumer не знают о схеме друг друга.
Изменил поле — консьюмер упал без предупреждения.

**Решение:** Confluent Schema Registry.

```python
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer

schema_registry = SchemaRegistryClient({"url": "http://schema-registry:8081"})
serializer = AvroSerializer(schema_registry, transaction_schema)
```

Преимущества:
- Schema evolution — добавил поле, старые консьюмеры не сломались
- Валидация на уровне брокера — невалидное сообщение не попадёт в топик
- Документация схемы живёт рядом с данными

---

## 10. 🟠 Динамический Blacklist из БД

**Проблема:** Санкционный список захардкожен в коде — обновление требует редеплоя.

```python
# сейчас — статика в rules.py
BLACKLISTED_ACCOUNTS: frozenset[str] = frozenset({"SANCTIONED001", ...})
```

**Решение:** Таблица в БД + кэш с TTL.

```python
# database/models.py
class BlacklistedAccount(Base):
    __tablename__ = "blacklisted_accounts"
    account_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    reason: Mapped[str]                    # OFAC / внутренний список
    added_at: Mapped[datetime]
    source: Mapped[str]                    # "OFAC" / "manual" / "automated"

# rules.py — кэш обновляется каждые 5 минут
from functools import lru_cache
from datetime import datetime

_blacklist_cache: frozenset[str] = frozenset()
_cache_updated_at: datetime | None = None

def get_blacklist(session: Session) -> frozenset[str]:
    global _blacklist_cache, _cache_updated_at
    now = datetime.utcnow()
    if _cache_updated_at is None or (now - _cache_updated_at).seconds > 300:
        rows = session.execute(select(BlacklistedAccount.account_id)).scalars().all()
        _blacklist_cache = frozenset(rows)
        _cache_updated_at = now
    return _blacklist_cache
```

Плюс scheduled job для загрузки актуального OFAC списка (обновляется ежедневно).

---

## Итог — порядок реализации

```
Phase 1 (до первого деплоя):
  1. Alembic миграции
  2. Graceful shutdown
  3. Dead Letter Queue
  4. Secrets management
  5. Healthcheck endpoint

Phase 2 (первая неделя в проде):
  6. Prometheus метрики + Grafana дашборд
  7. Retry с backoff
  8. Тесты (unit → integration → e2e)

Phase 3 (стабилизация):
  9. Schema Registry
  10. Динамический blacklist
```
