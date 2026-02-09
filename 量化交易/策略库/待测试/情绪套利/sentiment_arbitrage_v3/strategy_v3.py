# -*- coding: utf-8 -*-
"""
情绪套利策略 v3.0 - 核心决策引擎
实现 SS, SPP, TS, MCP 的数学计算和决策逻辑
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os
import sys

# 添加父目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class SentimentStrategyV3:
    """情绪套利策略 v3.0 核心引擎"""
    
    def __init__(self):
        self.config = self._load_config()
        self.probe_results = {}
        self.decision_history = []
        self.open_positions = {}
        
    def _load_config(self):
        """加载配置"""
        return {
            # SS (Sector Strength) 参数
            'ss_threshold': 15.0,           # 板块强度阈值
            'ss_min_stocks': 3,             # 板块最少股票数
            
            # SPP (Sell Pressure Probe) 参数  
            'spp_threshold': 80.0,          # 抛压阈值
            'spp_volume_threshold': 1000,   # 成交量阈值
            
            # TS (Thematic Synergy) 参数
            'ts_threshold': 70.0,            # 题材协同性阈值
            'ts_correlation_window': 20,     # 相关性计算窗口
            
            # MCP (Momentum Trigger Point) 参数
            'mcp_entry_threshold': 1.5,     # 入场动量阈值
            'mcp_exit_threshold': -0.5,     # 出场动量阈值
            'mcp_stop_loss': -3.0,          # 止损阈值
            
            # 仓位管理参数
            'max_positions': 5,             # 最大持仓数
            'position_size': 0.2,            # 单只股票仓位比例
            'rebalance_threshold': 0.1,     # 再平衡阈值
            
            # 时间参数
            'holding_days_max': 3,          # 最大持仓天数
            't1_exit_days': 1,              # T+1 退出天数
            't2_exit_days': 2,              # T+2 退出天数
        }
        
    def log(self, msg):
        """日志输出"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Strategy: {msg}")
        
    def load_probe_results(self, probe_file='D:/QuantWorkspace/export/probe_results.json'):
        """加载探针结果"""
        try:
            with open(probe_file, 'r', encoding='utf-8') as f:
                self.probe_results = json.load(f)
            self.log(f"Loaded probe results from {probe_file}")
            return True
        except Exception as e:
            self.log(f"Failed to load probe results: {e}")
            return False
            
    def calculate_composite_score(self, stock_data):
        """
        计算综合评分
        
        Score = w1 * SS_score + w2 * (1 - SPP_score/100) + w3 * TS_score + w4 * MCP_score
        """
        # 权重配置
        weights = {
            'ss': 0.3,      # 板块强度权重
            'spp': 0.25,    # 抛压权重（反向）
            'ts': 0.25,     # 题材协同权重
            'mcp': 0.2      # 动量触发权重
        }
        
        # 提取各项分数
        ss_score = stock_data.get('sector_strength', 0)
        spp_score = stock_data.get('spp_score', 100)  # 抛压分数越高越差
        ts_score = stock_data.get('ts_score', 0)
        mcp_score = stock_data.get('mcp_score', 0)
        
        # 标准化到 0-100
        ss_norm = min(ss_score / 50 * 100, 100)  # 假设50为满分
        spp_norm = max(0, 100 - spp_score)       # 抛压反向
        ts_norm = ts_score
        mcp_norm = max(0, min(mcp_score * 20, 100))  # 动量标准化
        
        # 计算综合分数
        composite_score = (
            weights['ss'] * ss_norm +
            weights['spp'] * spp_norm +
            weights['ts'] * ts_norm +
            weights['mcp'] * mcp_norm
        )
        
        return {
            'composite_score': composite_score,
            'components': {
                'ss_norm': ss_norm,
                'spp_norm': spp_norm,
                'ts_norm': ts_norm,
                'mcp_norm': mcp_norm
            }
        }
        
    def calculate_ss_score(self, sector, stock_data):
        """
        计算板块强度分数
        
        SS = (板块平均涨幅 * 涨停比例 * 量比均值) / 跌停比例
        """
        if not self.probe_results or 'sector_strength' not in self.probe_results:
            return 0
            
        sector_data = self.probe_results['sector_strength'].get(sector, {})
        
        if not sector_data:
            return 0
            
        # 基础 SS 分数
        base_ss = sector_data.get('score', 0)
        
        # 调整因子：股票数量
        stock_count = sector_data.get('stock_count', 1)
        count_factor = min(stock_count / 10, 1.0)  # 10只股票为满分
        
        # 调整因子：平均涨幅
        avg_change = sector_data.get('avg_change', 0)
        change_factor = max(0, min(avg_change / 5 + 1, 2))  # 5%涨幅为满分
        
        # 最终 SS 分数
        final_ss = base_ss * count_factor * change_factor
        
        return final_ss
        
    def calculate_spp_score(self, stock_code, real_time_data=None):
        """
        计算抛压探测分数 SPP (Sell Pressure Probe)
        
        SPP = ((大单卖出量 - 大单买入量) / 总成交量) * 价格波动率 * 100
        """
        if real_time_data is None:
            # 从探针结果获取基础数据
            if not self.probe_results or 'candidates' not in self.probe_results:
                return 100  # 无数据时给高分（表示压力大）
                
            # 查找候选股票数据
            candidates = self.probe_results['candidates']
            stock_data = next((c for c in candidates if c['stock'] == stock_code), None)
            
            if not stock_data:
                return 100
                
            # 简化的 SPP 计算
            change_pct = stock_data.get('change_pct', 0)
            volume_ratio = stock_data.get('volume_ratio', 1.0)
            
            # 基于涨幅和量比的抛压估算
            if change_pct < 0:
                base_pressure = abs(change_pct) * 10
            else:
                base_pressure = max(0, 5 - change_pct) * 5
                
            spp_score = base_pressure * max(0.5, volume_ratio / 2)
            
        else:
            # 实时数据计算
            volume = real_time_data.get('realtime_volume', 0)
            sell_pressure = real_time_data.get('sell_pressure', 0)
            price_volatility = real_time_data.get('price_volatility', 0)
            
            if volume < self.config['spp_volume_threshold']:
                return 100  # 成交量过低，抛压大
                
            spp_score = sell_pressure * price_volatility * 100
            
        return min(spp_score, 100)
        
    def calculate_ts_score(self, stock_code, sector):
        """
        计算题材协同性分数 TS (Thematic Synergy)
        
        TS = 同板块股票涨幅相关性 * 板块强度因子 * 领涨股因子
        """
        if not self.probe_results or 'candidates' not in self.probe_results:
            return 0
            
        # 获取同板块股票
        candidates = self.probe_results['candidates']
        sector_stocks = [c for c in candidates if c.get('sector') == sector]
        
        if len(sector_stocks) < self.config['ts_correlation_window']:
            return 0
            
        # 计算涨幅相关性（简化实现）
        changes = [c.get('change_pct', 0) for c in sector_stocks]
        
        if len(set(changes)) < 2:
            return 0
            
        # 简化的相关性计算
        avg_change = np.mean(changes)
        stock_change = next((c.get('change_pct', 0) for c in sector_stocks if c['stock'] == stock_code), 0)
        
        # 相关性评分
        if abs(avg_change) < 0.1:
            return 0
            
        correlation = 1 - abs(stock_change - avg_change) / (abs(avg_change) + 0.1)
        
        # 板块强度因子
        sector_strength = self.calculate_ss_score(sector, {})
        strength_factor = min(sector_strength / 20, 1.0)
        
        # 领涨股因子
        if stock_change > avg_change:
            leader_factor = 1.2
        elif stock_change > 0:
            leader_factor = 1.0
        else:
            leader_factor = 0.8
            
        ts_score = correlation * strength_factor * leader_factor * 100
        
        return min(ts_score, 100)
        
    def calculate_mcp_score(self, stock_data, current_price=None):
        """
        计算动量触发分数 MCP (Momentum Trigger Point)
        
        MCP = 短期动量 * 成交量动量 * 价格突破因子
        """
        if current_price is None:
            # 基于探针数据的动量估算
            change_pct = stock_data.get('change_pct', 0)
            volume_ratio = stock_data.get('volume_ratio', 1.0)
            
            # 短期动量分数
            if change_pct > 2:
                momentum_score = 80
            elif change_pct > 1:
                momentum_score = 60
            elif change_pct > 0:
                momentum_score = 40
            else:
                momentum_score = 20
                
            # 成交量动量
            volume_score = min(volume_ratio / 3 * 100, 100)
            
            # MCP 综合分数
            mcp_score = (momentum_score + volume_score) / 2
            
        else:
            # 实时价格动量计算
            # 这里需要历史数据，简化实现
            mcp_score = 50  # 中性值
            
        return mcp_score
        
    def should_enter_position(self, stock_code, sector, real_time_data=None):
        """
        判断是否应该入场
        
        入场条件：
        1. SS > threshold
        2. SPP < threshold (抛压小)
        3. TS > threshold
        4. MCP > threshold
        5. 综合评分 > 80
        6. 持仓数量 < max_positions
        """
        # 持仓数量检查
        if len(self.open_positions) >= self.config['max_positions']:
            return False, "已满仓"
            
        # 获取股票基础数据
        if not self.probe_results or 'candidates' not in self.probe_results:
            return False, "无探针数据"
            
        candidates = self.probe_results['candidates']
        stock_data = next((c for c in candidates if c['stock'] == stock_code), None)
        
        if not stock_data:
            return False, "非候选股票"
            
        # 计算各项指标
        ss_score = self.calculate_ss_score(sector, stock_data)
        spp_score = self.calculate_spp_score(stock_code, real_time_data)
        ts_score = self.calculate_ts_score(stock_code, sector)
        mcp_score = self.calculate_mcp_score(stock_data, real_time_data)
        
        # 检查各项阈值
        if ss_score < self.config['ss_threshold']:
            return False, f"SS不足: {ss_score:.1f} < {self.config['ss_threshold']}"
            
        if spp_score > self.config['spp_threshold']:
            return False, f"抛压过大: {spp_score:.1f} > {self.config['spp_threshold']}"
            
        if ts_score < self.config['ts_threshold']:
            return False, f"TS不足: {ts_score:.1f} < {self.config['ts_threshold']}"
            
        if mcp_score < self.config['mcp_entry_threshold']:
            return False, f"MCP不足: {mcp_score:.1f} < {self.config['mcp_entry_threshold']}"
            
        # 计算综合评分
        stock_metrics = {
            'sector_strength': ss_score,
            'spp_score': spp_score,
            'ts_score': ts_score,
            'mcp_score': mcp_score
        }
        
        composite_result = self.calculate_composite_score(stock_metrics)
        
        if composite_result['composite_score'] < 80:
            return False, f"综合评分不足: {composite_result['composite_score']:.1f} < 80"
            
        return True, {
            'score': composite_result['composite_score'],
            'metrics': stock_metrics,
            'components': composite_result['components']
        }
        
    def should_exit_position(self, stock_code, current_price, entry_price, entry_time):
        """
        判断是否应该出场
        
        出场条件：
        1. MCP < exit_threshold (动量衰减)
        2. 止损：价格下跌 > stop_loss
        3. 时间止损：持仓天数 > holding_days_max
        4. T+1/T+2 滚动退出策略
        """
        current_time = datetime.now()
        holding_days = (current_time - entry_time).days
        
        # 止损检查
        if current_price <= 0 or entry_price <= 0:
            return True, "价格异常"
            
        price_change = (current_price - entry_price) / entry_price * 100
        
        if price_change <= self.config['mcp_stop_loss']:
            return True, f"止损: {price_change:.2f}%"
            
        # 时间止损
        if holding_days >= self.config['holding_days_max']:
            return True, f"时间止损: {holding_days}天"
            
        # T+1/T+2 退出策略
        if price_change > 2 and holding_days >= self.config['t1_exit_days']:
            return True, f"T+1退出: {price_change:.2f}%"
            
        if price_change > 0.5 and holding_days >= self.config['t2_exit_days']:
            return True, f"T+2退出: {price_change:.2f}%"
            
        # 动量衰减检查（简化实现）
        if price_change < self.config['mcp_exit_threshold']:
            return True, f"动量衰减: {price_change:.2f}%"
            
        return False, "继续持有"
        
    def generate_daily_signals(self):
        """
        生成每日交易信号
        """
        if not self.probe_results or 'candidates' not in self.probe_results:
            self.log("No probe results available")
            return []
            
        signals = []
        candidates = self.probe_results['candidates']
        
        for candidate in candidates:
            stock_code = candidate['stock']
            sector = candidate.get('sector', '其他')
            
            # 检查是否应该入场
            should_enter, reason = self.should_enter_position(stock_code, sector)
            
            if should_enter:
                signal = {
                    'timestamp': datetime.now().isoformat(),
                    'stock': stock_code,
                    'sector': sector,
                    'action': 'BUY',
                    'reason': reason,
                    'confidence': reason['score'] / 100,
                    'metrics': reason['metrics']
                }
                signals.append(signal)
                self.log(f"BUY Signal: {stock_code} - Score: {reason['score']:.1f}")
                
        # 按综合评分排序
        signals.sort(key=lambda x: x['confidence'], reverse=True)
        
        # 限制信号数量
        max_signals = self.config['max_positions'] - len(self.open_positions)
        signals = signals[:max_signals]
        
        # 记录决策历史
        self.decision_history.extend(signals)
        
        return signals
        
    def update_position_status(self):
        """
        更新持仓状态并生成出场信号
        """
        exit_signals = []
        
        for stock_code, position in list(self.open_positions.items()):
            current_price = position.get('current_price', 0)
            entry_price = position.get('entry_price', 0)
            entry_time = datetime.fromisoformat(position.get('entry_time', datetime.now().isoformat()))
            
            should_exit, reason = self.should_exit_position(
                stock_code, current_price, entry_price, entry_time
            )
            
            if should_exit:
                signal = {
                    'timestamp': datetime.now().isoformat(),
                    'stock': stock_code,
                    'action': 'SELL',
                    'reason': reason,
                    'position': position
                }
                exit_signals.append(signal)
                self.log(f"SELL Signal: {stock_code} - {reason}")
                
                # 移除持仓
                del self.open_positions[stock_code]
                
        return exit_signals
        
    def get_strategy_status(self):
        """获取策略状态"""
        return {
            'config': self.config,
            'probe_loaded': bool(self.probe_results),
            'open_positions': len(self.open_positions),
            'decision_count': len(self.decision_history),
            'last_update': datetime.now().isoformat()
        }


def test_strategy():
    """测试策略"""
    strategy = SentimentStrategyV3()
    
    # 加载探针结果（如果存在）
    strategy.load_probe_results()
    
    # 生成信号
    signals = strategy.generate_daily_signals()
    
    print(f"\n=== Strategy Test Results ===")
    print(f"Generated {len(signals)} signals")
    
    for i, signal in enumerate(signals):
        print(f"{i+1}. {signal['stock']} ({signal['action']}): {signal['reason']}")
        
    # 更新状态
    status = strategy.get_strategy_status()
    print(f"\nStrategy Status: {json.dumps(status, indent=2, ensure_ascii=False)}")
    
    return strategy


if __name__ == "__main__":
    test_strategy()