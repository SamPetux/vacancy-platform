# Deploy: Yandex Cloud

Инструкция для выкладки vacancy-platform в production.
Первый город — Нижний Новгород. Цель MVP: API + админка + Celery (сбор + VK-публикация раз в час).

Официальные материалы Yandex Cloud:

- [Compute Cloud + Docker Compose](https://yandex.cloud/en/docs/compute/tutorials/docker-compose)
- [Managed Service for PostgreSQL](https://yandex.cloud/en/docs/managed-postgresql/)
- [Managed Service for Valkey (Redis-compatible)](https://yandex.cloud/en/docs/managed-valkey/)
- [Lockbox (секреты)](https://yandex.cloud/en/docs/lockbox/)

---

## Что выбрать (рекомендация)

Для текущего масштаба (1 город, десятки постов/день, Docker Compose уже есть) оптимален **простой путь**.

### Вариант A — рекомендуем сейчас

| Компонент | Выбор | Зачем |
|-----------|--------|--------|
| Приложение | **1× Compute Cloud VM** Ubuntu 22.04 | api + worker + scheduler + frontend + caddy |
| БД | PostgreSQL **в Docker на той же VM** | проще и дешевле на старте |
| Redis | Redis **в Docker на той же VM** | broker для Celery |
| Сеть | Публичный IP + Security Group | только 80/443 снаружи |
| Секреты | файл `.env` на VM (права 600) | Lockbox — следующим шагом |

**Железо VM (старт):**

- platform `standard-v3` или `standard-v2`
- **2 vCPU / 4 GB RAM** (если туго — 2 / 2, лучше 4 GB)
- диск **network-ssd 40–60 GB**
- зона: `ru-central1-a` (или любая одна зона)
- ОС: `ubuntu-2204-lts`

Этого хватит для MVP. Потом можно вынести Postgres в Managed.

### Вариант B — чуть «взрослее» (когда появится стабильный трафик)

| Компонент | Выбор |
|-----------|--------|
| App | та же VM |
| БД | **Managed PostgreSQL** (1 хост на старте; для HA — 2+ в разных зонах) |
| Redis | пока на VM; позже Managed Valkey |
| Секреты | **Lockbox** + service account на VM |

Managed PostgreSQL дороже self-hosted, но даёт бэкапы/патчи из коробки.  
Документация по HA: single-host **без SLA**; 2 хоста в разных AZ уже HA.

### Чего не брать на этом этапе

| Вариант | Почему рано |
|---------|-------------|
| Kubernetes / Managed K8s | избыточно для Compose-стека |
| Serverless Containers / Cloud Functions | Celery Beat + долгие worker’ы плохо ложатся |
| Отдельный VM под каждый сервис | лишние деньги и ops |
| Публичный Postgres/Redis в интернет | дыра в безопасности |

---

## Архитектура на VM (вариант A)

```text
Internet
   │  :80 / :443
   ▼
 Caddy
   ├─ /api/*  /health*  → api:8000
   └─ /*               → frontend:80
          │
   ┌──────┴──────┐
   api   worker   scheduler
          │
     postgres + redis  (только внутри docker network)
```

Публикация VK: Celery Beat → `publish_next_vk` раз в `VK_PUBLISH_INTERVAL_SECONDS` (сейчас 3600).

---

## Подготовка до выкладки (чеклист)

### 1. Локально / в репо

- [x] `docker-compose.yml` — dev
- [x] `docker-compose.prod.yml` — prod (без `--reload`, restart, без публикации портов БД)
- [ ] Домен (желательно): `jobs.example.ru` или поддомен
- [ ] DNS A-запись → публичный IP VM (после создания)
- [ ] Сильный `POSTGRES_PASSWORD`
- [ ] Production `.env` **только на сервере**, не в git

### 2. Секреты, которые должны быть на сервере

Скопируй с локальной машины (не коммить):

- `VK_SERVICE_TOKEN` — сбор с источников
- `VK_PUBLISH_TOKEN` — пост в community
- `VK_PUBLISH_PHOTO_ATTACHMENT` — общая картинка
- `VK_PUBLISH_ENABLED=true`
- `SUPERJOB_SECRET_KEY` / `SUPERJOB_CLIENT_ID`
- `POSTGRES_PASSWORD` (новый, не `vacancy`)

### 3. Данные

Два пути:

1. **С нуля на сервере** — `alembic upgrade head` → `seed` → `collect` (проще).
2. **Перенос локальной БД** — `pg_dump` / `pg_restore` (если жалко текущую очередь READY).

Для старта ленты обычно достаточно пути 1 + дождаться collect/publish.

---

## Пошаговый деплой (вариант A)

### Шаг 1. Облако

1. Аккаунт и billing в [console.yandex.cloud](https://console.yandex.cloud).
2. Каталог (folder), например `vacancy-prod`.
3. VPC сеть + subnet в одной зоне.
4. Security Group:
   - inbound TCP **22** — только твой IP
   - inbound TCP **80**, **443** — `0.0.0.0/0`
   - outbound — разрешить (VK / SuperJob / TrudVsem API)
5. Установить CLI: [yc](https://yandex.cloud/en/docs/cli/quickstart)

```bash
yc init
yc config list
```

### Шаг 2. Создать VM

Пример (подставь subnet / SSH-ключ):

```bash
yc compute instance create \
  --name vacancy-prod \
  --zone ru-central1-a \
  --network-interface subnet-name=<SUBNET>,nat-ip-version=ipv4,security-group-ids=<SG_ID> \
  --create-boot-disk image-folder-id=standard-images,image-family=ubuntu-2204-lts,size=50,type=network-ssd \
  --cores 2 \
  --memory 4 \
  --core-fraction 100 \
  --ssh-key ~/.ssh/id_ed25519.pub
```

Запомни публичный IP.

Альтернатива COI + compose: [tutorial](https://yandex.cloud/en/docs/compute/tutorials/docker-compose) — удобно, но для нашего репо проще обычная Ubuntu + git clone.

### Шаг 3. На VM: Docker + код

```bash
ssh ubuntu@<PUBLIC_IP>   # или yc-user — смотри образ

sudo apt update && sudo apt install -y git curl ca-certificates
# Docker Engine: https://docs.docker.com/engine/install/ubuntu/
sudo usermod -aG docker $USER
# перелогинься

git clone <YOUR_REPO_URL> vacancy-platform
cd vacancy-platform
cp .env.example .env
nano .env   # заполни секреты, APP_ENV=production
chmod 600 .env
```

Минимум в `.env` на сервере:

```bash
APP_ENV=production
POSTGRES_USER=vacancy
POSTGRES_PASSWORD=<STRONG>
POSTGRES_DB=vacancy

VK_SERVICE_TOKEN=...
VK_PUBLISH_ENABLED=true
VK_PUBLISH_GROUP_ID=241679288
VK_PUBLISH_TOKEN=...
VK_PUBLISH_PHOTO_ATTACHMENT=photo-...
VK_PUBLISH_INTERVAL_SECONDS=3600

SUPERJOB_SECRET_KEY=...
SUPERJOB_CLIENT_ID=...
```

`DATABASE_URL` / `REDIS_URL` в prod-compose задаются сервисам автоматически на `postgres` / `redis`.

### Шаг 4. Запуск

```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml exec api alembic upgrade head
docker compose -f docker-compose.prod.yml exec api python -m app.cli seed
docker compose -f docker-compose.prod.yml exec api python -m app.cli collect --city nizhny-novgorod
```

Проверки:

```bash
curl -s http://127.0.0.1:8080/health
curl -s http://127.0.0.1:8080/health/db
# снаружи (после DNS / IP):
curl -s http://<PUBLIC_IP>/health
```

Первая VK-публикация вручную (опционально):

```bash
docker compose -f docker-compose.prod.yml exec api python -m app.cli publish-once
```

Дальше Beat сам публикует раз в час.

### Шаг 5. HTTPS (когда есть домен)

1. DNS A → IP VM.
2. В `docker/caddy/Caddyfile` заменить `:80` на домен (Caddy сам возьмёт Let's Encrypt), либо поставить Yandex Certificate Manager + ALB позже.
3. Открыть 443 в Security Group.

Пока можно жить на `http://IP:8080` (порт из `HTTP_PORT`) — только для закрытого теста.

---

## Вариант B в двух словах

1. Создать Managed PostgreSQL 16, пользователь `pg_trgm` (как в `docker/postgres/init.sql`).
2. В `.env` на VM: `DATABASE_URL=postgresql+psycopg://user:pass@<MDB_HOST>:6432/db` (часто SSL).
3. В `docker-compose.prod.yml` **не** поднимать сервис `postgres` (или отключить depends).
4. Redis пока оставить в Compose.

---

## Операционка

| Действие | Команда |
|----------|---------|
| Логи | `docker compose -f docker-compose.prod.yml logs -f api worker scheduler` |
| Обновление | `git pull && docker compose -f docker-compose.prod.yml up -d --build` |
| Миграции | `... exec api alembic upgrade head` |
| Рестарт beat/worker | `... restart worker scheduler` |
| Бэкап Postgres (вариант A) | `docker compose ... exec -T postgres pg_dump -U vacancy vacancy > backup.sql` |

Бэкапы диска VM в Yandex Cloud: снимки диска по расписанию (Compute → Disks → snapshots) — включи сразу.

---

## Оценка порядка затрат (ориентир)

Точные цифры смотри в калькуляторе YC. Грубо для варианта A:

- VM 2/4 + SSD 50 GB — основной расход
- публичный IP + трафик (первые 100 GB исходящего часто free tier)
- Managed Postgres (вариант B) — заметно дороже VM-only

На старте **вариант A** обычно в разы дешевле B при том же функционале.

---

## Риски и правила

1. Не светить Postgres/Redis наружу.
2. Не класть `.env` в git / в публичные логи.
3. Service token ≠ publish token (уже разделено в конфиге).
4. Локальный Celery на ноутбуке после выкладки **выключить**, иначе двойные посты в VK (один guid частично страхует, но не полностью).
5. `VK_PUBLISH_INTERVAL_SECONDS=3600` сейчас; позже 5400 (90 мин) — только env + restart scheduler.

---

## Что сделать тебе по шагам прямо сейчас

1. Создать каталог + VPC + SG в Yandex Cloud.
2. Поднять VM 2 vCPU / 4 GB Ubuntu 22.04.
3. Установить Docker, склонировать репо, заполнить `.env`.
4. `docker compose -f docker-compose.prod.yml up -d --build`.
5. Миграции + seed + collect.
6. Проверить `/health` и один `publish-once`.
7. Остановить локальный celery worker/beat.

Когда VM будет с SSH-доступом — можно перейти в Agent mode и пройти деплой вместе (команды по SSH / checklist).
