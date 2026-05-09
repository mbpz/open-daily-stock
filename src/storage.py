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
import logging
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

# SQLAlchemy ORM 基类
Base = declarative_base()

# Current database schema version
CURRENT_SCHEMA_VERSION = 2


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

        # Ensure schema version is recorded
        self.ensure_schema_version()

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
        
        context = {
            'code': code,
            'date': today_data.date.isoformat(),
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
        return {
            'code': self.code,
            'name': self.name,
            'price': self.price,
            'change_pct': self.change_pct,
            'volume': self.volume,
            'volume_display': self._format_volume_display(),
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def _format_volume_display(self) -> str:
        """Format volume for display based on market type"""
        if self.volume is None:
            return '---'
        try:
            v = float(self.volume)
            code = self.code or ''
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
