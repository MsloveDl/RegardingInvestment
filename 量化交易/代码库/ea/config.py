"""
情绪套利策略 EA - 配置文件
版本: v1.0
生成日期: 2026-02-11
"""

# ==================== 策略参数 ====================

# 板块强度因子权重
SECTOR_SS_WEIGHTS = {
    'W1': 0.4,  # SR（涨停共振因子）权重
    'W2': 0.4,  # OR（封单强度比）权重
    'W3': 0.2,  # CR（抗撤单因子）权重
}

# 板块筛选条件
SECTOR_FILTER = {
    'min_sr': 3,           # 最小涨停共振数
    'min_cr': 0.5,         # 最小抗撤单因子
    'top_n': 3,            # 选取前 N 个板块
    'limit_up_threshold': 9.5,  # 涨停阈值（%）
}

# 个股池初始化参数
STOCK_POOL_INIT = {
    'min_change': 2.0,     # 最小开盘涨幅（%）
    'max_change': 5.0,     # 最大开盘涨幅（%）
    'top_n_per_sector': 20,  # 每个板块取前 N 只
}

# 抛压探测（SPP）参数 - 降级版：不使用 L2 买卖五档
SPP_PARAMS = {
    'max_drop_rate': -2.0,           # 最大跌幅（%）
    'min_volume_ratio': 0.5,         # 最小成交量比率
    'max_amplitude': 8.0,            # 最大振幅（%）
}

# 动量确认（MCP）参数
MCP_PARAMS = {
    'volume_surge_ratio': 1.5,  # 量比放大倍数
    'min_observation_seconds': 300,  # 最小观察期（秒，即 5 分钟）
}

# 板块协同（TS）参数
TS_PARAMS = {
    'min_synergy_ratio': 0.7,  # 最小协同比例（70%）
    'monitor_threshold': 0.6,  # 监控阈值（60%）
}

# ==================== 时间参数 ====================

TRADING_SCHEDULE = {
    'prepare_time': '09:24:50',      # 准备阶段
    'sector_scan_time': '09:25:00',  # 板块扫描
    'pool_init_time': '09:29:50',    # 监控池初始化
    'monitor_start_time': '09:30:00',  # 监控启动
    'monitor_end_time': '09:45:00',    # 监控结束
    'signal_start_time': '09:35:00',   # 信号开始时间（观察期后）
}

# 监控轮询频率（秒）
MONITOR_POLL_INTERVAL = 15

# ==================== 风控参数 ====================

RISK_CONTROL = {
    # 仓位管理
    'single_stock_position': 0.05,    # 单只个股仓位（5%）
    'max_daily_stocks': 3,            # 单日最大开仓个股数
    'max_sector_exposure': 0.15,      # 单一板块最大暴露仓位（15%）
    
    # 止损止盈
    'account_circuit_breaker': 0.03,  # 账户熔断阈值（3%）
    'max_holding_days': 3,            # 最大持仓天数（T+3）
    
    # 滑点
    'slippage': 0.005,                # 单边滑点（0.5%）
}

# 退出规则
EXIT_RULES = {
    't1_auction_exit': True,          # T+1 竞价卖出
    'limit_up_hold_threshold': 9.8,   # 涨停持有阈值（%）
    'limit_up_broken_exit': True,     # 炸板立即卖出
    'ma5_stop_loss': True,            # 跌破 5 日均线止损
    'intraday_ma_stop_loss': True,    # 跌破分时均线止损
}

# ==================== 数据参数 ====================

DATA_CONFIG = {
    'cache_enabled': True,            # 启用数据缓存
    'batch_request': True,            # 启用批量请求
    'max_cache_size': 1000,           # 最大缓存条目数
}

# ==================== 日志参数 ====================

LOG_CONFIG = {
    'log_level': 'INFO',              # 日志级别
    'log_file': 'logs/ea_strategy.log',  # 日志文件路径
    'max_bytes': 10 * 1024 * 1024,    # 单个日志文件最大大小（10MB）
    'backup_count': 5,                # 日志文件备份数量
}

# ==================== MiniQMT 配置 ====================

MINIQMT_CONFIG = {
    'account_id': '',                 # 账户 ID（需填写）
    'session_id': '',                 # 会话 ID（需填写）
    'data_path': '',                  # 数据路径（需填写）
}
