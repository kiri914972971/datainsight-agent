"""Complete API-backed business insight generation for the EDA page."""

import json
from urllib.parse import urlparse

import pandas as pd
import requests

from src.exploration import (
    calculate_correlation_pairs,
    summarize_categorical_columns,
    summarize_numeric_columns,
)


AI_OUTPUT_TOKEN_LIMIT = 3000
MAX_CONTINUATIONS = 2


def build_analysis_payload(
    df: pd.DataFrame,
    numeric_columns: list[str],
    category_columns: list[str],
) -> dict:
    return {
        "data_shape": {"rows": len(df), "columns": len(df.columns)},
        "numeric_statistics": summarize_numeric_columns(df, numeric_columns).replace({float("nan"): None}).to_dict("records"),
        "categorical_statistics": summarize_categorical_columns(df, category_columns).to_dict("records"),
        "correlation_pairs": calculate_correlation_pairs(df, numeric_columns).to_dict("records"),
    }


def request_ai_insights(
    payload: dict,
    api_key: str,
    model: str = "gpt-5.4-mini",
    base_url: str = "https://api.openai.com/v1",
) -> str:
    prompt = f"""
你是一名资深业务数据分析师。请根据下面的探索性分析结果，用简体中文输出可直接展示给业务人员的分析。

要求：
1. 使用“关键发现”“业务含义”“建议进一步分析的问题”三个标题。
2. 重点解释数值分布、类别集中度和字段相关关系背后的业务含义。
3. 不要逐字段复述均值、偏度、峰度、频数等统计结果；只在支撑关键判断时引用少量必要数字。
4. 不要讨论数据质量评分、缺失值、重复值、异常值处理或数据修复。
5. 不要把相关性或高频直接表述为确定因果；信息不足时明确建议结合业务背景验证。
6. 忽略 Identifier 字段，不对工号、订单号、ID 等做数值含义分析。
7. 内容简洁，使用 Markdown 编号或列表，每个部分最多 5 点，不超过 900 字。
8. 必须完整输出“关键发现”“业务含义”“建议进一步分析的问题”三个部分，并确保最后一句完整结束，不要在句子中间停止。

探索性分析结果：
{json.dumps(payload, ensure_ascii=False, default=str)}
""".strip()
    data = _request_completion(prompt, api_key, model, base_url, timeout=90)
    text = _extract_text(data)
    continuation_count = 0
    while _is_truncated(data) and continuation_count < MAX_CONTINUATIONS:
        continuation_prompt = f"""
下面是一份被接口截断的数据分析报告。请从截断位置继续写完尚未完成的内容。

要求：
- 只输出续写内容，不要重复已经完成的段落。
- 补全当前未完成的句子，并完成尚未输出的“业务含义”或“建议进一步分析的问题”部分。
- 最后一句必须完整结束。
- 保持简体中文和 Markdown 列表格式。

已输出内容：
{text}
""".strip()
        data = _request_completion(continuation_prompt, api_key, model, base_url, timeout=90)
        text = _merge_continuation(text, _extract_text(data))
        continuation_count += 1
    if _is_truncated(data):
        raise ValueError("AI 接口连续截断输出，请重试或选择支持更长输出的模型。")
    return text


def _request_completion(
    prompt: str,
    api_key: str,
    model: str,
    base_url: str,
    timeout: int,
) -> dict:
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    root = base_url.rstrip("/")
    try:
        if _is_deepseek_url(root):
            response = requests.post(
                f"{root}/chat/completions",
                headers=headers,
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": AI_OUTPUT_TOKEN_LIMIT,
                },
                timeout=timeout,
            )
        else:
            response = requests.post(
                f"{root}/responses",
                headers=headers,
                json={"model": model, "input": prompt, "max_output_tokens": AI_OUTPUT_TOKEN_LIMIT},
                timeout=timeout,
            )
            if response.status_code in {400, 404, 405}:
                response = requests.post(
                    f"{root}/chat/completions",
                    headers=headers,
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": AI_OUTPUT_TOKEN_LIMIT,
                    },
                    timeout=timeout,
                )
    except requests.ConnectionError as exc:
        hostname = urlparse(root).hostname or root
        raise ValueError(
            f"无法连接 {hostname}。请检查代理/TUN 模式、防火墙，或在本机终端重新启动应用后再试。"
        ) from exc
    except requests.Timeout as exc:
        raise ValueError(f"AI 接口连接超时：{urlparse(root).hostname or root}") from exc
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        message = _error_message(response)
        raise ValueError(f"接口返回 HTTP {response.status_code}：{message}") from exc
    return response.json()


def _is_deepseek_url(base_url: str) -> bool:
    hostname = (urlparse(base_url).hostname or "").lower()
    return hostname == "api.deepseek.com" or hostname.endswith(".deepseek.com")


def _extract_text(data: dict) -> str:
    if data.get("output_text"):
        return data["output_text"]
    choices = data.get("choices", [])
    if choices:
        content = choices[0].get("message", {}).get("content")
        if content:
            return content
    texts = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                texts.append(content["text"])
    if not texts:
        raise ValueError("AI 接口未返回可展示的文本内容。")
    return "\n".join(texts)


def _is_truncated(data: dict) -> bool:
    if data.get("status") == "incomplete":
        return True
    incomplete_details = data.get("incomplete_details") or {}
    if incomplete_details.get("reason") in {"max_output_tokens", "length"}:
        return True
    return any(choice.get("finish_reason") == "length" for choice in data.get("choices", []))


def _merge_continuation(existing: str, continuation: str) -> str:
    existing = existing.rstrip()
    continuation = continuation.lstrip()
    max_overlap = min(120, len(existing), len(continuation))
    for size in range(max_overlap, 0, -1):
        if existing[-size:] == continuation[:size]:
            return existing + continuation[size:]
    starts_new_block = continuation.startswith(("#", "-", "*", "关键发现", "业务含义", "建议进一步分析的问题"))
    separator = "\n\n" if starts_new_block and existing.endswith(("。", "！", "？", "\n")) else ""
    return existing + separator + continuation


def _error_message(response: requests.Response) -> str:
    try:
        data = response.json()
        error = data.get("error", data)
        if isinstance(error, dict):
            return str(error.get("message") or error.get("type") or error)
        return str(error)
    except ValueError:
        return response.text[:300] or "未知错误"
