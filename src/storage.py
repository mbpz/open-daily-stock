# -*- coding: utf-8 -*-
"""
===================================
A股自选股智能分析系统 - 存储层
===================================

职责：
1. 管理 SQLite 数据库连接（单例模式）
2. 定义 ORM 数据模型
3. 提供数据存取接口
4. 实现智能更新逻辑（断点续传）
"""

from __future__ import annotations

import atexit
import json
import logging
from contextlib import contextmanager
import time
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from pathlib import Path

import pandas as pd
from sqlalchemy import (
    create_engine,
    Column,
    String,
    Float,
    Date,
    DateTime,
    Integer,
    Index,
    UniqueConstraint,
    select,
    and_,
    desc,
    Text,
)
from sqlalchemy.orm import (
    declarative_base,
    sessionmaker,
    Session,
)
from sqlalchemy.exc import IntegrityError

from src.config import get_config

logger = logging.getLogger(__name__)

# ============================================================
# Network Degradation Cache
# ============================================================

MARKET_DATA_CACHE_TTL = {
    "A": 86400,   # A股: 1 day (seconds)
    "HK": 3600,   # 港股: 1 hour
    "US": 3600,   # 美股: 1 hour
}


class MarketDataCache:
    """
    市场数据缓存，用于网络降级时提供 fallback 数据

    缓存结构：
    {
        "code": {
            "data": {...},  # 市场数据
            "timestamp": float,  # 缓存时间
            "data_source": str,  # 数据来源
        }
    }
    """
    _instance: Optional['MarketDataCache'] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = __import__('threading').Lock()
        self._initialized = True

    @classmethod
    def get_instance(cls) -> 'MarketDataCache':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def set(self, code: str, data: Dict[str, Any], data_source: str = "Unknown") -> None:
        """缓存市场数据"""
        with self._lock:
            self._cache[code] = {
                "data": data,
                "timestamp": time.time(),
                "data_source": data_source,
            }

    def get(self, code: str) -> Optional[Dict[str, Any]]:
        """获取缓存的市场数据"""
        with self._lock:
            if code not in self._cache:
                return None
            entry = self._cache[code]
            return entry["data"]

    def get_with_staleness(self, code: str) -> tuple[Optional[Dict[str, Any]], bool, float]:
        """
        获取缓存数据及其 staleness 信息

        Returns:
            (data, is_stale, age_seconds)
        """
        with self._lock:
            if code not in self._cache:
                return None, True, float('inf')

            entry = self._cache[code]
            age = time.time() - entry["timestamp"]

            # 判断缓存类型
            market_type = self._get_market_type(code)
            ttl = MARKET_DATA_CACHE_TTL.get(market_type, 86400)

            return entry["data"], age > ttl, age

    def _get_market_type(self, code: str) -> str:
        """判断市场类型"""
        code_upper = code.upper()
        if code_upper.startswith('HK'):
            return "HK"
        elif code_upper.isalpha() and len(code_upper) <= 5:
            return "US"
        else:
            return "A"  # A股

    def get_cached_data(self, code: str) -> Optional[Dict[str, Any]]:
        """获取缓存数据（兼容性别名）"""
        return self.get(code)

    def clear_expired(self) -> int:
        """清除过期缓存"""
        with self._lock:
            now = time.time()
            expired_keys = []
            for code, entry in self._cache.items():
                market_type = self._get_market_type(code)
                ttl = MARKET_DATA_CACHE_TTL.get(market_type, 86400)
                if now - entry["timestamp"] > ttl:
                    expired_keys.append(code)

            for code in expired_keys:
                del self._cache[code]

            return len(expired_keys)


def get_market_cache() -> MarketDataCache:
    """获取市场数据缓存实例"""
    return MarketDataCache.get_instance()

# SQLAlchemy ORM 基类
Base = declarative_base()

# Current database schema version
CURRENT_SCHEMA_VERSION = 5  # P7-4: research_artifacts split (move large tool_output to its own table)


# === Migration System ===


def _run_migrations(db: 'DatabaseManager', from_version: int, to_version: int) -> None:
    """Run schema migrations from `from_version` to `to_version`.

    This is a placeholder for future migrations.  New migration steps should
    be added as conditions inside this function so that upgrades from any
    older version can be handled in a single pass.

    Args:
        db: DatabaseManager instance (can use db.get_session() for raw SQL).
        from_version: The version the database is currently at.
        to_version: The target schema version.
    """
    if from_version >= to_version:
        return

    logger.info(f"Running migrations: v{from_version} -> v{to_version}")

    # Example of how future migrations would be structured:
    # if from_version < 2:
    #     with db.get_session() as session:
    #         # Add new columns, create new tables, etc.
    #         pass
    #     logger.info("Migration v1 -> v2 applied")

    if from_version < 2 and to_version >= 2:
        # Placeholder: add `task_id` column to analysis_history (already
        # handled by _migrate_analysis_history_task_id), but future
        # migrations that require Data Definition Language go here.
        pass

    if from_version < 3 and to_version >= 3:
        # P5-6: Add FTS5 virtual table for RAG knowledge base
        _migrate_v3_add_fts5(db)
        logger.info("Migration v2 -> v3 applied (FTS5 RAG index)")

    if from_version < 4 and to_version >= 4:
        # P7-1: MarketReview table — auto-created via Base.metadata.create_all
        Base.metadata.create_all(db._engine)
        logger.info("Migration v3 -> v4 applied (MarketReview table)")

    if from_version < 5 and to_version >= 5:
        # P7-4: Split research_logs.steps_json — keep summary fields inline,
        # move large tool_output rows to a new research_artifacts table.
        _migrate_v5_split_research_artifacts(db)
        logger.info("Migration v4 -> v5 applied (research_artifacts split)")

    # Record the new schema version after all migrations succeed
    # Only insert if this version hasn't been recorded yet (idempotent)
    with db.get_session() as session:
        existing = session.execute(
            select(SchemaVersion).where(SchemaVersion.version == to_version)
        ).scalars().first()
        if existing is None:
            sv = SchemaVersion(
                version=to_version,
                description=f"Migrated from v{from_version} to v{to_version}",
            )
            session.add(sv)
            session.commit()
            logger.info(f"Migration complete. Schema at v{to_version}")
        else:
            logger.debug(f"Schema v{to_version} already recorded, skipping.")


def _migrate_v5_split_research_artifacts(db: "DatabaseManager") -> None:
    """P7-4: split research_logs.steps_json.

    Historically each ResearchStep's full ``tool_output`` was stored inside
    the ``steps_json`` column of ``research_logs``. For multi-step research
    (5+ iterations with search_news results), this column can grow to
    several MB per row, which:

      - slows down every read of research_logs (VACUUM, backup, grep)
      - bloats WAL and replication traffic
      - makes the table effectively write-once

    We add a new ``research_artifacts`` table keyed by (step_id, tool_name)
    and rewrite the steps_json column to omit ``tool_output``. Old rows
    are NOT migrated (the pre-v5 ``tool_output`` JSON is left in place —
    it's a one-time legacy write; the new code never re-reads it).
    """
    from sqlalchemy import text as _text
    with db.get_session() as session:
        conn = session.connection()
        # Idempotent: only create if it doesn't exist.
        existing = conn.execute(_text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='research_artifacts'"
        )).fetchone()
        if existing is None:
            conn.execute(_text("""
                CREATE TABLE research_artifacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    research_log_id INTEGER NOT NULL,
                    iteration INTEGER NOT NULL,
                    tool_name TEXT NOT NULL,
                    output_json TEXT NOT NULL,
                    output_size_bytes INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (research_log_id) REFERENCES research_logs(id) ON DELETE CASCADE
                )
            """))
            conn.execute(_text(
                "CREATE INDEX ix_research_artifacts_log ON research_artifacts(research_log_id)"
            ))
            conn.execute(_text(
                "CREATE INDEX ix_research_artifacts_tool ON research_artifacts(tool_name)"
            ))
            logger.info("Created research_artifacts table for splitting large tool outputs")
        session.commit()


