from unittest.mock import patch, MagicMock
from gateway_client import GatewayClient


def test_call_success():
    client = GatewayClient("http://localhost:18789", "fake-token", "kimi-coding/k2p5")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "id": "resp_123",
        "status": "completed",
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "Hello world"}]
            }
        ],
        "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
    }

    with patch("gateway_client.requests.post", return_value=mock_resp) as mock_post:
        result = client.call("You are a coder", "Write hello world")
        assert result["text"] == "Hello world"
        assert result["tokens"] == 15
        assert result["status"] == "completed"

        call_args = mock_post.call_args
        body = call_args[1]["json"]
        assert body["instructions"] == "You are a coder"
        assert body["input"][0]["content"] == "Write hello world"


def test_call_failure():
    client = GatewayClient("http://localhost:18789", "fake-token", "kimi-coding/k2p5")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "id": "resp_456",
        "status": "failed",
        "output": [],
        "usage": {"input_tokens": 10, "output_tokens": 0, "total_tokens": 10}
    }

    with patch("gateway_client.requests.post", return_value=mock_resp):
        result = client.call("system", "task")
        assert result["status"] == "failed"
        assert result["text"] == ""


def test_call_timeout():
    client = GatewayClient("http://localhost:18789", "fake-token", "kimi-coding/k2p5", timeout=5)

    import requests
    with patch("gateway_client.requests.post", side_effect=requests.Timeout("timeout")):
        result = client.call("system", "task")
        assert result["status"] == "timeout"
        assert result["text"] == ""


if __name__ == "__main__":
    test_call_success()
    test_call_failure()
    test_call_timeout()
    print("All gateway_client tests passed")
