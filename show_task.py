"""查看任务完整输出

Usage:
    venv/bin/python show_task.py                    # 显示最近一条任务
    venv/bin/python show_task.py AT-20260323-001    # 显示指定任务
    venv/bin/python show_task.py --list              # 列出所有任务
"""
import sys
import sqlite3
from db import Database


def show_task(db, task_id):
    task = db.get_task(task_id)
    if not task:
        print(f"任务 {task_id} 不存在")
        return

    print(f"📋 {task['task_id']}  [{task['status']}]")
    print(f"   消息: {task['user_message']}")
    print(f"   时间: {task['created_at']}")
    print()

    steps = db.get_steps(task_id)
    for s in steps:
        emoji = {"coder": "👨‍💻", "reviewer": "🔍", "researcher": "🔎",
                 "analyst": "📊", "architect": "🏗️"}.get(s["role"], "🤖")
        print(f"{'='*60}")
        print(f"{emoji} Step {s['step_order']}: {s['role']}  [{s['status']}]  {s['duration_ms']}ms  {s['tokens_used']} tokens")
        print(f"{'='*60}")
        if s["output"]:
            print(s["output"])
        else:
            print("(无输出)")
        print()


def list_tasks(db):
    with sqlite3.connect(db.db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT task_id, status, user_message, created_at FROM tasks ORDER BY created_at DESC LIMIT 20").fetchall()
    for r in rows:
        status_icon = {"completed": "✅", "failed": "❌", "running": "🔄", "partial": "⚠️"}.get(r["status"], "⏳")
        print(f"{status_icon} {r['task_id']}  {r['user_message'][:50]}  ({r['created_at']})")


def main():
    db = Database("data/agent_teams.db")

    if len(sys.argv) > 1:
        if sys.argv[1] == "--list":
            list_tasks(db)
            return
        show_task(db, sys.argv[1])
        return

    with sqlite3.connect(db.db_path) as conn:
        row = conn.execute("SELECT task_id FROM tasks ORDER BY created_at DESC LIMIT 1").fetchone()
    if row:
        show_task(db, row[0])
    else:
        print("暂无任务记录")


if __name__ == "__main__":
    main()
