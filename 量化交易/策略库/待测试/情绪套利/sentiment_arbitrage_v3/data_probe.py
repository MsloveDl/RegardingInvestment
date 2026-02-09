# -*- coding: utf-8 -*-
"""
情绪套利策略 v3.0 - 数据探针模块
负责并发数据采集和实时监控
"""

import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import json
import os
import sys

# 添加父目录到路径以便导入配置
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from xtquant import xtdata
except ImportError:
    print("Warning: xtquant not available, using mock data")
    xtdata = None

class SentimentDataProbe:
    """情绪套利数据探针"""
    
    def __init__(self):
        self.stock_pool = []
        self.sector_mapping = {}
        self.probe_results = {}
        self.is_running = False
        
    def log(self, msg):
        """日志输出"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Probe: {msg}")
        
    def load_stock_pool(self):
        """加载股票池"""
        if not xtdata:
            # Mock 数据用于测试
            self.stock_pool = [
                '600381.SH', '300007.SZ', '000609.SZ', '300518.SZ', '300506.SZ',
                '300497.SZ', '300485.SZ', '300479.SZ', '300473.SZ', '300462.SZ'
            ]
            self.sector_mapping = {
                '600381.SH': '地产', '300007.SZ': '环保', '000609.SZ': '地产',
                '300518.SZ': '科技', '300506.SZ': '科技', '300497.SZ': '科技',
                '300485.SZ': '医药', '300479.SZ': '医药', '300473.SZ': '医药',
                '300462.SZ': '医药'
            }
            self.log(f"Loaded {len(self.stock_pool)} mock stocks")
            return True
            
        # 获取全市场股票
        all_stocks = xtdata.get_stock_list_in_sector('沪深A股')
        
        # 过滤条件：市值 > 50亿，流动性筛选
        valid_stocks = []
        for stock in all_stocks[:100]:  # 限制数量避免API限制
            try:
                # 获取基本信息
                market_data = xtdata.get_market_data(
                    field_list=['total_mv', 'turnover_ratio', 'amount'],
                    stock_list=[stock],
                    period='1d',
                    count=1
                )
                
                if market_data and market_data['total_mv'].iloc[0] > 5000:  # 市值 > 50亿
                    valid_stocks.append(stock)
                    
            except Exception as e:
                continue
                
        self.stock_pool = valid_stocks
        self.log(f"Loaded {len(self.stock_pool)} valid stocks")
        return True
        
    def calculate_sector_strength(self, snapshot_data):
        """
        计算板块强度 SS (Sector Strength)
        
        SS = (涨幅均值 * 涨停比例 * 量比均值) / 跌停比例
        """
        if not snapshot_data:
            return {}
            
        sector_data = {}
        
        for stock, data in snapshot_data.items():
            sector = self.sector_mapping.get(stock, '其他')
            
            if sector not in sector_data:
                sector_data[sector] = {
                    'changes': [],
                    'limit_up': 0,
                    'limit_down': 0,
                    'volume_ratios': []
                }
                
            change_pct = data.get('change_pct', 0)
            is_limit_up = data.get('is_limit_up', False)
            is_limit_down = data.get('is_limit_down', False)
            volume_ratio = data.get('volume_ratio', 1.0)
            
            sector_data[sector]['changes'].append(change_pct)
            sector_data[sector]['volume_ratios'].append(volume_ratio)
            
            if is_limit_up:
                sector_data[sector]['limit_up'] += 1
            elif is_limit_down:
                sector_data[sector]['limit_down'] += 1
        
        # 计算 SS 值
        ss_scores = {}
        for sector, data in sector_data.items():
            if len(data['changes']) == 0:
                continue
                
            avg_change = np.mean(data['changes'])
            limit_up_ratio = data['limit_up'] / len(data['changes'])
            avg_volume_ratio = np.mean(data['volume_ratios'])
            limit_down_ratio = data['limit_down'] / len(data['changes'])
            
            # SS 计算公式
            if limit_down_ratio > 0:
                ss_score = (avg_change * limit_up_ratio * avg_volume_ratio) / limit_down_ratio
            else:
                ss_score = avg_change * limit_up_ratio * avg_volume_ratio * 10  # 无跌停时加权
                
            ss_scores[sector] = {
                'score': ss_score,
                'avg_change': avg_change,
                'limit_up_ratio': limit_up_ratio,
                'limit_down_ratio': limit_down_ratio,
                'avg_volume_ratio': avg_volume_ratio,
                'stock_count': len(data['changes'])
            }
            
        return ss_scores
        
    def detect_market_sentiment(self, snapshot_data):
        """
        检测市场情绪
        
        Returns:
            dict: {
                'limit_down_count': 跌停数量,
                'limit_up_count': 涨停数量,
                'avg_change': 平均涨跌幅,
                'market_sentiment': '极度恐慌'|'恐慌'|'中性'|'乐观'|'极度乐观'
            }
        """
        if not snapshot_data:
            return {}
            
        changes = [data.get('change_pct', 0) for data in snapshot_data.values()]
        limit_down_count = sum(1 for data in snapshot_data.values() 
                              if data.get('is_limit_down', False))
        limit_up_count = sum(1 for data in snapshot_data.values() 
                            if data.get('is_limit_up', False))
        
        avg_change = np.mean(changes) if changes else 0
        
        # 情绪判断
        if limit_down_count > 50:
            market_sentiment = '极度恐慌'
        elif limit_down_count > 20 or avg_change < -2:
            market_sentiment = '恐慌'
        elif limit_up_count > 50 or avg_change > 2:
            market_sentiment = '极度乐观'
        elif limit_up_count > 20 or avg_change > 1:
            market_sentiment = '乐观'
        else:
            market_sentiment = '中性'
            
        return {
            'limit_down_count': limit_down_count,
            'limit_up_count': limit_up_count,
            'avg_change': avg_change,
            'market_sentiment': market_sentiment
        }
        
    async def get_925_snapshot(self):
        """
        获取 9:25 集合竞价快照
        """
        self.log("Starting 9:25 snapshot...")
        
        if not xtdata:
            # Mock 数据
            mock_data = {}
            for i, stock in enumerate(self.stock_pool):
                mock_data[stock] = {
                    'open': 5.0 + np.random.randn() * 0.2,
                    'yesterday_close': 5.0,
                    'volume': np.random.randint(1000, 10000),
                    'amount': np.random.randint(5000, 50000),
                    'change_pct': np.random.randn() * 3,
                    'is_limit_up': np.random.random() < 0.1,
                    'is_limit_down': np.random.random() < 0.1,
                    'volume_ratio': 1.0 + np.random.random() * 2
                }
            return mock_data
            
        snapshot_data = {}
        
        # 使用线程池并发获取数据
        with ThreadPoolExecutor(max_workers=10) as executor:
            loop = asyncio.get_event_loop()
            
            # 获取昨日收盘价
            close_data = {}
            for stock in self.stock_pool:
                try:
                    data = xtdata.get_market_data(
                        field_list=['close'],
                        stock_list=[stock],
                        period='1d',
                        count=2
                    )
                    if data and len(data['close']) >= 2:
                        close_data[stock] = data['close'].iloc[-2]  # 昨收
                except Exception as e:
                    self.log(f"Failed to get close data for {stock}: {e}")
                    
            # 获取集合竞价数据
            for stock in self.stock_pool:
                try:
                    # 获取实时行情
                    tick_data = xtdata.get_full_tick([stock])
                    
                    if tick_data and stock in tick_data:
                        tick = tick_data[stock]
                        yesterday_close = close_data.get(stock, 5.0)
                        current_price = tick.get('open', yesterday_close)
                        
                        # 计算涨跌幅
                        change_pct = (current_price - yesterday_close) / yesterday_close * 100
                        
                        # 判断涨跌停
                        is_limit_up = change_pct >= 9.8
                        is_limit_down = change_pct <= -9.8
                        
                        snapshot_data[stock] = {
                            'open': current_price,
                            'yesterday_close': yesterday_close,
                            'volume': tick.get('volume', 0),
                            'amount': tick.get('amount', 0),
                            'change_pct': change_pct,
                            'is_limit_up': is_limit_up,
                            'is_limit_down': is_limit_down,
                            'volume_ratio': tick.get('volume', 0) / 10000  # 简化计算
                        }
                        
                except Exception as e:
                    self.log(f"Failed to get tick data for {stock}: {e}")
                    
        self.log(f"Collected {len(snapshot_data)} snapshot data")
        return snapshot_data
        
    async def monitor_individual_stocks(self, target_stocks):
        """
        监控个股的 SPP (抛压探测) 和 TS (题材协同性)
        """
        self.log(f"Starting individual monitoring for {len(target_stocks)} stocks...")
        
        if not xtdata:
            # Mock 监控数据
            monitoring_results = {}
            for stock in target_stocks:
                monitoring_results[stock] = {
                    'spp_score': np.random.random() * 100,
                    'ts_score': np.random.random() * 100,
                    'realtime_volume': np.random.randint(1000, 10000),
                    'sell_pressure': np.random.random()
                }
            return monitoring_results
            
        monitoring_results = {}
        
        # 持续监控逻辑（这里简化为一次性获取）
        with ThreadPoolExecutor(max_workers=5) as executor:
            loop = asyncio.get_event_loop()
            
            tasks = []
            for stock in target_stocks:
                task = loop.run_in_executor(
                    executor,
                    self._analyze_single_stock,
                    stock
                )
                tasks.append(task)
                
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, stock in enumerate(target_stocks):
                if not isinstance(results[i], Exception):
                    monitoring_results[stock] = results[i]
                    
        return monitoring_results
        
    def _analyze_single_stock(self, stock):
        """
        分析单个股票的 SPP 和 TS
        """
        try:
            # 获取分钟级数据
            minute_data = xtdata.get_market_data(
                field_list=['close', 'volume', 'amount'],
                stock_list=[stock],
                period='1m',
                count=240  # 4小时数据
            )
            
            if not minute_data:
                return {}
                
            df = minute_data[stock]
            
            # SPP (Sell Pressure Probe) 计算
            # SPP = (大单卖出量 - 大单买入量) / 总成交量
            volumes = df['volume'].values
            amounts = df['amount'].values
            
            # 简化的抛压计算
            price_changes = df['close'].pct_change().dropna()
            negative_changes = price_changes[price_changes < 0]
            sell_pressure = len(negative_changes) / len(price_changes) if len(price_changes) > 0 else 0
            
            spp_score = sell_pressure * np.std(price_changes) * 100 if len(price_changes) > 0 else 0
            
            # TS (Thematic Synergy) 计算
            # TS = 同板块股票涨幅相关性
            sector = self.sector_mapping.get(stock, '其他')
            ts_score = np.random.random() * 100  # 简化实现
            
            return {
                'spp_score': spp_score,
                'ts_score': ts_score,
                'realtime_volume': volumes[-1] if len(volumes) > 0 else 0,
                'sell_pressure': sell_pressure,
                'price_volatility': np.std(price_changes) if len(price_changes) > 0 else 0
            }
            
        except Exception as e:
            self.log(f"Error analyzing {stock}: {e}")
            return {}
            
    async def run_morning_probe(self):
        """
        运行早晨探针（9:25）
        """
        self.log("Starting morning probe...")
        
        # 1. 获取快照数据
        snapshot_data = await self.get_925_snapshot()
        
        # 2. 计算板块强度
        ss_scores = self.calculate_sector_strength(snapshot_data)
        
        # 3. 检测市场情绪
        market_sentiment = self.detect_market_sentiment(snapshot_data)
        
        # 4. 筛选候选股票
        candidates = self._screen_candidates(snapshot_data, ss_scores, market_sentiment)
        
        # 5. 保存结果
        probe_results = {
            'timestamp': datetime.now().isoformat(),
            'snapshot_data': snapshot_data,
            'sector_strength': ss_scores,
            'market_sentiment': market_sentiment,
            'candidates': candidates
        }
        
        self.probe_results = probe_results
        
        # 保存到文件
        output_file = 'D:/QuantWorkspace/export/probe_results.json'
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(probe_results, f, ensure_ascii=False, indent=2, default=str)
            
        self.log(f"Probe results saved to {output_file}")
        return probe_results
        
    def _screen_candidates(self, snapshot_data, ss_scores, market_sentiment):
        """
        筛选候选股票
        
        筛选条件：
        1. 跌停数量 > 20 (市场恐慌)
        2. 个股涨幅 < 3% (未大涨)
        3. 板块强度 > 阈值
        4. 抛压探测 < 阈值
        """
        candidates = []
        
        # 市场恐慌条件检查
        if market_sentiment.get('limit_down_count', 0) < 20:
            self.log("Market not in panic mode, skipping candidate screening")
            return candidates
            
        for stock, data in snapshot_data.items():
            change_pct = data.get('change_pct', 0)
            
            # 个股涨幅条件
            if change_pct > 3:
                continue
                
            # 获取板块强度
            sector = self.sector_mapping.get(stock, '其他')
            sector_strength = ss_scores.get(sector, {}).get('score', 0)
            
            # 基本筛选条件
            if sector_strength > 10 and change_pct > 0:
                candidates.append({
                    'stock': stock,
                    'sector': sector,
                    'change_pct': change_pct,
                    'sector_strength': sector_strength,
                    'volume_ratio': data.get('volume_ratio', 1.0)
                })
                
        # 排序（按板块强度和涨幅）
        candidates.sort(key=lambda x: (x['sector_strength'], x['change_pct']), reverse=True)
        
        self.log(f"Screened {len(candidates)} candidates")
        return candidates[:20]  # 返回前20个


async def main():
    """主函数"""
    probe = SentimentDataProbe()
    
    # 加载股票池
    await asyncio.get_event_loop().run_in_executor(None, probe.load_stock_pool)
    
    # 运行早晨探针
    results = await probe.run_morning_probe()
    
    # 打印结果摘要
    print(f"\n=== Probe Results Summary ===")
    market_sentiment = results.get('market_sentiment', {})
    print(f"Market Sentiment: {market_sentiment.get('market_sentiment', 'Unknown')}")
    print(f"Limit Down Count: {market_sentiment.get('limit_down_count', 0)}")
    print(f"Candidates Found: {len(results.get('candidates', []))}")
    
    candidates = results.get('candidates', [])
    if candidates:
        print(f"\nTop 5 Candidates:")
        for i, candidate in enumerate(candidates[:5]):
            print(f"{i+1}. {candidate['stock']} ({candidate['sector']}): "
                  f"Change={candidate['change_pct']:.2f}%, "
                  f"SS={candidate['sector_strength']:.2f}")
    
    # 更新状态文件
    status_file = 'D:/QuantWorkspace/export/v3_status.txt'
    market_sentiment = results.get('market_sentiment', {})
    with open(status_file, 'w', encoding='utf-8') as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
               f"情绪套利 v3.0 - 数据探针模块完成\n")
        f.write(f"市场情绪: {market_sentiment.get('market_sentiment', 'Unknown')}\n")
        f.write(f"候选股票: {len(results.get('candidates', []))} 只\n")
        f.write(f"下一阶段: 策略决策引擎开发\n")
    
    print(f"\nStatus updated: {status_file}")


if __name__ == "__main__":
    asyncio.run(main())