import time
import requests


class GatewayClient:
    def __init__(self, url, token, model, timeout=120):
        self.url = url.rstrip("/")
        self.token = token
        self.model = model
        self.timeout = timeout

    def call(self, system_prompt, user_message):
        """Call OpenResponses API. Returns dict with text, tokens, status, duration_ms."""
        start = time.time()

        try:
            resp = requests.post(
                f"{self.url}/v1/responses",
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "stream": False,
                    "instructions": system_prompt,
                    "input": [
                        {
                            "type": "message",
                            "role": "user",
                            "content": user_message,
                        }
                    ],
                    "max_output_tokens": 32768,
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.Timeout:
            return {"text": "", "tokens": 0, "status": "timeout",
                    "duration_ms": int((time.time() - start) * 1000)}
        except requests.RequestException as e:
            return {"text": "", "tokens": 0, "status": "error",
                    "duration_ms": int((time.time() - start) * 1000), "error": str(e)}

        duration_ms = int((time.time() - start) * 1000)
        status = data.get("status", "unknown")
        tokens = data.get("usage", {}).get("total_tokens", 0)

        text = ""
        for output_item in data.get("output", []):
            if output_item.get("type") == "message":
                for part in output_item.get("content", []):
                    if part.get("type") == "output_text":
                        text += part.get("text", "")

        return {"text": text, "tokens": tokens, "status": status, "duration_ms": duration_ms}
