# -*- coding: utf-8 -*-
"""
情绪套利策略 v3.0 - 回测框架
支持 T+1/T+2 滚动退出逻辑的完整回测系统
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os
import sys
# import matplotlib.pyplot as plt
# import seaborn as sns

# 添加父目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategy_v3 import SentimentStrategyV3

class SentimentBacktestV3:
    """情绪套利策略 v3.0 回测引擎"""
    
    def __init__(self, initial_capital=100000):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.positions = {}
        self.trade_history = []
        self.daily_returns = []
        self.portfolio_values = []
        
        # 回测配置
        self.commission_rate = 0.0003  # 手续费率
        self.slippage_rate = 0.001     # 滑点率
        self.max_positions = 5         # 最大持仓数
        
        # 策略引擎
        self.strategy = SentimentStrategyV3()
        
        # 回测结果
        self.results = {}
        
    def log(self, msg):
        """日志输出"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Backtest: {msg}")
        
    def load_historical_data(self, stock_list, start_date, end_date):
        """
        加载历史数据
        
        Args:
            stock_list: 股票代码列表
            start_date: 开始日期 'YYYY-MM-DD'
            end_date: 结束日期 'YYYY-MM-DD'
        """
        self.log(f"Loading historical data from {start_date} to {end_date}")
        
        historical_data = {}
        
        try:
            from xtquant import xtdata
            
            # 下载数据
            xtdata.download_history_data(stock_list, period='1d', 
                                        start_time=start_date.replace('-', ''),
                                        end_time=end_date.replace('-', ''))
            
            # 获取数据
            for stock in stock_list:
                try:
                    data = xtdata.get_market_data(
                        field_list=['open', 'high', 'low', 'close', 'volume', 'amount'],
                        stock_list=[stock],
                        period='1d',
                        start_time=start_date.replace('-', ''),
                        end_time=end_date.replace('-', '')
                    )
                    
                    if data and not data[stock].empty:
                        historical_data[stock] = data[stock]
                        self.log(f"Loaded {len(data[stock])} days for {stock}")
                    else:
                        self.log(f"No data for {stock}")
                        
                except Exception as e:
                    self.log(f"Failed to load data for {stock}: {e}")
                    
        except ImportError:
            # Mock 数据用于测试
            self.log("Using mock historical data")
            date_range = pd.date_range(start=start_date, end=end_date, freq='D')
            
            for stock in stock_list:
                # 生成模拟价格数据
                np.random.seed(hash(stock) % 1000)
                prices = 5.0 + np.random.randn(len(date_range)).cumsum() * 0.1
                volumes = np.random.randint(1000, 10000, len(date_range))
                
                df = pd.DataFrame({
                    'open': prices,
                    'high': prices * (1 + np.random.rand(len(date_range)) * 0.02),
                    'low': prices * (1 - np.random.rand(len(date_range)) * 0.02),
                    'close': prices * (1 + np.random.randn(len(date_range)) * 0.01),
                    'volume': volumes,
                    'amount': prices * volumes
                }, index=date_range)
                
                historical_data[stock] = df
                
        return historical_data
        
    def simulate_probe_data(self, date, stock_data):
        """
        模拟探针数据生成
        """
        # 基于当日数据生成模拟探针结果
        candidates = []
        
        for stock, df in stock_data.items():
            if len(df) > 0:
                row = df.iloc[-1]
                change_pct = (row['close'] - row['open']) / row['open'] * 100
                volume_ratio = row['volume'] / 10000  # 简化计算
                
                # 模拟板块
                sector = ['地产', '科技', '医药', '环保'][hash(stock) % 4]
                
                candidates.append({
                    'stock': stock,
                    'sector': sector,
                    'change_pct': change_pct,
                    'sector_strength': np.random.random() * 50,
                    'volume_ratio': volume_ratio
                })
        
        # 模拟市场情绪
        limit_down_count = np.random.randint(5, 30)
        market_sentiment = {
            'limit_down_count': limit_down_count,
            'limit_up_count': np.random.randint(0, 10),
            'avg_change': np.random.randn(),
            'market_sentiment': '恐慌' if limit_down_count > 20 else '中性'
        }
        
        # 模拟板块强度
        sectors = {}
        for candidate in candidates:
            sector = candidate['sector']
            if sector not in sectors:
                sectors[sector] = []
            sectors[sector].append(candidate)
            
        sector_strength = {}
        for sector, stocks in sectors.items():
            if len(stocks) > 0:
                avg_change = np.mean([s['change_pct'] for s in stocks])
                sector_strength[sector] = {
                    'score': np.random.random() * 30,
                    'avg_change': avg_change,
                    'stock_count': len(stocks)
                }
        
        probe_results = {
            'timestamp': date.isoformat(),
            'candidates': candidates,
            'market_sentiment': market_sentiment,
            'sector_strength': sector_strength
        }
        
        return probe_results
        
    def calculate_position_size(self, stock_price, available_capital):
        """
        计算仓位大小
        """
        max_position_value = available_capital * self.strategy.config['position_size']
        shares = int(max_position_value / stock_price / 100) * 100  # 整手
        return shares
        
    def execute_buy(self, stock, price, shares, date):
        """
        执行买入操作
        """
        if shares <= 0:
            return False
            
        # 计算交易成本
        base_cost = price * shares
        commission = base_cost * self.commission_rate
        slippage = base_cost * self.slippage_rate
        total_cost = base_cost + commission + slippage
        
        # 检查资金充足性
        if total_cost > self.current_capital:
            return False
            
        # 执行交易
        self.current_capital -= total_cost
        
        # 记录持仓
        self.positions[stock] = {
            'shares': shares,
            'entry_price': price,
            'entry_date': date,
            'entry_value': total_cost
        }
        
        # 记录交易历史
        trade = {
            'date': date,
            'stock': stock,
            'action': 'BUY',
            'price': price,
            'shares': shares,
            'value': total_cost,
            'capital': self.current_capital
        }
        self.trade_history.append(trade)
        
        self.log(f"BUY {stock}: {shares} shares @ {price:.2f}, cost: {total_cost:.2f}")
        return True
        
    def execute_sell(self, stock, price, date):
        """
        执行卖出操作
        """
        if stock not in self.positions:
            return False
            
        position = self.positions[stock]
        shares = position['shares']
        
        # 计算交易收入
        base_revenue = price * shares
        commission = base_revenue * self.commission_rate
        slippage = base_revenue * self.slippage_rate
        net_revenue = base_revenue - commission - slippage
        
        # 计算盈亏
        entry_cost = position['entry_value']
        profit = net_revenue - entry_cost
        profit_rate = profit / entry_cost * 100
        
        # 执行交易
        self.current_capital += net_revenue
        
        # 记录交易历史
        trade = {
            'date': date,
            'stock': stock,
            'action': 'SELL',
            'price': price,
            'shares': shares,
            'revenue': net_revenue,
            'profit': profit,
            'profit_rate': profit_rate,
            'capital': self.current_capital
        }
        self.trade_history.append(trade)
        
        # 移除持仓
        del self.positions[stock]
        
        self.log(f"SELL {stock}: {shares} shares @ {price:.2f}, profit: {profit_rate:.2f}%")
        return True
        
    def calculate_portfolio_value(self, stock_prices):
        """
        计算投资组合价值
        """
        portfolio_value = self.current_capital
        
        for stock, position in self.positions.items():
            if stock in stock_prices:
                market_value = position['shares'] * stock_prices[stock]
                portfolio_value += market_value
                
        return portfolio_value
        
    def run_backtest(self, stock_list, start_date, end_date):
        """
        运行回测
        
        Args:
            stock_list: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
        """
        self.log(f"Starting backtest: {start_date} to {end_date}")
        
        # 加载历史数据
        historical_data = self.load_historical_data(stock_list, start_date, end_date)
        
        if not historical_data:
            self.log("No historical data available")
            return {}
            
        # 获取交易日期
        all_dates = set()
        for stock_data in historical_data.values():
            all_dates.update(stock_data.index.date)
        trading_dates = sorted(list(all_dates))
        
        self.log(f"Trading {len(trading_dates)} days")
        
        # 逐日回测
        for date in trading_dates:
            # 获取当日数据
            daily_data = {}
            for stock, df in historical_data.items():
                if date in df.index.date:
                    daily_data[stock] = df.loc[df.index.date == date]
                    
            if len(daily_data) == 0:
                continue
                
            # 生成模拟探针数据
            probe_data = self.simulate_probe_data(date, daily_data)
            
            # 更新策略探针结果
            self.strategy.probe_results = probe_data
            
            # 生成交易信号
            signals = self.strategy.generate_daily_signals()
            
            # 执行买入信号
            available_capital = self.current_capital / self.max_positions
            
            for signal in signals:
                if len(self.positions) >= self.max_positions:
                    break
                    
                stock = signal['stock']
                if stock in daily_data and stock not in self.positions:
                    price = daily_data[stock]['close'].iloc[-1]
                    shares = self.calculate_position_size(price, available_capital)
                    
                    if shares > 0:
                        self.execute_buy(stock, price, shares, date)
                        
            # 检查卖出条件
            current_prices = {stock: df['close'].iloc[-1] for stock, df in daily_data.items()}
            
            for stock, position in list(self.positions.items()):
                if stock in current_prices:
                    current_price = current_prices[stock]
                    entry_price = position['entry_price']
                    entry_date = position['entry_date']
                    
                    # 计算持仓天数
                    holding_days = (date - entry_date).days if isinstance(date, (datetime, pd.Timestamp)) else 0
                    if isinstance(date, pd.Timestamp):
                        entry_date_dt = entry_date if isinstance(entry_date, pd.Timestamp) else pd.Timestamp(entry_date)
                        holding_days = (date - entry_date_dt).days
                    
                    # 计算收益率
                    profit_rate = (current_price - entry_price) / entry_price * 100
                    
                    # 卖出条件判断
                    should_sell = False
                    sell_reason = ""
                    
                    # 止损
                    if profit_rate <= self.strategy.config['mcp_stop_loss']:
                        should_sell = True
                        sell_reason = f"止损: {profit_rate:.2f}%"
                        
                    # 时间止损
                    elif holding_days >= self.strategy.config['holding_days_max']:
                        should_sell = True
                        sell_reason = f"时间止损: {holding_days}天"
                        
                    # T+1/T+2 退出
                    elif profit_rate > 2 and holding_days >= self.strategy.config['t1_exit_days']:
                        should_sell = True
                        sell_reason = f"T+1退出: {profit_rate:.2f}%"
                        
                    elif profit_rate > 0.5 and holding_days >= self.strategy.config['t2_exit_days']:
                        should_sell = True
                        sell_reason = f"T+2退出: {profit_rate:.2f}%"
                        
                    if should_sell:
                        self.execute_sell(stock, current_price, date)
                        
            # 计算投资组合价值
            portfolio_value = self.calculate_portfolio_value(current_prices)
            self.portfolio_values.append({
                'date': date,
                'value': portfolio_value,
                'capital': self.current_capital,
                'positions': len(self.positions)
            })
            
        # 计算回测结果
        self.calculate_performance()
        
        return self.results
        
    def calculate_performance(self):
        """
        计算回测绩效指标
        """
        if not self.portfolio_values:
            return
            
        # 基础指标
        final_value = self.portfolio_values[-1]['value']
        total_return = (final_value - self.initial_capital) / self.initial_capital * 100
        
        # 日收益率
        daily_values = [pv['value'] for pv in self.portfolio_values]
        daily_returns = [(daily_values[i] - daily_values[i-1]) / daily_values[i-1] 
                         for i in range(1, len(daily_values))]
        
        # 年化收益率
        trading_days = len(daily_returns)
        annual_return = (final_value / self.initial_capital) ** (252 / trading_days) - 1
        
        # 最大回撤
        peak_values = []
        peak = daily_values[0]
        max_drawdown = 0
        
        for value in daily_values:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak
            max_drawdown = max(max_drawdown, drawdown)
            peak_values.append(peak)
            
        max_drawdown *= 100
        
        # 夏普比率
        if daily_returns:
            sharpe_ratio = np.mean(daily_returns) / np.std(daily_returns) * np.sqrt(252) if np.std(daily_returns) > 0 else 0
        else:
            sharpe_ratio = 0
            
        # 交易统计
        buy_trades = [t for t in self.trade_history if t['action'] == 'BUY']
        sell_trades = [t for t in self.trade_history if t['action'] == 'SELL']
        profitable_trades = [t for t in sell_trades if t.get('profit_rate', 0) > 0]
        
        win_rate = len(profitable_trades) / len(sell_trades) * 100 if sell_trades else 0
        
        # 平均持仓天数
        holding_days = []
        for sell_trade in sell_trades:
            stock = sell_trade['stock']
            sell_date = sell_trade['date']
            
            # 查找对应的买入交易
            buy_trades_for_stock = [t for t in buy_trades if t['stock'] == stock and t['date'] < sell_date]
            if buy_trades_for_stock:
                buy_date = max(t['date'] for t in buy_trades_for_stock)
                holding_days.append((sell_date - buy_date).days)
                
        avg_holding_days = np.mean(holding_days) if holding_days else 0
        
        # 保存结果
        self.results = {
            'initial_capital': self.initial_capital,
            'final_value': final_value,
            'total_return': total_return,
            'annual_return': annual_return * 100,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'win_rate': win_rate,
            'total_trades': len(self.trade_history),
            'buy_trades': len(buy_trades),
            'sell_trades': len(sell_trades),
            'profitable_trades': len(profitable_trades),
            'avg_holding_days': avg_holding_days,
            'trading_days': trading_days,
            'daily_returns': daily_returns,
            'portfolio_values': self.portfolio_values,
            'trade_history': self.trade_history
        }
        
    def print_results(self):
        """打印回测结果"""
        if not self.results:
            print("No results to display")
            return
            
        print(f"\n{'='*50}")
        print(f"情绪套利策略 v3.0 回测结果")
        print(f"{'='*50}")
        print(f"初始资金: {self.results['initial_capital']:,.2f}")
        print(f"最终价值: {self.results['final_value']:,.2f}")
        print(f"总收益率: {self.results['total_return']:.2f}%")
        print(f"年化收益率: {self.results['annual_return']:.2f}%")
        print(f"最大回撤: {self.results['max_drawdown']:.2f}%")
        print(f"夏普比率: {self.results['sharpe_ratio']:.3f}")
        print(f"胜率: {self.results['win_rate']:.2f}%")
        print(f"总交易次数: {self.results['total_trades']}")
        print(f"买入次数: {self.results['buy_trades']}")
        print(f"卖出次数: {self.results['sell_trades']}")
        print(f"盈利交易: {self.results['profitable_trades']}")
        print(f"平均持仓天数: {self.results['avg_holding_days']:.1f}天")
        print(f"交易天数: {self.results['trading_days']}")
        print(f"{'='*50}")
        
    def save_results(self, filename='D:/QuantWorkspace/export/backtest_v3_results.json'):
        """保存回测结果"""
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        # 准备可序列化的结果
        serializable_results = {}
        for key, value in self.results.items():
            if isinstance(value, (list, dict)):
                # 转换日期对象
                if key in ['portfolio_values', 'trade_history']:
                    serializable_results[key] = []
                    for item in value:
                        if isinstance(item, dict):
                            serializable_item = {}
                            for k, v in item.items():
                                if hasattr(v, 'isoformat'):
                                    serializable_item[k] = v.isoformat()
                                else:
                                    serializable_item[k] = v
                            serializable_results[key].append(serializable_item)
                        else:
                            serializable_results[key].append(value)
                else:
                    serializable_results[key] = value
            else:
                serializable_results[key] = value
                
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(serializable_results, f, ensure_ascii=False, indent=2, default=str)
            
        self.log(f"Results saved to {filename}")


def run_sample_backtest():
    """运行示例回测"""
    # 配置
    stock_list = ['600381.SH', '300007.SZ', '000609.SZ', '300518.SZ', '300506.SZ']
    start_date = '2023-01-01'
    end_date = '2023-12-31'
    
    # 创建回测引擎
    backtest = SentimentBacktestV3(initial_capital=100000)
    
    # 运行回测
    results = backtest.run_backtest(stock_list, start_date, end_date)
    
    # 打印结果
    backtest.print_results()
    
    # 保存结果
    backtest.save_results()
    
    return backtest


if __name__ == "__main__":
    run_sample_backtest()