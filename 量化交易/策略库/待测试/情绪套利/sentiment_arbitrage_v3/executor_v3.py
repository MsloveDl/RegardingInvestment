# -*- coding: utf-8 -*-
"""
情绪套利策略 v3.0 - 模拟盘/实盘异步报单模块
实现高效的异步交易执行和风险管理
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import threading
import queue
import os
import sys

# 添加父目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class OrderExecutorV3:
    """订单执行器 v3.0"""
    
    def __init__(self, mode='paper'):
        """
        初始化订单执行器
        
        Args:
            mode: 'paper' 模拟盘, 'live' 实盘
        """
        self.mode = mode
        self.order_queue = asyncio.Queue()
        self.order_results = {}
        self.position_tracker = {}
        self.risk_manager = RiskManager()
        
        # 交易配置
        self.commission_rate = 0.0003
        self.slippage_rate = 0.001
        self.max_order_size = 0.3  # 单笔订单最大仓位比例
        
        # 异步任务管理
        self.running = False
        self.order_tasks = {}
        
        # API连接
        self.trader = None
        self.account_id = None
        
        self.log(f"OrderExecutor initialized in {mode} mode")
        
    def log(self, msg):
        """日志输出"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Executor: {msg}")
        
    async def initialize(self):
        """初始化交易接口"""
        if self.mode == 'live':
            try:
                from xtquant import xttrader
                
                # 初始化交易接口
                self.trader = xttrader.XtQuantTrader("./", session_id=1)
                
                # 连接账号
                connect_result = self.trader.connect()
                if connect_result == 0:
                    self.log("Trade connection successful")
                    
                    # 获取账号ID
                    accounts = self.trader.get_stock_account()
                    if accounts:
                        self.account_id = accounts[0]
                        self.log(f"Account ID: {self.account_id}")
                    else:
                        raise Exception("No account found")
                else:
                    raise Exception(f"Connection failed: {connect_result}")
                    
            except ImportError:
                self.log("xttrader not available, falling back to paper mode")
                self.mode = 'paper'
                
        else:
            self.log("Paper trading mode initialized")
            
        return True
        
    async def submit_order(self, order_request: Dict) -> str:
        """
        提交订单
        
        Args:
            order_request: 订单请求字典
                {
                    'stock': '600381.SH',
                    'action': 'BUY' | 'SELL',
                    'order_type': 'LIMIT' | 'MARKET',
                    'price': 5.50,
                    'quantity': 1000,
                    'time_limit': 'GTC' | 'IOC',
                    'strategy': 'sentiment_v3'
                }
                
        Returns:
            str: 订单ID
        """
        order_id = f"{order_request['stock']}_{order_request['action']}_{int(time.time())}"
        
        # 风险检查
        risk_check = await self.risk_manager.check_order_risk(order_request, self.position_tracker)
        if not risk_check['passed']:
            self.log(f"Order rejected by risk manager: {risk_check['reason']}")
            return None
            
        # 验证订单参数
        validation = self.validate_order(order_request)
        if not validation['valid']:
            self.log(f"Order validation failed: {validation['reason']}")
            return None
            
        # 添加到执行队列
        order_request['order_id'] = order_id
        order_request['submit_time'] = datetime.now().isoformat()
        
        await self.order_queue.put(order_request)
        self.log(f"Order submitted: {order_id}")
        
        return order_id
        
    def validate_order(self, order_request: Dict) -> Dict:
        """
        验证订单参数
        """
        try:
            stock = order_request.get('stock', '')
            action = order_request.get('action', '')
            price = order_request.get('price', 0)
            quantity = order_request.get('quantity', 0)
            
            # 基本参数检查
            if not stock or action not in ['BUY', 'SELL']:
                return {'valid': False, 'reason': 'Invalid stock or action'}
                
            if price <= 0 or quantity <= 0:
                return {'valid': False, 'reason': 'Invalid price or quantity'}
                
            # 数量检查（必须是100的倍数）
            if quantity % 100 != 0:
                return {'valid': False, 'reason': 'Quantity must be multiple of 100'}
                
            # 价格检查（涨跌停板）
            price_check = self.check_price_limits(stock, price)
            if not price_check['valid']:
                return {'valid': False, 'reason': price_check['reason']}
                
            return {'valid': True}
            
        except Exception as e:
            return {'valid': False, 'reason': f'Validation error: {str(e)}'}
            
    def check_price_limits(self, stock: str, price: float) -> Dict:
        """
        检查价格限制
        """
        try:
            if self.mode == 'live' and self.trader:
                # 获取实时行情
                quote = self.trader.get_full_tick([stock])
                if quote and stock in quote:
                    tick = quote[stock]
                    yesterday_close = tick.get('last_close', 0)
                    
                    if yesterday_close > 0:
                        limit_up = yesterday_close * 1.10  # 涨停价
                        limit_down = yesterday_close * 0.90  # 跌停价
                        
                        if price > limit_up:
                            return {'valid': False, 'reason': f'Price exceeds limit up: {limit_up:.2f}'}
                        elif price < limit_down:
                            return {'valid': False, 'reason': f'Price below limit down: {limit_down:.2f}'}
                            
            return {'valid': True}
            
        except Exception as e:
            self.log(f"Price limit check error: {e}")
            return {'valid': True}  # 出错时允许通过
            
    async def execute_order(self, order_request: Dict) -> Dict:
        """
        执行订单
        """
        order_id = order_request['order_id']
        stock = order_request['stock']
        action = order_request['action']
        price = order_request.get('price', 0)
        quantity = order_request['quantity']
        
        try:
            if self.mode == 'live' and self.trader:
                # 实盘交易
                result = await self.execute_live_order(order_request)
            else:
                # 模拟交易
                result = await self.execute_paper_order(order_request)
                
            # 更新持仓跟踪
            if result['success']:
                self.update_position_tracker(order_request, result)
                
            # 保存执行结果
            self.order_results[order_id] = {
                'order_request': order_request,
                'execution_result': result,
                'execute_time': datetime.now().isoformat()
            }
            
            return result
            
        except Exception as e:
            self.log(f"Order execution failed: {e}")
            error_result = {
                'success': False,
                'error': str(e),
                'order_id': order_id
            }
            self.order_results[order_id] = error_result
            return error_result
            
    async def execute_live_order(self, order_request: Dict) -> Dict:
        """
        执行实盘订单
        """
        try:
            from xtquant import xttype
            
            stock = order_request['stock']
            action = order_request['action']
            price = order_request.get('price', 0)
            quantity = order_request['quantity']
            order_type = order_request.get('order_type', 'LIMIT')
            
            # 转换订单类型
            if order_type == 'LIMIT':
                price_type = xttype.STOCK_PRICE_LIMIT
            elif order_type == 'MARKET':
                price_type = xttype.STOCK_PRICE_DEFAULT
            else:
                price_type = xttype.STOCK_PRICE_LIMIT
                
            # 转换买卖方向
            if action == 'BUY':
                side = xttype.STOCK_BUY
            else:
                side = xttype.STOCK_SELL
                
            # 提交订单
            order_id = self.trader.order_stock(
                account=self.account_id,
                stock_code=stock,
                order_type=price_type,
                order_volume=quantity,
                price_model=xttype.STOCK_PRICE_LIMIT,
                price=price,
                side=side,
                session_id=1
            )
            
            if order_id > 0:
                # 等待订单状态更新
                await self.wait_for_order_completion(order_id)
                
                return {
                    'success': True,
                    'order_id': order_id,
                    'message': 'Live order executed successfully'
                }
            else:
                return {
                    'success': False,
                    'error': f'Failed to submit order: {order_id}'
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f'Live order execution error: {str(e)}'
            }
            
    async def wait_for_order_completion(self, order_id: int, timeout: int = 30):
        """
        等待订单完成
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                # 获取订单状态
                orders = self.trader.query_stock_orders(self.account_id)
                
                for order in orders:
                    if order.order_id == order_id:
                        if order.order_status in [xttype.ORDER_SUCCEEDED, xttype.ORDER_CANCELED, xttype.ORDER_REJECTED]:
                            return order.order_status
                            
                await asyncio.sleep(1)
                
            except Exception as e:
                self.log(f"Order status query error: {e}")
                await asyncio.sleep(1)
                
        return None
        
    async def execute_paper_order(self, order_request: Dict) -> Dict:
        """
        执行模拟订单
        """
        # 模拟执行延迟
        await asyncio.sleep(0.1)
        
        stock = order_request['stock']
        action = order_request['action']
        price = order_request.get('price', 0)
        quantity = order_request['quantity']
        
        # 模拟成交价格（加入滑点）
        if action == 'BUY':
            execution_price = price * (1 + self.slippage_rate)
        else:
            execution_price = price * (1 - self.slippage_rate)
            
        # 计算成交金额
        total_amount = execution_price * quantity
        commission = total_amount * self.commission_rate
        
        # 模拟完全成交
        return {
            'success': True,
            'execution_price': round(execution_price, 2),
            'executed_quantity': quantity,
            'total_amount': round(total_amount, 2),
            'commission': round(commission, 2),
            'net_amount': round(total_amount + commission, 2),
            'message': 'Paper order executed successfully'
        }
        
    def update_position_tracker(self, order_request: Dict, execution_result: Dict):
        """
        更新持仓跟踪器
        """
        stock = order_request['stock']
        action = order_request['action']
        
        if execution_result['success']:
            executed_quantity = execution_result['executed_quantity']
            execution_price = execution_result['execution_price']
            
            if stock not in self.position_tracker:
                self.position_tracker[stock] = {
                    'quantity': 0,
                    'avg_cost': 0,
                    'total_cost': 0
                }
                
            position = self.position_tracker[stock]
            
            if action == 'BUY':
                # 买入更新
                old_quantity = position['quantity']
                old_cost = position['total_cost']
                new_cost = executed_quantity * execution_price
                
                position['quantity'] = old_quantity + executed_quantity
                position['total_cost'] = old_cost + new_cost
                position['avg_cost'] = position['total_cost'] / position['quantity']
                
            elif action == 'SELL':
                # 卖出更新
                if executed_quantity <= position['quantity':
                    position['quantity'] -= executed_quantity
                    
                    # 如果全部卖出，清空持仓记录
                    if position['quantity'] == 0:
                        position['avg_cost'] = 0
                        position['total_cost'] = 0
                        
            self.log(f"Position updated: {stock}, Quantity: {position['quantity']}, Avg Cost: {position['avg_cost']:.3f}")
            
    async def start_order_processing(self):
        """
        启动订单处理循环
        """
        self.running = True
        self.log("Order processing started")
        
        while self.running:
            try:
                # 从队列获取订单
                order_request = await asyncio.wait_for(self.order_queue.get(), timeout=1.0)
                
                # 异步执行订单
                task = asyncio.create_task(self.execute_order(order_request))
                self.order_tasks[order_request['order_id']] = task
                
                # 等待执行完成
                await task
                
                # 清理任务
                if order_request['order_id'] in self.order_tasks:
                    del self.order_tasks[order_request['order_id']]
                    
            except asyncio.TimeoutError:
                # 超时继续循环
                continue
            except Exception as e:
                self.log(f"Order processing error: {e}")
                
        self.log("Order processing stopped")
        
    async def stop_order_processing(self):
        """
        停止订单处理
        """
        self.running = False
        
        # 等待所有订单完成
        if self.order_tasks:
            await asyncio.gather(*self.order_tasks.values(), return_exceptions=True)
            
        self.log("Order processing stopped gracefully")
        
    def get_position_status(self) -> Dict:
        """
        获取持仓状态
        """
        total_value = 0
        total_cost = 0
        
        for stock, position in self.position_tracker.items():
            if position['quantity'] > 0:
                total_value += position['total_cost']
                total_cost += position['total_cost']
                
        return {
            'positions': self.position_tracker,
            'total_positions': len([p for p in self.position_tracker.values() if p['quantity'] > 0]),
            'total_value': total_value,
            'total_cost': total_cost,
            'update_time': datetime.now().isoformat()
        }
        
    def get_order_history(self) -> List[Dict]:
        """
        获取订单历史
        """
        return list(self.order_results.values())


class RiskManager:
    """风险管理器"""
    
    def __init__(self):
        self.max_positions = 5
        self.max_single_position = 0.3
        self.max_daily_orders = 20
        
        # 交易统计
        self.daily_order_count = 0
        self.last_reset_date = datetime.now().date()
        
    async def check_order_risk(self, order_request: Dict, position_tracker: Dict) -> Dict:
        """
        检查订单风险
        """
        # 重置日计数器
        current_date = datetime.now().date()
        if current_date != self.last_reset_date:
            self.daily_order_count = 0
            self.last_reset_date = current_date
            
        # 检查每日订单限制
        if self.daily_order_count >= self.max_daily_orders:
            return {
                'passed': False,
                'reason': f'Daily order limit exceeded: {self.daily_order_count}/{self.max_daily_orders}'
            }
            
        # 检查持仓数量限制
        current_positions = len([p for p in position_tracker.values() if p['quantity'] > 0])
        if order_request['action'] == 'BUY' and current_positions >= self.max_positions:
            return {
                'passed': False,
                'reason': f'Position limit exceeded: {current_positions}/{self.max_positions}'
            }
            
        # 检查单只股票仓位限制
        if order_request['action'] == 'BUY':
            stock = order_request['stock']
            if stock in position_tracker:
                current_quantity = position_tracker[stock]['quantity']
                # 这里需要获取账户总资金来计算比例，简化处理
                pass
                
        self.daily_order_count += 1
        
        return {
            'passed': True,
            'reason': 'Risk check passed'
        }


async def test_executor():
    """测试订单执行器"""
    # 创建执行器
    executor = OrderExecutorV3(mode='paper')
    
    # 初始化
    await executor.initialize()
    
    # 启动订单处理
    processing_task = asyncio.create_task(executor.start_order_processing())
    
    try:
        # 提交测试订单
        test_orders = [
            {
                'stock': '600381.SH',
                'action': 'BUY',
                'order_type': 'LIMIT',
                'price': 5.50,
                'quantity': 1000,
                'time_limit': 'GTC',
                'strategy': 'test'
            },
            {
                'stock': '600381.SH',
                'action': 'SELL',
                'order_type': 'LIMIT',
                'price': 5.60,
                'quantity': 500,
                'time_limit': 'GTC',
                'strategy': 'test'
            }
        ]
        
        order_ids = []
        for order in test_orders:
            order_id = await executor.submit_order(order)
            order_ids.append(order_id)
            
        # 等待执行完成
        await asyncio.sleep(2)
        
        # 打印结果
        print(f"\n=== Execution Results ===")
        for order_id in order_ids:
            if order_id and order_id in executor.order_results:
                result = executor.order_results[order_id]
                print(f"Order {order_id}: {result}")
                
        # 打印持仓状态
        position_status = executor.get_position_status()
        print(f"\nPosition Status: {json.dumps(position_status, indent=2, default=str)}")
        
    finally:
        # 停止处理
        await executor.stop_order_processing()
        processing_task.cancel()
        

if __name__ == "__main__":
    asyncio.run(test_executor())