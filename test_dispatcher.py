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
        assert "nonexistent" not in context
    finally:
        os.unlink(db_path)
        os.unlink(tmp_file)


def test_analyze_task():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        d = make_dispatcher(db_path)
        plan, is_fallback = d.analyze_task("深入调研CPO产业链")
        assert is_fallback is True
        assert len(plan["steps"]) == 3  # researcher → analyst → reviewer
        assert plan["steps"][0]["role"] == "researcher"
    finally:
        os.unlink(db_path)


def test_hard_rule_check():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        d = make_dispatcher(db_path)
        # Short content should fail
        issues = d._hard_rule_check("太短了")
        assert len(issues) > 0

        # Good content should pass
        good = "这是一份报告" * 500 + "\n|---|---|\n| 数据 | 100亿 |"
        issues = d._hard_rule_check(good)
        assert len(issues) == 0
    finally:
        os.unlink(db_path)


if __name__ == "__main__":
    test_read_context_files()
    test_analyze_task()
    test_hard_rule_check()
    print("All dispatcher tests passed")
