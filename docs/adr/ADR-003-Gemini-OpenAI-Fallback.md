# ADR-003: Gemini + OpenAI Fallback AI 策略

**状态:** 已接受
**日期:** 2026-05-10

---

## 背景

open-daily-stock 需要 AI 能力对股票进行分析。用户可能有不同的 AI API Key：
- Google Gemini（免费额度）
- OpenAI（付费，可能通过 DeepSeek/通义等兼容 API 调用）

需要一种策略在保证分析质量的同时降低成本。

## 决策

采用 **Gemini 优先，OpenAI fallback** 的 AI 策略：

```
分析请求 → Gemini API → 成功 → 返回结果
                 ↓ 失败
           OpenAI 兼容 API → 返回结果
                 ↓ 失败
              返回错误
```

### 选择理由

1. **成本优化** — Gemini 免费额度足够个人用户日常使用
2. **容错性** — 单一 API 故障不影响服务可用性
3. **灵活性** — 支持 DeepSeek、通义等 OpenAI 兼容 API
4. **A股适配** — Gemini 中文理解能力较强

### 实施

```python
# analyzer.py
class Analyzer:
    def __init__(self, config: dict):
        self.gemini_key = config.get("apis", {}).get("gemini_key")
        self.openai_key = config.get("apis", {}).get("openai_key")
        self.openai_base = config.get("apis", {}).get("openai_base")

    def analyze(self, stock: str, market: str) -> dict:
        # 优先 Gemini
        try:
            return self._analyze_gemini(stock, market)
        except Exception as e:
            logger.warning(f"Gemini failed: {e}, falling back to OpenAI")

        # Fallback OpenAI 兼容 API
        if self.openai_key:
            return self._analyze_openai(stock, market)

        raise AIError("All AI providers failed")
```

### API Key 配置

```json
{
  "apis": {
    "gemini_key": "AIxxx",
    "deepseek_key": "sk-xxx",      // OpenAI 兼容
    "openai_base": "https://api.deepseek.com"
  }
}
```

---

## 后果

**正面：**
- 免费用户可使用 Gemini 完成分析
- 付费用户可配置 DeepSeek 等低成本方案
- 单 API 故障不影响服务

**负面：**
- 需要用户自己提供 API Key
- 模型能力可能有差异（Gemini vs GPT-4）

**替代方案考虑：**
- 仅 Gemini: 成本低但模型能力有限
- 仅 OpenAI: 成本高，依赖单一供应商
- 云端聚合: 架构复杂，增加延迟
