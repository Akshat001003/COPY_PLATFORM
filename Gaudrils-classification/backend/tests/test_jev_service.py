import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app.services import jev_service


class JevSettingsTests(unittest.TestCase):
    def test_reads_batch_size_without_a_run_mode_setting(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings_file = Path(directory) / "settings.txt"
            settings_file.write_text("batch_size=16\n", encoding="utf-8")
            with patch.object(jev_service, "SETTINGS_FILE", settings_file):
                self.assertEqual(
                    jev_service.get_jev_settings(),
                    {"batch_size": 16},
                )

    def test_rejects_batch_size_above_supported_limit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings_file = Path(directory) / "settings.txt"
            settings_file.write_text("batch_size=65\n", encoding="utf-8")
            with patch.object(jev_service, "SETTINGS_FILE", settings_file):
                with self.assertRaisesRegex(ValueError, "from 1 to 64"):
                    jev_service.get_jev_settings()


class JevRequestTests(unittest.TestCase):
    @patch.dict(os.environ, {"JEV_API_KEY": "jev-test-key"}, clear=True)
    @patch("app.services.jev_service.requests.post")
    def test_single_guardrail_request_uses_direct_typesafe_api(
        self,
        post: Mock,
    ) -> None:
        post.return_value = Mock(
            json=lambda: {
                "answers": {
                    "category": {
                        "type": "choice",
                        "choice": "Relevant",
                        "confidence": 0.94,
                    },
                },
                "usage": {},
            },
            raise_for_status=Mock(),
        )

        result = jev_service.classify_guardrail(
            "Example guardrail",
            {"Relevant": "Related to the topic"},
        )

        self.assertEqual(post.call_args.args[0], jev_service.JEV_API_URL)
        self.assertEqual(post.call_args.kwargs["json"]["model"], "jev-1.13.0")
        self.assertEqual(post.call_args.kwargs["json"]["state"], "Example guardrail")
        self.assertEqual(result["category"], "Relevant")

    @patch.dict(os.environ, {"JEV_API_KEY": "jev-test-key"}, clear=True)
    @patch("app.services.jev_service.requests.post")
    def test_sends_one_typed_question_per_guardrail_to_typesafe(
        self,
        post: Mock,
    ) -> None:
        post.return_value = Mock(
            json=lambda: {
                "answers": {
                    "guardrail_0": {
                        "type": "choice",
                        "choice": "Relevant",
                        "confidence": 0.94,
                        "probabilities": {"Relevant": 0.94},
                    },
                    "guardrail_1": {
                        "type": "choice",
                        "choice": "Not relevant",
                        "confidence": 0.89,
                        "probabilities": {"Not relevant": 0.89},
                    },
                },
                "usage": {"input_tokens": 120, "output_tokens": 2, "cost": 0.001},
            },
            raise_for_status=Mock(),
        )

        result = jev_service.classify_guardrails_batch(
            [
                {
                    "question_id": "guardrail_0",
                    "guardrail_id": "A",
                    "text": "First guardrail",
                },
                {
                    "question_id": "guardrail_1",
                    "guardrail_id": "B",
                    "text": "Second guardrail",
                },
            ],
            {"Relevant": "Related to the topic", "Not relevant": "Unrelated"},
            "audience=HCP",
        )

        self.assertEqual(post.call_args.args[0], jev_service.JEV_API_URL)
        self.assertEqual(
            post.call_args.kwargs["headers"]["Authorization"],
            "Bearer jev-test-key",
        )
        request_payload = post.call_args.kwargs["json"]
        self.assertEqual(request_payload["model"], "jev-1.13.0")
        self.assertEqual(len(request_payload["questions"]), 2)
        self.assertIn(
            "guardrail_0",
            request_payload["questions"]["guardrail_0"]["instructions"],
        )
        self.assertIn(
            "guardrail_1",
            request_payload["questions"]["guardrail_1"]["instructions"],
        )
        self.assertEqual(request_payload["state"]["context"], "audience=HCP")
        self.assertEqual(
            request_payload["state"]["guardrails"][0]["text"],
            "First guardrail",
        )
        self.assertEqual(result["answers"]["guardrail_0"]["choice"], "Relevant")
        self.assertEqual(result["usage"]["input_tokens"], 120)

    @patch.dict(os.environ, {"JEV_API_KEY": "jev-test-key"}, clear=True)
    @patch("app.services.jev_service.requests.post")
    def test_metadata_uses_the_same_typesafe_endpoint_and_model(
        self,
        post: Mock,
    ) -> None:
        post.return_value = Mock(
            json=lambda: {
                "answers": {
                    "brand": {"type": "choice", "choice": "Jardiance"},
                    "market": {"type": "choice", "choice": "Canada"},
                    "asset_type": {"type": "choice", "choice": "Email"},
                },
                "usage": {"input_tokens": 80, "output_tokens": 6},
            },
            raise_for_status=Mock(),
        )

        result = jev_service.detect_metadata_batch(
            [{"label": "campaign.xlsx", "text": "Jardiance email in Canada"}],
            {
                "brand": {"Jardiance": "Appears in campaign.xlsx"},
                "market": {"Canada": "Appears in campaign.xlsx"},
                "asset_type": {"Email": "Appears in campaign.xlsx"},
            },
        )

        self.assertEqual(post.call_count, 1)
        self.assertEqual(post.call_args.args[0], jev_service.JEV_API_URL)
        self.assertEqual(
            post.call_args.kwargs["headers"]["Authorization"],
            "Bearer jev-test-key",
        )
        request_payload = post.call_args.kwargs["json"]
        self.assertEqual(request_payload["model"], "jev-1.13.0")
        self.assertEqual(set(request_payload["questions"]), {
            "brand", "market", "asset_type",
        })
        self.assertTrue(
            all(
                question["type"] == "choice"
                for question in request_payload["questions"].values()
            )
        )
        self.assertEqual(
            request_payload["questions"]["brand"]["criteria"]["No brand found"],
            "No clear evidence for this field.",
        )
        self.assertEqual(result["answers"]["market"]["choice"], "Canada")
        self.assertEqual(result["usage"]["input_tokens"], 80)

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "openrouter-test-key"}, clear=True)
    def test_jev_requires_its_own_typesafe_api_key(self) -> None:
        with self.assertRaisesRegex(ValueError, "JEV_API_KEY"):
            jev_service._authorization_headers()


if __name__ == "__main__":
    unittest.main()
