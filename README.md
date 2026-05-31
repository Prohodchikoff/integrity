# 📘 Integrity

> *Сервіс перевірки якості даних: SQL-моделі з залежностями, data tests і REST API для асинхронного run/test у цільовій БД.*

---

## 👤 Автор

- **ПІБ**: Іванець Дмитро Романович
- **Група**: ФЕС-42
- **Керівник**: Васюта Василь Михайлович, кандидат фізико-математичних наук, асистент кафедри оптоелектроніки та інформаційних технологій
- **Дата виконання**: [31.05.2026]

---

## 📌 Загальна інформація

- **Тип проєкту**: REST API (backend)
- **Мова програмування**: Python 3.12
- **Фреймворки / Бібліотеки**: FastAPI, SQLAlchemy, Jinja2, Pydantic, Uvicorn, aiomysql, pyodbc

---

## 🧠 Опис функціоналу

- 📂 Проєкти integrity: `integrity.yml`, каталоги `models/` та `tests/`
- 🔗 Компіляція SQL-моделей з `ref()` та `source()` (Jinja2), побудова DAG
- ▶️ **Run** — створення/оновлення views у БД за топологічним порядком моделей
- ✅ **Test** — вбудовані перевірки (`not_null`, `unique`, `not_blank`, `positive`, `relationships`) і кастомні SQL-тести
- ⏳ Асинхронні jobs (run/test) зі збереженням статусу та результату в MySQL
- 🌐 REST API + Swagger (`/docs`) для керування проєктами, підключеннями і jobs
- 🐳 Docker-стек з AdventureWorks2014 (див. `docker/README.md`)

---

## 🧱 Опис основних класів / файлів


| Клас / Файл                    | Призначення                                    |
| ------------------------------ | ---------------------------------------------- |
| `app/main.py`                  | Точка входу FastAPI, lifespan (jobs DB)        |
| `app/settings.py`              | Завантаження `app/config/environments.yaml`    |
| `app/api/routes.py`            | `/projects`, `/config`, `/test_connection`     |
| `app/api/project_routes.py`    | `/projects/run`, `/test`, `/jobs`, `/parse`    |
| `app/integrity/compiler.py`    | Рендер SQL (`ref`, `source`), валідація SELECT |
| `app/integrity/runner.py`      | Завантаження графа, `run_project`, CREATE VIEW |
| `app/integrity/test_runner.py` | Запуск тестів з `integrity.yml`                |
| `app/integrity/project.py`     | Парсинг `integrity.yml`, конфіг тестів         |
| `app/jobs/project_jobs.py`     | Фонові jobs, запис у MySQL                     |
| `app/config/environments.yaml` | Профілі БД (`projects` → `environment`)        |
| `app/config/adventure/`        | Демо-проєкт (AdventureWorks `Person`)          |
| `docker-compose.yml`           | MySQL jobs + MSSQL + API                       |


---

## ▶️ Як запустити проєкт "з нуля"

### 1. Встановлення інструментів

- Python 3.12+
- pip, venv
- **Docker** (рекомендовано для повного стеку) або локально:
  - MySQL 8 — jobs (`JOB_DATABASE_URL`)
  - SQL Server з БД **AdventureWorks2014** (для проєкту `adventure`)
- ODBC Driver 18 for SQL Server (для локального MSSQL / образ API)

### 2. Клонування репозиторію

```bash
git clone https://github.com/your-user/integrity.git
cd integrity
```

### 3. Встановлення залежностей

```bash
python -m venv venv
source venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Створення `.env` файлів

```bash
cp .env.example .env
```

Приклад `.env`:

```
JOB_DATABASE_URL=mysql+aiomysql://integrity:integrity@localhost:3307/jobs
```

Профілі підключення до БД проєктів — у `app/config/environments.yaml` (ключ `projects:` обовʼязковий). Для Docker див. `docker/README.md`.

### 5. Запуск

**Варіант A — Docker (усі сервіси):**

```bash
docker compose up --build
```

**Варіант B — лише API локально**:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Swagger: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🔌 API приклади

### 📋 Проєкти та конфіг

**GET /projects**

Список імен проєктів з `environments.yaml`.

**GET /test_connection?project=adventure&env=docker**

Перевірка підключення до БД.

**GET /config?project_name=adventure&env_name=docker**

Resolved config для проєкту/середовища.

---

### ▶️ Run і test (async jobs)

**POST /projects/run**

```json
{
  "project_name": "adventure",
  "env": "docker"
}
```

**Response:**

```json
{
  "job_id": "uuid",
  "status": "queued"
}
```

**POST /projects/test**

```json
{
  "project_name": "adventure",
  "env": "docker"
}
```

**GET /projects/jobs/{job_id}**

Статус і прогрес job.

**GET /projects/jobs/{job_id}/result**

Результат run або test після завершення.

---

### 📐 Parse

**POST /projects/parse**

```json
{
  "project_name": "adventure"
}
```

Повертає порядок виконання моделей і список `ref`.

---

## 🖱️ Інструкція для користувача

1. **Відкрити Swagger** — [http://localhost:8000/docs](http://localhost:8000/docs)
2. **Перевірити підключення** — `GET /test_connection` з `project=adventure` та `env=docker` (або `dev` для локального MSSQL).
3. **Запустити моделі (run)**:
  - `POST /projects/run` з тілом `project_name` + `env`
  - відстежувати `GET /projects/jobs/{job_id}`
  - переглянути результат: `GET /projects/jobs/{job_id}/result`
4. **Запустити тести (test)**:
  - `POST /projects/test` — аналогічно run
  - у результаті — `summary` (passed/failed) і список тестів
5. **Після зміни `environments.yaml`** — `POST /config/reload` без перезапуску процесу.

---

## 🧾 Використані джерела / література

- [FastAPI](https://fastapi.tiangolo.com/) — документація
- [SQLAlchemy 2.0](https://docs.sqlalchemy.org/)
- [dbt tests](https://docs.getdbt.com/docs/build/tests) — ідея data tests
- [AdventureWorks sample databases](https://github.com/Microsoft/sql-server-samples/tree/master/samples/databases/adventure-works)
- [Jinja2](https://jinja.palletsprojects.com/) — шаблони SQL

---

