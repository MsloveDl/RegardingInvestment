"""
个股监控模块
9:30-9:45 动态监控目标板块内的补涨个股，触发买入信号
"""

from typing import List, Dict, Any
from datetime import datetime, timedelta
import time
import threading

from modules.data_adapter import DataAdapter
from utils.logger import logger
from utils.signal_bus import signal_bus, SignalType, emit_buy_signal
import config


class StockMonitor:
    """个股监控器"""
    
    def __init__(self, top_sectors: List[str], data_adapter: DataAdapter):
        """
        初始化个股监控器
        
        Args:
            top_sectors: 目标板块列表
            data_adapter: 数据适配器
        """
        self.top_sectors = top_sectors
        self.data_adapter = data_adapter
        self.monitor_pool: List[str] = []
        self.prev_snapshot: Dict[str, Dict] = {}
        self.is_running = False
        self.start_time = None
        
        # 初始化监控池
        self._init_pool()
    
    def _init_pool(self):
        """9:29:50 初始化监控池"""
        logger.info("=" * 60)
        logger.info("初始化监控池（9:29:50）")
        logger.info("=" * 60)
        
        pool = []
        
        # 使用昨天的数据进行测试（非交易时间）
        from datetime import datetime, timedelta
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
        logger.info(f"使用日期: {yesterday} (非交易时间使用昨天数据)")
        
        for sector in self.top_sectors:
            logger.info(f"处理板块: {sector}")
            
            # 获取板块内股票
            stocks = self.data_adapter.get_stocks_in_sector(sector)
            if not stocks:
                logger.warning(f"板块 {sector} 无股票数据")
                continue
            
            # 获取开盘数据
            quote_data = self.data_adapter.get_market_data_batch(
                stocks=stocks,
                fields=['open', 'pre_close'],
                period='1d',
                start_time=yesterday,
                end_time=yesterday
            )
            
            # 筛选：开盘涨幅 +2% ~ +5%
            filtered = []
            for stock in stocks:
                if stock in quote_data:
                    data = quote_data[stock]
                    if 'open' in data and 'pre_close' in data:
                        open_price = data['open']
                        pre_close = data['pre_close']
                        if pre_close > 0:
                            change = (open_price / pre_close - 1) * 100
                            if config.STOCK_POOL_INIT['min_change'] <= change <= config.STOCK_POOL_INIT['max_change']:
                                filtered.append((stock, change))
            
            # 取涨幅最大的 Top N
            filtered.sort(key=lambda x: x[1], reverse=True)
            top_n = config.STOCK_POOL_INIT['top_n_per_sector']
            sector_pool = [stock for stock, change in filtered[:top_n]]
            
            logger.info(f"板块 {sector}: 筛选出 {len(sector_pool)} 只股票（涨幅 {config.STOCK_POOL_INIT['min_change']}%-{config.STOCK_POOL_INIT['max_change']}%）")
            
            pool.extend(sector_pool)
        
        self.monitor_pool = pool
        
        logger.info("=" * 60)
        logger.info(f"监控池初始化完成，共 {len(self.monitor_pool)} 只股票")
        logger.info(f"监控池: {self.monitor_pool[:10]}{'...' if len(self.monitor_pool) > 10 else ''}")
        logger.info("=" * 60)
        
        # 发送信号
        signal_bus.emit(SignalType.POOL_INITIALIZED, {
            'monitor_pool': self.monitor_pool,
            'pool_size': len(self.monitor_pool)
        })
    
    def monitor_loop(self):
        """9:30-9:45 循环监控"""
        self.is_running = True
        self.start_time = datetime.now()
        
        logger.info("=" * 60)
        logger.info("启动个股监控（9:30-9:45）")
        logger.info(f"监控间隔: {config.MONITOR_POLL_INTERVAL} 秒")
        logger.info("=" * 60)
        
        # 发送信号
        signal_bus.emit(SignalType.MONITOR_STARTED, {
            'pool_size': len(self.monitor_pool)
        })
        
        loop_count = 0
        
        while self.is_running and self._is_in_window():
            loop_count += 1
            logger.info(f"--- 监控轮询 #{loop_count} ---")
            
            # 批量请求实时行情（使用免费接口，不使用 L2）
            if not self.monitor_pool:
                logger.warning("监控池为空，停止监控")
                break
            
            realtime_batch = self.data_adapter.get_realtime_quote_batch(self.monitor_pool)
            
            if not realtime_batch:
                logger.warning("未获取到实时行情数据")
                time.sleep(config.MONITOR_POLL_INTERVAL)
                continue
            
            # 逐个检查
            for stock in self.monitor_pool:
                if stock not in realtime_batch:
                    continue
                
                data = realtime_batch[stock]
                
                # 1. SPP 抛压探测
                if self._check_selling_pressure(stock, data):
                    continue
                
                # 2. TS 板块协同
                if not self._check_sector_synergy(stock):
                    continue
                
                # 3. MCP 动量确认
                if self._check_momentum_confirmation(stock, data):
                    # 触发买入信号
                    emit_buy_signal(
                        stock_code=stock,
                        price=data.get('last_price', 0),
                        reason="MCP 动量确认触发"
                    )
                    logger.info(f"★★★ 买入信号触发: {stock} @ {data.get('last_price', 0):.2f}")
            
            # 等待下一次轮询
            time.sleep(config.MONITOR_POLL_INTERVAL)
        
        self.is_running = False
        logger.info("=" * 60)
        logger.info("个股监控结束")
        logger.info("=" * 60)
        
        # 发送信号
        signal_bus.emit(SignalType.MONITOR_STOPPED, {})
    
    def _is_in_window(self) -> bool:
        """检查是否在监控窗口内（9:30-9:45）"""
        now = datetime.now()
        current_time = now.time()
        
        start_time = datetime.strptime(config.TRADING_SCHEDULE['monitor_start_time'], '%H:%M:%S').time()
        end_time = datetime.strptime(config.TRADING_SCHEDULE['monitor_end_time'], '%H:%M:%S').time()
        
        return start_time <= current_time <= end_time
    
    def _check_selling_pressure(self, stock: str, data: Dict) -> bool:
        """
        抛压探测（SPP）- 降级版：不使用 L2 买卖五档
        
        Args:
            stock: 股票代码
            data: 实时行情数据
        
        Returns:
            True = 高抛压，剔除；False = 正常
        """
        # 降级版策略：使用涨跌幅和成交量判断
        
        # 1. 检查涨跌幅（如果跌幅过大，视为高抛压）
        change_rate = data.get('change_rate', 0)
        if change_rate < -2.0:  # 跌幅超过 2%
            logger.debug(f"{stock}: 跌幅过大 {change_rate:.2f}%，剔除")
            return True
        
        # 2. 检查成交量（如果成交量萎缩，可能是抛压）
        volume = data.get('volume', 0)
        if stock in self.prev_snapshot and 'volume' in self.prev_snapshot[stock]:
            prev_volume = self.prev_snapshot[stock]['volume']
            if prev_volume > 0:
                volume_ratio = volume / prev_volume
                if volume_ratio < 0.5:  # 成交量萎缩超过 50%
                    logger.debug(f"{stock}: 成交量萎缩 {volume_ratio:.2%}，剔除")
                    return True
        
        # 3. 检查振幅（如果振幅过大，可能是波动剧烈）
        high = data.get('high', 0)
        low = data.get('low', 0)
        pre_close = data.get('pre_close', 0)
        if pre_close > 0:
            amplitude = ((high - low) / pre_close) * 100
            if amplitude > 8.0:  # 振幅超过 8%
                logger.debug(f"{stock}: 振幅过大 {amplitude:.2f}%，剔除")
                return True
        
        return False
    
    def _check_sector_synergy(self, stock: str) -> bool:
        """
        板块协同性（TS）- 降级版：简化检查
        
        Args:
            stock: 股票代码
        
        Returns:
            True = 板块协同良好；False = 板块走弱
        """
        try:
            # 找到该股票所属的板块
            stock_sector = None
            for sector in self.top_sectors:
                sector_stocks = self.data_adapter.get_stocks_in_sector(sector)
                if stock in sector_stocks:
                    stock_sector = sector
                    break
            
            if not stock_sector:
                return True  # 找不到板块，默认通过
            
            # 获取板块内所有监控池股票的当前涨跌情况
            sector_monitor_stocks = [s for s in self.monitor_pool 
                                    if s in self.data_adapter.get_stocks_in_sector(stock_sector)]
            
            if len(sector_monitor_stocks) < 3:
                return True  # 样本太少，默认通过
            
            # 批量获取这些股票的实时数据（使用免费接口）
            realtime_data = self.data_adapter.get_realtime_quote_batch(sector_monitor_stocks)
            
            # 统计上涨股票数量
            up_count = 0
            for s, data in realtime_data.items():
                change_rate = data.get('change_rate', 0)
                if change_rate > 0:  # 涨幅为正
                    up_count += 1
            
            # 计算板块协同比例
            synergy_ratio = up_count / len(realtime_data) if realtime_data else 0
            threshold = config.TS_PARAMS['monitor_threshold']
            
            if synergy_ratio < threshold:
                logger.debug(f"{stock}: 板块协同不足 {synergy_ratio:.2%} < {threshold:.2%}")
                return False
            
            return True
        except Exception as e:
            logger.error(f"检查板块协同失败: {e}")
            return True  # 出错时默认通过
    
    def _check_momentum_confirmation(self, stock: str, data: Dict) -> bool:
        """
        动量确认（MCP）- 降级版：使用免费行情数据
        
        Args:
            stock: 股票代码
            data: 实时行情数据
        
        Returns:
            True = 动量确认触发；False = 未触发
        """
        # 检查是否在观察期内（9:30-9:35）
        if self.start_time:
            elapsed = (datetime.now() - self.start_time).total_seconds()
            if elapsed < config.MCP_PARAMS['min_observation_seconds']:
                return False
        
        # 检查是否有历史快照
        if stock not in self.prev_snapshot:
            self.prev_snapshot[stock] = data
            return False
        
        prev = self.prev_snapshot[stock]
        
        # 价格突破
        current_price = data.get('last_price', 0)
        prev_price = prev.get('last_price', 0)
        price_break = current_price > prev_price
        
        # 量比放大
        current_volume = data.get('volume', 0)
        prev_volume = prev.get('volume', 0)
        volume_surge_ratio = config.MCP_PARAMS['volume_surge_ratio']
        
        if prev_volume > 0:
            volume_surge = current_volume > prev_volume * volume_surge_ratio
        else:
            volume_surge = False
        
        # 更新快照
        self.prev_snapshot[stock] = data
        
        # 判断是否触发
        if price_break and volume_surge:
            logger.info(f"{stock}: 价格突破 {prev_price:.2f} -> {current_price:.2f}, "
                       f"量比 {current_volume/max(prev_volume, 1):.2f}x")
            return True
        
        return False
    
    def stop(self):
        """停止监控"""
        self.is_running = False
        logger.info("收到停止信号，准备停止监控...")
