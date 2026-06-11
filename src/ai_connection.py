import requests
from urllib.parse import urlparse


def test_ai_connection(api_key: str, model: str, base_url: str) -> str:
    if not api_key.strip():
        raise ValueError("请先填写 API Key。")
    if not model.strip():
        raise ValueError("请先填写模型名称。")
    if not base_url.strip().startswith(("http://", "https://")):
        raise ValueError("API 地址必须以 http:// 或 https:// 开头。")

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    root = base_url.rstrip("/")
    try:
        if _is_deepseek_url(root):
            response = requests.post(
                f"{root}/chat/completions",
                headers=headers,
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": "请只回复：连接成功"}],
                    "max_tokens": 128,
                },
                timeout=30,
            )
        else:
            response = requests.post(
                f"{root}/responses",
                headers=headers,
                json={"model": model, "input": "请只回复：连接成功"},
                timeout=30,
            )
        if response.status_code in {400, 404, 405} and not _is_deepseek_url(root):
            response = requests.post(
                f"{root}/chat/completions",
                headers=headers,
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": "请只回复：连接成功"}],
                    "max_tokens": 128,
                },
                timeout=30,
            )
    except requests.ConnectionError as exc:
        raise ValueError(_connection_error_message(root)) from exc
    except requests.Timeout as exc:
        raise ValueError(f"连接 {urlparse(root).hostname or root} 超时，请检查网络或代理设置。") from exc
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise ValueError(f"接口返回 HTTP {response.status_code}：{_error_message(response)}") from exc
    return _extract_text(response.json()).strip() or "连接成功"


def _is_deepseek_url(base_url: str) -> bool:
    hostname = (urlparse(base_url).hostname or "").lower()
    return hostname == "api.deepseek.com" or hostname.endswith(".deepseek.com")


def _connection_error_message(base_url: str) -> str:
    hostname = urlparse(base_url).hostname or base_url
    return (
        f"无法连接 {hostname}。API 地址和模型名称可能是正确的，但当前运行环境的外部网络连接被阻止。"
        "请检查代理/TUN 模式、防火墙是否允许 Python 访问网络，或在本机终端重新启动应用后再试。"
    )


def _extract_text(data: dict) -> str:
    if data.get("output_text"):
        return data["output_text"]
    choices = data.get("choices", [])
    if choices:
        content = choices[0].get("message", {}).get("content")
        if content:
            return content
    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                return content["text"]
    raise ValueError("AI 接口未返回可展示的文本内容。")


def _error_message(response: requests.Response) -> str:
    try:
        data = response.json()
        error = data.get("error", data)
        if isinstance(error, dict):
            return str(error.get("message") or error.get("type") or error)
        return str(error)
    except ValueError:
        return response.text[:300] or "未知错误"
