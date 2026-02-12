"""
情绪套利策略 EA - 主控层
版本: v1.0
生成日期: 2026-02-11
"""

import schedule
import threading
import time
from datetime import datetime

from modules import DataAdapter, SectorScanner, StockMonitor, RiskManager
from utils.logger import logger
from utils.trading_calendar import trading_calendar
from utils.signal_bus import signal_bus, SignalType
import config


class MainController:
    """策略主控器"""
    
    def __init__(self, total_capital: float = 100000):
        """
        初始化主控器
        
        Args:
            total_capital: 总资产
        """
        # 初始化日志
        logger.setup(
            log_file=config.LOG_CONFIG['log_file'],
            log_level=config.LOG_CONFIG['log_level'],
            max_bytes=config.LOG_CONFIG['max_bytes'],
            backup_count=config.LOG_CONFIG['backup_count']
        )
        
        logger.info("=" * 80)
        logger.info("情绪套利策略 EA 初始化")
        logger.info(f"总资产: {total_capital:,.2f}")
        logger.info("=" * 80)
        
        # 初始化模块
        self.data_adapter = DataAdapter(
            cache_enabled=config.DATA_CONFIG['cache_enabled'],
            max_cache_size=config.DATA_CONFIG['max_cache_size']
        )
        self.sector_scanner = SectorScanner(self.data_adapter)
        self.stock_monitor = None
        self.risk_manager = RiskManager(self.data_adapter, total_capital)
        
        # 状态变量
        self.top_sectors = []
        self.is_running = False
        
        # 订阅信号
        self._subscribe_signals()
    
    def _subscribe_signals(self):
        """订阅信号"""
        # 订阅买入信号
        signal_bus.subscribe(SignalType.BUY, self._on_buy_signal)
        
        # 订阅卖出信号
        signal_bus.subscribe(SignalType.SELL, self._on_sell_signal)
        
        # 订阅熔断信号
        signal_bus.subscribe(SignalType.CIRCUIT_BREAKER, self._on_circuit_breaker)
    
    def _on_buy_signal(self, signal):
        """处理买入信号"""
        stock_code = signal.data.get('stock_code')
        price = signal.data.get('price')
        reason = signal.data.get('reason', '')
        
        logger.info(f"收到买入信号: {stock_code} @ {price:.2f}, 原因: {reason}")
        
        # 检查是否可以买入
        if not self.risk_manager.can_buy(stock_code):
            return
        
        # 计算买入数量
        position_size = self.risk_manager.total_capital * config.RISK_CONTROL['single_stock_position']
        quantity = int(position_size / price / 100) * 100  # 向下取整到100股
        
        if quantity < 100:
            logger.warning(f"{stock_code}: 资金不足，无法买入")
            return
        
        # 执行买入（这里只是记录，实际下单需要调用 xttrader）
        logger.info(f"执行买入: {stock_code}, 数量: {quantity}, 价格: {price:.2f}")
        self.risk_manager.add_position(stock_code, price, quantity, reason)
    
    def _on_sell_signal(self, signal):
        """处理卖出信号"""
        stock_code = signal.data.get('stock_code')
        price = signal.data.get('price')
        reason = signal.data.get('reason', '')
        urgent = signal.data.get('urgent', False)
        
        logger.info(f"收到卖出信号: {stock_code} @ {price:.2f}, 原因: {reason}, 紧急: {urgent}")
        
        # 执行卖出（这里只是记录，实际下单需要调用 xttrader）
        if stock_code in self.risk_manager.positions:
            position = self.risk_manager.positions[stock_code]
            logger.info(f"执行卖出: {stock_code}, 数量: {position.quantity}, 价格: {price:.2f}")
    
    def _on_circuit_breaker(self, signal):
        """处理熔断信号"""
        reason = signal.data.get('reason', '')
        logger.warning(f"触发熔断: {reason}")
    
    def run(self):
        """策略主循环"""
        self.is_running = True
        
        logger.info("策略主控启动，等待交易时间...")
        
        # 设置定时任务
        schedule.every().day.at(config.TRADING_SCHEDULE['prepare_time']).do(self._prepare)
        schedule.every().day.at(config.TRADING_SCHEDULE['sector_scan_time']).do(self._scan_sectors)
        schedule.every().day.at(config.TRADING_SCHEDULE['pool_init_time']).do(self._init_monitor)
        schedule.every().day.at(config.TRADING_SCHEDULE['monitor_start_time']).do(self._start_monitor)
        schedule.every().day.at(config.TRADING_SCHEDULE['monitor_end_time']).do(self._stop_monitor)
        
        # 全天风控检查（每分钟）
        schedule.every(60).seconds.do(self.risk_manager.check_exit_conditions)
        
        # 账户熔断检查（每 30 秒）
        schedule.every(30).seconds.do(self.risk_manager.check_circuit_breaker)
        
        # 主循环
        while self.is_running:
            try:
                schedule.run_pending()
                time.sleep(1)
            except KeyboardInterrupt:
                logger.info("收到中断信号，准备退出...")
                self.stop()
                break
            except Exception as e:
                logger.error(f"主循环异常: {e}", exc_info=True)
                time.sleep(5)
    
    def _prepare(self):
        """9:24:50 准备阶段"""
        logger.info("=" * 80)
        logger.info("准备阶段（9:24:50）")
        logger.info("=" * 80)
        
        # 清空缓存
        self.data_adapter.clear_cache()
        
        # 检查交易日历
        if not trading_calendar.is_trading_day():
            logger.info("今日非交易日，策略休眠。")
            return
        
        logger.info("今日为交易日，准备就绪。")
    
    def _scan_sectors(self):
        """9:25 板块扫描"""
        if not trading_calendar.is_trading_day():
            return
        
        self.top_sectors = self.sector_scanner.scan_at_925()
        
        if not self.top_sectors:
            logger.warning("未找到符合条件的板块，今日不交易。")
    
    def _init_monitor(self):
        """9:29:50 初始化监控池"""
        if not self.top_sectors:
            return
        
        self.stock_monitor = StockMonitor(self.top_sectors, self.data_adapter)
    
    def _start_monitor(self):
        """9:30 启动监控"""
        if not self.stock_monitor:
            return
        
        # 在独立线程中运行监控循环
        threading.Thread(target=self.stock_monitor.monitor_loop, daemon=True).start()
    
    def _stop_monitor(self):
        """9:45 停止监控"""
        if self.stock_monitor:
            self.stock_monitor.stop()
            logger.info("监控窗口关闭，今日买入操作结束。")
    
    def stop(self):
        """停止策略"""
        self.is_running = False
        
        # 打印统计信息
        logger.info("=" * 80)
        logger.info("策略停止")
        logger.info("=" * 80)
        
        # 数据适配器统计
        stats = self.data_adapter.get_stats()
        logger.info(f"数据请求统计: 请求次数={stats['request_count']}, "
                   f"缓存命中={stats['cache_hit_count']}, "
                   f"命中率={stats['cache_hit_rate']*100:.2f}%")
        
        # 持仓摘要
        summary = self.risk_manager.get_position_summary()
        logger.info(f"持仓摘要: 持仓数={summary['total_positions']}, "
                   f"总市值={summary['total_value']:,.2f}, "
                   f"总盈亏={summary['total_profit']:,.2f}, "
                   f"盈亏率={summary['total_profit_rate']*100:.2f}%")
        
        logger.info("=" * 80)


def main():
    """主函数"""
    # 创建主控器
    controller = MainController(total_capital=100000)
    
    # 运行策略
    try:
        controller.run()
    except Exception as e:
        logger.error(f"策略运行异常: {e}", exc_info=True)
    finally:
        controller.stop()


if __name__ == '__main__':
    main()
