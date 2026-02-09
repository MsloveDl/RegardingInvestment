# -*- coding: utf-8 -*-
"""
情绪套利策略 v3.0 - 配置文件
"""

# 策略核心配置
STRATEGY_CONFIG = {
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

# 交易执行配置
EXECUTION_CONFIG = {
    # 交易模式
    'mode': 'paper',  # 'paper' 模拟盘, 'live' 实盘
    
    # 费用配置
    'commission_rate': 0.0003,  # 手续费率
    'slippage_rate': 0.001,     # 滑点率
    'stamp_tax_rate': 0.001,    # 印花税率（仅卖出）
    
    # 订单配置
    'max_order_size': 0.3,       # 单笔订单最大仓位比例
    'default_order_type': 'LIMIT',  # 默认订单类型
    'order_timeout': 30,          # 订单超时时间（秒）
    
    # 风险控制
    'max_daily_orders': 20,       # 每日最大订单数
    'max_single_position': 0.3,   # 单只股票最大仓位
    'max_total_position': 0.95,   # 最大总仓位
}

# 回测配置
BACKTEST_CONFIG = {
    'initial_capital': 100000,    # 初始资金
    'start_date': '2023-01-01',   # 回测开始日期
    'end_date': '2023-12-31',     # 回测结束日期
    
    # 基准配置
    'benchmark': '000300.SH',     # 沪深300作为基准
    
    # 数据配置
    'data_frequency': 'daily',    # 数据频率
    'forward_fill': True,          # 是否向前填充
}

# 数据源配置
DATA_CONFIG = {
    # 股票池配置
    'stock_pool': {
        'min_market_cap': 50,     # 最小市值（亿）
        'min_turnover': 1000000,   # 最小成交额
        'exclude_st': True,         # 排除ST股票
        'exclude_new_stock_days': 60, # 排除新股天数
    },
    
    # 探针配置
    'probe_time': '09:25:00',    # 集合竞价时间
    'probe_stocks_limit': 100,    # 探针股票数量限制
    
    # 实时数据配置
    'realtime_update_interval': 5, # 实时更新间隔（秒）
}

# 日志配置
LOG_CONFIG = {
    'level': 'INFO',              # 日志级别
    'file_path': 'D:/QuantWorkspace/logs/sentiment_v3.log',
    'max_file_size': 100 * 1024 * 1024,  # 最大文件大小
    'backup_count': 10,            # 备份数量
    'console_output': True,        # 控制台输出
}

# KPI 目标配置
KPI_TARGETS = {
    # 收益目标
    'annual_return_target': 0.15,  # 年化收益率目标 15%
    'max_drawdown_target': 0.08,  # 最大回撤目标 8%
    
    # 风险目标
    'sharpe_ratio_target': 2.0,   # 夏普比率目标
    'volatility_target': 0.12,    # 波动率目标 12%
    
    # 交易目标
    'win_rate_target': 0.65,       # 胜率目标 65%
    'avg_holding_days_target': 2,  # 平均持仓天数目标
    'profit_per_trade_target': 500, # 每笔交易利润目标
}

# 板块映射配置
SECTOR_MAPPING = {
    # 主要板块分类
    '地产': ['000001.SZ', '000002.SZ', '600381.SH'],
    '科技': ['000858.SZ', '002415.SZ', '300750.SZ'],
    '医药': ['000423.SZ', '002007.SZ', '300122.SZ'],
    '消费': ['000858.SZ', '002304.SZ', '600519.SH'],
    '金融': ['000001.SZ', '600036.SH', '601398.SH'],
    '环保': ['300007.SZ', '002573.SZ', '600381.SH'],
}

# 监控配置
MONITOR_CONFIG = {
    # 性能监控
    'enable_performance_monitor': True,
    'monitor_interval': 60,  # 监控间隔（秒）
    
    # 告警配置
    'alert_enable': True,
    'alert_emails': [],  # 告警邮箱列表
    
    # 报告配置
    'daily_report_enable': True,
    'weekly_report_enable': True,
    'monthly_report_enable': True,
}