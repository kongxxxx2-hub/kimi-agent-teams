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
import fcntl

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dispatcher import Dispatcher

MENTION_PATTERN = re.compile(r"@AgentLeader\w*", re.IGNORECASE)
TELEGRAM_API = "https://api.telegram.org/bot{token}"
LOCK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", ".listener.lock")
OFFSET_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", ".listener_offset")


class TelegramListener:
    def __init__(self, config_path="config.json", db_path="data/agent_teams.db",
                 dry_run=False, once=False):
        with open(config_path) as f:
            self.config = json.load(f)

        self.leader_token = self.config["telegram"]["bots"]["leader"]["token"]
        self.poll_token = self.leader_token
        self.group_chat_id = int(self.config["telegram"]["group_chat_id"])
        self.once = once
        self.dry_run = dry_run
        self.running = True
        self.start_time = int(time.time())
        self.processed_ids = set()  # dedup: track processed update IDs

        # Load persisted offset
        self.offset = self._load_offset()

        self.dispatcher = Dispatcher(
            config_path=config_path,
            db_path=db_path,
            dry_run=dry_run,
            roles_dir=os.path.join(os.path.dirname(os.path.abspath(__file__)), "roles"),
        )

        signal.signal(signal.SIGTERM, self._shutdown)
        signal.signal(signal.SIGINT, self._shutdown)

    def _load_offset(self):
        """Load persisted offset from file."""
        try:
            with open(OFFSET_FILE) as f:
                return int(f.read().strip())
        except (FileNotFoundError, ValueError):
            return 0

    def _save_offset(self):
        """Persist offset to file."""
        os.makedirs(os.path.dirname(OFFSET_FILE), exist_ok=True)
        with open(OFFSET_FILE, "w") as f:
            f.write(str(self.offset))

    def _shutdown(self, signum, frame):
        print(f"[listener] Received signal {signum}, shutting down...")
        self._save_offset()
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
            if resp.status_code == 409:
                # Another process is polling this bot. Wait and retry.
                print("[listener] 409 Conflict - waiting 35s for other poller to release...", file=sys.stderr)
                time.sleep(35)
                return []
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
        """Remove @mention and return the task text."""
        task = MENTION_PATTERN.sub("", text).strip()
        return task if task else None

    def _is_relevant(self, update):
        """Check if an update is a relevant message in our group."""
        msg = update.get("message")
        if not msg:
            return False

        # Dedup: skip already processed
        update_id = update.get("update_id")
        if update_id in self.processed_ids:
            return False

        chat_id = msg.get("chat", {}).get("id")
        if chat_id != self.group_chat_id:
            return False

        text = msg.get("text", "")
        if not text:
            return False

        if not MENTION_PATTERN.search(text):
            return False

        # Skip messages older than script startup
        msg_date = msg.get("date", 0)
        if msg_date < self.start_time:
            return False

        return True

    def process_update(self, update):
        """Process a single relevant update."""
        update_id = update["update_id"]
        self.processed_ids.add(update_id)

        msg = update["message"]
        text = msg["text"]
        sender = msg.get("from", {}).get("first_name", "Unknown")

        task_text = self._extract_task(text)
        if not task_text:
            print(f"[listener] Empty task from {sender}, skipping")
            return

        print(f"[listener] Task from {sender}: {task_text[:80]}")

        try:
            result = self.dispatcher.execute(task_text)

            status = result.get("status", "unknown")
            task_id = result.get("task_id", "?")
            output_path = result.get("output_path")

            summary = f"✅ 任务 {task_id} 已完成" if status == "completed" else f"❌ 任务 {task_id} {status}"
            if output_path:
                summary += f"\n📁 {output_path}"

            self._send_message(summary)
            print(f"[listener] Task {task_id} finished: {status}")

        except Exception as e:
            print(f"[listener] Error: {e}", file=sys.stderr)
            self._send_message(f"❌ 任务执行出错: {e}")

    def run(self):
        """Main loop: poll for updates and dispatch tasks."""
        print(f"[listener] Started at {self.start_time}, polling group {self.group_chat_id}")
        print(f"[listener] Mode: {'once' if self.once else 'daemon'}, dry_run: {self.dry_run}")
        print(f"[listener] Persisted offset: {self.offset}")

        # If no persisted offset, consume existing updates to skip history
        if self.offset == 0:
            print("[listener] No persisted offset, consuming history...")
            initial_updates = self._get_updates()
            if initial_updates:
                self.offset = initial_updates[-1]["update_id"] + 1
                self._save_offset()
                print(f"[listener] Skipped {len(initial_updates)} updates, offset={self.offset}")

        while self.running:
            updates = self._get_updates()

            for update in updates:
                # Always advance offset FIRST (even if we skip the message)
                self.offset = update["update_id"] + 1
                self._save_offset()

                if self._is_relevant(update):
                    self.process_update(update)

                    if self.once:
                        print("[listener] --once mode, exiting")
                        return

            if not updates:
                time.sleep(3)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Agent Teams Telegram Listener")
    parser.add_argument("--once", action="store_true", help="Process one message and exit")
    parser.add_argument("--dry-run", action="store_true", help="Print instead of sending to Telegram")
    parser.add_argument("--config", default="config.json", help="Config file path")
    parser.add_argument("--db", default="data/agent_teams.db", help="Database file path")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.db) or ".", exist_ok=True)

    # Single instance lock
    os.makedirs(os.path.dirname(LOCK_FILE), exist_ok=True)
    lock_fd = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("[listener] Another instance is already running, exiting.")
        sys.exit(1)

    listener = TelegramListener(
        config_path=args.config,
        db_path=args.db,
        dry_run=args.dry_run,
        once=args.once,
    )
    try:
        listener.run()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        listener._save_offset()
        lock_fd.close()
        print("[listener] Exited cleanly.")


if __name__ == "__main__":
    main()
