"""Minimal Telegram agent scaffold.

This file provides a tiny polling-based Telegram agent you can run during
development. It is intentionally dependency-light (uses `requests`) and
demonstrates how to receive `/goal` messages and forward them to a callback
in your orchestrator.

Notes:
- For production use, prefer a webhook with Flask/FastAPI or use
  `python-telegram-bot` for robust polling/webhook handling.
- Configure TELEGRAM_BOT_TOKEN in your environment before running.
"""
import os
import time
import threading
import requests
import logging

logging.basicConfig(level=logging.INFO)


class TelegramAgent:
    def __init__(self, token=None, poll_interval=3, goal_callback=None):
        self.token = token or os.environ.get("TELEGRAM_BOT_TOKEN")
        if not self.token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN not set")
        self.base = f"https://api.telegram.org/bot{self.token}"
        self.poll_interval = poll_interval
        self.goal_callback = goal_callback
        self._running = False
        self._offset = None

    def start_polling(self):
        if self._running:
            return
        self._running = True
        t = threading.Thread(target=self._poll_loop, daemon=True)
        t.start()
        logging.info("TelegramAgent started polling")

    def stop(self):
        self._running = False

    def _poll_loop(self):
        while self._running:
            try:
                params = {"timeout": 10}
                if self._offset:
                    params["offset"] = self._offset
                resp = requests.get(self.base + "/getUpdates", params=params, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                for upd in data.get("result", []) or []:
                    self._offset = upd["update_id"] + 1
                    self._handle_update(upd)
            except Exception as e:
                logging.exception("Error while polling Telegram: %s", e)
                time.sleep(2)
            time.sleep(self.poll_interval)

    def _handle_update(self, upd: dict):
        msg = upd.get("message") or upd.get("edited_message")
        if not msg:
            return
        text = msg.get("text", "")
        chat_id = msg["chat"]["id"]
        logging.info("Received message from %s: %s", chat_id, text)

        # Simple command pattern: /goal <text>
        if text and text.strip().lower().startswith("/goal"):
            goal_text = text.strip()[len("/goal"):].strip()
            if not goal_text:
                self.send_message(chat_id, "Usage: /goal <your goal description>")
                return
            # Optionally call the orchestrator callback
            if self.goal_callback:
                try:
                    self.goal_callback(goal_text)
                    self.send_message(chat_id, f"Enqueued goal: {goal_text}")
                except Exception as e:
                    logging.exception("Goal callback failed: %s", e)
                    self.send_message(chat_id, f"Failed to enqueue goal: {e}")
            else:
                # No callback provided: echo the goal back
                self.send_message(chat_id, f"Received goal: {goal_text}")
        else:
            # Keep the agent simple: respond to /help or unknown messages
            if text and text.strip().lower().startswith("/help"):
                self.send_message(chat_id, "Send /goal <description> to create a new autonomous goal.")
            else:
                # Optionally ignore other messages to reduce noise
                logging.debug("Ignoring non-goal message")

    def send_message(self, chat_id: int, text: str):
        try:
            resp = requests.post(self.base + "/sendMessage", json={"chat_id": chat_id, "text": text}, timeout=15)
            resp.raise_for_status()
        except Exception:
            logging.exception("Failed to send message to %s", chat_id)


if __name__ == "__main__":
    # Example CLI usage: run the agent and print incoming goals.
    def example_callback(goal_text: str):
        # Replace this with a call into your orchestrator (e.g., enqueue/run goal)
        logging.info("example_callback got goal: %s", goal_text)

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Set TELEGRAM_BOT_TOKEN in your environment to run the example.")
    else:
        agent = TelegramAgent(token=token, goal_callback=example_callback)
        agent.start_polling()
        print("Polling started. Send /goal messages to the bot.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            agent.stop()
            print("Stopped")
