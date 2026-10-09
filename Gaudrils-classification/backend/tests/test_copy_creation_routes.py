import unittest
from io import BytesIO
from unittest.mock import patch

from fastapi import HTTPException
from starlette.datastructures import UploadFile

from app.api.routes import detect_copy_creation_metadata


class CopyCreationRouteTests(unittest.IsolatedAsyncioTestCase):
    async def test_requires_project_brief_and_actual_material(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            await detect_copy_creation_metadata(
                project_description="Project overview",
                actual_material_description="",
                reference_description="",
                project_files=[],
                actual_material_files=[],
                reference_files=[],
            )

        self.assertEqual(raised.exception.status_code, 400)
        self.assertIn("Actual Material", raised.exception.detail)

    async def test_accepts_text_and_optional_documents_and_returns_metadata(self) -> None:
        expected = {
            "metadata": {
                "brand": {"value": "Jardiance", "source": "Project Brief description"},
            },
            "classification_context": "Project and material context",
        }
        with patch(
            "app.api.routes.detect_copy_metadata",
            return_value=expected,
        ) as detect:
            result = await detect_copy_creation_metadata(
                project_description="Jardiance campaign",
                actual_material_description="Email invitation",
                reference_description="Style guide",
                project_files=[],
                actual_material_files=[],
                reference_files=[],
            )

        self.assertEqual(result, expected)
        self.assertEqual(len(detect.call_args.args[0]), 3)
        self.assertEqual(
            detect.call_args.args[0][2],
            {"label": "Reference Material description", "text": "Style guide"},
        )

    async def test_directly_labeled_descriptions_return_without_jev_call(self) -> None:
        result = await detect_copy_creation_metadata(
            project_description="brand: mankind, asset: email",
            actual_material_description="market : india",
            reference_description="",
            project_files=[],
            actual_material_files=[],
            reference_files=[],
        )

        self.assertEqual(
            result["metadata"],
            {
                "brand": {
                    "value": "mankind",
                    "source": "Project Brief description",
                },
                "market": {
                    "value": "India",
                    "source": "Actual Material description",
                },
                "asset_type": {
                    "value": "Email",
                    "source": "Project Brief description",
                },
            },
        )

    async def test_xlsx_uses_only_its_filename_and_returns_warning(self) -> None:
        spreadsheet = UploadFile(
            filename="guardrails.xlsx",
            file=BytesIO(b"not parsed as a workbook"),
        )

        with patch(
            "app.api.routes.extract_document_text",
            side_effect=AssertionError("XLSX contents should not be parsed"),
        ) as extract:
            result = await detect_copy_creation_metadata(
                project_description="brand: mankind, asset: email",
                actual_material_description="market: india",
                reference_description="",
                project_files=[spreadsheet],
                actual_material_files=[],
                reference_files=[],
            )

        extract.assert_not_called()
        self.assertEqual(result["metadata"]["market"]["value"], "India")
        self.assertEqual(
            result["metadata"]["market"]["source"],
            "Actual Material description",
        )
        self.assertEqual(
            result["warnings"],
            [
                "Project Brief / guardrails.xlsx: only the spreadsheet filename "
                "is included; its contents are not analyzed."
            ],
        )
        self.assertIn("Spreadsheet filename: guardrails.xlsx", result["classification_context"])
        self.assertNotIn("not parsed as a workbook", result["classification_context"])

    @patch("app.services.copy_creation_service.detect_metadata_batch")
    async def test_xlsx_filename_sets_brand_and_unresolved_fields_use_defaults(
        self,
        detect_batch,
    ) -> None:
        detect_batch.return_value = {
            "answers": {"brand": {"choice": "Jardiance"}},
            "usage": {},
        }
        spreadsheet = UploadFile(
            filename="Jardiance_Guardrails_Relevance.xlsx",
            file=BytesIO(b"workbook content is not read"),
        )

        result = await detect_copy_creation_metadata(
            project_description="",
            actual_material_description="generic copy",
            reference_description="",
            project_files=[spreadsheet],
            actual_material_files=[],
            reference_files=[],
        )

        self.assertEqual(
            result["metadata"],
            {
                "brand": {
                    "value": "Jardiance",
                    "source": "Project Brief / Jardiance_Guardrails_Relevance.xlsx",
                },
                "market": {"value": "Canada", "source": "Default value"},
                "asset_type": {"value": "Email", "source": "Default value"},
            },
        )
        self.assertEqual(set(detect_batch.call_args.args[1]), {"brand"})

    async def test_rejects_unsupported_upload_extension(self) -> None:
        unsupported_file = UploadFile(
            filename="content.txt",
            file=BytesIO(b"not supported"),
        )
        with self.assertRaises(HTTPException) as raised:
            await detect_copy_creation_metadata(
                project_description="Project overview",
                actual_material_description="",
                reference_description="",
                project_files=[],
                actual_material_files=[unsupported_file],
                reference_files=[],
            )

        self.assertEqual(raised.exception.status_code, 400)
        self.assertIn("PDF, DOCX, and XLSX", raised.exception.detail)


if __name__ == "__main__":
    unittest.main()
