"""Agent Teams V2 — Telegram Listener

Polls the Telegram group chat for messages mentioning @AgentLeader,
then dispatches tasks via the Dispatcher.

Usage:
    venv/bin/python telegram_listener.py          # daemon mode
    venv/bin/python telegram_listener.py --once    # process one message and exit
"""
import json
import os
import re
import signal
import sys
import time

import requests

# Ensure project root is on path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dispatcher import Dispatcher

MENTION_PATTERN = re.compile(r"@AgentLeader\w*", re.IGNORECASE)
POLL_INTERVAL = 3  # seconds between getUpdates calls
TELEGRAM_API = "https://api.telegram.org/bot{token}"


class TelegramListener:
    def __init__(self, config_path="config.json", db_path="data/agent_teams.db",
                 dry_run=False, once=False):
        with open(config_path) as f:
            self.config = json.load(f)

        self.leader_token = self.config["telegram"]["bots"]["leader"]["token"]
        # Leader bot is no longer polled by clawdbot (binding removed), so we can use it directly
        self.poll_token = self.leader_token
        self.group_chat_id = int(self.config["telegram"]["group_chat_id"])
        self.once = once
        self.dry_run = dry_run
        self.running = True
        self.offset = 0  # Telegram update offset
        self.start_time = int(time.time())

        self.dispatcher = Dispatcher(
            config_path=config_path,
            db_path=db_path,
            dry_run=dry_run,
            roles_dir=os.path.join(os.path.dirname(os.path.abspath(__file__)), "roles"),
        )

        # Graceful shutdown
        signal.signal(signal.SIGTERM, self._shutdown)
        signal.signal(signal.SIGINT, self._shutdown)

    def _shutdown(self, signum, frame):
        print(f"[listener] Received signal {signum}, shutting down...")
        self.running = False

    def _get_updates(self):
        """Poll Telegram Bot API for new messages."""
        try:
            resp = requests.get(
                f"{TELEGRAM_API.format(token=self.poll_token)}/getUpdates",
                params={
                    "offset": self.offset,
                    "timeout": 30,
                    "allowed_updates": json.dumps(["message"]),
                },
                timeout=35,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("ok"):
                return data.get("result", [])
        except requests.RequestException as e:
            print(f"[listener] getUpdates error: {e}", file=sys.stderr)
        return []

    def _send_message(self, text):
        """Send a message to the group chat via leader bot."""
        if self.dry_run:
            print(f"[leader] {text}")
            return True
        try:
            resp = requests.post(
                f"{TELEGRAM_API.format(token=self.leader_token)}/sendMessage",
                json={"chat_id": self.group_chat_id, "text": text},
                timeout=10,
            )
            return resp.ok
        except requests.RequestException:
            return False

    def _extract_task(self, text):
        """Remove @mention and return the task text. Returns None if empty."""
        task = MENTION_PATTERN.sub("", text).strip()
        return task if task else None

    def _is_relevant(self, update):
        """Check if an update is a relevant message in our group."""
        msg = update.get("message")
        if not msg:
            return False

        # Must be from our group
        chat_id = msg.get("chat", {}).get("id")
        if chat_id != self.group_chat_id:
            return False

        # Must have text
        text = msg.get("text", "")
        if not text:
            return False

        # Must mention @AgentLeader
        if not MENTION_PATTERN.search(text):
            return False

        # Skip messages older than script startup
        msg_date = msg.get("date", 0)
        if msg_date < self.start_time:
            return False

        return True

    def process_update(self, update):
        """Process a single relevant update."""
        msg = update["message"]
        text = msg["text"]
        sender = msg.get("from", {}).get("first_name", "Unknown")
        msg_id = msg.get("message_id", "?")

        task_text = self._extract_task(text)
        if not task_text:
            print(f"[listener] Empty task from {sender} (msg {msg_id}), skipping")
            return

        print(f"[listener] Task from {sender}: {task_text[:80]}")

        try:
            result = self.dispatcher.execute(task_text)

            # Send final summary back to group
            status = result.get("status", "unknown")
            task_id = result.get("task_id", "?")
            steps = result.get("steps_completed", 0)
            output_path = result.get("output_path")

            if status == "completed":
                summary = f"任务 {task_id} 已完成 ({steps} 步)"
            elif status == "partial":
                summary = f"任务 {task_id} 部分完成 ({steps} 步)"
            else:
                summary = f"任务 {task_id} 失败"

            if output_path:
                summary += f"\n📁 {output_path}"

            # Include a brief excerpt of the final output
            final_output = result.get("final_output", "")
            if final_output:
                excerpt = final_output[:300]
                if len(final_output) > 300:
                    excerpt += "..."
                summary += f"\n\n📝 最终产出摘要:\n{excerpt}"

            self._send_message(summary)
            print(f"[listener] Task {task_id} finished with status: {status}")

        except Exception as e:
            error_msg = f"任务执行出错: {e}"
            print(f"[listener] Error: {e}", file=sys.stderr)
            self._send_message(error_msg)

    def run(self):
        """Main loop: poll for updates and dispatch tasks."""
        print(f"[listener] Started at {self.start_time}, polling group {self.group_chat_id}")
        print(f"[listener] Mode: {'once' if self.once else 'daemon'}, dry_run: {self.dry_run}")

        # Consume existing updates to skip history
        print("[listener] Consuming existing updates to skip history...")
        initial_updates = self._get_updates()
        if initial_updates:
            self.offset = initial_updates[-1]["update_id"] + 1
            print(f"[listener] Skipped {len(initial_updates)} existing updates, offset={self.offset}")

        while self.running:
            updates = self._get_updates()

            for update in updates:
                self.offset = update["update_id"] + 1

                if self._is_relevant(update):
                    self.process_update(update)

                    if self.once:
                        print("[listener] --once mode, exiting after first task")
                        return

            if not updates:
                time.sleep(POLL_INTERVAL)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Agent Teams Telegram Listener")
    parser.add_argument("--once", action="store_true", help="Process one message and exit")
    parser.add_argument("--dry-run", action="store_true", help="Print instead of sending to Telegram")
    parser.add_argument("--config", default="config.json", help="Config file path")
    parser.add_argument("--db", default="data/agent_teams.db", help="Database file path")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.db) or ".", exist_ok=True)

    listener = TelegramListener(
        config_path=args.config,
        db_path=args.db,
        dry_run=args.dry_run,
        once=args.once,
    )
    listener.run()


if __name__ == "__main__":
    main()
