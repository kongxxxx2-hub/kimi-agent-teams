"""Agent Teams V2 — Core Dispatcher

Usage:
    venv/bin/python dispatcher.py "任务描述"
    venv/bin/python dispatcher.py --dry-run "任务描述"
"""
import json
import os
import re
import sys
from datetime import datetime

from db import Database
from gateway_client import GatewayClient
from fallback import fallback_dispatch
from telegram_display import TelegramDisplay

VALID_ROLES = {"coder", "reviewer", "researcher", "analyst", "architect"}
OUTPUT_DIR = "~/Desktop/AgentTeams_Output"

MAX_REVIEW_ROUNDS = 2

LEADER_REVIEW_PROMPT = """你是严格的审稿人。你的职责是找出产出中的不足，而不是夸奖。

审核标准（每项 1-10 分）：
1. 完整性：是否覆盖了用户要求的所有方面
2. 深度：分析是否有具体数据支撑，不是泛泛而谈
3. 准确性：信息是否准确，逻辑链是否完整（论据→论点→结论）
4. 可操作性：结论是否具体可执行，不是空话

规则：
- 你必须找出至少 2 个可以改进的地方
- 如果任一项低于 7 分，verdict 必须是 revise
- 只有四项都 >= 7 分才能 pass

只输出 JSON：
{"verdict":"pass","scores":{"完整性":8,"深度":7,"准确性":8,"可操作性":7},"issues":["问题1","问题2"],"feedback":"总体评价"}
或
{"verdict":"revise","scores":{"完整性":6,"深度":5,"准确性":7,"可操作性":6},"issues":["问题1","问题2"],"feedback":"需要补充的内容","target_role":"researcher"}"""

