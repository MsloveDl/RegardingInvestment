"""
风控执行模块
全天监控持仓，执行 T+1/T+2 退出逻辑，管理全局熔断
"""

from typing import Dict, List
from datetime import datetime, timedelta
from enum import Enum

from modules.data_adapter import DataAdapter
from utils.logger import logger
from utils.signal_bus import signal_bus, SignalType, emit_sell_signal, emit_circuit_breaker
from utils.trading_calendar import trading_calendar
import config


class ExitReason(Enum):
    """退出原因枚举"""
    T1_AUCTION = "T+1竞价止盈"
    LIMIT_UP_HOLD = "涨停持有至T+2"
    LIMIT_UP_BROKEN = "炸板卖出"
    MA5_STOP_LOSS = "跌破5日均线止损"
    INTRADAY_MA_STOP_LOSS = "跌破分时均线止损"
    TIME_STOP_LOSS = "时间止损(T+3)"


class Position:
    """持仓对象"""
    
    def __init__(self, stock_code: str, buy_date: datetime, buy_price: float, 
                 quantity: int, buy_reason: str = ""):
        """
        初始化持仓
        
        Args:
            stock_code: 股票代码
            buy_date: 买入日期
            buy_price: 买入价格
            quantity: 持仓数量
            buy_reason: 买入原因
        """
        self.stock_code = stock_code
        self.buy_date = buy_date
        self.buy_price = buy_price
        self.quantity = quantity
        self.buy_reason = buy_reason
        self.holding_days = 0
        self.max_profit = 0.0
        self.current_price = buy_price
    
    def update_price(self, current_price: float):
        """更新当前价格"""
        self.current_price = current_price
        profit = (current_price - self.buy_price) / self.buy_price
        if profit > self.max_profit:
            self.max_profit = profit
    
    def get_profit_rate(self) -> float:
        """获取盈利率"""
        return (self.current_price - self.buy_price) / self.buy_price
    
    def get_profit_amount(self) -> float:
        """获取盈利金额"""
        return (self.current_price - self.buy_price) * self.quantity
    
    def __repr__(self):
        return f"Position({self.stock_code}, buy={self.buy_price:.2f}, " \
               f"current={self.current_price:.2f}, profit={self.get_profit_rate()*100:.2f}%)"


