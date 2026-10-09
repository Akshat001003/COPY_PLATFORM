def _jev_usage(item: dict) -> dict:
    usage = item.get("JEV_Usage", {}) or {}
    return {
        "input_tokens": usage.get("input_tokens", 0) or 0,
        "output_tokens": usage.get("output_tokens", 0) or 0,
        "cost": usage.get("cost", 0) or 0,
    }


def _llm_usage(item: dict) -> dict:
    usage = item.get("LLM_Usage", {}) or {}
    return {
        "input_tokens": usage.get("prompt_tokens", 0) or 0,
        "output_tokens": usage.get("completion_tokens", 0) or 0,
        "cost": usage.get("cost", 0) or 0,
    }


def compare_classifications(jev_results: list, llm_results: list) -> dict:
    """
    Matches jev_results and llm_results by GuardrailId and compares the
    selected category from each engine. Guardrails present on only one
    side are skipped, not treated as errors.
    """

    jev_map = {item["GuardrailId"]: item for item in jev_results}
    llm_map = {item["GuardrailId"]: item for item in llm_results}

    shared_ids = [gid for gid in jev_map if gid in llm_map]

    comparisons = []
    agreements = 0

    for guardrail_id in shared_ids:
        jev_item = jev_map[guardrail_id]
        llm_item = llm_map[guardrail_id]

        jev_category = (jev_item.get("JEV_Category") or "").strip()
        llm_category = (llm_item.get("LLM_Category") or "").strip()

        agreement = jev_category.lower() == llm_category.lower()
        if agreement:
            agreements += 1

        jev_usage = _jev_usage(jev_item)
        llm_usage = _llm_usage(llm_item)

        comparisons.append({
            "GuardrailId": guardrail_id,
            "ShortRule": jev_item.get("ShortRule") or llm_item.get("ShortRule"),
            "JEV_Category": jev_category,
            "LLM_Category": llm_category,
            "agreement": agreement,
            "JEV_Confidence": jev_item.get("JEV_Confidence"),
            "JEV_Input_Tokens": jev_usage["input_tokens"],
            "JEV_Output_Tokens": jev_usage["output_tokens"],
            "JEV_Cost": jev_usage["cost"],
            "LLM_Input_Tokens": llm_usage["input_tokens"],
            "LLM_Output_Tokens": llm_usage["output_tokens"],
            "LLM_Cost": llm_usage["cost"],
        })

    total_compared = len(comparisons)
    disagreements = total_compared - agreements
    agreement_percentage = (
        round((agreements / total_compared) * 100, 2)
        if total_compared > 0
        else 0
    )

    return {
        "total_compared": total_compared,
        "agreements": agreements,
        "disagreements": disagreements,
        "agreement_percentage": agreement_percentage,
        "comparisons": comparisons,
    }
