"""Agent Teams V2 — Core Dispatcher

Usage:
    venv/bin/python dispatcher.py "任务描述"
    venv/bin/python dispatcher.py --dry-run "任务描述"
"""
import json
import os
import re
import sys

from db import Database
from gateway_client import GatewayClient
from fallback import fallback_dispatch
from telegram_display import TelegramDisplay

VALID_ROLES = {"coder", "reviewer", "researcher", "analyst", "architect"}

ANALYSIS_PROMPT = """你是一个任务分析器。分析用户的任务，输出一个 JSON 分派计划。

规则：
- 拆分为 1-5 个步骤
- 每个步骤指定一个角色: coder, reviewer, researcher, analyst, architect
- 步骤按执行顺序排列
- 如果任务提到文件路径，放在 context_files 数组里

只输出 JSON，不要其他文字。格式：
{
  "summary": "一句话总结任务",
  "steps": [
    {"role": "coder", "task": "具体任务描述", "context_files": ["/path/to/file"]}
  ]
}"""


class Dispatcher:
    def __init__(self, config_path="config.json", db_path="data/agent_teams.db",
                 dry_run=False, roles_dir="roles"):
        with open(config_path) as f:
            self.config = json.load(f)

        self.db = Database(db_path)
        self.dry_run = dry_run
        self.roles_dir = roles_dir

        gw = self.config["gateway"]
        disp = self.config["dispatcher"]
        self.client = GatewayClient(gw["url"], gw["token"], disp["model"], disp["step_timeout_seconds"])
        self.max_steps = disp["max_steps"]
        self.max_context_bytes = disp["max_context_bytes"]

        bot_tokens = {name: info["token"] for name, info in self.config["telegram"]["bots"].items()}
        group_id = self.config["telegram"]["group_chat_id"]
        self.display = TelegramDisplay(bot_tokens, group_id)

    def parse_dispatch_plan(self, raw_text):
        """Parse k2p5's response into a dispatch plan. Returns None if invalid."""
        json_match = re.search(r'\{[\s\S]*\}', raw_text)
        if not json_match:
            return None

        try:
            plan = json.loads(json_match.group())
        except json.JSONDecodeError:
            return None

        if not isinstance(plan.get("steps"), list) or len(plan["steps"]) == 0:
            return None

        for step in plan["steps"]:
            if step.get("role") not in VALID_ROLES:
                return None
            if not step.get("task"):
                return None

        # Cap steps with notification
        if len(plan["steps"]) > self.max_steps:
            plan["_truncated_from"] = len(plan["steps"])
            plan["steps"] = plan["steps"][:self.max_steps]

        return plan

    def read_context_files(self, file_paths):
        """Read files and return combined context string."""
        parts = []
        total_bytes = 0
        max_per_file = 50 * 1024  # 50KB

        for path in file_paths:
            if not os.path.isfile(path):
                continue
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read(max_per_file)
                size = len(content.encode("utf-8"))
                if total_bytes + size > self.max_context_bytes:
                    break
                total_bytes += size
                parts.append(f"--- {path} ---\n{content}")
            except OSError:
                continue

        return "\n\n".join(parts)

    def load_role_prompt(self, role):
        """Load system prompt for a role from roles/*.md."""
        path = os.path.join(self.roles_dir, f"{role}.md")
        if os.path.isfile(path):
            with open(path, "r") as f:
                return f.read()
        return f"你是 {role}，请完成用户给你的任务。"

    def analyze_task(self, user_message):
        """Use k2p5 to analyze task and create dispatch plan. Falls back to keywords."""
        result = self.client.call(ANALYSIS_PROMPT, user_message)

        if result["status"] == "completed":
            plan = self.parse_dispatch_plan(result["text"])
            if plan:
                return plan, False  # (plan, is_fallback)

        # Fallback
        step = fallback_dispatch(user_message)
        return {
            "summary": user_message[:50],
            "steps": [step],
        }, True

    def execute(self, user_message):
        """Main entry point: analyze task, dispatch to roles, collect results."""
        task_id = self.db.generate_task_id()

        # 1. Analyze
        plan, is_fallback = self.analyze_task(user_message)
        self.db.create_task(task_id, user_message, json.dumps(plan, ensure_ascii=False))
        self.db.update_task_status(task_id, "running")

        roles = [s["role"] for s in plan["steps"]]
        self.display.send("leader", self.display.format_task_start(
            task_id, plan.get("summary", user_message[:50]), roles
        ), dry_run=self.dry_run)

        if is_fallback:
            self.display.send("leader", self.display.format_fallback_warning(), dry_run=self.dry_run)

        # Notify if plan was truncated
        if "_truncated_from" in plan:
            self.display.send("leader", self.display.format_truncation_warning(
                plan["_truncated_from"], self.max_steps
            ), dry_run=self.dry_run)

        # 2. Execute steps sequentially
        previous_output = ""
        completed_steps = 0
        final_status = "completed"

        for i, step in enumerate(plan["steps"]):
            role = step["role"]
            task_desc = step["task"]
            context_files = step.get("context_files", [])

            # Build user message for this role
            role_input_parts = [f"任务: {task_desc}"]
            if context_files:
                file_context = self.read_context_files(context_files)
                if file_context:
                    role_input_parts.append(f"相关文件:\n{file_context}")
            if previous_output:
                role_input_parts.append(f"上一步 ({plan['steps'][i-1]['role']}) 的输出:\n{previous_output}")

            role_input = "\n\n".join(role_input_parts)
            system_prompt = self.load_role_prompt(role)

            # Call API
            result = self.client.call(system_prompt, role_input)

            # Record step
            self.db.create_step(
                task_id, i + 1, role, role_input, result["text"],
                result.get("tokens", 0), result.get("duration_ms", 0), result["status"]
            )

            if result["status"] != "completed" or not result["text"]:
                error_msg = result.get("error", result["status"])
                self.display.send("leader", self.display.format_error(
                    task_id, i + 1, role, error_msg
                ), dry_run=self.dry_run)
                final_status = "partial" if completed_steps > 0 else "failed"
                break

            # Send concise summary to group
            lines = result["text"].strip().split("\n")
            summary_line = lines[-1] if lines else result["text"][:100]
            self.display.send(role, self.display.format_step_summary(
                role, task_desc[:30], summary_line[:100]
            ), dry_run=self.dry_run)

            previous_output = result["text"]
            completed_steps += 1

        # 3. Finalize
        self.db.update_task_status(task_id, final_status)
        self.display.send("leader", self.display.format_task_end(
            task_id, final_status, completed_steps
        ), dry_run=self.dry_run)

        return {
            "task_id": task_id,
            "status": final_status,
            "steps_completed": completed_steps,
            "final_output": previous_output,
        }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Agent Teams V2 Dispatcher")
    parser.add_argument("message", help="Task message to dispatch")
    parser.add_argument("--dry-run", action="store_true", help="Print to stdout instead of Telegram")
    parser.add_argument("--config", default="config.json", help="Config file path")
    parser.add_argument("--db", default="data/agent_teams.db", help="Database file path")
    args = parser.parse_args()

    # Ensure data dir exists
    os.makedirs(os.path.dirname(args.db) or ".", exist_ok=True)

    dispatcher = Dispatcher(
        config_path=args.config,
        db_path=args.db,
        dry_run=args.dry_run,
        roles_dir=os.path.join(os.path.dirname(os.path.abspath(__file__)), "roles"),
    )
    result = dispatcher.execute(args.message)

    # Always output result summary to stdout (Leader agent reads this)
    print(f"\n--- Result ---")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
