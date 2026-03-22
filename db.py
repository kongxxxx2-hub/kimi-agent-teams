import sqlite3
from datetime import datetime


class Database:
    def __init__(self, db_path="data/agent_teams.db"):
        self.db_path = db_path
        self._init_tables()

    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    user_message TEXT NOT NULL,
                    dispatch_plan TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS steps (
                    step_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL REFERENCES tasks(task_id),
                    step_order INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    input_prompt TEXT,
                    output TEXT,
                    tokens_used INTEGER DEFAULT 0,
                    duration_ms INTEGER DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

    def generate_task_id(self):
        now = datetime.now()
        date_str = now.strftime("%Y%m%d")
        with self._conn() as conn:
            row = conn.execute(
                "SELECT MAX(CAST(SUBSTR(task_id, -3) AS INTEGER)) as max_seq FROM tasks WHERE task_id LIKE ?",
                (f"AT-{date_str}-%",)
            ).fetchone()
            seq = (row["max_seq"] or 0) + 1
        return f"AT-{date_str}-{seq:03d}"

    def create_task(self, task_id, user_message, dispatch_plan=None):
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO tasks (task_id, user_message, dispatch_plan) VALUES (?, ?, ?)",
                (task_id, user_message, dispatch_plan)
            )
        return task_id

    def get_task(self, task_id):
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        return dict(row) if row else None

    def update_task_status(self, task_id, status):
        completed_at = datetime.now().isoformat() if status in ("completed", "failed", "partial") else None
        with self._conn() as conn:
            if completed_at:
                conn.execute(
                    "UPDATE tasks SET status = ?, completed_at = ? WHERE task_id = ?",
                    (status, completed_at, task_id)
                )
            else:
                conn.execute(
                    "UPDATE tasks SET status = ? WHERE task_id = ?",
                    (status, task_id)
                )

    def create_step(self, task_id, step_order, role, input_prompt, output, tokens_used, duration_ms, status):
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO steps (task_id, step_order, role, input_prompt, output, tokens_used, duration_ms, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (task_id, step_order, role, input_prompt, output, tokens_used, duration_ms, status)
            )

    def get_steps(self, task_id):
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM steps WHERE task_id = ? ORDER BY step_order", (task_id,)
            ).fetchall()
        return [dict(r) for r in rows]