def _migrate_v3_add_fts5(db: 'DatabaseManager') -> None:
    """P5-6: Create FTS5 virtual table and triggers for RAG knowledge base.

    The FTS5 table indexes analysis_history.result_json text for full-text
    search, enabling the LLM to reference past analyses when generating new ones.
    """
    from sqlalchemy import text

    with db.get_session() as session:
        conn = session.connection()
        try:
            # Check if FTS table already exists (idempotent)
            result = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='analysis_fts'"
            ))
            if result.fetchone() is not None:
                logger.info("FTS5 table analysis_fts already exists, skipping creation")
                session.commit()
                return

            # Create FTS5 virtual table with content= analysis_history
            conn.execute(text("""
                CREATE VIRTUAL TABLE IF NOT EXISTS analysis_fts USING fts5(
                    code, stock_name, result_text,
                    content='analysis_history', content_rowid='id'
                )
            """))
            logger.info("Created FTS5 virtual table: analysis_fts")

            # Create triggers to keep FTS index in sync
            # Check each trigger exists before creating (compatible with older SQLite)
            for trigger_name, trigger_sql in [
                ("analysis_fts_ai", """
                    CREATE TRIGGER analysis_fts_ai AFTER INSERT ON analysis_history BEGIN
                        INSERT INTO analysis_fts(rowid, code, stock_name, result_text)
                        VALUES (new.id, new.code,
                                COALESCE(
                                    (SELECT json_extract(new.result_json, '$.name')),
                                    (SELECT json_extract(new.result_json, '$.code')),
                                    new.code
                                ),
                                COALESCE(new.result_json, ''));
                    END
                """),
                ("analysis_fts_ad", """
                    CREATE TRIGGER analysis_fts_ad AFTER DELETE ON analysis_history BEGIN
                        INSERT INTO analysis_fts(analysis_fts, rowid, code, stock_name, result_text)
                        VALUES ('delete', old.id, old.code, '', '');
                    END
                """),
                ("analysis_fts_au", """
                    CREATE TRIGGER analysis_fts_au AFTER UPDATE ON analysis_history BEGIN
                        INSERT INTO analysis_fts(analysis_fts, rowid, code, stock_name, result_text)
                        VALUES ('delete', old.id, old.code, '', '');
                        INSERT INTO analysis_fts(rowid, code, stock_name, result_text)
                        VALUES (new.id, new.code,
                                COALESCE(
                                    (SELECT json_extract(new.result_json, '$.name')),
                                    (SELECT json_extract(new.result_json, '$.code')),
                                    new.code
                                ),
                                COALESCE(new.result_json, ''));
                    END
                """),
            ]:
                existing = conn.execute(text(
                    "SELECT name FROM sqlite_master WHERE type='trigger' AND name=:name"
                ), {"name": trigger_name}).fetchone()
                if existing is None:
                    conn.execute(text(trigger_sql))
                    logger.debug(f"Created trigger: {trigger_name}")

            logger.info("Created FTS5 triggers (INSERT/UPDATE/DELETE)")

            # Rebuild index from existing data
            conn.execute(text(
                "INSERT INTO analysis_fts(analysis_fts) VALUES ('rebuild')"
            ))
            logger.info("Rebuilt FTS5 index from existing analysis_history data")

            session.commit()
        except Exception as e:
            session.rollback()
            logger.warning(f"FTS5 migration v3 failed (non-fatal): {e}")
            # Don't raise — FTS is an enhancement, not a critical path


# === 数据模型定义 ===

class SchemaVersion(Base):
    """数据库 schema 版本记录（用于迁移）"""
    __tablename__ = 'schema_version'

    id = Column(Integer, primary_key=True, autoincrement=True)
    version = Column(Integer, nullable=False, default=1)
    applied_at = Column(DateTime, default=datetime.now)
    description = Column(String(200))


class StockDaily(Base):
    """
    股票日线数据模型
    
    存储每日行情数据和计算的技术指标
    支持多股票、多日期的唯一约束
    """
    __tablename__ = 'stock_daily'
    
    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # 股票代码（如 600519, 000001）
    code = Column(String(10), nullable=False, index=True)
    
    # 交易日期
    date = Column(Date, nullable=False, index=True)
    
    # OHLC 数据
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    
    # 成交数据
    volume = Column(Float)  # 成交量（股）
    amount = Column(Float)  # 成交额（元）
    pct_chg = Column(Float)  # 涨跌幅（%）
    
    # 技术指标
    ma5 = Column(Float)
    ma10 = Column(Float)
    ma20 = Column(Float)
    volume_ratio = Column(Float)  # 量比
    
    # 数据来源
    data_source = Column(String(50))  # 记录数据来源（如 AkshareFetcher）
    
    # 更新时间
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # 唯一约束：同一股票同一日期只能有一条数据
    __table_args__ = (
        UniqueConstraint('code', 'date', name='uix_code_date'),
        Index('ix_code_date', 'code', 'date'),
    )
    
    def __repr__(self):
        return f"<StockDaily(code={self.code}, date={self.date}, close={self.close})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'code': self.code,
            'date': self.date,
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume,
            'amount': self.amount,
            'pct_chg': self.pct_chg,
            'ma5': self.ma5,
            'ma10': self.ma10,
            'ma20': self.ma20,
            'volume_ratio': self.volume_ratio,
            'data_source': self.data_source,
        }


class DailyHistory(Base):
    """
    每日行情历史原始数据

    与 stock_daily 的区别：daily_history 仅存储原始 OHLCV 数据，
    不包含技术指标，作为数据获取动作 (get_kline_data) 的持久化记录。
    支持幂等插入（code + date 唯一约束）。
    """
    __tablename__ = 'daily_history'

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(10), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)
    pct_chg = Column(Float)
    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        UniqueConstraint('code', 'date', name='uix_daily_history_code_date'),
        Index('ix_daily_history_code_date', 'code', 'date'),
    )

    def __repr__(self):
        return f"<DailyHistory(code={self.code}, date={self.date}, close={self.close})>"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'code': self.code,
            'date': self.date.isoformat() if isinstance(self.date, date) else str(self.date),
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume,
            'pct_chg': self.pct_chg,
        }