ANALYSIS_PROMPT = """你是一个 JSON 任务分析器。你只输出 JSON，绝对不输出任何其他文字。

分析用户任务，拆分为步骤，每步指定角色。

角色只有这5个: coder, reviewer, researcher, analyst, architect

直接输出以下格式的JSON（不要markdown代码块，不要解释）：
{"summary":"一句话总结","steps":[{"role":"coder","task":"具体描述"}]}"""


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

    def _leader_review(self, task_id, plan, combined_output):
        """Leader reviews combined output. Returns (passed, revised_steps_output)."""
        original_request = plan.get("_original_message", plan.get("summary", ""))

        for review_round in range(1, MAX_REVIEW_ROUNDS + 1):
            review_input = (
                f"原始任务: {original_request}\n\n"
                f"计划: {json.dumps(plan.get('steps', []), ensure_ascii=False)}\n\n"
                f"团队产出:\n{combined_output}"
            )

            result = self.client.call(LEADER_REVIEW_PROMPT, review_input)

            if result["status"] != "completed" or not result["text"]:
                self.display.send("leader",
                    f"🔄 审核 (第{review_round}轮): API 调用失败，视为通过",
                    dry_run=self.dry_run)
                return True, combined_output

            # Parse review JSON
            json_match = re.search(r'\{[\s\S]*\}', result["text"])
            if not json_match:
                self.display.send("leader",
                    f"🔄 审核 (第{review_round}轮): 解析失败，视为通过",
                    dry_run=self.dry_run)
                return True, combined_output

            try:
                review = json.loads(json_match.group())
            except json.JSONDecodeError:
                self.display.send("leader",
                    f"🔄 审核 (第{review_round}轮): JSON 解析失败，视为通过",
                    dry_run=self.dry_run)
                return True, combined_output

            verdict = review.get("verdict", "pass")
            feedback = review.get("feedback", "")

            if verdict == "pass":
                self.display.send("leader",
                    f"✅ 审核通过 (第{review_round}轮): {feedback[:100]}",
                    dry_run=self.dry_run)
                return True, combined_output

            # verdict == "revise"
            target_role = review.get("target_role", "researcher")
            if target_role not in VALID_ROLES:
                target_role = "researcher"

            self.display.send("leader",
                f"🔄 审核 (第{review_round}轮): 需要 {target_role} 修订 — {feedback[:100]}",
                dry_run=self.dry_run)

            # Find the original task for this role
            original_task = ""
            for step in plan.get("steps", []):
                if step["role"] == target_role:
                    original_task = step["task"]
                    break
            if not original_task:
                original_task = plan.get("summary", "")

            # Re-run the target role with feedback
            revision_input = (
                f"任务: {original_task}\n\n"
                f"Leader 审核反馈 (第{review_round}轮修订):\n{feedback}\n\n"
                f"你之前的产出:\n{combined_output}\n\n"
                f"请根据反馈修订和补充你的产出。"
            )
            system_prompt = self.load_role_prompt(target_role)
            revision_result = self.client.call(system_prompt, revision_input)

            # Record revision step
            step_order = len(self.db.get_steps(task_id)) + 1
            self.db.create_step(
                task_id, step_order, target_role, revision_input,
                revision_result["text"],
                revision_result.get("tokens", 0),
                revision_result.get("duration_ms", 0),
                revision_result["status"]
            )

            if revision_result["status"] != "completed" or not revision_result["text"]:
                self.display.send("leader",
                    f"❌ {target_role} 修订失败，使用原始产出",
                    dry_run=self.dry_run)
                return False, combined_output

            # Send revision summary
            rev_lines = revision_result["text"].strip().split("\n")
            rev_summary = rev_lines[-1] if rev_lines else revision_result["text"][:100]
            self.display.send(target_role,
                f"🔄 修订完成 — {rev_summary[:100]}",
                dry_run=self.dry_run)

            combined_output = revision_result["text"]

        # Exhausted review rounds
        self.display.send("leader",
            f"⚠️ 已达最大修订轮数 ({MAX_REVIEW_ROUNDS})，使用最新产出",
            dry_run=self.dry_run)
        return False, combined_output

    def analyze_task(self, user_message):
        """Use k2p5 to analyze task and create dispatch plan. Falls back to keywords."""
        result = self.client.call(ANALYSIS_PROMPT, user_message)

        if result["status"] == "completed" and result["text"]:
            plan = self.parse_dispatch_plan(result["text"])
            if plan:
                return plan, False  # (plan, is_fallback)
            # Log parse failure for debugging
            print(f"[dispatcher] k2p5 分析返回但JSON解析失败, 前200字: {result['text'][:200]}", file=sys.stderr)

        # Fallback
        fallback_result = fallback_dispatch(user_message)
        if isinstance(fallback_result, list):
            steps = fallback_result
        else:
            steps = [fallback_result]
        return {
            "summary": user_message[:50],
            "steps": steps,
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

        # 3. Leader review loop
        if final_status == "completed" and previous_output:
            plan["_original_message"] = user_message
            self.display.send("leader", "🔍 Leader 开始审核产出...", dry_run=self.dry_run)
            review_passed, previous_output = self._leader_review(
                task_id, plan, previous_output
            )
            if not review_passed:
                final_status = "completed"  # still completed, just with revisions

        # 4. Save output to file
        output_path = self._save_output(task_id, plan, completed_steps)

        # 5. Finalize
        self.db.update_task_status(task_id, final_status)

        end_msg = self.display.format_task_end(task_id, final_status, completed_steps)
        if output_path:
            end_msg += f"\n📁 {output_path}"
        self.display.send("leader", end_msg, dry_run=self.dry_run)

        return {
            "task_id": task_id,
            "status": final_status,
            "steps_completed": completed_steps,
            "final_output": previous_output,
            "output_path": output_path,
        }

    def _save_output(self, task_id, plan, completed_steps):
        """Save full task output as a markdown file."""
        if completed_steps == 0:
            return None

        steps = self.db.get_steps(task_id)
        if not steps:
            return None

        # Build markdown
        summary = plan.get("summary", task_id)
        lines = [f"# {summary}\n"]
        lines.append(f"**任务ID**: {task_id}")
        lines.append(f"**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append(f"**步骤数**: {completed_steps}\n")

        role_emoji = {"coder": "👨‍💻", "reviewer": "🔍", "researcher": "🔎",
                      "analyst": "📊", "architect": "🏗️"}

        for s in steps:
            if s["status"] != "completed" or not s["output"]:
                continue
            emoji = role_emoji.get(s["role"], "🤖")
            lines.append(f"---\n\n## {emoji} {s['role'].capitalize()}\n")
            lines.append(s["output"])
            lines.append("")

        # Write file
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        # Clean summary for filename
        safe_name = re.sub(r'[^\w\u4e00-\u9fff-]', '_', summary)[:30].strip('_')
        filename = f"{task_id}_{safe_name}.md"
        filepath = os.path.join(OUTPUT_DIR, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        # Generate PDF
        pdf_path = self._md_to_pdf(filepath)

        return pdf_path or filepath

    def _md_to_pdf(self, md_path):
        """Convert markdown file to PDF. Returns PDF path or None."""
        try:
            import markdown
            os.environ.setdefault("DYLD_LIBRARY_PATH", "/opt/homebrew/lib")
            from weasyprint import HTML

            with open(md_path, encoding="utf-8") as f:
                md_text = f.read()

            html_body = markdown.markdown(md_text, extensions=["tables", "fenced_code"])
            html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
@font-face {{
    font-family: "CJK";
    src: local("Hiragino Sans GB"), local("Heiti SC"), local("STHeiti");
}}
body {{ font-family: "CJK", "Hiragino Sans GB", "Heiti SC", "STHeiti", sans-serif; font-size: 12px; line-height: 1.8; margin: 2cm; color: #333; }}
h1 {{ font-family: "CJK", "Hiragino Sans GB", "Heiti SC", sans-serif; color: #1a1a1a; border-bottom: 2px solid #e0e0e0; padding-bottom: 8px; font-size: 22px; }}
h2 {{ font-family: "CJK", "Hiragino Sans GB", "Heiti SC", sans-serif; color: #2c3e50; margin-top: 1.5em; font-size: 18px; }}
h3 {{ font-family: "CJK", "Hiragino Sans GB", "Heiti SC", sans-serif; color: #34495e; font-size: 15px; }}
table {{ border-collapse: collapse; width: 100%; margin: 1em 0; font-family: "CJK", "Hiragino Sans GB", "Heiti SC", sans-serif; }}
th, td {{ border: 1px solid #ddd; padding: 6px 8px; text-align: left; font-size: 11px; }}
th {{ background: #f5f5f5; font-weight: bold; }}
tr:nth-child(even) {{ background: #fafafa; }}
code {{ background: #f4f4f4; padding: 2px 6px; border-radius: 3px; font-size: 11px; }}
pre {{ background: #f8f8f8; padding: 12px; border-radius: 6px; overflow-x: auto; font-size: 11px; }}
blockquote {{ border-left: 4px solid #3498db; margin: 1em 0; padding: 0.5em 1em; background: #f0f7ff; }}
strong {{ font-family: "CJK", "Hiragino Sans GB", "Heiti SC", sans-serif; }}
</style></head><body>{html_body}</body></html>"""

            pdf_path = md_path.replace(".md", ".pdf")
            HTML(string=html).write_pdf(pdf_path)
            return pdf_path
        except Exception as e:
            print(f"[dispatcher] PDF 生成失败: {e}", file=sys.stderr)
            return None


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
