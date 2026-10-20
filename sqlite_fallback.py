import logging
import os
import re
import sqlite3

logger = logging.getLogger(__name__)

DEFAULT_SQLITE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "cyberbullying.db"
)


class SQLiteCursorWrapper:
    def __init__(self, cursor, conn):
        self._cursor = cursor
        self._conn = conn
        self._mock_result = None

    @property
    def lastrowid(self):
        return self._cursor.lastrowid

    @property
    def rowcount(self):
        return self._cursor.rowcount

    def _adapt_query(self, query, params=None):
        q = query.strip()

        # Handle MySQL lock functions
        if re.search(r"SELECT\s+GET_LOCK", q, re.IGNORECASE) or re.search(
            r"SELECT\s+RELEASE_LOCK", q, re.IGNORECASE
        ):
            self._mock_result = [(1,)]
            return None, None

        # Handle IS_NULLABLE queries
        if re.search(r"SELECT\s+IS_NULLABLE\s+FROM\s+INFORMATION_SCHEMA", q, re.IGNORECASE):
            self._mock_result = [("YES",)]
            return None, None

        # Handle KEY_COLUMN_USAGE (foreign keys)
        if re.search(r"INFORMATION_SCHEMA\.KEY_COLUMN_USAGE", q, re.IGNORECASE):
            self._mock_result = [(1,)]
            return None, None

        # Handle INFORMATION_SCHEMA.COLUMNS check
        if re.search(r"INFORMATION_SCHEMA\.COLUMNS", q, re.IGNORECASE):
            table_match = re.search(r"TABLE_NAME\s*=\s*['\"]?(\w+)['\"]?", q, re.IGNORECASE)
            col_match = re.search(r"COLUMN_NAME\s*=\s*['\"]?(\w+)['\"]?", q, re.IGNORECASE)
            table_name = table_match.group(1) if table_match else None
            col_name = col_match.group(1) if col_match else None
            if not col_name and params and len(params) > 0:
                col_name = params[-1]

            if table_name and col_name:
                try:
                    self._cursor.execute(f"PRAGMA table_info({table_name})")
                    existing_cols = [row[1].lower() for row in self._cursor.fetchall()]
                    found = 1 if col_name.lower() in existing_cols else 0
                    self._mock_result = [(found,)]
                except Exception:
                    self._mock_result = [(0,)]
            else:
                self._mock_result = [(0,)]
            return None, None

        # No-op MySQL-specific ALTER statements unsupported in SQLite
        if re.search(r"\bALTER\s+TABLE\s+\w+\s+ADD\s+CONSTRAINT\b", q, re.IGNORECASE):
            return None, None
        if re.search(r"\bALTER\s+TABLE\s+\w+\s+MODIFY\b", q, re.IGNORECASE):
            return None, None

        # Adapt MySQL DDL
        q = re.sub(r"\bINT\s+AUTO_INCREMENT\s+PRIMARY\s+KEY\b", "INTEGER PRIMARY KEY AUTOINCREMENT", q, flags=re.IGNORECASE)
        q = re.sub(r"\bAUTO_INCREMENT\s+PRIMARY\s+KEY\b", "PRIMARY KEY AUTOINCREMENT", q, flags=re.IGNORECASE)
        q = re.sub(r"\bAUTO_INCREMENT\b", "", q, flags=re.IGNORECASE)
        q = re.sub(r"\bINSERT\s+IGNORE\s+INTO\b", "INSERT OR IGNORE INTO", q, flags=re.IGNORECASE)
        q = re.sub(r"\bAFTER\s+\w+\b", "", q, flags=re.IGNORECASE)
        q = re.sub(r"\bON\s+UPDATE\s+CURRENT_TIMESTAMP\b", "", q, flags=re.IGNORECASE)

        # Replace MySQL parameter placeholder %s with SQLite ?
        q = q.replace("%s", "?")
        return q, params

    def execute(self, query, params=None):
        self._mock_result = None
        adapted, adapted_params = self._adapt_query(query, params)

        if adapted is None:
            return self

        try:
            if adapted_params:
                self._cursor.execute(adapted, adapted_params)
            else:
                self._cursor.execute(adapted)
        except sqlite3.OperationalError as op_err:
            # Handle duplicate column add error in SQLite gracefully
            if "duplicate column name" in str(op_err).lower():
                return self
            raise
        return self

    def executemany(self, query, seq_of_params):
        adapted, _ = self._adapt_query(query)
        if adapted is None:
            return self
        return self._cursor.executemany(adapted, seq_of_params)

    def fetchone(self):
        if self._mock_result is not None:
            if self._mock_result:
                return self._mock_result.pop(0)
            return None
        return self._cursor.fetchone()

    def fetchall(self):
        if self._mock_result is not None:
            res = self._mock_result
            self._mock_result = None
            return res
        return self._cursor.fetchall()

    def fetchmany(self, size=None):
        if self._mock_result is not None:
            return self._mock_result
        return self._cursor.fetchmany(size) if size else self._cursor.fetchmany()

    def close(self):
        return self._cursor.close()

    def __iter__(self):
        return iter(self._cursor)


class SQLiteConnectionWrapper:
    def __init__(self, raw_conn):
        self._raw_conn = raw_conn

    def cursor(self):
        return SQLiteCursorWrapper(self._raw_conn.cursor(), self._raw_conn)

    def commit(self):
        return self._raw_conn.commit()

    def rollback(self):
        return self._raw_conn.rollback()

    def close(self):
        return self._raw_conn.close()


def _sqlite_date_format(val, fmt):
    if not val:
        return ""
    s = str(val).strip()
    if fmt == "%Y-%m-%d":
        return s[:10]
    if fmt in ("%Y-%m-%d %H:%i", "%Y-%m-%d %H:%M"):
        return s[:16]
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(s)
        py_fmt = str(fmt).replace("%i", "%M")
        return dt.strftime(py_fmt)
    except Exception:
        return s[:16]


def get_sqlite_connection(db_path=None):
    from datetime import datetime

    target_path = db_path or os.getenv("SQLITE_DB_PATH", DEFAULT_SQLITE_PATH)
    conn = sqlite3.connect(
        target_path,
        check_same_thread=False,
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
    )
    conn.execute("PRAGMA foreign_keys = ON")
    conn.create_function("DATE_FORMAT", 2, _sqlite_date_format)
    conn.create_function("DATABASE", 0, lambda: "cyberbullying_detection")
    conn.create_function("NOW", 0, lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    conn.create_function("CURDATE", 0, lambda: datetime.now().strftime("%Y-%m-%d"))
    return SQLiteConnectionWrapper(conn)
