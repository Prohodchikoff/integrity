#!/usr/bin/env bash
# One-shot restore of AdventureWorks2014 into the mssql service (Linux container).
set -euo pipefail

: "${MSSQL_SA_PASSWORD:=YourStrong!Passw0rd}"
: "${MSSQL_HOST:=mssql}"
: "${DB_NAME:=AdventureWorks2014}"

BAK_PATH="/var/opt/mssql/backup/AdventureWorks2014.bak"
DATA_DIR="/var/opt/mssql/data"

sqlcmd_base() {
  /opt/mssql-tools18/bin/sqlcmd -S "$MSSQL_HOST" -U sa -P "$MSSQL_SA_PASSWORD" -C "$@"
}

wait_for_sql() {
  echo "Waiting for SQL Server at ${MSSQL_HOST}..."
  for _ in $(seq 1 90); do
    if sqlcmd_base -Q "SELECT 1" &>/dev/null; then
      return 0
    fi
    sleep 2
  done
  echo "SQL Server did not become ready in time." >&2
  exit 1
}

database_exists() {
  local id
  id="$(
    sqlcmd_base -Q "SET NOCOUNT ON; SELECT DB_ID(N'${DB_NAME}')" -h -1 -W \
      | tr -d '[:space:]'
  )"
  [[ -n "$id" && "$id" != "NULL" ]]
}

database_state() {
  sqlcmd_base -d master -Q "SET NOCOUNT ON; SELECT state_desc FROM sys.databases WHERE name = N'${DB_NAME}'" \
    -h -1 -W | tr -d '[:space:]'
}

wait_for_database_online() {
  echo "Waiting for database ${DB_NAME} to be ONLINE..."
  local state=""
  for _ in $(seq 1 120); do
    state="$(database_state || true)"
    if [[ "$state" == "ONLINE" ]]; then
      echo "Database ${DB_NAME} is ONLINE."
      return 0
    fi
    sleep 2
  done
  echo "Database ${DB_NAME} did not become ONLINE in time (last state: ${state:-unknown})." >&2
  exit 1
}

ensure_integrity_schema() {
  sqlcmd_base -d "$DB_NAME" -Q "
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = N'integrity')
    EXEC(N'CREATE SCHEMA integrity');
"
}

wait_for_sql

if database_exists; then
  echo "Database ${DB_NAME} already exists — skipping restore."
  wait_for_database_online
  ensure_integrity_schema
  echo "Restore complete."
  exit 0
fi

mkdir -p "$(dirname "$BAK_PATH")"
if [[ ! -s "$BAK_PATH" ]]; then
  echo "Backup file missing at ${BAK_PATH}. Run mssql-bak-fetch first." >&2
  exit 1
fi

echo "Reading backup file list..."
data_logical=""
log_logical=""
while IFS='|' read -r logical physical type _rest; do
  logical="${logical//[[:space:]]/}"
  type="${type//[[:space:]]/}"
  [[ -z "$logical" || "$logical" == "LogicalName" ]] && continue
  if [[ "$type" == "D" ]]; then
    data_logical="$logical"
  elif [[ "$type" == "L" ]]; then
    log_logical="$logical"
  fi
done < <(
  sqlcmd_base -Q "SET NOCOUNT ON; RESTORE FILELISTONLY FROM DISK = N'${BAK_PATH}';" \
    -s "|" -W -h -1
)

if [[ -z "$data_logical" || -z "$log_logical" ]]; then
  echo "Using default logical file names for AdventureWorks2014.bak"
  data_logical="AdventureWorks2014_Data"
  log_logical="AdventureWorks2014_Log"
fi

data_target="${DATA_DIR}/${DB_NAME}.mdf"
log_target="${DATA_DIR}/${DB_NAME}_log.ldf"

echo "Restoring ${DB_NAME} (data=${data_logical}, log=${log_logical})..."
sqlcmd_base -Q "
RESTORE DATABASE [${DB_NAME}]
FROM DISK = N'${BAK_PATH}'
WITH
  MOVE N'${data_logical}' TO N'${data_target}',
  MOVE N'${log_logical}' TO N'${log_target}',
  REPLACE,
  STATS = 10;
"

wait_for_database_online
ensure_integrity_schema
echo "Restore complete."