class DatabaseManager:
    """
    数据库管理器 - 单例模式
    
    职责：
    1. 管理数据库连接池
    2. 提供 Session 上下文管理
    3. 封装数据存取操作
    """
    
    _instance: Optional['DatabaseManager'] = None
    
    def __new__(cls, *args, **kwargs):
        """单例模式实现"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, db_url: Optional[str] = None):
        """
        初始化数据库管理器
        
        Args:
            db_url: 数据库连接 URL（可选，默认从配置读取）
        """
        if self._initialized:
            return
        
        if db_url is None:
            config = get_config()
            db_url = config.get_db_url()
        
        # 创建数据库引擎
        self._engine = create_engine(
            db_url,
            echo=False,  # 设为 True 可查看 SQL 语句
            pool_pre_ping=True,  # 连接健康检查
        )
        
        # 创建 Session 工厂
        self._SessionLocal = sessionmaker(
            bind=self._engine,
            autocommit=False,
            autoflush=False,
        )
        
        # 创建所有表
        Base.metadata.create_all(self._engine)

        # Migration: ensure task_id column exists in analysis_history
        self._migrate_analysis_history_task_id()

        # Ensure schema version is recorded and run migrations if needed
        existing_version = self.ensure_schema_version()
        if existing_version < CURRENT_SCHEMA_VERSION:
            _run_migrations(self, existing_version, CURRENT_SCHEMA_VERSION)

        # Initialize FTS5 full-text index for RAG knowledge base
        self._init_fts5()

        self._initialized = True
        logger.info(f"数据库初始化完成: {db_url}")

        # 注册退出钩子，确保程序退出时关闭数据库连接
        atexit.register(DatabaseManager._cleanup_engine, self._engine)
    
    @classmethod
    def get_instance(cls) -> 'DatabaseManager':
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def reset_instance(cls) -> None:
        """重置单例（用于测试）"""
        if cls._instance is not None:
            cls._instance._engine.dispose()
            cls._instance = None

    @classmethod
    def _cleanup_engine(cls, engine) -> None:
        """
        清理数据库引擎（atexit 钩子）

        确保程序退出时关闭所有数据库连接，避免 ResourceWarning

        Args:
            engine: SQLAlchemy 引擎对象
        """
        try:
            if engine is not None:
                engine.dispose()
                logger.debug("数据库引擎已清理")
        except Exception as e:
            logger.warning(f"清理数据库引擎时出错: {e}")
    
    def get_session(self) -> Session:
        """
        获取数据库 Session
        
        使用示例:
            with db.get_session() as session:
                # 执行查询
                session.commit()  # 如果需要
        """
        session = self._SessionLocal()
        try:
            return session
        except Exception:
            session.close()
            raise

    @contextmanager
    def session_scope(self) -> Session:
        """Provide a transactional scope around a series of operations.

        Commits on clean exit, rolls back on exception, always closes.
        Prefer this over :meth:`get_session` for any multi-statement work
        because it makes commit/rollback boundaries explicit and is
        independent of the underlying SQLAlchemy session protocol.

        Usage:
            with db.session_scope() as session:
                session.add(thing)
                # commit happens automatically on block exit
        """
        session = self._SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _migrate_analysis_history_task_id(self):
        """Add task_id column to analysis_history if it doesn't exist (migration from v1 schema)."""
        from sqlalchemy import text
        try:
            with self.get_session() as session:
                # Check if task_id column exists
                result = session.execute(text("PRAGMA table_info(analysis_history)"))
                columns = [row[1] for row in result.fetchall()]
                if 'task_id' not in columns:
                    session.execute(text("ALTER TABLE analysis_history ADD COLUMN task_id VARCHAR(50)"))
                    session.commit()
                    logger.info("Migration: added task_id column to analysis_history")
        except Exception as e:
            logger.warning(f"Migration check failed: {e}")

    def _init_fts5(self):
        """Create FTS5 full-text index on analysis_history for RAG knowledge base.

        Uses standalone FTS5 mode (not content-sync) because the indexed fields
        (analysis_summary, trend_analysis, risk_alerts) are extracted from the
        JSON result_json column via json_extract(). INSERT/UPDATE/DELETE triggers
        keep the FTS5 index in sync automatically.
        """
        from sqlalchemy import text
        try:
            with self.get_session() as session:
                # Drop any pre-existing FTS5 table with wrong schema (e.g. from
                # earlier content-sync mode that doesn't store these columns).
                session.execute(text(
                    "DROP TABLE IF EXISTS analysis_fts"
                ))
                # Create standalone FTS5 virtual table (no content= binding;
                # columns store their own data independently of content table).
                session.execute(text("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS analysis_fts USING fts5(
                        code, analysis_summary, trend_analysis, risk_alerts
                    )
                """))
                # Drop old triggers first (they may reference stale column schemas)
                session.execute(text(
                    "DROP TRIGGER IF EXISTS analysis_fts_insert"
                ))
                session.execute(text(
                    "DROP TRIGGER IF EXISTS analysis_fts_delete"
                ))
                session.execute(text(
                    "DROP TRIGGER IF EXISTS analysis_fts_update"
                ))
                # Trigger: keep FTS5 in sync on INSERT
                session.execute(text("""
                    CREATE TRIGGER IF NOT EXISTS analysis_fts_insert
                    AFTER INSERT ON analysis_history BEGIN
                        INSERT INTO analysis_fts(rowid, code, analysis_summary,
                            trend_analysis, risk_alerts)
                        VALUES (
                            new.rowid, new.code,
                            COALESCE(json_extract(new.result_json, '$.analysis_summary'), ''),
                            COALESCE(json_extract(new.result_json, '$.trend_analysis'), ''),
                            COALESCE(json_extract(new.result_json, '$.risk_alerts'), '')
                        );
                    END
                """))
                # Trigger: keep FTS5 in sync on DELETE
                session.execute(text("""
                    CREATE TRIGGER IF NOT EXISTS analysis_fts_delete
                    AFTER DELETE ON analysis_history BEGIN
                        DELETE FROM analysis_fts WHERE rowid = old.rowid;
                    END
                """))
                # Trigger: keep FTS5 in sync on UPDATE
                session.execute(text("""
                    CREATE TRIGGER IF NOT EXISTS analysis_fts_update
                    AFTER UPDATE ON analysis_history BEGIN
                        DELETE FROM analysis_fts WHERE rowid = old.rowid;
                        INSERT INTO analysis_fts(rowid, code, analysis_summary,
                            trend_analysis, risk_alerts)
                        VALUES (
                            new.rowid, new.code,
                            COALESCE(json_extract(new.result_json, '$.analysis_summary'), ''),
                            COALESCE(json_extract(new.result_json, '$.trend_analysis'), ''),
                            COALESCE(json_extract(new.result_json, '$.risk_alerts'), '')
                        );
                    END
                """))
                session.commit()
                logger.info("FTS5 full-text index initialized for analysis_history")
        except Exception as e:
            logger.warning(f"FTS5 initialization failed (non-critical): {e}")

    def has_today_data(self, code: str, target_date: Optional[date] = None) -> bool:
        """
        检查是否已有指定日期的数据
        
        用于断点续传逻辑：如果已有数据则跳过网络请求
        
        Args:
            code: 股票代码
            target_date: 目标日期（默认今天）
            
        Returns:
            是否存在数据
        """
        if target_date is None:
            target_date = date.today()
        
        with self.get_session() as session:
            result = session.execute(
                select(StockDaily).where(
                    and_(
                        StockDaily.code == code,
                        StockDaily.date == target_date
                    )
                )
            ).scalar_one_or_none()
            
            return result is not None
    
    def get_latest_data(
        self, 
        code: str, 
        days: int = 2
    ) -> List[StockDaily]:
        """
        获取最近 N 天的数据
        
        用于计算"相比昨日"的变化
        
        Args:
            code: 股票代码
            days: 获取天数
            
        Returns:
            StockDaily 对象列表（按日期降序）
        """
        with self.get_session() as session:
            results = session.execute(
                select(StockDaily)
                .where(StockDaily.code == code)
                .order_by(desc(StockDaily.date))
                .limit(days)
            ).scalars().all()
            
            return list(results)
    
    def get_data_range(
        self, 
        code: str, 
        start_date: date, 
        end_date: date
    ) -> List[StockDaily]:
        """
        获取指定日期范围的数据
        
        Args:
            code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            StockDaily 对象列表
        """
        with self.get_session() as session:
            results = session.execute(
                select(StockDaily)
                .where(
                    and_(
                        StockDaily.code == code,
                        StockDaily.date >= start_date,
                        StockDaily.date <= end_date
                    )
                )
                .order_by(StockDaily.date)
            ).scalars().all()
            
            return list(results)
    
    def save_daily_data(
        self, 
        df: pd.DataFrame, 
        code: str,
        data_source: str = "Unknown"
    ) -> int:
        """
        保存日线数据到数据库
        
        策略：
        - 使用 UPSERT 逻辑（存在则更新，不存在则插入）
        - 跳过已存在的数据，避免重复
        
        Args:
            df: 包含日线数据的 DataFrame
            code: 股票代码
            data_source: 数据来源名称
            
        Returns:
            新增/更新的记录数
        """
        if df is None or df.empty:
            logger.warning(f"保存数据为空，跳过 {code}")
            return 0
        
        saved_count = 0
        
        with self.get_session() as session:
            try:
                for _, row in df.iterrows():
                    # 解析日期
                    row_date = row.get('date')
                    if isinstance(row_date, str):
                        row_date = datetime.strptime(row_date, '%Y-%m-%d').date()
                    elif isinstance(row_date, datetime):
                        row_date = row_date.date()
                    elif isinstance(row_date, pd.Timestamp):
                        row_date = row_date.date()
                    
                    # 检查是否已存在
                    existing = session.execute(
                        select(StockDaily).where(
                            and_(
                                StockDaily.code == code,
                                StockDaily.date == row_date
                            )
                        )
                    ).scalar_one_or_none()
                    
                    if existing:
                        # 更新现有记录
                        existing.open = row.get('open')
                        existing.high = row.get('high')
                        existing.low = row.get('low')
                        existing.close = row.get('close')
                        existing.volume = row.get('volume')
                        existing.amount = row.get('amount')
                        existing.pct_chg = row.get('pct_chg')
                        existing.ma5 = row.get('ma5')
                        existing.ma10 = row.get('ma10')
                        existing.ma20 = row.get('ma20')
                        existing.volume_ratio = row.get('volume_ratio')
                        existing.data_source = data_source
                        existing.updated_at = datetime.now()
                    else:
                        # 创建新记录
                        record = StockDaily(
                            code=code,
                            date=row_date,
                            open=row.get('open'),
                            high=row.get('high'),
                            low=row.get('low'),
                            close=row.get('close'),
                            volume=row.get('volume'),
                            amount=row.get('amount'),
                            pct_chg=row.get('pct_chg'),
                            ma5=row.get('ma5'),
                            ma10=row.get('ma10'),
                            ma20=row.get('ma20'),
                            volume_ratio=row.get('volume_ratio'),
                            data_source=data_source,
                        )
                        session.add(record)
                        saved_count += 1
                
                session.commit()
                logger.info(f"保存 {code} 数据成功，新增 {saved_count} 条")
                
            except Exception as e:
                session.rollback()
                logger.error(f"保存 {code} 数据失败: {e}")
                raise
        
        return saved_count

    def save_daily_history(
        self,
        code: str,
        data: List[Dict[str, Any]],
    ) -> int:
        """
        Save raw OHLCV data to daily_history (idempotent).

        Skips rows where (code, date) already exist.

        Args:
            code: Stock code.
            data: List of dicts, each with keys: date (str), open, high,
                  low, close, volume, pct_chg.

        Returns:
            Number of new rows inserted.
        """
        if not data:
            return 0

        saved = 0
        session = self.get_session()
        try:
            for row in data:
                row_date = row.get('date')
                if isinstance(row_date, str):
                    try:
                        row_date = datetime.strptime(row_date, '%Y-%m-%d').date()
                    except ValueError:
                        row_date = datetime.strptime(row_date, '%Y%m%d').date()
                elif isinstance(row_date, datetime):
                    row_date = row_date.date()

                # Idempotent: skip if already exists
                existing = session.execute(
                    select(DailyHistory).where(
                        and_(
                            DailyHistory.code == code,
                            DailyHistory.date == row_date,
                        )
                    )
                ).scalar_one_or_none()

                if existing is not None:
                    continue

                record = DailyHistory(
                    code=code,
                    date=row_date,
                    open=row.get('open'),
                    high=row.get('high'),
                    low=row.get('low'),
                    close=row.get('close'),
                    volume=row.get('volume'),
                    pct_chg=row.get('pct_chg'),
                )
                session.add(record)
                saved += 1

            session.commit()
            if saved:
                logger.info(f"daily_history: saved {saved} new rows for {code}")
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

        return saved

    def get_daily_history(
        self,
        code: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve OHLCV history from daily_history.

        Args:
            code: Stock code.
            start_date: Inclusive start date (optional).
            end_date: Inclusive end date (optional).

        Returns:
            List of dicts ordered by date ascending.
        """
        with self.get_session() as session:
            conditions = [DailyHistory.code == code]
            if start_date is not None:
                conditions.append(DailyHistory.date >= start_date)
            if end_date is not None:
                conditions.append(DailyHistory.date <= end_date)

            results = session.execute(
                select(DailyHistory)
                .where(and_(*conditions))
                .order_by(DailyHistory.date)
            ).scalars().all()

            return [r.to_dict() for r in results]

    def get_analysis_context(
        self,
        code: str,
        target_date: Optional[date] = None
    ) -> Optional[Dict[str, Any]]:
        """
        获取分析所需的上下文数据
        
        返回今日数据 + 昨日数据的对比信息
        
        Args:
            code: 股票代码
            target_date: 目标日期（默认今天）
            
        Returns:
            包含今日数据、昨日对比等信息的字典
        """
        if target_date is None:
            target_date = date.today()
        
        # 获取最近2天数据
        recent_data = self.get_latest_data(code, days=2)
        
        if not recent_data:
            logger.warning(f"未找到 {code} 的数据")
            return None
        
        today_data = recent_data[0]
        yesterday_data = recent_data[1] if len(recent_data) > 1 else None
        
        # Determine market type: CN (6-digit numeric), HK (5-digit), US (alpha)
        market = self._detect_market(code)

        context = {
            'code': code,
            'date': today_data.date.isoformat(),
            'market': market,
            'today': today_data.to_dict(),
        }
        
        if yesterday_data:
            context['yesterday'] = yesterday_data.to_dict()
            
            # 计算相比昨日的变化
            if yesterday_data.volume and yesterday_data.volume > 0:
                context['volume_change_ratio'] = round(
                    today_data.volume / yesterday_data.volume, 2
                )
            
            if yesterday_data.close and yesterday_data.close > 0:
                context['price_change_ratio'] = round(
                    (today_data.close - yesterday_data.close) / yesterday_data.close * 100, 2
                )
            
            # 均线形态判断
            context['ma_status'] = self._analyze_ma_status(today_data)
        
        return context

    @staticmethod
    def _detect_market(code: str) -> str:
        """Detect market type from stock code.

        Returns:
            "CN" for A-shares (6-digit numeric), "HK" for HK stocks (5-digit),
            "US" for US stocks (alphabetic).
        """
        code_upper = code.upper().replace(".", "")
        if code_upper.startswith("HK"):
            return "HK"
        elif code_upper.isdigit() and len(code_upper) == 5:
            return "HK"
        elif code_upper.isalpha() and len(code_upper) <= 5:
            return "US"
        elif code_upper.isdigit() and len(code_upper) == 6:
            return "CN"
        else:
            return "Unknown"

    def _analyze_ma_status(self, data: StockDaily) -> str:
        """
        分析均线形态

        判断条件：
        - 多头排列：close > ma5 > ma10 > ma20
        - 空头排列：close < ma5 < ma10 < ma20
        - 震荡整理：其他情况
        """
        close = data.close or 0
        ma5 = data.ma5 or 0
        ma10 = data.ma10 or 0
        ma20 = data.ma20 or 0

        if close > ma5 > ma10 > ma20 > 0:
            return "多头排列 📈"
        elif close < ma5 < ma10 < ma20 and ma20 > 0:
            return "空头排列 📉"
        elif close > ma5 and ma5 > ma10:
            return "短期向好 🔼"
        elif close < ma5 and ma5 < ma10:
            return "短期走弱 🔽"
        else:
            return "震荡整理 ↔️"

    def save_analysis_history(
        self,
        code: str,
        status: str,
        result_json: Optional[str] = None,
        error: Optional[str] = None
    ) -> int:
        """
        保存分析历史记录

        Args:
            code: 股票代码
            status: 状态（pending/running/done/failed）
            result_json: 分析结果 JSON 字符串
            error: 错误信息

        Returns:
            新增记录的 ID
        """
        with self.get_session() as session:
            history = AnalysisHistory(
                code=code,
                timestamp=datetime.now(),
                status=status,
                result_json=result_json,
                error=error
            )
            session.add(history)
            session.commit()
            return history.id

    def get_analysis_history(
        self,
        limit: int = 50
    ) -> List[AnalysisHistory]:
        """
        获取分析历史记录

        Args:
            limit: 返回记录数限制

        Returns:
            AnalysisHistory 对象列表（按时间降序）
        """
        with self.get_session() as session:
            results = session.execute(
                select(AnalysisHistory)
                .order_by(desc(AnalysisHistory.timestamp))
                .limit(limit)
            ).scalars().all()
            return list(results)

    def get_analysis_history_by_code(
        self,
        code: str,
        limit: int = 10
    ) -> List[AnalysisHistory]:
        """
        获取指定股票的分析历史记录

        Args:
            code: 股票代码
            limit: 返回记录数限制

        Returns:
            AnalysisHistory 对象列表（按时间降序）
        """
        with self.get_session() as session:
            results = session.execute(
                select(AnalysisHistory)
                .where(AnalysisHistory.code == code)
                .order_by(desc(AnalysisHistory.timestamp))
                .limit(limit)
            ).scalars().all()
            return list(results)

    def search_analyses(
        self,
        query: str,
        code: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """P5-6: Full-text search analysis_history via FTS5.

        Searches the result_json text of past analyses.  Optionally filters
        by stock code.

        Args:
            query: FTS5 search query string.
            code: Optional stock code filter.
            limit: Maximum number of results (default 5).

        Returns:
            List of dicts with keys: id, code, stock_name, timestamp,
            result_json, score (relevance rank).  Returns empty list when
            the FTS index doesn't exist yet (graceful degradation).
        """
        import re as _re
        import time as _time
        from sqlalchemy import text as _text

        def _fts5_safe_query(query: str) -> str:
            """Prepare a FTS5-compatible query string.

            Adds prefix matching (*) to each token. For Chinese tokens that
            FTS5 cannot prefix-match (e.g. '盘整' in '高位盘整'), the result
            will fall back to a LIKE-based secondary search handled by the
            caller.
            """
            tokens = query.split()
            prefixed = []
            for token in tokens:
                if _re.match(r'^[\w一-鿿]+$', token):
                    prefixed.append(token + '*')
                else:
                    prefixed.append(token)
            return ' '.join(prefixed)

        t0 = _time.time()
        try:
            with self.get_session() as session:
                conn = session.connection()
                check = conn.execute(_text(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='analysis_fts'"
                ))
                if check.fetchone() is None:
                    logger.debug("FTS5 table not yet created; returning empty results")
                    return []

                fts_query = _fts5_safe_query(query)

                if code:
                    sql = _text("""
                        SELECT rowid AS id, code, analysis_summary, trend_analysis, risk_alerts, rank
                        FROM analysis_fts
                        WHERE analysis_fts MATCH :query AND code = :code
                        ORDER BY rank
                        LIMIT :limit
                    """)
                    rows = conn.execute(sql, {"query": fts_query, "code": code, "limit": limit}).fetchall()
                else:
                    sql = _text("""
                        SELECT rowid AS id, code, analysis_summary, trend_analysis, risk_alerts, rank
                        FROM analysis_fts
                        WHERE analysis_fts MATCH :query
                        ORDER BY rank
                        LIMIT :limit
                    """)
                    rows = conn.execute(sql, {"query": fts_query, "limit": limit}).fetchall()

                # Fallback: if FTS returned no results for a multi-character
                # Chinese query, try LIKE-based search on the content table.
                # This handles cases where FTS5 tokenized the content as a single
                # token (e.g. '高位盘整') and the query token (e.g. '盘整')
                # cannot match as a prefix.
                if not rows and len(query.strip()) >= 2 and not any(c in query for c in '*()":'):
                    like_pattern = f"%{query.replace(' ', '%')}%"
                    if code:
                        like_rows = conn.execute(
                            _text("""
                                SELECT id AS rowid, code,
                                    COALESCE(json_extract(result_json, '$.analysis_summary'), '') AS analysis_summary,
                                    '' AS trend_analysis, '' AS risk_alerts,
                                    0.0 AS rank
                                FROM analysis_history
                                WHERE result_json LIKE :pattern AND code = :code
                                ORDER BY timestamp DESC LIMIT :limit
                            """),
                            {"pattern": like_pattern, "code": code, "limit": limit}
                        ).fetchall()
                    else:
                        like_rows = conn.execute(
                            _text("""
                                SELECT id AS rowid, code,
                                    COALESCE(json_extract(result_json, '$.analysis_summary'), '') AS analysis_summary,
                                    '' AS trend_analysis, '' AS risk_alerts,
                                    0.0 AS rank
                                FROM analysis_history
                                WHERE result_json LIKE :pattern
                                ORDER BY timestamp DESC LIMIT :limit
                            """),
                            {"pattern": like_pattern, "limit": limit}
                        ).fetchall()
                    rows = like_rows

                results = []
                for row in rows:
                    row_id = row[0]
                    # Fetch timestamp from the content table
                    ts_result = conn.execute(
                        _text("SELECT timestamp FROM analysis_history WHERE id = :id"),
                        {"id": row_id}
                    ).fetchone()
                    timestamp = ts_result[0] if ts_result else None
                    # Fetch stock name from result_json if available
                    name_result = conn.execute(
                        _text("SELECT json_extract(result_json, '$.name') FROM analysis_history WHERE id = :id"),
                        {"id": row_id}
                    ).fetchone()
                    stock_name = name_result[0] if name_result and name_result[0] else ""

                    results.append({
                        "id": row_id,
                        "code": row[1],
                        "stock_name": stock_name,
                        "result_text": row[2] or "",
                        "score": row[5] if len(row) > 5 else 0.0,
                        "timestamp": timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp) if timestamp else None,
                    })

                elapsed = (_time.time() - t0) * 1000
                logger.debug(f"FTS search '{query[:50]}' returned {len(results)} results in {elapsed:.1f}ms")
                return results
        except Exception as e:
            logger.warning(f"FTS search failed (non-fatal): {e}")
            return []

    def rebuild_fts_index(self) -> bool:
        """P5-6: Rebuild the FTS5 index from the content table.

        Useful after bulk imports or data migrations.  Returns True on
        success, False when the FTS table doesn't exist yet.
        """
        from sqlalchemy import text as _text
        import time as _time

        t0 = _time.time()
        try:
            with self.get_session() as session:
                conn = session.connection()
                check = conn.execute(_text(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='analysis_fts'"
                ))
                if check.fetchone() is None:
                    logger.debug("FTS5 table not yet created; cannot rebuild")
                    return False

                # Clear FTS table and rebuild from content table
                # (standalone FTS5 tables need manual repopulation; rebuild
                # command only works with content= binding)
                conn.execute(_text("DELETE FROM analysis_fts"))
                conn.execute(_text("""
                    INSERT INTO analysis_fts(rowid, code, analysis_summary,
                        trend_analysis, risk_alerts)
                    SELECT
                        ah.id,
                        ah.code,
                        COALESCE(json_extract(ah.result_json, '$.analysis_summary'), ''),
                        COALESCE(json_extract(ah.result_json, '$.trend_analysis'), ''),
                        COALESCE(json_extract(ah.result_json, '$.risk_alerts'), '')
                    FROM analysis_history ah
                    WHERE ah.result_json IS NOT NULL
                """))
                session.commit()
                elapsed = (_time.time() - t0) * 1000
                logger.info(f"FTS5 index rebuilt in {elapsed:.1f}ms")
                return True
        except Exception as e:
            logger.warning(f"FTS5 rebuild failed: {e}")
            return False

    def ensure_schema_version(self) -> int:
        """Ensure schema_version table is populated. Returns current version."""
        with self.get_session() as session:
            try:
                existing = session.execute(
                    select(SchemaVersion).order_by(desc(SchemaVersion.version))
                ).scalars().first()

                if existing is None:
                    # First run: record current version
                    sv = SchemaVersion(version=CURRENT_SCHEMA_VERSION,
                                       description="Initial schema with stock_daily + analysis_history")
                    session.add(sv)
                    session.commit()
                    logger.info(f"Schema version set to {CURRENT_SCHEMA_VERSION}")
                    return CURRENT_SCHEMA_VERSION
                return existing.version
            except Exception:
                session.rollback()
                raise

    def save_task(self, task_id: str, code: str, status: str,
                  result_json: str = None, error: str = None) -> None:
        """Save or update a task in AnalysisHistory"""
        with self.get_session() as session:
            try:
                existing = session.execute(
                    select(AnalysisHistory).where(AnalysisHistory.task_id == task_id)
                ).scalars().first()

                if existing:
                    existing.status = status
                    if result_json is not None:
                        existing.result_json = result_json
                    if error is not None:
                        existing.error = error
                else:
                    entry = AnalysisHistory(
                        task_id=task_id,
                        code=code,
                        status=status,
                        result_json=result_json,
                        error=error,
                    )
                    session.add(entry)
                session.commit()
            except Exception:
                session.rollback()
                raise

    def load_tasks(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Load recent tasks from database"""
        with self.get_session() as session:
            try:
                results = session.execute(
                    select(AnalysisHistory)
                    .order_by(desc(AnalysisHistory.timestamp))
                    .limit(limit)
                ).scalars().all()
                return [r.to_dict() for r in results]
            except Exception:
                session.rollback()
                return []

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get a single task by ID"""
        with self.get_session() as session:
            try:
                result = session.execute(
                    select(AnalysisHistory).where(AnalysisHistory.task_id == task_id)
                ).scalars().first()
                return result.to_dict() if result else None
            except Exception:
                session.rollback()
                return None

    # === Task Log CRUD (task_log table) ===

    def save_task_log(self, task_id: str, action: str, code: str,
                      status: str = "pending",
                      result_json: Optional[str] = None) -> None:
        """Create a new entry in task_log or update if task_id exists."""
        with self.get_session() as session:
            try:
                existing = session.execute(
                    select(TaskLog).where(TaskLog.task_id == task_id)
                ).scalars().first()

                if existing:
                    existing.status = status
                    if result_json is not None:
                        existing.result_json = result_json
                else:
                    entry = TaskLog(
                        task_id=task_id,
                        action=action,
                        code=code,
                        status=status,
                        result_json=result_json,
                    )
                    session.add(entry)
                session.commit()
            except Exception:
                session.rollback()
                raise

    def update_task_log(self, task_id: str, status: str,
                        completed_at: Optional[datetime] = None,
                        result_json: Optional[str] = None) -> None:
        """Update status (and optionally result) of an existing task_log entry."""
        with self.get_session() as session:
            try:
                entry = session.execute(
                    select(TaskLog).where(TaskLog.task_id == task_id)
                ).scalars().first()
                if entry is None:
                    logger.warning(f"update_task_log: task_id {task_id} not found")
                    return
                entry.status = status
                if completed_at is not None:
                    entry.completed_at = completed_at
                else:
                    entry.completed_at = datetime.now()
                if result_json is not None:
                    entry.result_json = result_json
                session.commit()
            except Exception:
                session.rollback()
                raise

    def get_task_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return recent task_log entries (most recent first)."""
        with self.get_session() as session:
            try:
                results = session.execute(
                    select(TaskLog)
                    .order_by(desc(TaskLog.created_at))
                    .limit(limit)
                ).scalars().all()
                return [r.to_dict() for r in results]
            except Exception:
                session.rollback()
                return []

    def get_task_log(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get a single task_log entry by task_id."""
        with self.get_session() as session:
            try:
                result = session.execute(
                    select(TaskLog).where(TaskLog.task_id == task_id)
                ).scalars().first()
                return result.to_dict() if result else None
            except Exception:
                session.rollback()
                return None

    # === Position CRUD ===

    def save_position(self, code: str, name: str, shares: float, buy_price: float,
                      buy_date: date, current_price: Optional[float] = None) -> Position:
        """Create a new position"""
        with self.get_session() as session:
            position = Position(
                code=code,
                name=name,
                shares=shares,
                buy_price=buy_price,
                buy_date=buy_date,
                current_price=current_price or buy_price,
            )
            session.add(position)
            session.commit()
            session.refresh(position)
            return position

    def get_positions(self) -> List[Position]:
        """Get all positions"""
        with self.get_session() as session:
            results = session.execute(
                select(Position).order_by(desc(Position.created_at))
            ).scalars().all()
            return list(results)

    def get_position(self, position_id: int) -> Optional[Position]:
        """Get a position by ID"""
        with self.get_session() as session:
            return session.execute(
                select(Position).where(Position.id == position_id)
            ).scalars().first()

    def update_position(self, position_id: int, **kwargs) -> Optional[Position]:
        """Update a position (current_price, shares, buy_price)"""
        with self.get_session() as session:
            position = session.execute(
                select(Position).where(Position.id == position_id)
            ).scalars().first()
            if not position:
                return None
            for key, value in kwargs.items():
                if hasattr(position, key) and value is not None:
                    setattr(position, key, value)
            position.updated_at = datetime.now()
            session.commit()
            session.refresh(position)
            return position

    def delete_position(self, position_id: int) -> bool:
        """Delete a position by ID"""
        with self.get_session() as session:
            position = session.execute(
                select(Position).where(Position.id == position_id)
            ).scalars().first()
            if not position:
                return False
            session.delete(position)
            session.commit()
            return True

    # === Market CRUD ===

    def save_market(self, code: str, name: str, price: float,
                    change_pct: float, volume: int) -> Market:
        """Create or update a market entry"""
        with self.get_session() as session:
            existing = session.execute(
                select(Market).where(Market.code == code)
            ).scalars().first()
            if existing:
                existing.name = name
                existing.price = price
                existing.change_pct = change_pct
                existing.volume = volume
                existing.updated_at = datetime.now()
                session.commit()
                return existing
            else:
                market = Market(
                    code=code,
                    name=name,
                    price=price,
                    change_pct=change_pct,
                    volume=volume,
                )
                session.add(market)
                session.commit()
                return market

    def get_markets(self) -> List[Market]:
        """Get all markets"""
        with self.get_session() as session:
            results = session.execute(
                select(Market)
            ).scalars().all()
            return list(results)

    def get_market(self, code: str) -> Optional[Market]:
        """Get a market by code"""
        with self.get_session() as session:
            return session.execute(
                select(Market).where(Market.code == code)
            ).scalars().first()

    # === Market Data Cache (for network degradation fallback) ===

    def save_market_cache(self, code: str, data: Dict[str, Any], data_source: str) -> None:
        """Save market data to cache for fallback when network fails"""
        cache = get_market_cache()
        cache.set(code, data, data_source)

    def get_market_cache(self, code: str) -> Optional[Dict[str, Any]]:
        """Get cached market data"""
        cache = get_market_cache()
        return cache.get(code)

    def get_market_cache_with_staleness(self, code: str) -> tuple[Optional[Dict[str, Any]], bool, float]:
        """Get cached market data with staleness info. Returns (data, is_stale, age_seconds)"""
        cache = get_market_cache()
        return cache.get_with_staleness(code)

    # === Alert CRUD ===

    def save_alert(self, stock: str, condition: str, threshold: float,
                   channel: str = 'wechat', enabled: bool = True) -> Alert:
        """Create a new alert"""
        with self.get_session() as session:
            alert = Alert(
                stock=stock,
                condition=condition,
                threshold=threshold,
                channel=channel,
                enabled=1 if enabled else 0,
            )
            session.add(alert)
            session.commit()
            session.refresh(alert)
            return alert

    def get_alerts(self) -> List[Alert]:
        """Get all alerts"""
        with self.get_session() as session:
            results = session.execute(
                select(Alert).order_by(desc(Alert.created_at))
            ).scalars().all()
            return list(results)

    def get_alert(self, alert_id: int) -> Optional[Alert]:
        """Get an alert by ID"""
        with self.get_session() as session:
            return session.execute(
                select(Alert).where(Alert.id == alert_id)
            ).scalars().first()

    def toggle_alert(self, alert_id: int) -> Optional[Alert]:
        """Toggle alert enabled state"""
        with self.get_session() as session:
            alert = session.execute(
                select(Alert).where(Alert.id == alert_id)
            ).scalars().first()
            if not alert:
                return None
            alert.enabled = 0 if alert.enabled else 1
            alert.updated_at = datetime.now()
            session.commit()
            session.refresh(alert)
            return alert

    def delete_alert(self, alert_id: int) -> bool:
        """Delete an alert by ID"""
        with self.get_session() as session:
            alert = session.execute(
                select(Alert).where(Alert.id == alert_id)
            ).scalars().first()
            if not alert:
                return False
            session.delete(alert)
            session.commit()
            return True

    # === Notification CRUD ===

    def save_notification(self, title: str, message: str, level: str = "info",
                          category: str = "system", action: Optional[str] = None) -> Optional[int]:
        """Add a notification and enforce max 500 stored rows."""
        with self.get_session() as session:
            # Enforce max 500 notifications
            count = session.query(NotificationRecord).count()
            if count >= 500:
                # Delete oldest to make room
                oldest = session.execute(
                    select(NotificationRecord).order_by(NotificationRecord.created_at).limit(1)
                ).scalars().first()
                if oldest:
                    session.delete(oldest)
            record = NotificationRecord(
                title=title, message=message, level=level,
                category=category, action=action,
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            return record.id

    def get_notifications(self, limit: int = 50, category: Optional[str] = None,
                          unread_only: bool = False) -> List[Dict[str, Any]]:
        """Get recent notifications, optionally filtered."""
        with self.get_session() as session:
            conditions = []
            if category:
                conditions.append(NotificationRecord.category == category)
            if unread_only:
                conditions.append(NotificationRecord.read == 0)
            query = select(NotificationRecord).order_by(desc(NotificationRecord.created_at)).limit(limit)
            if conditions:
                query = query.where(and_(*conditions))
            results = session.execute(query).scalars().all()
            return [r.to_dict() for r in results]

    def get_unread_count(self) -> int:
        """Return count of unread notifications."""
        with self.get_session() as session:
            return session.query(NotificationRecord).filter(
                NotificationRecord.read == 0
            ).count()

    def mark_notification_read(self, notification_id: int) -> bool:
        """Mark a single notification as read."""
        with self.get_session() as session:
            record = session.execute(
                select(NotificationRecord).where(NotificationRecord.id == notification_id)
            ).scalars().first()
            if not record:
                return False
            record.read = 1
            session.commit()
            return True

    def mark_all_notifications_read(self) -> int:
        """Mark all notifications as read. Returns count updated."""
        with self.get_session() as session:
            count = session.execute(
                select(NotificationRecord).where(NotificationRecord.read == 0)
            ).scalars().all()
            updated = len(count)
            for record in count:
                record.read = 1
            session.commit()
            return updated

    def clear_old_notifications(self, days: int = 7) -> int:
        """Remove notifications older than `days`. Returns count deleted."""
        cutoff = datetime.now() - timedelta(days=days)
        with self.get_session() as session:
            old = session.execute(
                select(NotificationRecord).where(NotificationRecord.created_at < cutoff)
            ).scalars().all()
            count = len(old)
            for record in old:
                session.delete(record)
            session.commit()
            return count

    # === Simulated Trading Account Persistence ===

    def save_sim_account(self, account_data: Optional[Dict]) -> None:
        """Save simulated trading account state as JSON.

        Args:
            account_data: Account dict from SimAccount.to_dict(), or None to clear.
        """
        with self.get_session() as session:
            existing = session.execute(
                select(SimAccountRecord)
            ).scalars().first()
            if existing:
                if account_data is None:
                    session.delete(existing)
                else:
                    existing.data_json = json.dumps(account_data, ensure_ascii=False)
                    existing.updated_at = datetime.now()
            elif account_data is not None:
                record = SimAccountRecord(
                    data_json=json.dumps(account_data, ensure_ascii=False),
                )
                session.add(record)
            session.commit()

    def load_sim_account(self) -> Optional[Dict]:
        """Load simulated trading account state from JSON.

        Returns:
            Account dict for SimAccount.from_dict(), or None if not saved.
        """
        with self.get_session() as session:
            record = session.execute(
                select(SimAccountRecord)
            ).scalars().first()
            if record and record.data_json:
                try:
                    return json.loads(record.data_json)
                except json.JSONDecodeError:
                    logger.warning("Failed to decode sim_account JSON; returning None")
                    return None
            return None


class SimAccountRecord(Base):
    """Simulated trading account persistence record."""
    __tablename__ = 'sim_account'

    id = Column(Integer, primary_key=True, default=1)
    data_json = Column(Text)
    updated_at = Column(DateTime, default=datetime.now)

    def __repr__(self):
        return f"<SimAccountRecord(updated_at={self.updated_at})>"


class AnalysisHistory(Base):
    """
    分析历史记录模型

    存储历史分析任务的结果，支持回放功能
    """
    __tablename__ = 'analysis_history'

    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True)

    # 任务 ID（UUID，用于 DataService 关联）
    task_id = Column(String(50), index=True)

    # 股票代码
    code = Column(String(10), nullable=False, index=True)

    # 时间戳
    timestamp = Column(DateTime, default=datetime.now, index=True)

    # 状态：pending/running/completed/failed/cancelled
    status = Column(String(20), default="pending")

    # 分析结果 JSON
    result_json = Column(Text)

    # 错误信息
    error = Column(Text)

    def __repr__(self):
        return f"<AnalysisHistory(task_id={self.task_id}, code={self.code}, status={self.status})>"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'id': self.id,
            'task_id': self.task_id,
            'code': self.code,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'status': self.status,
            'result_json': self.result_json,
            'error': self.error,
        }


class TaskLog(Base):
    """
    任务执行日志

    独立于 AnalysisHistory，专门记录数据服务层（DataService）的任务执行生命周期。
    每个任务从创建到完成都有一条记录，可用于监控和重放。
    """
    __tablename__ = 'task_log'

    task_id = Column(String(50), primary_key=True)
    action = Column(String(50), nullable=False, index=True)
    code = Column(String(10), nullable=False, index=True)
    status = Column(String(20), default="pending", index=True)  # pending/running/done/failed
    created_at = Column(DateTime, default=datetime.now)
    completed_at = Column(DateTime)
    result_json = Column(Text)

    def __repr__(self):
        return f"<TaskLog(task_id={self.task_id}, action={self.action}, status={self.status})>"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'task_id': self.task_id,
            'action': self.action,
            'code': self.code,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'result_json': self.result_json,
        }


