# -*- coding: utf-8 -*-
"""
情绪套利策略 v3.0 - 主程序
整合数据探针、策略引擎、回测系统和订单执行器
"""

import asyncio
import os
import sys
import json
from datetime import datetime, time
import logging

# 添加项目路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)
sys.path.append(os.path.dirname(current_dir))

from data_probe import SentimentDataProbe
from strategy_v3 import SentimentStrategyV3
from backtest_v3 import SentimentBacktestV3
from executor_v3 import OrderExecutorV3
from config import STRATEGY_CONFIG, EXECUTION_CONFIG, BACKTEST_CONFIG, LOG_CONFIG

class SentimentArbitrageV3:
    """情绪套利策略 v3.0 主控制器"""
    
    def __init__(self, mode='paper'):
        self.mode = mode
        self.logger = self._setup_logger()
        
        # 初始化各模块
        self.data_probe = SentimentDataProbe()
        self.strategy = SentimentStrategyV3()
        self.backtest_engine = None
        self.executor = None
        
        # 状态管理
        self.is_running = False
        self.current_positions = {}
        self.last_probe_time = None
        
        self.logger.info(f"Sentiment Arbitrage v3.0 initialized in {mode} mode")
        
    def _setup_logger(self):
        """设置日志"""
        logger = logging.getLogger('SentimentV3')
        logger.setLevel(getattr(logging, LOG_CONFIG['level']))
        
        # 清除现有处理器
        logger.handlers.clear()
        
        # 文件处理器
        os.makedirs(os.path.dirname(LOG_CONFIG['file_path']), exist_ok=True)
        file_handler = logging.FileHandler(LOG_CONFIG['file_path'], encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        
        # 控制台处理器
        if LOG_CONFIG['console_output']:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            logger.addHandler(console_handler)
            
        # 格式化器
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        if LOG_CONFIG['console_output']:
            console_handler.setFormatter(formatter)
            
        logger.addHandler(file_handler)
        return logger
        
    async def initialize(self):
        """初始化系统"""
        self.logger.info("Initializing Sentiment Arbitrage v3.0...")
        
        try:
            # 初始化订单执行器
            if self.mode in ['paper', 'live']:
                self.executor = OrderExecutorV3(mode=self.mode)
                await self.executor.initialize()
                
            # 加载股票池
            await self.data_probe.load_stock_pool()
            
            # 初始化策略
            self.strategy.config.update(STRATEGY_CONFIG)
            
            self.logger.info("Initialization completed")
            return True
            
        except Exception as e:
            self.logger.error(f"Initialization failed: {e}")
            return False
            
    async def run_morning_probe(self):
        """运行早晨探针"""
        self.logger.info("Starting morning probe...")
        
        try:
            # 运行探针
            probe_results = await self.data_probe.run_morning_probe()
            
            # 更新策略数据
            self.strategy.probe_results = probe_results
            
            # 生成交易信号
            signals = self.strategy.generate_daily_signals()
            
            self.logger.info(f"Generated {len(signals)} trading signals")
            
            return signals
            
        except Exception as e:
            self.logger.error(f"Morning probe failed: {e}")
            return []
            
    async def execute_signals(self, signals):
        """执行交易信号"""
        if not signals or not self.executor:
            return
            
        self.logger.info(f"Executing {len(signals)} signals...")
        
        # 启动订单处理
        processing_task = asyncio.create_task(self.executor.start_order_processing())
        
        try:
            for signal in signals:
                try:
                    # 构建订单请求
                    order_request = {
                        'stock': signal['stock'],
                        'action': signal['action'],
                        'order_type': EXECUTION_CONFIG['default_order_type'],
                        'price': 0,  # 市价单
                        'quantity': 1000,  # 固定数量，实际应该根据资金计算
                        'time_limit': 'IOC',
                        'strategy': 'sentiment_v3'
                    }
                    
                    # 提交订单
                    order_id = await self.executor.submit_order(order_request)
                    
                    if order_id:
                        self.logger.info(f"Order submitted: {order_id}")
                    else:
                        self.logger.warning(f"Order submission failed: {signal['stock']}")
                        
                except Exception as e:
                    self.logger.error(f"Signal execution failed: {signal['stock']}, error: {e}")
                    
        finally:
            # 停止订单处理
            await self.executor.stop_order_processing()
            processing_task.cancel()
            
    async def run_backtest(self, stock_list=None, start_date=None, end_date=None):
        """运行回测"""
        self.logger.info("Starting backtest...")
        
        try:
            # 使用配置或默认参数
            stock_list = stock_list or ['600381.SH', '300007.SZ', '000609.SZ']
            start_date = start_date or BACKTEST_CONFIG['start_date']
            end_date = end_date or BACKTEST_CONFIG['end_date']
            
            # 创建回测引擎
            self.backtest_engine = SentimentBacktestV3(
                initial_capital=BACKTEST_CONFIG['initial_capital']
            )
            
            # 运行回测
            results = self.backtest_engine.run_backtest(stock_list, start_date, end_date)
            
            # 打印结果
            self.backtest_engine.print_results()
            
            # 保存结果
            self.backtest_engine.save_results()
            
            return results
            
        except Exception as e:
            self.logger.error(f"Backtest failed: {e}")
            return {}
            
    async def run_live_trading(self):
        """运行实时交易"""
        self.logger.info("Starting live trading...")
        
        if not self.executor:
            self.logger.error("Executor not initialized")
            return
            
        self.is_running = True
        
        try:
            # 启动订单处理循环
            processing_task = asyncio.create_task(self.executor.start_order_processing())
            
            while self.is_running:
                current_time = datetime.now().time()
                
                # 检查是否在交易时间
                if time(9, 15) <= current_time <= time(15, 0):
                    # 检查是否到探针时间
                    if (self.last_probe_time is None or 
                        (datetime.now() - self.last_probe_time).seconds > 300):  # 5分钟间隔
                        
                        # 运行探针
                        signals = await self.run_morning_probe()
                        
                        # 执行信号
                        if signals:
                            await self.execute_signals(signals)
                            
                        self.last_probe_time = datetime.now()
                        
                # 等待下次检查
                await asyncio.sleep(10)
                
        except KeyboardInterrupt:
            self.logger.info("Live trading stopped by user")
        except Exception as e:
            self.logger.error(f"Live trading error: {e}")
        finally:
            self.is_running = False
            await self.executor.stop_order_processing()
            processing_task.cancel()
            
    def stop_trading(self):
        """停止交易"""
        self.is_running = False
        self.logger.info("Trading stopped")
        
    def get_status(self):
        """获取系统状态"""
        status = {
            'mode': self.mode,
            'is_running': self.is_running,
            'last_probe_time': self.last_probe_time.isoformat() if self.last_probe_time else None,
            'current_positions': len(self.current_positions),
            'strategy_status': self.strategy.get_strategy_status(),
        }
        
        if self.executor:
            status['executor_status'] = self.executor.get_position_status()
            
        if self.backtest_engine:
            status['backtest_results'] = self.backtest_engine.results
            
        return status


async def main():
    """主函数"""
    print("=== 情绪套利策略 v3.0 - 终极实战版 ===")
    print("1. 运行回测")
    print("2. 运行模拟盘")
    print("3. 运行实盘")
    print("4. 仅运行数据探针")
    
    choice = input("请选择运行模式 (1-4): ").strip()
    
    # 创建主控制器
    mode = 'paper' if choice == '2' else 'live' if choice == '3' else 'backtest'
    controller = SentimentArbitrageV3(mode=mode)
    
    # 初始化
    if not await controller.initialize():
        print("初始化失败")
        return
        
    try:
        if choice == '1':
            # 运行回测
            await controller.run_backtest()
            
        elif choice == '2':
            # 运行模拟盘
            await controller.run_live_trading()
            
        elif choice == '3':
            # 运行实盘
            confirm = input("确认运行实盘交易? (yes/no): ").strip().lower()
            if confirm == 'yes':
                await controller.run_live_trading()
            else:
                print("取消实盘交易")
                
        elif choice == '4':
            # 仅运行数据探针
            signals = await controller.run_morning_probe()
            print(f"生成 {len(signals)} 个信号")
            
    except KeyboardInterrupt:
        print("\n用户中断操作")
    except Exception as e:
        print(f"运行错误: {e}")
    finally:
        controller.stop_trading()


if __name__ == "__main__":
    asyncio.run(main())