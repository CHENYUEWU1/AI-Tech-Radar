from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from analyzers.schemas import AnalysisResult


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROMPT_PATH = PROJECT_ROOT / "prompts" / "ai_analysis.yaml"


def test_analysis_result_valid() -> None:
    result = AnalysisResult(
        importance=8,
        category="LLM",
        tags=["Agent", "MCP"],
        summary="OpenAI 发布了新的 Agent 框架。",
        impact="Agent 开发门槛降低。",
        action="关注后续 API 与生态进展。",
    )

    assert result.importance == 8
    assert result.category == "LLM"
    assert result.tags == ["Agent", "MCP"]
    assert result.to_dict()["summary"]


def test_importance_must_be_between_1_and_10() -> None:
    with pytest.raises(ValueError, match="1 and 10"):
        AnalysisResult(importance=0, category="LLM")
    with pytest.raises(ValueError, match="1 and 10"):
        AnalysisResult(importance=11, category="LLM")


def test_tags_must_be_non_empty_strings() -> None:
    with pytest.raises(ValueError, match="tags"):
        AnalysisResult(importance=5, category="LLM", tags=["Agent", ""])


def test_prompt_yaml_structure() -> None:
    with PROMPT_PATH.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    system_prompt = data["system_prompt"]
    assert system_prompt["role"] == "AI 科技分析师"
    assert {"LLM", "Agent", "RAG", "AI Infra", "GPU", "开源模型"} <= set(
        system_prompt["focus_areas"]
    )
    assert "不编造信息" in system_prompt["rules"]
    assert "importance 范围 1-10" in system_prompt["rules"]
    assert "user_prompt" in data
