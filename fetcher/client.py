"""共享 HTTP 客户端（Step 4 实现）。

计划对外接口见项目《开发指令.md》的「接口契约」一节，签名已冻结：
    class HttpClient(timeout=15.0, retries=2, delay=0.4)
        .get(url, **kw) / .get_json(url, **kw) / .close() / with 语句
    class HttpError(RuntimeError)
"""

from __future__ import annotations
