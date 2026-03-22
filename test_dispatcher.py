import os
import json
import tempfile
from dispatcher import Dispatcher

MOCK_CONFIG = {
    "gateway": {"url": "http://localhost:18789", "token": "fake"},
    "telegram": {
        "group_chat_id": "-1003716709219",
        "bots": {"leader": {"token": "fake"}, "coder": {"token": "fake"}, "reviewer": {"token": "fake"},
                 "researcher": {"token": "fake"}, "analyst": {"token": "fake"}, "architect": {"token": "fake"}}
    },
    "dispatcher": {"model": "kimi-coding/k2p5", "max_steps": 5, "step_timeout_seconds": 120, "max_context_bytes": 153600}
}


def make_dispatcher(db_path):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(MOCK_CONFIG, f)
        config_path = f.name
    return Dispatcher(config_path=config_path, db_path=db_path, dry_run=True,
                      roles_dir=os.path.join(os.path.dirname(os.path.abspath(__file__)), "roles"))


def test_parse_dispatch_plan_valid():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        d = make_dispatcher(db_path)
        plan_json = json.dumps({
            "summary": "写代码并review",
            "steps": [
                {"role": "coder", "task": "写脚本"},
                {"role": "reviewer", "task": "审查代码"}
            ]
        })
        plan = d.parse_dispatch_plan(plan_json)
        assert plan is not None
        assert len(plan["steps"]) == 2
        assert plan["steps"][0]["role"] == "coder"
    finally:
        os.unlink(db_path)


def test_parse_dispatch_plan_invalid():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        d = make_dispatcher(db_path)
        assert d.parse_dispatch_plan("not json") is None
        assert d.parse_dispatch_plan('{"steps":"not a list"}') is None
        assert d.parse_dispatch_plan('{"steps":[{"role":"unknown","task":"x"}]}') is None
    finally:
        os.unlink(db_path)


def test_parse_dispatch_plan_max_steps():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        d = make_dispatcher(db_path)
        plan_json = json.dumps({
            "summary": "big task",
            "steps": [{"role": "coder", "task": f"step {i}"} for i in range(10)]
        })
        plan = d.parse_dispatch_plan(plan_json)
        assert len(plan["steps"]) == 5
        assert plan["_truncated_from"] == 10
    finally:
        os.unlink(db_path)


def test_read_context_files():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("print('hello')\n" * 10)
        tmp_file = f.name
    try:
        d = make_dispatcher(db_path)
        context = d.read_context_files([tmp_file, "/nonexistent/file.py"])
        assert "hello" in context
        # Nonexistent file should be silently skipped
        assert "nonexistent" not in context
    finally:
        os.unlink(db_path)
        os.unlink(tmp_file)


if __name__ == "__main__":
    test_parse_dispatch_plan_valid()
    test_parse_dispatch_plan_invalid()
    test_parse_dispatch_plan_max_steps()
    test_read_context_files()
    print("All dispatcher tests passed")
