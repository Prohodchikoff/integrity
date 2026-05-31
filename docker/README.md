# Docker

Стек: **MySQL (jobs)** + **SQL Server (AdventureWorks2014)** + **FastAPI** для проєкту **`adventure`**.

## Сервіси

| Сервіс | Роль |
|--------|------|
| `mysql-jobs` | метадані async jobs (`integrity_job_statuses`) |
| `mssql-bak-fetch` | одноразово: завантажує [AdventureWorks2014.bak](https://github.com/Microsoft/sql-server-samples/releases/download/adventureworks/AdventureWorks2014.bak) у volume |
| `mssql` | SQL Server 2022 |
| `mssql-restore` | одноразово: `RESTORE` БД `AdventureWorks2014` + схема `integrity` |
| `api` | FastAPI (чекає успішного restore) |

Перший запуск може зайняти **5–15 хв** (завантаження ~45 MB + restore). `.bak` кешується у volume `mssql-backup`.

## Запуск

```bash
cp docker/.env.example .env   # опційно (порти)
docker compose up --build
```

У фоні:

```bash
docker compose up --build -d
docker compose logs -f mssql-bak-fetch mssql-restore api
```

### Endpoints

| Що | URL / адреса |
|----|----------------|
| Swagger | http://localhost:8000/docs |
| API | http://localhost:8000 |
| AdventureWorks (SSMS, з хоста) | `127.0.0.1,14330`, login `sa`, password `YourStrong!Passw0rd`, DB `AdventureWorks2014` |
| Jobs MySQL (з хоста) | `localhost:3307`, user `integrity` / password `integrity`, DB `jobs` |

MSSQL на хості **14330** (не 1433), щоб не конфліктувати з локальним SQL Server.

### Перевірка

```bash
curl http://localhost:8000/projects

# підключення до БД (query: project, env)
curl "http://localhost:8000/test_connection?project=adventure&env=docker"

# resolved config (тут параметр env_name)
curl "http://localhost:8000/config?project_name=adventure&env_name=docker"
```

### Run / test (async jobs)

```bash
curl -X POST http://localhost:8000/projects/run \
  -H "Content-Type: application/json" \
  -d '{"project_name":"adventure","env":"docker"}'

curl -X POST http://localhost:8000/projects/test \
  -H "Content-Type: application/json" \
  -d '{"project_name":"adventure","env":"docker"}'
```

Статус job: `GET /projects/jobs/{job_id}`.

## Проєкт `adventure`

- Код: `app/config/adventure/` (`integrity.yml`, `models/`, `tests/`).
- Моделі читають `Person.Person`; views — у схемі **`integrity`** (`[integrity].[stg_person]` тощо).

## Конфіг

Профілі БД: [`app/config/environments.yaml`](../app/config/environments.yaml).

Для Docker потрібен профіль **`docker`** (`host: mssql`, `database: AdventureWorks2014`). Файл монтується в контейнер `api`.

Після правки YAML без перезапуску:

```bash
curl -X POST http://localhost:8000/config/reload
```

Змінні `INTEGRITY_ENV` / `INTEGRITY_PROJECT` у `docker-compose` — для зручності; у запитах API все одно передавай `project_name` / `env` (або `env_name` на `/config`).

## Повне перестворення

```bash
docker compose down -v
docker compose up --build
```
