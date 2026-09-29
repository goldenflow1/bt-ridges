"""Minimal ClickHouse HTTP client (stdlib only)."""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

DEFAULT_SETTINGS = {
    "output_format_json_quote_64bit_integers": "0",
    "date_time_output_format": "iso",
}


class ClickHouseError(RuntimeError):
    pass


class ClickHouse:
    def __init__(self, url: str, user: str, password: str, database: str, timeout: float = 30):
        self.url = url.rstrip("/") + "/"
        self.user = user
        self.password = password
        self.database = database
        self.timeout = timeout

    @classmethod
    def from_env(cls, database_env: str = "METERLINE_DATABASE") -> "ClickHouse":
        return cls(
            os.environ["METERLINE_CLICKHOUSE_URL"],
            os.environ["METERLINE_CLICKHOUSE_USER"],
            os.environ["METERLINE_CLICKHOUSE_PASSWORD"],
            os.environ[database_env],
        )

    def _post(self, sql: str, params: dict[str, Any] | None, body: bytes | None = None) -> bytes:
        query = {"database": self.database, **DEFAULT_SETTINGS}
        for name, value in (params or {}).items():
            query[f"param_{name}"] = str(value)
        if body is None:
            payload = sql.encode()
        else:
            query["query"] = sql
            payload = body
        request = urllib.request.Request(
            self.url + "?" + urllib.parse.urlencode(query),
            data=payload,
            method="POST",
            headers={"X-ClickHouse-User": self.user, "X-ClickHouse-Key": self.password},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            detail = error.read().decode(errors="replace").strip()
            raise ClickHouseError(detail) from None

    def query(self, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Run a SELECT and return rows as dicts."""
        raw = self._post(sql.rstrip().rstrip(";") + "\nFORMAT JSONEachRow", params)
        return [json.loads(line) for line in raw.decode().splitlines() if line.strip()]

    def command(self, sql: str, params: dict[str, Any] | None = None) -> None:
        """Run a statement that returns no rows (DDL, OPTIMIZE, SYSTEM ...)."""
        self._post(sql, params)

    def insert(self, table: str, rows: list[dict[str, Any]]) -> None:
        """Insert rows in a single INSERT (one data part)."""
        if not rows:
            return
        body = "\n".join(json.dumps(row) for row in rows).encode()
        self._post(f"INSERT INTO {table} FORMAT JSONEachRow", None, body)
