"""
信号总线模块
用于模块间的信号传递和事件通知
"""

from typing import Callable, Dict, List, Any
from datetime import datetime
from enum import Enum


class SignalType(Enum):
    """信号类型枚举"""
    BUY = "buy"                    # 买入信号
    SELL = "sell"                  # 卖出信号
    SECTOR_SCANNED = "sector_scanned"  # 板块扫描完成
    POOL_INITIALIZED = "pool_initialized"  # 监控池初始化完成
    MONITOR_STARTED = "monitor_started"    # 监控启动
    MONITOR_STOPPED = "monitor_stopped"    # 监控停止
    CIRCUIT_BREAKER = "circuit_breaker"    # 熔断触发
    POSITION_UPDATED = "position_updated"  # 持仓更新


class Signal:
    """信号对象"""
    
    def __init__(self, signal_type: SignalType, data: Dict[str, Any] = None):
        """
        初始化信号
        
        Args:
            signal_type: 信号类型
            data: 信号数据
        """
        self.signal_type = signal_type
        self.data = data or {}
        self.timestamp = datetime.now()
    
    def __repr__(self):
        return f"Signal(type={self.signal_type.value}, data={self.data}, time={self.timestamp})"


class SignalBus:
    """信号总线"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.initialized = True
            self.subscribers: Dict[SignalType, List[Callable]] = {}
            self.signal_history: List[Signal] = []
            self.max_history = 1000  # 最大历史记录数
    
    def subscribe(self, signal_type: SignalType, callback: Callable):
        """
        订阅信号
        
        Args:
            signal_type: 信号类型
            callback: 回调函数
        """
        if signal_type not in self.subscribers:
            self.subscribers[signal_type] = []
        
        if callback not in self.subscribers[signal_type]:
            self.subscribers[signal_type].append(callback)
    
    def unsubscribe(self, signal_type: SignalType, callback: Callable):
        """
        取消订阅
        
        Args:
            signal_type: 信号类型
            callback: 回调函数
        """
        if signal_type in self.subscribers:
            if callback in self.subscribers[signal_type]:
                self.subscribers[signal_type].remove(callback)
    
    def emit(self, signal_type: SignalType, data: Dict[str, Any] = None):
        """
        发送信号
        
        Args:
            signal_type: 信号类型
            data: 信号数据
        """
        signal = Signal(signal_type, data)
        
        # 记录到历史
        self.signal_history.append(signal)
        if len(self.signal_history) > self.max_history:
            self.signal_history.pop(0)
        
        # 通知订阅者
        if signal_type in self.subscribers:
            for callback in self.subscribers[signal_type]:
                try:
                    callback(signal)
                except Exception as e:
                    print(f"信号处理错误: {e}")
    
    def get_history(self, signal_type: SignalType = None, limit: int = 100) -> List[Signal]:
        """
        获取信号历史
        
        Args:
            signal_type: 信号类型（None 表示所有类型）
            limit: 最大返回数量
        
        Returns:
            信号列表
        """
        if signal_type is None:
            return self.signal_history[-limit:]
        
        filtered = [s for s in self.signal_history if s.signal_type == signal_type]
        return filtered[-limit:]
    
    def clear_history(self):
        """清空信号历史"""
        self.signal_history.clear()


# 全局信号总线实例
signal_bus = SignalBus()


def emit_buy_signal(stock_code: str, price: float, reason: str = ""):
    """
    发送买入信号
    
    Args:
        stock_code: 股票代码
        price: 触发价格
        reason: 触发原因
    """
    signal_bus.emit(SignalType.BUY, {
        'stock_code': stock_code,
        'price': price,
        'reason': reason
    })


def emit_sell_signal(stock_code: str, price: float, reason: str = "", urgent: bool = False):
    """
    发送卖出信号
    
    Args:
        stock_code: 股票代码
        price: 触发价格
        reason: 触发原因
        urgent: 是否紧急（炸板等）
    """
    signal_bus.emit(SignalType.SELL, {
        'stock_code': stock_code,
        'price': price,
        'reason': reason,
        'urgent': urgent
    })


def emit_circuit_breaker(reason: str = ""):
    """
    发送熔断信号
    
    Args:
        reason: 熔断原因
    """
    signal_bus.emit(SignalType.CIRCUIT_BREAKER, {
        'reason': reason
    })
