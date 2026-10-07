"""共享 HTTP 客户端（Step 4 实现）。

计划对外接口见项目《开发指令.md》的「接口契约」一节，签名已冻结：
    class HttpClient(timeout=15.0, retries=2, delay=0.4)
        .get(url, **kw) / .get_json(url, **kw) / .close() / with 语句
    class HttpError(RuntimeError)

设计要点：
- 所有外部请求都收敛到这里，适配器不允许直接用 httpx，便于统一 UA、重试与错误类型。
- get_json 必须兜住「响应头说是 text/html、body 其实是 JSON」的情况（QQ 音乐就是如此）。
"""

from __future__ import annotations

import json
import random
import time
from typing import Any

import httpx

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# 这些状态码属于「可以重试」的失败，而不是确定的业务结果
RETRY_STATUS = {408, 429, 500, 502, 503, 504}


class HttpError(RuntimeError):
    """所有网络层错误的统一出口，调用方只需捕获这一种。"""


class HttpClient:
    """带 UA 伪装、指数退避重试的轻量 HTTP 客户端。"""

    def __init__(self, timeout: float = 15.0, retries: int = 2, delay: float = 0.4):
        self.timeout = timeout
        self.retries = retries
        self.delay = delay
        self._client = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={
                "User-Agent": DEFAULT_UA,
                "Accept": "*/*",
                "Accept-Language": "zh-CN,zh;q=0.9",
            },
        )

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """发起请求，失败按指数退避 + 随机抖动重试，用尽后抛 HttpError。"""
        last_error: Exception | None = None

        for attempt in range(self.retries + 1):
            try:
                response = self._client.request(method, url, **kwargs)
                if response.status_code not in RETRY_STATUS:
                    return response
                last_error = HttpError(
                    f"{method} {url} 返回可重试状态码 {response.status_code}"
                )
            except Exception as exc:  # noqa: BLE001 - 统一收敛为 HttpError
                last_error = exc

            if attempt < self.retries:
                time.sleep(self.delay * (2**attempt) + random.uniform(0, 0.3))

        raise HttpError(f"{method} {url} 请求失败: {last_error}")

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def get_json(self, url: str, **kwargs: Any) -> Any:
        """取 JSON；响应头 content-type 撒谎时，退回手动 json.loads。"""
        response = self.get(url, **kwargs)
        try:
            return response.json()
        except ValueError:
            try:
                return json.loads(response.text)
            except ValueError as exc:
                raise HttpError(
                    f"{url} 响应不是合法 JSON: {exc}; "
                    f"content-type={response.headers.get('content-type')!r}"
                ) from exc

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> HttpClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