class Position(Base):
    """
    持仓记录模型

    存储用户的股票持仓信息
    """
    __tablename__ = 'positions'

    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True)

    # 股票代码
    code = Column(String(10), nullable=False)

    # 股票名称
    name = Column(String(100))

    # 持股数量
    shares = Column(Float, nullable=False)

    # 买入价格
    buy_price = Column(Float, nullable=False)

    # 买入日期
    buy_date = Column(Date, nullable=False)

    # 当前价格
    current_price = Column(Float)

    # 创建时间
    created_at = Column(DateTime, default=datetime.now)

    # 更新时间
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self):
        return f"<Position(code={self.code}, shares={self.shares}, buy_price={self.buy_price})>"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'id': self.id,
            'code': self.code,
            'name': self.name,
            'shares': self.shares,
            'buy_price': self.buy_price,
            'buy_date': self.buy_date.isoformat() if self.buy_date else None,
            'current_price': self.current_price,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class Market(Base):
    """
    市场行情模型

    存储股票市场的实时行情数据
    """
    __tablename__ = 'markets'

    # 股票代码（主键）
    code = Column(String(10), primary_key=True)

    # 股票名称
    name = Column(String(100))

    # 当前价格
    price = Column(Float)

    # 涨跌幅（%）
    change_pct = Column(Float)

    # 成交量
    volume = Column(Integer)

    # 更新时间
    updated_at = Column(DateTime, default=datetime.now)

    def __repr__(self):
        return f"<Market(code={self.code}, name={self.name}, price={self.price})>"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        volume_val = self.volume
        if isinstance(volume_val, bytes):
            volume_val = int.from_bytes(volume_val, byteorder='little')
        return {
            'code': self.code,
            'name': self.name,
            'price': self.price,
            'change_pct': self.change_pct,
            'volume': volume_val,
            'volume_display': format_volume_display(self.volume, self.code),
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


def format_volume_display(volume: float, code: str) -> str:
    """Format volume for display based on market type.

    A股/港股: >=1万 显示 "X.XX万"
    美股: 显示 "X.XXM" / "X.XXK"
    """
    if volume is None:
        return '---'
    try:
        v = float(volume)
        # A股/港股 use 万 (ten thousands)
        if code.startswith('hk') or (len(code) == 6 and code.isdigit() and not code.startswith('9')):
            if v >= 100000000:
                return f"{v/100000000:.1f}亿"
            elif v >= 10000:
                return f"{v/10000:.0f}万"
            return f"{v:.0f}"
        else:
            # US stocks use M/B notation
            if v >= 1000000000:
                return f"{v/1000000000:.1f}B"
            elif v >= 1000000:
                return f"{v/1000000:.1f}M"
            elif v >= 1000:
                return f"{v/1000:.1f}K"
            return f"{v:.0f}"
    except (ValueError, TypeError):
        return '---'


class Alert(Base):
    """告警配置模型"""
    __tablename__ = 'alerts'

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock = Column(String(10), nullable=False)
    condition = Column(String(20), nullable=False)  # price_above, price_below
    threshold = Column(Float, nullable=False)
    channel = Column(String(20), default='wechat')  # wechat, feishu, telegram, email
    enabled = Column(Integer, default=1)  # 1=enabled, 0=disabled
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'stock': self.stock,
            'condition': self.condition,
            'threshold': self.threshold,
            'channel': self.channel,
            'enabled': bool(self.enabled),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class NotificationRecord(Base):
    """In-app notification record model."""
    __tablename__ = 'notifications'

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    message = Column(String(1000), nullable=False)
    level = Column(String(20), nullable=False, default='info')
    category = Column(String(30), nullable=False, default='system')
    action = Column(String(500))
    read = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now, index=True)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'title': self.title,
            'message': self.message,
            'level': self.level,
            'category': self.category,
            'action': self.action,
            'read': bool(self.read),
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class MarketReview(Base):
    """Market review report model (P6-2)."""
    __tablename__ = 'market_reviews'

    id = Column(Integer, primary_key=True, autoincrement=True)
    review_date = Column(String(10), nullable=False, index=True)  # YYYY-MM-DD
    report_md = Column(Text, nullable=False)  # Markdown report
    market_summary = Column(Text)  # Brief summary for listing
    created_at = Column(DateTime, default=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'review_date': self.review_date,
            'report_md': self.report_md,
            'market_summary': self.market_summary,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


    # === P7-1: Backup & Restore ===

    def backup(self, backup_path: Optional[str] = None) -> str:
        """Create a SQL dump backup of the database.

        Args:
            backup_path: Optional path for the backup file.
                         Defaults to data/stock_analysis_backup_<timestamp>.db

        Returns:
            Path to the backup file.
        """
        import shutil
        from datetime import datetime

        if backup_path is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = f"data/stock_analysis_backup_{timestamp}.db"

        # Ensure parent directory exists
        Path(backup_path).parent.mkdir(parents=True, exist_ok=True)

        # Get the source DB path from the engine URL
        source_path = str(self._engine.url).replace('sqlite:///', '')
        if not source_path or source_path == ':memory:':
            logger.warning("Cannot backup in-memory database")
            return ""

        shutil.copy2(source_path, backup_path)
        logger.info(f"Database backed up to {backup_path}")
        return backup_path

    def restore(self, backup_path: str) -> bool:
        """Restore database from a backup file.

        Args:
            backup_path: Path to the backup .db file.

        Returns:
            True if restore succeeded.
        """
        import shutil

        if not Path(backup_path).exists():
            logger.error(f"Backup file not found: {backup_path}")
            return False

        source_path = str(self._engine.url).replace('sqlite:///', '')
        shutil.copy2(backup_path, source_path)
        logger.info(f"Database restored from {backup_path}")
        return True


# 便捷函数
def get_db() -> DatabaseManager:
    """获取数据库管理器实例的快捷方式"""
    return DatabaseManager.get_instance()


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.DEBUG)
    
    db = get_db()
    
    print("=== 数据库测试 ===")
    print(f"数据库初始化成功")
    
    # 测试检查今日数据
    has_data = db.has_today_data('600519')
    print(f"茅台今日是否有数据: {has_data}")
    
    # 测试保存数据
    test_df = pd.DataFrame({
        'date': [date.today()],
        'open': [1800.0],
        'high': [1850.0],
        'low': [1780.0],
        'close': [1820.0],
        'volume': [10000000],
        'amount': [18200000000],
        'pct_chg': [1.5],
        'ma5': [1810.0],
        'ma10': [1800.0],
        'ma20': [1790.0],
        'volume_ratio': [1.2],
    })
    
    saved = db.save_daily_data(test_df, '600519', 'TestSource')
    print(f"保存测试数据: {saved} 条")
    
    # 测试获取上下文
    context = db.get_analysis_context('600519')
    print(f"分析上下文: {context}")