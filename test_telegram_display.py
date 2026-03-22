from telegram_display import TelegramDisplay


def test_format_step_summary():
    td = TelegramDisplay({}, "-1003716709219")
    summary = td.format_step_summary("coder", "重构 liuban.py 选股逻辑", "已完成重构，新增3个筛选条件")
    assert "✓" in summary
    assert len(summary) < 200


def test_format_task_start():
    td = TelegramDisplay({}, "-1003716709219")
    msg = td.format_task_start("AT-20260322-001", "重构选股脚本并 review", ["coder", "reviewer"])
    assert "AT-20260322-001" in msg
    assert "Coder" in msg


def test_format_task_end():
    td = TelegramDisplay({}, "-1003716709219")
    msg = td.format_task_end("AT-20260322-001", "completed", 2)
    assert "AT-20260322-001" in msg


def test_format_fallback_warning():
    td = TelegramDisplay({}, "-1003716709219")
    msg = td.format_fallback_warning()
    assert "⚠" in msg


def test_format_truncation_warning():
    td = TelegramDisplay({}, "-1003716709219")
    msg = td.format_truncation_warning(8, 5)
    assert "8" in msg
    assert "5" in msg


if __name__ == "__main__":
    test_format_step_summary()
    test_format_task_start()
    test_format_task_end()
    test_format_fallback_warning()
    test_format_truncation_warning()
    print("All telegram_display tests passed")
