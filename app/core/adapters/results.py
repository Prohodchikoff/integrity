
class RowsResult:
    def __init__(self, rows):
        self._rows = list(rows) if rows else []

    def scalar_one(self):
        if not self._rows:
            raise ValueError("No rows returned")
        if len(self._rows) > 1:
            raise ValueError(f"Expected one row, got {len(self._rows)}")
        return self._rows[0][0]

    def scalar(self):
        if not self._rows:
            return None
        return self._rows[0][0]
