[Bug Report]: 非 Anthropic provider 使用自定义 API 时 `create_chat_llm` 因 `default_headers` 重复关键字导致 Session 启动失败

## 问题描述

当使用自定义 API（如 Moonshot、OpenRouter 等）并启用 `ENABLE_CUSTOM_API` 时，发送文本会话会触发 `TypeError: ChatOpenAI() got multiple values for keyword argument 'default_headers'`，导致 Session 启动失败。

## 复现步骤

1. 在 **API Key 设置 → 文本对话模型配置** 中选择服务商为 **自定义**
2. 填写自定义 API URL（如 `http://192.168.31.254:3766/v1`）、模型 ID（如 `Moonshot V1`）和 API Key
3. 勾选 **启用自定义API**
4. 保存配置
5. 发送文本会话
6. 前端收到 `session_failed`，控制台报错：

```
Error starting session: utils.llm_client.ChatOpenAI() got multiple values for keyword argument 'default_headers'
```

## 根因分析

`utils/llm_client.py` 的 `create_chat_llm` 函数中：

1. `get_cache_kwargs(base_url)` 返回的字典**始终包含** `default_headers` 键（即使为空字典 `{}`）
2. `OmniOfflineClient.__init__` 调用 `create_chat_llm` 时通过 `kw` 传入了 `default_headers=self.default_headers`
3. 代码**仅对 anthropic 分支**做了 `default_headers` 合并（`cache_kw.pop(...) + kw.pop(...)`）
4. 非 anthropic 分支没有合并，直接 `return ChatOpenAI(..., **cache_kw, **kw)` → `cache_kw` 和 `kw` 都包含 `default_headers` → `TypeError`

### 相关代码

```python
# utils/llm_client.py: create_chat_llm
cache_kw = get_cache_kwargs(base_url)  # 始终返回 {"default_headers": {...}, ...}

# 仅 anthropic 做了合并
if base_url and "api.anthropic.com" in base_url:
    merged_headers = {
        **cache_kw.pop("default_headers", {}),
        **kw.pop("default_headers", {}),
        **anthropic_headers,
    }
    kw["default_headers"] = merged_headers

return ChatOpenAI(..., **cache_kw, **kw)  # 非 anthropic 时重复 default_headers
```

## 环境信息

- N.E.K.O 版本：v0.8.1
- 使用场景：自定义 API（ENABLE_CUSTOM_API = true）
- 错误文件：`utils/llm_client.py`
- 调用栈：
  ```
  main_logic/core.py:4150  OmniOfflineClient.__init__
  main_logic/omni_offline_client.py:589  create_chat_llm(..., default_headers=self.default_headers)
  utils/llm_client.py:705  ChatOpenAI(..., **cache_kw, **kw)
  ```

## 期望行为

任何 provider（包括自定义 API）在 `cache_kw` 和 `kw` 都包含 `default_headers` 时，应该像 anthropic 分支一样先合并再传给 `ChatOpenAI`，不应抛出 `TypeError`。

## 建议修复

在 anthropic `if` 分支之后、非 anthropic 分支也添加 `default_headers` 合并逻辑：

```python
elif "default_headers" in kw:
    merged_headers = {
        **cache_kw.pop("default_headers", {}),
        **kw.pop("default_headers", {}),
    }
    kw["default_headers"] = merged_headers
```

## 补充说明

- API 连通性测试（`/api/config/test_connectivity`）能正常通过，因为测试不经过 `OmniOfflineClient`
- 只有实际发送会话、创建 `OmniOfflineClient` 实例时才会触发
- `get_core_config()` 中 `conversationModelUrl` → `CONVERSATION_MODEL_URL` 的映射是正确的，配置本身没有问题
