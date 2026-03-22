import requests


class TelegramDisplay:
    """Send concise summaries to Telegram group chat via bot tokens."""

    TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"

    def __init__(self, bot_tokens, group_chat_id):
        """
        bot_tokens: dict like {"coder": "token...", "leader": "token...", ...}
        group_chat_id: str like "-1003716709219"
        """
        self.bot_tokens = bot_tokens
        self.group_chat_id = group_chat_id

    def format_step_summary(self, role, task_brief, result_brief):
        return f"✓ {task_brief} — {result_brief}"

    def format_task_start(self, task_id, summary, roles):
        role_chain = " → ".join(r.capitalize() for r in roles)
        return f"📋 {task_id}: {summary}\n流程: {role_chain}"

    def format_task_end(self, task_id, status, step_count):
        status_icon = "✓" if status == "completed" else "✗"
        return f"{status_icon} {task_id} 完成，共 {step_count} 步"

    def format_fallback_warning(self):
        return "⚠ 自动分析失败，使用规则分派"

    def format_error(self, task_id, step_order, role, error_msg):
        return f"✗ {task_id} 步骤 {step_order} ({role}) 失败: {error_msg}"

    def format_truncation_warning(self, original_count, max_steps):
        return f"⚠ 任务计划有 {original_count} 步，已简化为前 {max_steps} 步"

    def send(self, role, text, dry_run=False):
        """Send message to group chat using the specified role's bot token.
        Falls back to 'leader' token if role token not found.
        """
        if dry_run:
            print(f"[{role}] {text}")
            return True

        token = self.bot_tokens.get(role) or self.bot_tokens.get("leader")
        if not token or token == "TODO":
            print(f"[DRY-{role}] {text}")
            return False

        try:
            resp = requests.post(
                self.TELEGRAM_API.format(token=token),
                json={"chat_id": self.group_chat_id, "text": text},
                timeout=10,
            )
            return resp.ok
        except requests.RequestException:
            return False
