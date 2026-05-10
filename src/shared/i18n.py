# -*- coding: utf-8 -*-
"""Simple i18n translation system for TUI/GUI.

Supports Chinese (zh), Japanese (ja), and Korean (ko).
Uses a flat key-value dictionary pattern with no heavy framework.
"""
from typing import Dict

TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "zh": {
        # App
        "app.title": "open-daily-stock",
        "app.subtitle": "智能股票分析系统",
        # Navigation
        "nav.markets": "行情",
        "nav.analyze": "分析",
        "nav.tasks": "任务",
        "nav.config": "配置",
        "nav.logs": "日志",
        # Markets
        "markets.title": "自选股行情",
        "markets.code": "代码",
        "markets.name": "名称",
        "markets.price": "最新价",
        "markets.change": "涨跌幅",
        "markets.volume": "成交量",
        "markets.refresh": "刷新",
        "markets.screener": "筛选",
        "markets.export": "导出CSV",
        # Analysis
        "analysis.title": "AI 分析",
        "analysis.input_code": "输入股票代码",
        "analysis.analyze": "开始分析",
        "analysis.result": "分析结果",
        "analysis.loading": "分析中...",
        # Tasks
        "tasks.title": "任务列表",
        "tasks.pending": "等待中",
        "tasks.running": "运行中",
        "tasks.completed": "已完成",
        "tasks.failed": "失败",
        "tasks.cancel": "取消",
        # Sim Trading
        "sim.buy": "买入",
        "sim.sell": "卖出",
        "sim.cash": "可用资金",
        "sim.assets": "总资产",
        "sim.pnl": "盈亏",
        # Actions
        "action.ok": "操作成功",
        "action.error": "操作失败",
        "action.cancel": "取消",
        "action.confirm": "确认",
        # Status
        "status.online": "在线",
        "status.offline": "离线",
        "status.connecting": "连接中...",
        "status.trading": "交易中",
        "status.closed": "休市",
        "status.pre_close": "盘前/盘后",
        "status.lunch": "午休",
        # Errors
        "error.network": "网络连接失败",
        "error.timeout": "请求超时",
        "error.unknown": "未知错误",
    },
    "ja": {
        "app.title": "open-daily-stock",
        "app.subtitle": "スマート株式分析システム",
        "nav.markets": "相場",
        "nav.analyze": "分析",
        "nav.tasks": "タスク",
        "nav.config": "設定",
        "nav.logs": "ログ",
        "markets.title": "お気に入り銘柄",
        "markets.code": "コード",
        "markets.name": "銘柄名",
        "markets.price": "現在値",
        "markets.change": "変動率",
        "markets.volume": "出来高",
        "markets.refresh": "更新",
        "markets.screener": "スクリーナー",
        "markets.export": "CSV出力",
        "analysis.title": "AI分析",
        "analysis.input_code": "銘柄コード入力",
        "analysis.analyze": "分析開始",
        "analysis.result": "分析結果",
        "analysis.loading": "分析中...",
        "tasks.title": "タスク一覧",
        "tasks.pending": "待機中",
        "tasks.running": "実行中",
        "tasks.completed": "完了",
        "tasks.failed": "失敗",
        "tasks.cancel": "キャンセル",
        "sim.buy": "買い",
        "sim.sell": "売り",
        "sim.cash": "利用可能資金",
        "sim.assets": "総資産",
        "sim.pnl": "損益",
        "action.ok": "成功",
        "action.error": "失敗",
        "action.cancel": "キャンセル",
        "action.confirm": "確認",
        "status.online": "オンライン",
        "status.offline": "オフライン",
        "status.connecting": "接続中...",
        "status.trading": "取引中",
        "status.closed": "休場",
        "status.pre_close": "プレクローズ",
        "status.lunch": "昼休み",
        "error.network": "ネットワーク接続失敗",
        "error.timeout": "タイムアウト",
        "error.unknown": "不明なエラー",
    },
    "ko": {
        "app.title": "open-daily-stock",
        "app.subtitle": "스마트 주식 분석 시스템",
        "nav.markets": "시세",
        "nav.analyze": "분석",
        "nav.tasks": "작업",
        "nav.config": "설정",
        "nav.logs": "로그",
        "markets.title": "관심 종목",
        "markets.code": "코드",
        "markets.name": "종목명",
        "markets.price": "현재가",
        "markets.change": "등락률",
        "markets.volume": "거래량",
        "markets.refresh": "새로고침",
        "markets.screener": "스크리너",
        "markets.export": "CSV 내보내기",
        "analysis.title": "AI 분석",
        "analysis.input_code": "종목코드 입력",
        "analysis.analyze": "분석 시작",
        "analysis.result": "분석 결과",
        "analysis.loading": "분석 중...",
        "tasks.title": "작업 목록",
        "tasks.pending": "대기 중",
        "tasks.running": "실행 중",
        "tasks.completed": "완료",
        "tasks.failed": "실패",
        "tasks.cancel": "취소",
        "sim.buy": "매수",
        "sim.sell": "매도",
        "sim.cash": "사용 가능 자금",
        "sim.assets": "총 자산",
        "sim.pnl": "손익",
        "action.ok": "성공",
        "action.error": "실패",
        "action.cancel": "취소",
        "action.confirm": "확인",
        "status.online": "온라인",
        "status.offline": "오프라인",
        "status.connecting": "연결 중...",
        "status.trading": "거래 중",
        "status.closed": "휴장",
        "status.pre_close": "장전/장후",
        "status.lunch": "점심시간",
        "error.network": "네트워크 연결 실패",
        "error.timeout": "요청 시간 초과",
        "error.unknown": "알 수 없는 오류",
    },
}

# Default language
DEFAULT_LANG = "zh"


def _normalize_lang(lang: str) -> str:
    """Normalize a language code to a 2-letter code.

    Handles both 'zh_CN' and 'zh' -> 'zh', etc.
    """
    # Strip region suffix (e.g., "zh_CN" -> "zh")
    lang = lang.strip().lower()
    if "_" in lang:
        lang = lang.split("_")[0]
    elif "-" in lang:
        lang = lang.split("-")[0]
    return lang


def get_current_lang() -> str:
    """Get current language from config."""
    try:
        from src.config import get_config
        lang = _normalize_lang(get_config().language)
        if lang in TRANSLATIONS:
            return lang
    except Exception:
        pass
    return DEFAULT_LANG


def t(key: str, lang: str = None) -> str:
    """Translate a key to the current language.

    Args:
        key: Translation key like 'markets.title'
        lang: Language code (default: from config)

    Returns:
        Translated string, or key itself if not found
    """
    if lang is None:
        lang = get_current_lang()
    else:
        lang = _normalize_lang(lang)
    return TRANSLATIONS.get(lang, {}).get(key, TRANSLATIONS[DEFAULT_LANG].get(key, key))


def get_available_languages() -> Dict[str, str]:
    """Get list of available languages.
    Returns: {code: native_name}"""
    return {
        "zh": "中文",
        "ja": "日本語",
        "ko": "한국어",
    }