class RiskManager:
    """风控管理器"""
    
    def __init__(self, data_adapter: DataAdapter, total_capital: float = 100000):
        """
        初始化风控管理器
        
        Args:
            data_adapter: 数据适配器
            total_capital: 总资产
        """
        self.data_adapter = data_adapter
        self.total_capital = total_capital
        self.positions: Dict[str, Position] = {}
        self.circuit_breaker = False
        self.daily_buy_count = 0
        self.last_check_date = None
    
    def add_position(self, stock_code: str, buy_price: float, quantity: int, buy_reason: str = ""):
        """
        添加持仓
        
        Args:
            stock_code: 股票代码
            buy_price: 买入价格
            quantity: 持仓数量
            buy_reason: 买入原因
        """
        position = Position(
            stock_code=stock_code,
            buy_date=datetime.now(),
            buy_price=buy_price,
            quantity=quantity,
            buy_reason=buy_reason
        )
        self.positions[stock_code] = position
        self.daily_buy_count += 1
        
        logger.info(f"新增持仓: {position}")
        
        # 发送信号
        signal_bus.emit(SignalType.POSITION_UPDATED, {
            'action': 'add',
            'stock_code': stock_code,
            'position': position
        })
    
    def remove_position(self, stock_code: str, reason: str = ""):
        """
        移除持仓
        
        Args:
            stock_code: 股票代码
            reason: 移除原因
        """
        if stock_code in self.positions:
            position = self.positions.pop(stock_code)
            logger.info(f"移除持仓: {stock_code}, 原因: {reason}, 盈利: {position.get_profit_rate()*100:.2f}%")
            
            # 发送信号
            signal_bus.emit(SignalType.POSITION_UPDATED, {
                'action': 'remove',
                'stock_code': stock_code,
                'reason': reason,
                'profit_rate': position.get_profit_rate()
            })
    
    def check_exit_conditions(self):
        """检查退出条件"""
        if not self.positions:
            return
        
        logger.debug(f"检查退出条件，当前持仓: {len(self.positions)} 只")
        
        # 获取当前行情
        stock_codes = list(self.positions.keys())
        quote_data = self.data_adapter.get_market_data_batch(
            stocks=stock_codes,
            fields=['close', 'high', 'low', 'volume'],
            period='1d'
        )
        
        for stock_code, position in list(self.positions.items()):
            if stock_code not in quote_data:
                continue
            
            data = quote_data[stock_code]
            current_price = data.get('close', position.current_price)
            position.update_price(current_price)
            
            # 计算持仓天数
            holding_days = (datetime.now() - position.buy_date).days
            position.holding_days = holding_days
            
            # 检查各种退出条件
            exit_reason = None
            
            # 1. T+1 竞价卖出（常规止盈）
            if holding_days >= 1 and self._is_auction_time():
                if config.EXIT_RULES['t1_auction_exit']:
                    # 检查是否涨停封死
                    if not self._is_limit_up_sealed(stock_code, data):
                        exit_reason = ExitReason.T1_AUCTION
            
            # 2. 涨停持有（T+1 封死涨停 → 持有至 T+2）
            elif holding_days == 1 and self._is_limit_up_sealed(stock_code, data):
                logger.info(f"{stock_code}: T+1 涨停封死，持有至 T+2")
                continue
            
            # 3. 炸板卖出（T+1 盘中涨停后开板）
            elif holding_days >= 1 and self._is_limit_up_broken(stock_code, data):
                if config.EXIT_RULES['limit_up_broken_exit']:
                    exit_reason = ExitReason.LIMIT_UP_BROKEN
            
            # 4. 动态止损（跌破 5 日均线）
            elif self._is_below_ma5(stock_code, data):
                if config.EXIT_RULES['ma5_stop_loss']:
                    exit_reason = ExitReason.MA5_STOP_LOSS
            
            # 5. 时间止损（T+3 强制卖出）
            elif holding_days >= config.RISK_CONTROL['max_holding_days']:
                exit_reason = ExitReason.TIME_STOP_LOSS
            
            # 执行卖出
            if exit_reason:
                emit_sell_signal(
                    stock_code=stock_code,
                    price=current_price,
                    reason=exit_reason.value,
                    urgent=(exit_reason == ExitReason.LIMIT_UP_BROKEN)
                )
                self.remove_position(stock_code, exit_reason.value)
    
    def check_circuit_breaker(self):
        """检查账户熔断"""
        if not self.positions:
            return
        
        # 计算总浮动亏损
        total_loss = 0.0
        for position in self.positions.values():
            profit = position.get_profit_amount()
            if profit < 0:
                total_loss += abs(profit)
        
        # 计算亏损比例
        loss_rate = total_loss / self.total_capital
        
        # 检查是否触发熔断
        threshold = config.RISK_CONTROL['account_circuit_breaker']
        if loss_rate >= threshold:
            if not self.circuit_breaker:
                self.circuit_breaker = True
                logger.warning(f"触发账户熔断！总浮动亏损: {loss_rate*100:.2f}% >= {threshold*100:.2f}%")
                emit_circuit_breaker(f"总浮动亏损达到 {loss_rate*100:.2f}%")
        else:
            if self.circuit_breaker:
                logger.info(f"账户熔断解除，当前亏损: {loss_rate*100:.2f}%")
                self.circuit_breaker = False
    
    def can_buy(self, stock_code: str) -> bool:
        """
        检查是否可以买入
        
        Args:
            stock_code: 股票代码
        
        Returns:
            是否可以买入
        """
        # 检查熔断状态
        if self.circuit_breaker:
            logger.warning(f"账户熔断中，拒绝买入 {stock_code}")
            return False
        
        # 检查单日最大开仓数
        today = datetime.now().date()
        if self.last_check_date != today:
            self.daily_buy_count = 0
            self.last_check_date = today
        
        if self.daily_buy_count >= config.RISK_CONTROL['max_daily_stocks']:
            logger.warning(f"单日最大开仓数已达 {config.RISK_CONTROL['max_daily_stocks']}，拒绝买入 {stock_code}")
            return False
        
        # 检查是否已持仓
        if stock_code in self.positions:
            logger.warning(f"{stock_code} 已持仓，拒绝重复买入")
            return False
        
        return True
    
    def _is_auction_time(self) -> bool:
        """检查是否为竞价时间（9:25）"""
        now = datetime.now()
        current_time = now.time()
        auction_time = datetime.strptime('09:25:00', '%H:%M:%S').time()
        
        # 允许 9:25:00 - 9:25:30 之间
        return auction_time <= current_time <= datetime.strptime('09:25:30', '%H:%M:%S').time()
    
    def _is_limit_up_sealed(self, stock_code: str, data: Dict) -> bool:
        """
        检查是否涨停封死
        
        Args:
            stock_code: 股票代码
            data: 行情数据
        
        Returns:
            是否涨停封死
        """
        # 简化处理：涨幅 >= 9.8% 视为涨停封死
        if stock_code not in self.positions:
            return False
        
        position = self.positions[stock_code]
        current_price = data.get('close', position.current_price)
        change = (current_price - position.buy_price) / position.buy_price * 100
        
        threshold = config.EXIT_RULES['limit_up_hold_threshold']
        return change >= threshold
    
    def _is_limit_up_broken(self, stock_code: str, data: Dict) -> bool:
        """
        检查是否炸板（涨停后开板）
        
        Args:
            stock_code: 股票代码
            data: 行情数据
        
        Returns:
            是否炸板
        """
        try:
            # 检查今日是否曾经涨停
            high = data.get('high', 0)
            current_price = data.get('close', 0)
            
            if stock_code not in self.positions:
                return False
            
            position = self.positions[stock_code]
            
            # 计算涨停价（前收盘价 * 1.1）
            limit_up_price = position.buy_price * 1.1
            
            # 如果最高价接近涨停价（误差 0.5%），但当前价低于涨停价 2%
            if high >= limit_up_price * 0.995 and current_price < limit_up_price * 0.98:
                logger.warning(f"{stock_code}: 检测到炸板，最高={high:.2f}, 当前={current_price:.2f}, 涨停价={limit_up_price:.2f}")
                return True
            
            return False
        except Exception as e:
            logger.error(f"检查炸板失败: {e}")
            return False
    
    def _is_below_ma5(self, stock_code: str, data: Dict) -> bool:
        """
        检查是否跌破 5 日均线
        
        Args:
            stock_code: 股票代码
            data: 行情数据
        
        Returns:
            是否跌破 5 日均线
        """
        try:
            # 获取最近 10 天的收盘价（用于计算 MA5）
            from datetime import datetime, timedelta
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=15)).strftime('%Y%m%d')
            
            hist_data = self.data_adapter.get_market_data_batch(
                stocks=[stock_code],
                fields=['close'],
                period='1d',
                start_time=start_date,
                end_time=end_date
            )
            
            if stock_code not in hist_data or 'close' not in hist_data[stock_code]:
                return False
            
            closes = hist_data[stock_code]['close']
            if isinstance(closes, (list, tuple)) and len(closes) >= 5:
                # 计算 MA5
                ma5 = sum(closes[-5:]) / 5
                current_price = data.get('close', 0)
                
                # 跌破 MA5
                if current_price < ma5:
                    logger.info(f"{stock_code}: 跌破 MA5，当前价={current_price:.2f}, MA5={ma5:.2f}")
                    return True
            
            return False
        except Exception as e:
            logger.error(f"计算 MA5 失败: {e}")
            return False
    
    def get_position_summary(self) -> Dict:
        """
        获取持仓摘要
        
        Returns:
            持仓摘要字典
        """
        if not self.positions:
            return {
                'total_positions': 0,
                'total_value': 0.0,
                'total_profit': 0.0,
                'total_profit_rate': 0.0
            }
        
        total_value = 0.0
        total_profit = 0.0
        
        for position in self.positions.values():
            value = position.current_price * position.quantity
            profit = position.get_profit_amount()
            total_value += value
            total_profit += profit
        
        return {
            'total_positions': len(self.positions),
            'total_value': total_value,
            'total_profit': total_profit,
            'total_profit_rate': total_profit / total_value if total_value > 0 else 0.0,
            'circuit_breaker': self.circuit_breaker
        }
