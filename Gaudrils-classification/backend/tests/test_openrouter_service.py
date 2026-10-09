import os
import unittest
from unittest.mock import Mock, patch

from app.services.openrouter_service import classify_with_llm


class LlmCategoryParsingTests(unittest.TestCase):
    @patch("app.services.openrouter_service.requests.post")
    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"})
    def test_extracts_configured_category_and_preserves_answer(
        self,
        post: Mock,
    ) -> None:
        answer = "Category: approved\nReason: The rule meets requirements."
        response = Mock()
        response.ok = True
        response.json.return_value = {
            "choices": [{"message": {"content": answer}}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 5},
        }
        post.return_value = response

        result = classify_with_llm(
            "Example guardrail",
            {"Approved": "Meets requirements", "Rejected": "Does not meet"},
            "test-model",
            "Classify this rule",
        )

        self.assertEqual(result["category"], "Approved")
        self.assertEqual(
            result["answer"],
            "Category: Approved\nReason: The rule meets requirements.",
        )
        self.assertEqual(result["usage"]["prompt_tokens"], 12)
        self.assertEqual(
            post.call_args.kwargs["json"]["max_tokens"],
            512,
        )

    @patch("app.services.openrouter_service.requests.post")
    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"})
    def test_extracts_and_sanitizes_category_after_model_preamble(
        self,
        post: Mock,
    ) -> None:
        response = Mock()
        response.ok = True
        response.json.return_value = {
            "choices": [{
                "message": {
                    "content": (
                        "Here's a thinking process:\n"
                        "Long model preamble.\n\n"
                        "Category: Rejected\n"
                        "Reason: It violates the privacy requirement.\n"
                        "Additional unneeded text."
                    )
                }
            }],
            "usage": {},
        }
        post.return_value = response

        result = classify_with_llm(
            "Do not disclose private patient information.",
            {"Approved": "Meets requirements", "Rejected": "Violates requirements"},
            "test-model",
            "Choose a category and give one short reason.",
        )

        self.assertEqual(result["category"], "Rejected")
        self.assertEqual(
            result["answer"],
            "Category: Rejected\nReason: It violates the privacy requirement.",
        )

    @patch("app.services.openrouter_service.requests.post")
    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"})
    def test_free_model_uses_json_and_matches_category_with_description(
        self,
        post: Mock,
    ) -> None:
        response = Mock()
        response.ok = True
        response.json.return_value = {
            "choices": [{
                "message": {
                    "content": (
                        '{"category":"Privacy: Personal data protection",'
                        '"reason":"The rule protects private patient data."}'
                    )
                }
            }],
            "usage": {},
        }
        post.return_value = response

        result = classify_with_llm(
            "Never disclose patient data.",
            {"Privacy": "Personal data protection", "Other": "Other topics"},
            "nvidia/nemotron-3.5-lightning:free",
            "Classify the guardrail.",
        )

        payload = post.call_args.kwargs["json"]
        self.assertEqual(result["category"], "Privacy")
        self.assertEqual(
            result["answer"],
            "Category: Privacy\nReason: The rule protects private patient data.",
        )
        self.assertEqual(payload["response_format"], {"type": "json_object"})
        self.assertEqual(payload["reasoning"], {"effort": "none"})

    @patch("app.services.openrouter_service.requests.post")
    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"})
    def test_retries_without_temperature_when_provider_rejects_it(
        self,
        post: Mock,
    ) -> None:
        unsupported = Mock()
        unsupported.status_code = 400
        unsupported.text = '{"error":"temperature is not supported"}'
        accepted = Mock()
        accepted.ok = True
        accepted.json.return_value = {
            "choices": [{"message": {"content": "Category: Approved"}}],
            "usage": {},
        }
        post.side_effect = [unsupported, accepted]

        result = classify_with_llm(
            "Example guardrail",
            {"Approved": "Meets requirements"},
            "anthropic/claude-sonnet-5",
            "Classify this rule",
        )

        self.assertEqual(result["category"], "Approved")
        self.assertEqual(post.call_count, 2)
        self.assertEqual(post.call_args_list[0].kwargs["json"]["temperature"], 0)
        self.assertEqual(post.call_args_list[0].kwargs["json"]["max_tokens"], 512)
        self.assertNotIn("temperature", post.call_args_list[1].kwargs["json"])
        self.assertEqual(post.call_args_list[1].kwargs["json"]["max_tokens"], 512)


if __name__ == "__main__":
    unittest.main()
