# -*- coding: utf-8 -*-
"""
===================================
A股自选股智能分析系统 - AI分析层
===================================

职责：
1. 封装 Gemini API 调用逻辑
2. 利用 Google Search Grounding 获取实时新闻
3. 结合技术面和消息面生成分析报告
"""

import json
import logging
import threading
from typing import Optional
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from src.config import get_config
from src.cn_prompts import CNPromptBuilder, CN_ANALYST_SYSTEM_PROMPT

# P0-5: 类型已迁至 src.llm.types。re-import 保持存量 import 路径可用。
from src.llm.types import AnalysisResult, DeepAnalysisResult, OrchestratorCancelled  # noqa: F401
from src.llm.prompts import (  # noqa: F401  re-export for backward compat
    STOCK_NAME_MAP, get_stock_name_multi_source,
    TECHNICAL_SYSTEM_PROMPT, FUNDAMENTAL_SYSTEM_PROMPT, NEWS_SYSTEM_PROMPT,
    SYNTHESIZER_PROMPT, DEEP_AGENTS, DEEP_PROMPTS,
    format_volume, format_amount, build_analysis_prompt,
)
from src.llm.client import (  # noqa: F401  re-export for backward compat
    LLMClient,
    init_gemini_model, init_openai_client, switch_to_fallback_model,
    is_available as llm_is_available,
)
from src.llm.parsing import (  # noqa: F401  re-export for backward compat
    fix_json_string, parse_response, parse_text_response, parse_specialist_json,
)
logger = logging.getLogger(__name__)


