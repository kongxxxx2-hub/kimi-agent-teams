import os
import tempfile
from db import Database


def test_create_task_and_steps():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        db = Database(db_path)
        task_id = db.create_task("AT-20260322-001", "帮我写个脚本", '{"steps":[]}')
        assert task_id == "AT-20260322-001"

        task = db.get_task(task_id)
        assert task["status"] == "pending"
        assert task["user_message"] == "帮我写个脚本"

        db.update_task_status(task_id, "running")
        task = db.get_task(task_id)
        assert task["status"] == "running"

        db.create_step(task_id, 1, "coder", "写代码", "代码写好了", 500, 3000, "completed")
        steps = db.get_steps(task_id)
        assert len(steps) == 1
        assert steps[0]["role"] == "coder"
        assert steps[0]["tokens_used"] == 500

        db.update_task_status(task_id, "completed")
        task = db.get_task(task_id)
        assert task["status"] == "completed"
        assert task["completed_at"] is not None
    finally:
        os.unlink(db_path)


def test_generate_task_id():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        db = Database(db_path)
        tid1 = db.generate_task_id()
        assert tid1.startswith("AT-")
        # Create a task so the next ID increments
        db.create_task(tid1, "test task")
        tid2 = db.generate_task_id()
        assert tid1 != tid2
    finally:
        os.unlink(db_path)


if __name__ == "__main__":
    test_create_task_and_steps()
    test_generate_task_id()
    print("All db tests passed")
