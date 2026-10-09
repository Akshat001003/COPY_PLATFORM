import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app.services import jev_service


class JevSettingsTests(unittest.TestCase):
    def test_reads_batch_mode_and_batch_size(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings_file = Path(directory) / "settings.txt"
            settings_file.write_text(
                "mode=batch\nbatch_size=16\n",
                encoding="utf-8",
            )
            with patch.object(jev_service, "SETTINGS_FILE", settings_file):
                self.assertEqual(
                    jev_service.get_jev_settings(),
                    {"mode": "batch", "batch_size": 16},
                )

    def test_rejects_batch_size_above_supported_limit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings_file = Path(directory) / "settings.txt"
            settings_file.write_text(
                "mode=batch\nbatch_size=65\n",
                encoding="utf-8",
            )
            with patch.object(jev_service, "SETTINGS_FILE", settings_file):
                with self.assertRaisesRegex(ValueError, "from 1 to 64"):
                    jev_service.get_jev_settings()


class JevBatchRequestTests(unittest.TestCase):
    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}, clear=True)
    @patch("app.services.jev_service.requests.post")
    def test_sends_one_independent_question_per_guardrail(
        self,
        post: Mock,
    ) -> None:
        post.return_value = Mock(
            json=lambda: {
                "answers": {
                    "guardrail_0": {
                        "choice": "Relevant",
                        "confidence": 0.94,
                        "probabilities": {"Relevant": 0.94},
                    },
                    "guardrail_1": {
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

        request_payload = post.call_args.kwargs["json"]
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
        self.assertEqual(
            result["answers"]["guardrail_0"]["choice"],
            "Relevant",
        )
        self.assertEqual(result["usage"]["input_tokens"], 120)

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}, clear=True)
    @patch("app.services.jev_service.requests.post")
    def test_metadata_is_sent_as_three_choice_questions_in_one_request(
        self,
        post: Mock,
    ) -> None:
        post.return_value = Mock(
            json=lambda: {
                "answers": {
                    "brand": {"choice": "Jardiance"},
                    "market": {"choice": "Canada"},
                    "asset_type": {"choice": "Email"},
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
        request_payload = post.call_args.kwargs["json"]
        self.assertEqual(request_payload["model"], jev_service.JEV_MODEL)
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
    def test_jev_auth_uses_openrouter_key_for_decisions_endpoint(self) -> None:
        self.assertEqual(
            jev_service._authorization_headers()["Authorization"],
            "Bearer openrouter-test-key",
        )

    @patch.dict(os.environ, {"JEV_API_KEY": "jev-test-key"}, clear=True)
    def test_jev_api_key_alone_is_not_used_for_openrouter_endpoint(self) -> None:
        with self.assertRaisesRegex(ValueError, "OPENROUTER_API_KEY"):
            jev_service._authorization_headers()


if __name__ == "__main__":
    unittest.main()