@dataclass
class GeminiAnalyzer:
    """
    Gemini AI 分析器
    
    职责：
    1. 调用 Google Gemini API 进行股票分析
    2. 结合预先搜索的新闻和技术面数据生成分析报告
    3. 解析 AI 返回的 JSON 格式结果
    
    使用方式：
        analyzer = GeminiAnalyzer()
        result = analyzer.analyze(context, news_context)
    """
    
    # ========================================
    # 系统提示词 - 决策仪表盘 v2.0
    # ========================================
    # 输出格式升级：从简单信号升级为决策仪表盘
    # 核心模块：核心结论 + 数据透视 + 舆情情报 + 作战计划
    # ========================================
    
    SYSTEM_PROMPT = """你是一位专注于趋势交易的 A 股投资分析师，负责生成专业的【决策仪表盘】分析报告。

## 核心交易理念（必须严格遵守）

### 1. 严进策略（不追高）
- **绝对不追高**：当股价偏离 MA5 超过 5% 时，坚决不买入
- **乖离率公式**：(现价 - MA5) / MA5 × 100%
- 乖离率 < 2%：最佳买点区间
- 乖离率 2-5%：可小仓介入
- 乖离率 > 5%：严禁追高！直接判定为"观望"

### 2. 趋势交易（顺势而为）
- **多头排列必须条件**：MA5 > MA10 > MA20
- 只做多头排列的股票，空头排列坚决不碰
- 均线发散上行优于均线粘合
- 趋势强度判断：看均线间距是否在扩大

### 3. 效率优先（筹码结构）
- 关注筹码集中度：90%集中度 < 15% 表示筹码集中
- 获利比例分析：70-90% 获利盘时需警惕获利回吐
- 平均成本与现价关系：现价高于平均成本 5-15% 为健康

### 4. 买点偏好（回踩支撑）
- **最佳买点**：缩量回踩 MA5 获得支撑
- **次优买点**：回踩 MA10 获得支撑
- **观望情况**：跌破 MA20 时观望

### 5. 风险排查重点
- 减持公告（股东、高管减持）
- 业绩预亏/大幅下滑
- 监管处罚/立案调查
- 行业政策利空
- 大额解禁

## 输出格式：决策仪表盘 JSON

请严格按照以下 JSON 格式输出，这是一个完整的【决策仪表盘】：

```json
{
    "sentiment_score": 0-100整数,
    "trend_prediction": "强烈看多/看多/震荡/看空/强烈看空",
    "operation_advice": "买入/加仓/持有/减仓/卖出/观望",
    "confidence_level": "高/中/低",
    
    "dashboard": {
        "core_conclusion": {
            "one_sentence": "一句话核心结论（30字以内，直接告诉用户做什么）",
            "signal_type": "🟢买入信号/🟡持有观望/🔴卖出信号/⚠️风险警告",
            "time_sensitivity": "立即行动/今日内/本周内/不急",
            "position_advice": {
                "no_position": "空仓者建议：具体操作指引",
                "has_position": "持仓者建议：具体操作指引"
            }
        },
        
        "data_perspective": {
            "trend_status": {
                "ma_alignment": "均线排列状态描述",
                "is_bullish": true/false,
                "trend_score": 0-100
            },
            "price_position": {
                "current_price": 当前价格数值,
                "ma5": MA5数值,
                "ma10": MA10数值,
                "ma20": MA20数值,
                "bias_ma5": 乖离率百分比数值,
                "bias_status": "安全/警戒/危险",
                "support_level": 支撑位价格,
                "resistance_level": 压力位价格
            },
            "volume_analysis": {
                "volume_ratio": 量比数值,
                "volume_status": "放量/缩量/平量",
                "turnover_rate": 换手率百分比,
                "volume_meaning": "量能含义解读（如：缩量回调表示抛压减轻）"
            },
            "chip_structure": {
                "profit_ratio": 获利比例,
                "avg_cost": 平均成本,
                "concentration": 筹码集中度,
                "chip_health": "健康/一般/警惕"
            }
        },
        
        "intelligence": {
            "latest_news": "【最新消息】近期重要新闻摘要",
            "risk_alerts": ["风险点1：具体描述", "风险点2：具体描述"],
            "positive_catalysts": ["利好1：具体描述", "利好2：具体描述"],
            "earnings_outlook": "业绩预期分析（基于年报预告、业绩快报等）",
            "sentiment_summary": "舆情情绪一句话总结"
        },
        
        "battle_plan": {
            "sniper_points": {
                "ideal_buy": "理想买入点：XX元（在MA5附近）",
                "secondary_buy": "次优买入点：XX元（在MA10附近）",
                "stop_loss": "止损位：XX元（跌破MA20或X%）",
                "take_profit": "目标位：XX元（前高/整数关口）"
            },
            "position_strategy": {
                "suggested_position": "建议仓位：X成",
                "entry_plan": "分批建仓策略描述",
                "risk_control": "风控策略描述"
            },
            "action_checklist": [
                "✅/⚠️/❌ 检查项1：多头排列",
                "✅/⚠️/❌ 检查项2：乖离率<5%",
                "✅/⚠️/❌ 检查项3：量能配合",
                "✅/⚠️/❌ 检查项4：无重大利空",
                "✅/⚠️/❌ 检查项5：筹码健康"
            ]
        }
    },
    
    "analysis_summary": "100字综合分析摘要",
    "key_points": "3-5个核心看点，逗号分隔",
    "risk_warning": "风险提示",
    "buy_reason": "操作理由，引用交易理念",
    
    "trend_analysis": "走势形态分析",
    "short_term_outlook": "短期1-3日展望",
    "medium_term_outlook": "中期1-2周展望",
    "technical_analysis": "技术面综合分析",
    "ma_analysis": "均线系统分析",
    "volume_analysis": "量能分析",
    "pattern_analysis": "K线形态分析",
    "fundamental_analysis": "基本面分析",
    "sector_position": "板块行业分析",
    "company_highlights": "公司亮点/风险",
    "news_summary": "新闻摘要",
    "market_sentiment": "市场情绪",
    "hot_topics": "相关热点",
    
    "search_performed": true/false,
    "data_sources": "数据来源说明"
}
```

## 评分标准

### 强烈买入（80-100分）：
- ✅ 多头排列：MA5 > MA10 > MA20
- ✅ 低乖离率：<2%，最佳买点
- ✅ 缩量回调或放量突破
- ✅ 筹码集中健康
- ✅ 消息面有利好催化

### 买入（60-79分）：
- ✅ 多头排列或弱势多头
- ✅ 乖离率 <5%
- ✅ 量能正常
- ⚪ 允许一项次要条件不满足

### 观望（40-59分）：
- ⚠️ 乖离率 >5%（追高风险）
- ⚠️ 均线缠绕趋势不明
- ⚠️ 有风险事件

### 卖出/减仓（0-39分）：
- ❌ 空头排列
- ❌ 跌破MA20
- ❌ 放量下跌
- ❌ 重大利空

## 决策仪表盘核心原则

1. **核心结论先行**：一句话说清该买该卖
2. **分持仓建议**：空仓者和持仓者给不同建议
3. **精确狙击点**：必须给出具体价格，不说模糊的话
4. **检查清单可视化**：用 ✅⚠️❌ 明确显示每项检查结果
5. **风险优先级**：舆情中的风险点要醒目标出"""

    def __init__(self, api_key: Optional[str] = None):
        """
        初始化 AI 分析器

        优先级：Gemini > OpenAI 兼容 API

        Args:
            api_key: Gemini API Key（可选，默认从配置读取）
        """
        config = get_config()
        api_key = api_key or config.gemini_api_key

        self._cn_mode = False  # Whether to use A-share specific CN prompts

        # Create the LLM client. system_prompt initial value comes from class attr.
        # Subsequent mutations to self._system_prompt route through the
        # property setter below, keeping client.system_prompt in sync.

        # All provider state is owned by LLMClient
        self._client = LLMClient(
            api_key=api_key,
            gemini_model=config.gemini_model,
            gemini_fallback_model=config.gemini_model_fallback,
            openai_api_key=config.openai_api_key,
            openai_base_url=config.openai_base_url,
            openai_model=config.openai_model,
            system_prompt=self.SYSTEM_PROMPT,
        )

    # ============================================================
    # State delegation to LLMClient — backward-compat properties
    # Old code reads/writes self._model / self._openai_client etc.;
    # these properties keep that working while LLMClient owns the state.
    # ============================================================

    @property
    def _api_key(self) -> Optional[str]:
        return self._client.api_key

    @property
    def _model(self):
        return self._client.model

    @_model.setter
    def _model(self, value) -> None:
        self._client.model = value

    @property
    def _openai_client(self):
        return self._client.openai_client

    @_openai_client.setter
    def _openai_client(self, value) -> None:
        self._client.openai_client = value

    @property
    def _current_model_name(self) -> Optional[str]:
        return self._client.current_model_name

    @_current_model_name.setter
    def _current_model_name(self, value) -> None:
        self._client.current_model_name = value

    @property
    def _using_fallback(self) -> bool:
        return self._client.using_fallback

    @_using_fallback.setter
    def _using_fallback(self, value: bool) -> None:
        self._client.using_fallback = value

    @property
    def _use_openai(self) -> bool:
        return self._client.use_openai

    @_use_openai.setter
    def _use_openai(self, value: bool) -> None:
        self._client.use_openai = value

    @property
    def _system_prompt(self) -> str:
        return self._client.system_prompt

    @_system_prompt.setter
    def _system_prompt(self, value: str) -> None:
        self._client.system_prompt = value

    def _init_openai_fallback(self) -> None:
        """初始化 OpenAI 兼容 API（委托 LLMClient.init_openai）"""
        self._client.init_openai()

    def _init_model(self) -> None:
        """初始化 Gemini 模型（委托 LLMClient.__init__ 已完成；保留为 no-op 兼容旧调用）"""
        # LLMClient.__init__ 已做完 Gemini 初始化；这里保留以防外部代码调用
        pass

    def _switch_to_fallback_model(self) -> bool:
        """运行时切换到备选模型（委托 LLMClient.switch_to_fallback）"""
        return self._client.switch_to_fallback()

    def is_available(self) -> bool:
        """检查分析器是否可用（委托 LLMClient.is_available）"""
        return self._client.is_available()
    
    def _call_openai_api(self, prompt: str, generation_config: dict) -> str:
        """调用 OpenAI 兼容 API（委托 LLMClient.call_openai）"""
        return self._client.call_openai(prompt, generation_config)

    def _call_api_with_retry(
        self,
        prompt: str,
        generation_config: dict,
        cancellation_event: Optional["threading.Event"] = None,
    ) -> str:
        """调用 AI API（委托 LLMClient.call_with_retry，含 Gemini 重试+OpenAI fallback+取消支持）"""
        return self._client.call_with_retry(prompt, generation_config, cancellation_event)

    def analyze(
        self,
        context: Dict[str, Any],
        news_context: Optional[str] = None,
        enable_rag: bool = True,
    ) -> AnalysisResult:
        """
        分析单只股票

        流程：
        1. 格式化输入数据（技术面 + 新闻 + RAG 历史上下文）
        2. 调用 Gemini API（带重试和模型切换）
        3. 解析 JSON 响应
        4. 返回结构化结果

        Args:
            context: 从 storage.get_analysis_context() 获取的上下文数据
            news_context: 预先搜索的新闻内容（可选）
            enable_rag: 是否启用 RAG 历史分析上下文（默认 True）

        Returns:
            AnalysisResult 对象
        """
        code = context.get('code', 'Unknown')
        config = get_config()
        
        # 请求前增加延时（防止连续请求触发限流）
        request_delay = config.gemini_request_delay
        if request_delay > 0:
            logger.debug(f"[LLM] 请求前等待 {request_delay:.1f} 秒...")
            time.sleep(request_delay)
        
        # 优先从上下文获取股票名称（由 main.py 传入）
        name = context.get('stock_name')
        if not name or name.startswith('股票'):
            # 备选：从 realtime 中获取
            if 'realtime' in context and context['realtime'].get('name'):
                name = context['realtime']['name']
            else:
                # 最后从映射表获取
                name = STOCK_NAME_MAP.get(code, f'股票{code}')
        
        # 如果模型不可用，返回默认结果
        if not self.is_available():
            return AnalysisResult(
                code=code,
                name=name,
                sentiment_score=50,
                trend_prediction='震荡',
                operation_advice='持有',
                confidence_level='低',
                analysis_summary='AI 分析功能未启用（未配置 API Key）',
                risk_warning='请配置 Gemini API Key 后重试',
                success=False,
                error_message='Gemini API Key 未配置',
            )
        
        try:
            # === Determine market and set appropriate prompts ===
            # CN market detection: explicit market field OR 6-digit numeric code
            is_cn = (
                context.get("market") == "CN"
                or (code.isdigit() and len(code) == 6)
            )
            self._cn_mode = is_cn
            if is_cn:
                self._system_prompt = CN_ANALYST_SYSTEM_PROMPT
            else:
                self._system_prompt = self.SYSTEM_PROMPT

            # === P5-6: RAG historical analysis context ===
            rag_context = ""
            if enable_rag:
                try:
                    from src.rag import build_rag_context
                    rag_context = build_rag_context(code)
                    if rag_context:
                        logger.debug(f"[RAG] 为 {code} 注入了历史分析上下文 ({len(rag_context)} 字符)")
                except Exception as e:
                    logger.warning(f"[RAG] 获取历史上下文失败 (非致命): {e}")

            # Format input (includes technical data + news)
            if self._cn_mode:
                prompt = CNPromptBuilder.build_analysis_prompt(
                    context,
                    inst_context="",
                    news_context=news_context or "",
                    industry_context="",
                )
            else:
                prompt = self._format_prompt(context, name, news_context)

            # Prepend RAG historical context to prompt
            if rag_context:
                prompt = rag_context + "\n\n" + prompt
            
            # 获取模型名称
            model_name = getattr(self, '_current_model_name', None)
            if not model_name:
                model_name = getattr(self._model, '_model_name', 'unknown')
                if hasattr(self._model, 'model_name'):
                    model_name = self._model.model_name
            
            logger.info(f"========== AI 分析 {name}({code}) ==========")
            logger.info(f"[LLM配置] 模型: {model_name}")
            logger.info(f"[LLM配置] Prompt 长度: {len(prompt)} 字符")
            logger.info(f"[LLM配置] 是否包含新闻: {'是' if news_context else '否'}")
            
            # 记录完整 prompt 到日志（INFO级别记录摘要，DEBUG记录完整）
            prompt_preview = prompt[:500] + "..." if len(prompt) > 500 else prompt
            logger.info(f"[LLM Prompt 预览]\n{prompt_preview}")
            logger.debug(f"=== 完整 Prompt ({len(prompt)}字符) ===\n{prompt}\n=== End Prompt ===")

            # 设置生成配置（从配置文件读取温度参数）
            config = get_config()
            generation_config = {
                "temperature": config.gemini_temperature,
                "max_output_tokens": 8192,
            }

            logger.info(f"[LLM调用] 开始调用 Gemini API (temperature={generation_config['temperature']}, max_tokens={generation_config['max_output_tokens']})...")
            
            # 使用带重试的 API 调用
            start_time = time.time()
            response_text = self._call_api_with_retry(prompt, generation_config)
            elapsed = time.time() - start_time
            
            # 记录响应信息
            logger.info(f"[LLM返回] Gemini API 响应成功, 耗时 {elapsed:.2f}s, 响应长度 {len(response_text)} 字符")
            
            # 记录响应预览（INFO级别）和完整响应（DEBUG级别）
            response_preview = response_text[:300] + "..." if len(response_text) > 300 else response_text
            logger.info(f"[LLM返回 预览]\n{response_preview}")
            logger.debug(f"=== Gemini 完整响应 ({len(response_text)}字符) ===\n{response_text}\n=== End Response ===")
            
            # 解析响应
            result = self._parse_response(response_text, code, name)
            result.raw_response = response_text
            result.search_performed = bool(news_context)
            
            logger.info(f"[LLM解析] {name}({code}) 分析完成: {result.trend_prediction}, 评分 {result.sentiment_score}")
            
            return result
            
        except Exception as e:
            logger.error(f"AI 分析 {name}({code}) 失败: {e}")
            return AnalysisResult(
                code=code,
                name=name,
                sentiment_score=50,
                trend_prediction='震荡',
                operation_advice='持有',
                confidence_level='低',
                analysis_summary=f'分析过程出错: {str(e)[:100]}',
                risk_warning='分析失败，请稍后重试或手动分析',
                success=False,
                error_message=str(e),
            )
    
    def _call_gemini_stream(self, prompt: str, generation_config: dict):
        """流式调用 Gemini（委托 LLMClient.call_gemini_stream）"""
        yield from self._client.call_gemini_stream(prompt, generation_config)

    def _call_openai_stream(self, prompt: str, generation_config: dict):
        """流式调用 OpenAI（委托 LLMClient.call_openai_stream）"""
        yield from self._client.call_openai_stream(prompt, generation_config)

    def analyze_stream(
        self,
        context: Dict[str, Any],
        news_context: Optional[str] = None,
        enable_rag: bool = True,
    ):
        """
        Analyze a single stock with streaming response.

        Yields chunks as they arrive from the LLM, then yields a final
        "done" event with the parsed AnalysisResult.

        Each yield is a dict:
          {"type": "chunk", "data": "partial text..."}
        Final yield:
          {"type": "done", "result": AnalysisResult}

        Args:
            context: Analysis context data (same as analyze())
            news_context: Pre-searched news content (optional)
            enable_rag: 是否启用 RAG 历史分析上下文（默认 True）

        Yields:
            dict: Stream events
        """
        code = context.get('code', 'Unknown')
        config_obj = get_config()

        # Request delay
        request_delay = config_obj.gemini_request_delay
        if request_delay > 0:
            logger.debug(f"[LLM Stream] 请求前等待 {request_delay:.1f} 秒...")
            time.sleep(request_delay)

        # Resolve stock name
        name = context.get('stock_name')
        if not name or name.startswith('股票'):
            if 'realtime' in context and context['realtime'].get('name'):
                name = context['realtime']['name']
            else:
                name = STOCK_NAME_MAP.get(code, f'股票{code}')

        # If model not available, yield error result
        if not self.is_available():
            result = AnalysisResult(
                code=code,
                name=name,
                sentiment_score=50,
                trend_prediction='震荡',
                operation_advice='持有',
                confidence_level='低',
                analysis_summary='AI 分析功能未启用（未配置 API Key）',
                risk_warning='请配置 Gemini API Key 后重试',
                success=False,
                error_message='Gemini API Key 未配置',
            )
            yield {"type": "done", "result": result}
            return

        try:
            # Determine market and set prompts
            is_cn = (
                context.get("market") == "CN"
                or (code.isdigit() and len(code) == 6)
            )
            self._cn_mode = is_cn
            if is_cn:
                self._system_prompt = CN_ANALYST_SYSTEM_PROMPT
            else:
                self._system_prompt = self.SYSTEM_PROMPT

            # === P5-6: RAG historical analysis context ===
            rag_context = ""
            if enable_rag:
                try:
                    from src.rag import build_rag_context
                    rag_context = build_rag_context(code)
                    if rag_context:
                        logger.debug(f"[RAG Stream] 为 {code} 注入了历史分析上下文 ({len(rag_context)} 字符)")
                except Exception as e:
                    logger.warning(f"[RAG Stream] 获取历史上下文失败 (非致命): {e}")

            # Format prompt
            if self._cn_mode:
                prompt = CNPromptBuilder.build_analysis_prompt(
                    context,
                    inst_context="",
                    news_context=news_context or "",
                    industry_context="",
                )
            else:
                prompt = self._format_prompt(context, name, news_context)

            # Prepend RAG historical context to prompt
            if rag_context:
                prompt = rag_context + "\n\n" + prompt

            model_name = getattr(self, '_current_model_name', 'unknown')
            logger.info(f"========== AI 流式分析 {name}({code}) ==========")
            logger.info(f"[LLM Stream] 模型: {model_name}, Prompt 长度: {len(prompt)} 字符")
            logger.debug(f"=== 流式 Prompt ===\\n{prompt}\\n=== End Prompt ===")

            generation_config = {
                "temperature": config_obj.gemini_temperature,
                "max_output_tokens": 8192,
            }

            # Stream tokens
            start_time = time.time()
            full_text_parts = []

            for chunk_text in self._client.call_gemini_stream(prompt, generation_config):
                full_text_parts.append(chunk_text)
                yield {"type": "chunk", "data": chunk_text}

            elapsed = time.time() - start_time
            full_text = "".join(full_text_parts)
            logger.info(f"[LLM Stream] 响应完成, 耗时 {elapsed:.2f}s, 总长度 {len(full_text)} 字符")

            # Parse the full response
            result = self._parse_response(full_text, code, name)
            result.raw_response = full_text
            result.search_performed = bool(news_context)

            logger.info(f"[LLM Stream] {name}({code}) 分析完成: {result.trend_prediction}, 评分 {result.sentiment_score}")
            yield {"type": "done", "result": result}

        except Exception as e:
            logger.error(f"AI 流式分析 {name}({code}) 失败: {e}")
            result = AnalysisResult(
                code=code,
                name=name,
                sentiment_score=50,
                trend_prediction='震荡',
                operation_advice='持有',
                confidence_level='低',
                analysis_summary=f'流式分析过程出错: {str(e)[:100]}',
                risk_warning='分析失败，请稍后重试或手动分析',
                success=False,
                error_message=str(e),
            )
            yield {"type": "done", "result": result}

    def _format_prompt(
        self,
        context: Dict[str, Any],
        name: str,
        news_context: Optional[str] = None
    ) -> str:
        """格式化分析提示词（委托 src.llm.prompts.build_analysis_prompt）"""
        return build_analysis_prompt(context, name, news_context)

    def _format_volume(self, volume: Optional[float]) -> str:
        """格式化成交量显示（委托 src.llm.prompts.format_volume）"""
        return format_volume(volume)

    def _format_amount(self, amount: Optional[float]) -> str:
        """格式化成交额显示（委托 src.llm.prompts.format_amount）"""
        return format_amount(amount)

    def _parse_response(self, response_text: str, code: str, name: str) -> AnalysisResult:
        """委托 src.llm.parsing.parse_response"""
        return parse_response(response_text, code, name)

    def _fix_json_string(self, json_str: str) -> str:
        """委托 src.llm.parsing.fix_json_string"""
        return fix_json_string(json_str)

    def _parse_text_response(self, response_text: str, code: str, name: str) -> AnalysisResult:
        """委托 src.llm.parsing.parse_text_response"""
        return parse_text_response(response_text, code, name)

    def batch_analyze(
        self, 
        contexts: List[Dict[str, Any]],
        delay_between: float = 2.0
    ) -> List[AnalysisResult]:
        """
        批量分析多只股票
        
        注意：为避免 API 速率限制，每次分析之间会有延迟
        
        Args:
            contexts: 上下文数据列表
            delay_between: 每次分析之间的延迟（秒）
            
        Returns:
            AnalysisResult 列表
        """
        results = []

        for i, context in enumerate(contexts):
            if i > 0:
                logger.debug(f"等待 {delay_between} 秒后继续...")
                time.sleep(delay_between)

            result = self.analyze(context)
            results.append(result)

        return results

    # ============================================================
    # P5-5: Deep Analysis (Multi-Agent Mode)
    # ============================================================

    def deep_analyze(
        self,
        context: Dict[str, Any],
        enabled_agents: Optional[List[str]] = None,
    ) -> DeepAnalysisResult:
        """
        Run deep analysis with 3 specialist agents + 1 synthesizer.

        Workflow:
        1. Run technical, fundamental, news agents in parallel
        2. Collect all 3 specialist outputs
        3. Synthesizer produces final integrated verdict
        4. Fall back to single-shot if any specialist fails

        Args:
            context: Stock analysis context (from storage.get_analysis_context())
            enabled_agents: List of agent names to enable (e.g. ["technical", "fundamental", "news"])
                            If None, uses config value deep_analysis_agents.

        Returns:
            DeepAnalysisResult with individual specialist scores and final verdict
        """
        code = context.get('code', 'Unknown')
        config = get_config()

        # Resolve stock name
        name = context.get('stock_name')
        if not name or name.startswith('股票'):
            if 'realtime' in context and context['realtime'].get('name'):
                name = context['realtime']['name']
            else:
                name = STOCK_NAME_MAP.get(code, f'股票{code}')

        # Determine which agents to run
        if enabled_agents is None:
            enabled_str = getattr(config, 'deep_analysis_agents', 'technical,fundamental,news')
            enabled_agents = [a.strip() for a in enabled_str.split(',') if a.strip()]
        enabled_agents = [a for a in enabled_agents if a in DEEP_AGENTS]

        if not enabled_agents:
            return DeepAnalysisResult.error_result(
                code, name, "没有启用的深度分析代理"
            )

        # If model not available, return error for all agents
        if not self.is_available():
            return DeepAnalysisResult.error_result(
                code, name, "AI 分析功能未启用（未配置 API Key）"
            )

        # Build per-specialist context prompts
        specialist_prompts = self._build_specialist_prompts(context, name, enabled_agents)

        # Run specialist agents in parallel
        logger.info(f"[DeepAnalyze] 启动深度分析: {name}({code}), agents={enabled_agents}")
        start_time = time.time()

        specialist_results: Dict[str, Optional[Dict[str, Any]]] = {}
        raw_outputs: Dict[str, str] = {}
        failed_agents: List[str] = []

        with ThreadPoolExecutor(max_workers=min(len(enabled_agents), 3)) as pool:
            futures = {}
            for agent_name in enabled_agents:
                prompt = specialist_prompts[agent_name]
                system_prompt = DEEP_PROMPTS[agent_name]
                futures[pool.submit(
                    self._run_specialist, agent_name, system_prompt, prompt
                )] = agent_name

            for future in as_completed(futures):
                agent_name = futures[future]
                try:
                    result_dict, raw_text = future.result(timeout=90)
                    specialist_results[agent_name] = result_dict
                    raw_outputs[agent_name] = raw_text
                    score = result_dict.get('score', 50) if result_dict else 50
                    logger.info(f"[DeepAnalyze] {agent_name}: score={score}")
                except Exception as e:
                    logger.warning(f"[DeepAnalyze] {agent_name} agent failed: {e}")
                    failed_agents.append(agent_name)
                    specialist_results[agent_name] = None
                    raw_outputs[agent_name] = str(e)

        elapsed_specialists = time.time() - start_time
        logger.info(f"[DeepAnalyze] 专家分析完成, 耗时 {elapsed_specialists:.2f}s, 失败: {failed_agents}")

        # Fall back to single-shot if ALL agents failed
        successful = [a for a in enabled_agents if a not in failed_agents]
        if not successful:
            logger.warning(f"[DeepAnalyze] 所有专家失败, 回退到单次分析")
            single_result = self.analyze(context)
            return DeepAnalysisResult(
                code=code,
                name=name,
                sentiment_score=single_result.sentiment_score,
                trend_prediction=single_result.trend_prediction,
                operation_advice=single_result.operation_advice,
                composite_score=single_result.sentiment_score,
                final_verdict=self._score_to_verdict(single_result.sentiment_score),
                key_catalysts=(single_result.key_points or "").split(','),
                risk_factors=[single_result.risk_warning] if single_result.risk_warning else [],
                technical=None,
                fundamental=None,
                news=None,
                synthesis_text=f"单次分析回退 (专家全部失败: {', '.join(failed_agents)}): {single_result.analysis_summary}",
                raw_specialist_outputs=raw_outputs,
                success=True,
            )

        # Synthesize: combine specialist outputs into final verdict
        synthesis_result = self._synthesize(
            specialist_results, raw_outputs, context, name, code, failed_agents
        )

        total_elapsed = time.time() - start_time
        logger.info(f"[DeepAnalyze] 深度分析完成, 总耗时 {total_elapsed:.2f}s, "
                     f"score={synthesis_result.sentiment_score}, verdict={synthesis_result.final_verdict}")

        return synthesis_result

    def _build_specialist_prompts(
        self,
        context: Dict[str, Any],
        name: str,
        enabled_agents: List[str],
    ) -> Dict[str, str]:
        """Build focused input prompts for each specialist agent.

        Each specialist gets the stock context but with a narrow focus:
        - technical: price, indicators, volume, patterns
        - fundamental: financials, PE/PB, institutional data
        - news: news content and sentiment signals
        """
        code = context.get('code', 'Unknown')
        today = context.get('today', {})

        prompts = {}

        if "technical" in enabled_agents:
            prompts["technical"] = self._format_technical_prompt(context, name, code, today)

        if "fundamental" in enabled_agents:
            prompts["fundamental"] = self._format_fundamental_prompt(context, name, code, today)

        if "news" in enabled_agents:
            prompts["news"] = self._format_news_prompt(context, name, code)

        return prompts

    def _format_technical_prompt(
        self, context: Dict[str, Any], name: str, code: str, today: Dict[str, Any]
    ) -> str:
        """Build technical analysis prompt for the technical specialist."""
        prompt = f"""Analyze stock {name}({code}) from a TECHNICAL perspective only.

Price Data:
- Close: {today.get('close', 'N/A')}, Open: {today.get('open', 'N/A')}
- High: {today.get('high', 'N/A')}, Low: {today.get('low', 'N/A')}
- Change: {today.get('pct_chg', 'N/A')}%
- MA5: {today.get('ma5', 'N/A')}, MA10: {today.get('ma10', 'N/A')}, MA20: {today.get('ma20', 'N/A')}
- MA Status: {context.get('ma_status', 'N/A')}
- Volume: {self._format_volume(today.get('volume'))}
"""

        if 'realtime' in context:
            rt = context['realtime']
            prompt += f"""- Volume Ratio: {rt.get('volume_ratio', 'N/A')}
- Turnover Rate: {rt.get('turnover_rate', 'N/A')}%
"""

        if 'trend_analysis' in context:
            t = context['trend_analysis']
            prompt += f"""- Trend Status: {t.get('trend_status', 'N/A')}
- Bias MA5: {t.get('bias_ma5', 0):+.2f}%
- Signal Score: {t.get('signal_score', 0)}/100
"""

        prompt += """
Output JSON:
{"trend": "bullish/bearish/neutral", "key_signals": ["signal1", "signal2"], "support": float, "resistance": float, "score": 0-100, "reasoning": "brief analysis"}"""
        return prompt

    def _format_fundamental_prompt(
        self, context: Dict[str, Any], name: str, code: str, today: Dict[str, Any]
    ) -> str:
        """Build fundamental analysis prompt for the fundamental specialist."""
        prompt = f"""Analyze stock {name}({code}) from a FUNDAMENTAL perspective only.

"""

        if 'realtime' in context:
            rt = context['realtime']
            prompt += f"""- PE Ratio: {rt.get('pe_ratio', 'N/A')}
- PB Ratio: {rt.get('pb_ratio', 'N/A')}
- Market Cap: {self._format_amount(rt.get('total_mv'))}
"""

        if 'financials' in context:
            fin = context['financials']
            if isinstance(fin, dict):
                for k, v in list(fin.items())[:8]:
                    prompt += f"- {k}: {v}\n"

        if 'chip' in context:
            c = context['chip']
            prompt += f"""- Profit Ratio: {c.get('profit_ratio', 0):.1%}
- Avg Cost: {c.get('avg_cost', 'N/A')}
"""

        prompt += """
Output JSON:
{"valuation": "undervalued/fair/overvalued", "key_metrics": ["metric1", "metric2"], "risks": ["risk1"], "score": 0-100, "reasoning": "brief analysis"}"""
        return prompt

    def _format_news_prompt(
        self, context: Dict[str, Any], name: str, code: str
    ) -> str:
        """Build news/sentiment analysis prompt."""
        prompt = f"""Analyze stock {name}({code}) from a NEWS/SENTIMENT perspective only.

"""

        if 'news' in context:
            news_data = context['news']
            if isinstance(news_data, str):
                prompt += f"Recent News:\n{news_data[:2000]}\n"
            elif isinstance(news_data, list):
                for n in news_data[:10]:
                    prompt += f"- {n}\n"

        if 'market_sentiment' in context:
            prompt += f"Market Sentiment: {context['market_sentiment']}\n"

        prompt += """
Output JSON:
{"sentiment": "positive/negative/neutral", "key_drivers": ["driver1"], "risk_events": ["event1"], "score": 0-100, "reasoning": "brief analysis"}"""
        return prompt

    def _run_specialist(
        self,
        agent_name: str,
        system_prompt: str,
        user_prompt: str,
    ) -> tuple:
        """Run a single specialist agent with its dedicated system prompt.

        Temporarily overrides self._system_prompt to use the specialist's prompt,
        then restores it afterward.

        Args:
            agent_name: Name of the specialist (for logging)
            system_prompt: The specialist's system prompt
            user_prompt: The focused input for this specialist

        Returns:
            Tuple of (parsed_json_dict, raw_response_text)
        """
        # Save original system prompt
        original_prompt = self._system_prompt
        original_cn_mode = self._cn_mode

        try:
            self._system_prompt = system_prompt
            self._cn_mode = False  # Use neutral mode for specialists

            config = get_config()
            generation_config = {
                "temperature": min(config.gemini_temperature, 0.5),
                "max_output_tokens": 2048,
            }

            start = time.time()
            response_text = self._call_api_with_retry(user_prompt, generation_config)
            elapsed = time.time() - start

            logger.debug(f"[DeepAnalyze:{agent_name}] response in {elapsed:.2f}s, {len(response_text)} chars")

            # Parse specialist JSON output
            parsed = self._parse_specialist_json(response_text, agent_name)

            return parsed, response_text

        finally:
            # Restore original prompts
            self._system_prompt = original_prompt
            self._cn_mode = original_cn_mode

    def _parse_specialist_json(self, response_text: str, agent_name: str) -> Dict[str, Any]:
        """委托 src.llm.parsing.parse_specialist_json"""
        return parse_specialist_json(response_text, agent_name)

    def _synthesize(
        self,
        specialist_results: Dict[str, Optional[Dict[str, Any]]],
        raw_outputs: Dict[str, str],
        context: Dict[str, Any],
        name: str,
        code: str,
        failed_agents: List[str],
    ) -> DeepAnalysisResult:
        """Synthesize specialist outputs into a final DeepAnalysisResult.

        Uses the SYNTHESIZER_PROMPT and calls the LLM to integrate findings.
        Falls back to simple averaging if synthesizer call fails.
        """
        # Build synthesis input
        synth_input_parts = [f"Synthesize analysis for {name}({code}):\n"]

        for agent_name in ["technical", "fundamental", "news"]:
            result = specialist_results.get(agent_name)
            if result:
                synth_input_parts.append(f"\n### {agent_name.upper()} Report:\n{json.dumps(result, ensure_ascii=False)}")
            elif agent_name in failed_agents:
                synth_input_parts.append(f"\n### {agent_name.upper()}: FAILED")

        synth_input = "\n".join(synth_input_parts)
        synth_input += """
\nOutput JSON:
{"final_verdict": "看涨/看跌/中性", "composite_score": 0-100, "sentiment_score": 0-100, "trend_prediction": "强烈看多/看多/震荡/看空/强烈看空", "operation_advice": "买入/加仓/持有/减仓/卖出/观望", "key_catalysts": ["catalyst1"], "risk_factors": ["risk1"], "reasoning": "brief synthesis"}"""

        # Try LLM synthesis
        try:
            original_prompt = self._system_prompt
            self._system_prompt = SYNTHESIZER_PROMPT

            config = get_config()
            generation_config = {
                "temperature": min(config.gemini_temperature, 0.5),
                "max_output_tokens": 2048,
            }

            synth_text = self._call_api_with_retry(synth_input, generation_config)
            self._system_prompt = original_prompt

            parsed = self._parse_specialist_json(synth_text, "synthesizer")

            scores = []
            for an in ["technical", "fundamental", "news"]:
                r = specialist_results.get(an)
                if r and isinstance(r, dict):
                    s = r.get('score', 50)
                    if isinstance(s, (int, float)):
                        scores.append(s)

            avg_score = int(sum(scores) / len(scores)) if scores else 50

            return DeepAnalysisResult(
                code=code,
                name=name,
                sentiment_score=int(parsed.get('sentiment_score', avg_score)),
                trend_prediction=parsed.get('trend_prediction', '震荡'),
                operation_advice=parsed.get('operation_advice', '观望'),
                composite_score=int(parsed.get('composite_score', avg_score)),
                final_verdict=parsed.get('final_verdict', self._score_to_verdict(avg_score)),
                key_catalysts=parsed.get('key_catalysts', []),
                risk_factors=parsed.get('risk_factors', []),
                technical=specialist_results.get('technical'),
                fundamental=specialist_results.get('fundamental'),
                news=specialist_results.get('news'),
                synthesis_text=synth_text,
                raw_specialist_outputs=raw_outputs,
                success=True,
            )

        except Exception as e:
            logger.warning(f"[DeepAnalyze] Synthesizer failed: {e}, using averaging fallback")
            return self._synthesize_fallback(
                specialist_results, raw_outputs, name, code, failed_agents
            )

    def _synthesize_fallback(
        self,
        specialist_results: Dict[str, Optional[Dict[str, Any]]],
        raw_outputs: Dict[str, str],
        name: str,
        code: str,
        failed_agents: List[str],
    ) -> DeepAnalysisResult:
        """Fallback synthesis: average specialist scores when LLM synthesis fails."""
        scores = []
        for an in ["technical", "fundamental", "news"]:
            r = specialist_results.get(an)
            if r and isinstance(r, dict):
                s = r.get('score', 50)
                if isinstance(s, (int, float)):
                    scores.append(int(s))

        if not scores:
            return DeepAnalysisResult.error_result(code, name, "所有专家分析失败")

        avg_score = int(sum(scores) / len(scores))

        return DeepAnalysisResult(
            code=code,
            name=name,
            sentiment_score=avg_score,
            trend_prediction=self._score_to_trend(avg_score),
            operation_advice=self._score_to_advice(avg_score),
            composite_score=avg_score,
            final_verdict=self._score_to_verdict(avg_score),
            key_catalysts=[],
            risk_factors=[],
            technical=specialist_results.get('technical'),
            fundamental=specialist_results.get('fundamental'),
            news=specialist_results.get('news'),
            synthesis_text=f"Fallback averaging (synthesizer failed: {failed_agents})",
            raw_specialist_outputs=raw_outputs,
            success=True,
        )

    def _score_to_verdict(self, score: int) -> str:
        """Convert numeric score to Chinese verdict."""
        if score >= 70:
            return "看涨"
        elif score >= 40:
            return "中性"
        return "看跌"

    def _score_to_trend(self, score: int) -> str:
        """Convert numeric score to trend prediction."""
        if score >= 80:
            return "强烈看多"
        elif score >= 60:
            return "看多"
        elif score >= 40:
            return "震荡"
        elif score >= 20:
            return "看空"
        return "强烈看空"

    def _score_to_advice(self, score: int) -> str:
        """Convert numeric score to operation advice."""
        if score >= 80:
            return "买入"
        elif score >= 60:
            return "加仓"
        elif score >= 40:
            return "持有"
        elif score >= 20:
            return "减仓"
        return "卖出"


# 便捷函数
def get_analyzer() -> GeminiAnalyzer:
    """获取 Gemini 分析器实例"""
    return GeminiAnalyzer()


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.DEBUG)
    
    # 模拟上下文数据
    test_context = {
        'code': '600519',
        'date': '2026-01-09',
        'today': {
            'open': 1800.0,
            'high': 1850.0,
            'low': 1780.0,
            'close': 1820.0,
            'volume': 10000000,
            'amount': 18200000000,
            'pct_chg': 1.5,
            'ma5': 1810.0,
            'ma10': 1800.0,
            'ma20': 1790.0,
            'volume_ratio': 1.2,
        },
        'ma_status': '多头排列 📈',
        'volume_change_ratio': 1.3,
        'price_change_ratio': 1.5,
    }
    
    analyzer = GeminiAnalyzer()
    
    if analyzer.is_available():
        print("=== AI 分析测试 ===")
        result = analyzer.analyze(test_context)
        print(f"分析结果: {result.to_dict()}")
    else:
        print("Gemini API 未配置，跳过测试")


