import unittest

from app.main import app


class FrontendCorsTests(unittest.IsolatedAsyncioTestCase):
    async def test_local_frontend_origins_can_read_api_responses(self) -> None:
        for origin in (
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ):
            with self.subTest(origin=origin):
                messages = []

                async def receive():
                    return {"type": "http.request", "body": b"", "more_body": False}

                async def send(message):
                    messages.append(message)

                await app(
                    {
                        "type": "http",
                        "asgi": {"version": "3.0"},
                        "http_version": "1.1",
                        "method": "OPTIONS",
                        "scheme": "http",
                        "path": "/api/models",
                        "raw_path": b"/api/models",
                        "query_string": b"",
                        "root_path": "",
                        "headers": [
                            (b"origin", origin.encode()),
                            (b"access-control-request-method", b"GET"),
                        ],
                        "client": ("127.0.0.1", 1234),
                        "server": ("127.0.0.1", 8000),
                    },
                    receive,
                    send,
                )

                response_headers = dict(messages[0]["headers"])
                self.assertEqual(
                    response_headers[b"access-control-allow-origin"].decode(),
                    origin
                )


if __name__ == "__main__":
    unittest.main()
