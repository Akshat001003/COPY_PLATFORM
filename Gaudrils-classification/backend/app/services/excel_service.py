import pandas as pd
import os
from pathlib import Path



def inspect_excel(file_path: str) -> dict:
    """
    Read an Excel workbook and return basic information
    about its sheets, rows, and columns.
    """

    excel_file = pd.ExcelFile(file_path)

    sheets = {}

    for sheet_name in excel_file.sheet_names:
        df = pd.read_excel(
            file_path,
            sheet_name=sheet_name
        )

        sheets[sheet_name] = {
            "rows": len(df),
            "columns": list(df.columns)
        }

    return {
        "filename": Path(file_path).name,
        "sheet_count": len(excel_file.sheet_names),
        "sheets": sheets
    }


def get_guardrails(file_path: str, limit: int = 5) -> list:
    df = pd.read_excel(file_path, sheet_name="Guardrails")

    records = df.head(limit).fillna("").to_dict(orient="records")

    return records

def save_jev_results(
    file_path: str,
    results: list,
    output_dir: str = "output"
) -> str:

    df = pd.read_excel(
        file_path,
        sheet_name="Guardrails"
    )

    result_map = {
        item["GuardrailId"]: item
        for item in results
    }

    df["JEV_Category"] = df["GuardrailId"].map(
        lambda x: result_map.get(x, {}).get("JEV_Category", "")
    )

    df["JEV_Confidence"] = df["GuardrailId"].map(
        lambda x: result_map.get(x, {}).get("JEV_Confidence", "")
    )

    df["JEV_Probabilities"] = df["GuardrailId"].map(
        lambda x: result_map.get(x, {}).get("JEV_Probabilities", "")
    )

    df["JEV_Input_Tokens"] = df["GuardrailId"].map(
        lambda x: result_map.get(x, {}).get(
            "JEV_Usage", {}
        ).get("input_tokens", "")
    )

    df["JEV_Output_Tokens"] = df["GuardrailId"].map(
        lambda x: result_map.get(x, {}).get(
            "JEV_Usage", {}
        ).get("output_tokens", "")
    )

    df["JEV_Cost"] = df["GuardrailId"].map(
        lambda x: result_map.get(x, {}).get(
            "JEV_Usage", {}
        ).get("cost", "")
    )

    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(
        output_dir,
        "jev_classification_results.xlsx"
    )

    df.to_excel(
        output_path,
        sheet_name="JEV Results",
        index=False
    )

    return output_path


def save_comparison_results(
    file_path: str,
    comparison_result: dict,
    model: str,
    output_dir: str = "output",
    file_id: str = "comparison"
) -> str:

    df = pd.read_excel(
        file_path,
        sheet_name="Guardrails"
    )

    comparison_map = {
        item["GuardrailId"]: item
        for item in comparison_result.get("comparisons", [])
    }

    df["JEV_Category"] = df["GuardrailId"].map(
        lambda x: comparison_map.get(x, {}).get("JEV_Category", "")
    )

    df["JEV_Confidence"] = df["GuardrailId"].map(
        lambda x: comparison_map.get(x, {}).get("JEV_Confidence", "")
    )

    df["LLM_Model"] = df["GuardrailId"].map(
        lambda x: model if x in comparison_map else ""
    )

    df["LLM_Category"] = df["GuardrailId"].map(
        lambda x: comparison_map.get(x, {}).get("LLM_Category", "")
    )

    df["Agreement"] = df["GuardrailId"].map(
        lambda x: comparison_map.get(x, {}).get("agreement", "")
    )

    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(
        output_dir,
        f"{file_id}_comparison.xlsx"
    )

    df.to_excel(
        output_path,
        sheet_name="Comparison Results",
        index=False
    )

    return output_path