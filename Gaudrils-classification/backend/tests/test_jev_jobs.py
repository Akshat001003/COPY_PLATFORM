import unittest
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd
from fastapi import BackgroundTasks

from app.api import routes
from app.models.schemas import FullClassificationRequest, LLMFullClassificationRequest


class JevBackgroundJobTests(unittest.TestCase):
    def setUp(self) -> None:
        self.job_id = "test-job"
        with routes._jev_jobs_lock:
            routes._jev_jobs[self.job_id] = {
                "job_id": self.job_id,
                "file_id": "worker-test-file",
                "status": "queued",
            }
        with routes._llm_jobs_lock:
            routes._llm_jobs[self.job_id] = {
                "job_id": self.job_id,
                "file_id": "worker-test-file",
                "status": "queued",
            }

    def tearDown(self) -> None:
        with routes._jev_jobs_lock:
            for job_id, job in list(routes._jev_jobs.items()):
                if job_id == self.job_id or job.get("file_id") in {
                    "test-file",
                    "worker-test-file",
                }:
                    del routes._jev_jobs[job_id]
        with routes._llm_jobs_lock:
            for job_id, job in list(routes._llm_jobs.items()):
                if job_id == self.job_id or job.get("file_id") in {
                    "test-file",
                    "worker-test-file",
                }:
                    del routes._llm_jobs[job_id]

    @patch("app.api.routes.save_jev_results", return_value="output.xlsx")
    @patch("app.api.routes.classify_guardrails_batch")
    @patch("app.api.routes.pd.read_excel")
    def test_batch_job_maps_each_answer_to_its_guardrail(
        self,
        read_excel: Mock,
        classify_batch: Mock,
        _save_results: Mock,
    ) -> None:
        read_excel.return_value = pd.DataFrame([
            {"GuardrailId": "A", "ShortRule": "Rule A"},
            {"GuardrailId": "EMPTY", "ShortRule": None},
            {"GuardrailId": "B", "ShortRule": "Rule B"},
            {"GuardrailId": "C", "ShortRule": "Rule C"},
        ])

        def batch_response(guardrails, categories, context):
            self.assertEqual(context, "")
            self.assertEqual(set(categories), {"A", "B", "C"})
            return {
                "answers": {
                    item["question_id"]: {
                        "choice": item["guardrail_id"],
                        "confidence": 0.9,
                        "probabilities": {item["guardrail_id"]: 0.9},
                    }
                    for item in guardrails
                },
                "usage": {
                    "input_tokens": len(guardrails) * 20,
                    "output_tokens": len(guardrails),
                    "cost": len(guardrails) * 0.001,
                },
            }

        classify_batch.side_effect = batch_response

        routes._run_full_jev_job(
            self.job_id,
            "workbook.xlsx",
            {"A": "Category A", "B": "Category B", "C": "Category C"},
            "",
            "batch",
            2,
            0,
        )

        job = routes._jev_jobs[self.job_id]
        self.assertEqual(job["status"], "done")
        self.assertEqual(
            [item["GuardrailId"] for item in job["results"]],
            ["A", "B", "C"],
        )
        self.assertEqual(
            [item["JEV_Category"] for item in job["results"]],
            ["A", "B", "C"],
        )
        self.assertEqual(job["usage"]["input_tokens"], 60)
        self.assertEqual(job["failed"], 0)
        self.assertEqual(job["completed"], 4)
        self.assertEqual(classify_batch.call_count, 2)
        _save_results.assert_called_once()

    @patch("app.api.routes.save_jev_results", return_value="output.xlsx")
    @patch("app.api.routes.classify_guardrail")
    @patch("app.api.routes.pd.read_excel")
    def test_normal_job_keeps_one_request_per_guardrail(
        self,
        read_excel: Mock,
        classify_one: Mock,
        _save_results: Mock,
    ) -> None:
        read_excel.return_value = pd.DataFrame([
            {"GuardrailId": "A", "ShortRule": "Rule A"},
            {"GuardrailId": "B", "ShortRule": "Rule B"},
        ])
        classify_one.side_effect = [
            {
                "category": "Category A",
                "confidence": 0.9,
                "probabilities": {"Category A": 0.9},
                "usage": {"input_tokens": 10},
            },
            {
                "category": "Category B",
                "confidence": 0.8,
                "probabilities": {"Category B": 0.8},
                "usage": {"input_tokens": 12},
            },
        ]

        routes._run_full_jev_job(
            self.job_id,
            "workbook.xlsx",
            {"Category A": "A", "Category B": "B"},
            "",
            "normal",
            20,
            0,
        )

        job = routes._jev_jobs[self.job_id]
        self.assertEqual(job["status"], "done")
        self.assertEqual(job["processed"], 2)
        self.assertEqual(job["usage"]["input_tokens"], 22)
        self.assertEqual(classify_one.call_count, 2)
        _save_results.assert_called_once()

    @patch("app.api.routes.save_jev_results", return_value="output.xlsx")
    @patch("app.api.routes.classify_guardrails_batch")
    @patch("app.api.routes.pd.read_excel")
    @patch("app.api.routes.get_jev_settings")
    def test_full_run_endpoint_submits_and_reports_background_job(
        self,
        get_settings: Mock,
        read_excel: Mock,
        classify_batch: Mock,
        _save_results: Mock,
    ) -> None:
        get_settings.return_value = {"mode": "batch", "batch_size": 2}
        read_excel.return_value = pd.DataFrame([
            {"GuardrailId": "A", "ShortRule": "Rule A"},
        ])
        classify_batch.return_value = {
            "answers": {
                "guardrail_0": {
                    "choice": "Relevant",
                    "confidence": 0.9,
                    "probabilities": {"Relevant": 0.9},
                },
            },
            "usage": {"input_tokens": 20, "output_tokens": 1, "cost": 0.001},
        }

        with tempfile.TemporaryDirectory() as directory:
            workbook = Path(directory) / "test-file.xlsx"
            workbook.touch()
            with patch.object(routes, "UPLOAD_DIR", directory):
                background_tasks = BackgroundTasks()
                submitted = asyncio.run(
                    routes.classify_all(
                        "test-file",
                        FullClassificationRequest(
                            categories={"Relevant": "Related"},
                        ),
                        background_tasks,
                    )
                )
                self.assertEqual(submitted["status"], "queued")
                self.assertEqual(submitted["mode"], "batch")
                asyncio.run(background_tasks())
                status = asyncio.run(
                    routes.get_jev_run_status("test-file", submitted["job_id"])
                )

        self.assertEqual(status["status"], "done")
        self.assertEqual(status["results"][0]["GuardrailId"], "A")
        _save_results.assert_called_once()

    @patch("app.api.routes.save_jev_results", return_value="output.xlsx")
    @patch("app.api.routes.classify_guardrails_batch")
    @patch("app.api.routes.classify_guardrail")
    @patch("app.api.routes.pd.read_excel")
    @patch("app.api.routes.get_jev_settings")
    def test_full_run_mode_overrides_settings_mode(
        self,
        get_settings: Mock,
        read_excel: Mock,
        classify_one: Mock,
        classify_batch: Mock,
        _save_results: Mock,
    ) -> None:
        get_settings.return_value = {"mode": "batch", "batch_size": 2}
        read_excel.return_value = pd.DataFrame([
            {"GuardrailId": "A", "ShortRule": "Rule A"},
        ])
        classify_one.return_value = {
            "category": "Relevant",
            "confidence": 0.9,
            "probabilities": {"Relevant": 0.9},
            "usage": {"input_tokens": 10},
        }

        with tempfile.TemporaryDirectory() as directory:
            workbook = Path(directory) / "test-file.xlsx"
            workbook.touch()
            with patch.object(routes, "UPLOAD_DIR", directory):
                background_tasks = BackgroundTasks()
                submitted = asyncio.run(
                    routes.classify_all(
                        "test-file",
                        FullClassificationRequest(
                            categories={"Relevant": "Related"},
                            mode="normal",
                        ),
                        background_tasks,
                    )
                )
                asyncio.run(background_tasks())

        self.assertEqual(submitted["mode"], "normal")
        self.assertEqual(submitted["batch_size"], 2)
        classify_one.assert_called_once()
        classify_batch.assert_not_called()

    @patch("app.api.routes.classify_with_llm")
    @patch("app.api.routes.pd.read_excel")
    def test_custom_llm_job_processes_only_requested_rows(
        self,
        read_excel: Mock,
        classify_llm: Mock,
    ) -> None:
        read_excel.return_value = pd.DataFrame([
            {"GuardrailId": "A", "ShortRule": "Rule A"},
            {"GuardrailId": "B", "ShortRule": "Rule B"},
            {"GuardrailId": "C", "ShortRule": "Rule C"},
        ])
        classify_llm.side_effect = [
            {
                "category": "Approved",
                "answer": "Category: Approved\nReason: Meets criteria.",
                "usage": {"prompt_tokens": 10, "completion_tokens": 3, "cost": 0.001},
            },
            {
                "category": "Rejected",
                "answer": "Category: Rejected\nReason: Fails criteria.",
                "usage": {"prompt_tokens": 12, "completion_tokens": 4, "cost": 0.002},
            },
        ]

        routes._run_full_llm_job(
            self.job_id,
            "workbook.xlsx",
            {"Approved": "Meets requirements", "Rejected": "Does not meet"},
            "test-model",
            "Classify",
            "",
            2,
        )

        job = routes._llm_jobs[self.job_id]
        self.assertEqual(job["status"], "done")
        self.assertEqual(job["dataset_rows"], 3)
        self.assertEqual(job["total_rows"], 2)
        self.assertEqual(
            [item["GuardrailId"] for item in job["results"]],
            ["A", "B"],
        )
        self.assertEqual(
            job["results"][0]["LLM_Answer"],
            "Category: Approved\nReason: Meets criteria.",
        )
        self.assertEqual(job["usage"]["input_tokens"], 22)
        self.assertEqual(classify_llm.call_count, 2)

    @patch(
        "app.api.routes.classify_with_llm",
        side_effect=ValueError("OpenRouter error 400: model access denied"),
    )
    @patch("app.api.routes.pd.read_excel")
    def test_llm_job_retains_provider_error_for_dashboard(
        self,
        read_excel: Mock,
        _classify_llm: Mock,
    ) -> None:
        read_excel.return_value = pd.DataFrame([
            {"GuardrailId": "A", "ShortRule": "Rule A"},
        ])

        routes._run_full_llm_job(
            self.job_id,
            "workbook.xlsx",
            {"Approved": "Meets requirements"},
            "anthropic/claude-sonnet-5",
            "Classify this rule",
            "",
            0,
        )

        job = routes._llm_jobs[self.job_id]
        self.assertEqual(job["status"], "done")
        self.assertEqual(job["failed"], 1)
        self.assertEqual(
            job["failures"][0]["error"],
            "OpenRouter error 400: model access denied",
        )

    @patch("app.api.routes.classify_with_llm")
    @patch("app.api.routes.pd.read_excel")
    def test_llm_run_endpoint_submits_custom_background_job(
        self,
        read_excel: Mock,
        classify_llm: Mock,
    ) -> None:
        read_excel.return_value = pd.DataFrame([
            {"GuardrailId": "A", "ShortRule": "Rule A"},
            {"GuardrailId": "B", "ShortRule": "Rule B"},
        ])
        classify_llm.return_value = {
            "category": "Approved",
            "answer": "Category: Approved\nReason: Meets criteria.",
            "usage": {"prompt_tokens": 10, "completion_tokens": 3, "cost": 0.001},
        }

        with tempfile.TemporaryDirectory() as directory:
            workbook = Path(directory) / "llm-test-file.xlsx"
            workbook.touch()
            with patch.object(routes, "UPLOAD_DIR", directory):
                background_tasks = BackgroundTasks()
                submitted = asyncio.run(
                    routes.classify_llm_all(
                        "llm-test-file",
                        LLMFullClassificationRequest(
                            categories={"Approved": "Meets requirements"},
                            model="test-model",
                            prompt="Classify",
                            limit=1,
                        ),
                        background_tasks,
                    )
                )
                self.assertEqual(submitted["status"], "queued")
                asyncio.run(background_tasks())
                status = asyncio.run(
                    routes.get_llm_run_status(
                        "llm-test-file",
                        submitted["job_id"],
                    )
                )

        self.assertEqual(status["status"], "done")
        self.assertEqual(status["total_rows"], 1)
        self.assertEqual(status["results"][0]["GuardrailId"], "A")
        self.assertEqual(classify_llm.call_count, 1)


if __name__ == "__main__":
    unittest.main()
