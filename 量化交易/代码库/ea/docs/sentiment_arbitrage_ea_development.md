# 情绪套利策略 EA - 开发说明文档

**版本**: v1.0  
**生成日期**: 2026-02-11  
**状态**: 开发完成，待测试  

---

## 1. 项目概述

本项目是基于《情绪套利策略 v3.0》的 EA（Expert Advisor）实现，针对 MiniQMT（xtquant）环境优化，通过批量请求、智能采样、降低频率等手段，将数据流量控制在 5-10MB/日，适合实盘部署。

**核心理念**：不预测，只跟随。利用 9:25 竞价数据锁定最强板块，9:30-9:45 动态捕捉补涨个股。

---

## 2. 项目结构

```
ea/
├── main.py                    # 主入口（策略主控层）
├── config.py                  # 配置文件（参数、权重）
├── modules/                   # 核心模块
│   ├── __init__.py
│   ├── data_adapter.py        # 数据适配层
│   ├── sector_scanner.py      # 板块扫描模块
│   ├── stock_monitor.py       # 个股监控模块
│   └── risk_manager.py        # 风控执行模块
├── utils/                     # 工具模块
│   ├── __init__.py
│   ├── logger.py              # 日志工具
│   ├── trading_calendar.py   # 交易日历
│   └── signal_bus.py          # 信号总线
├── tests/                     # 测试文件
│   ├── test_data_adapter.py
│   ├── test_sector_scanner.py
│   └── test_stock_monitor.py
├── config/                    # 配置目录
│   └── trading_calendar.json  # 交易日历数据（需手动创建）
└── logs/                      # 日志目录（自动创建）
```

---

## 3. 核心模块说明

### 3.1 数据适配层 (`data_adapter.py`)

**职责**：封装 MiniQMT 接口，实现批量请求、缓存、降级策略。

**核心功能**：
- `get_all_stocks()`: 获取全市场股票列表
- `get_stocks_in_sector(sector)`: 获取板块内股票列表
- `get_market_data_batch(stocks, fields)`: 批量请求行情数据
- `get_l2_quote_batch(stocks)`: 批量请求 L2 买卖五档数据
- `get_sector_list()`: 获取板块列表

**优化手段**：
- 批量请求：避免循环单票请求
- 数据缓存：避免重复请求
- 模拟模式：未安装 xtquant 时使用模拟数据

### 3.2 板块扫描模块 (`sector_scanner.py`)

**职责**：9:25 锁定全市场最强的 1-3 个板块。

**核心逻辑**：
1. 获取全市场竞价数据
2. 计算每个板块的 SS 因子（SR + OR + CR）
3. 筛选 SS 排名前三且 SR >= 3 的板块

**输出**：目标板块列表（如 `['电力设备', '通信', '计算机']`）

### 3.3 个股监控模块 (`stock_monitor.py`)

**职责**：9:30-9:45 动态监控目标板块内的补涨个股，触发买入信号。

**核心逻辑**：
1. 初始化监控池：每个板块取开盘涨幅 +2%~+5% 的 Top 20
2. 15 秒轮询监控：批量请求 L2 数据
3. 逐个检查：SPP（抛压探测）→ TS（板块协同）→ MCP（动量确认）
4. 触发买入信号

**输出**：买入信号（包含股票代码、触发价格、触发原因）

### 3.4 风控执行模块 (`risk_manager.py`)

**职责**：全天监控持仓，执行 T+1/T+2 退出逻辑，管理全局熔断。

**核心逻辑**：
- **退出规则**：
  - T+1 竞价止盈
  - 涨停持有至 T+2
  - 炸板立即卖出
  - 跌破 5 日均线止损
  - T+3 时间止损
- **全局风控**：
  - 账户熔断（总浮动亏损 >= 3%）
  - 单日最大开仓数（3 只）
  - 单股仓位（5%）

### 3.5 主控层 (`main.py`)

**职责**：时间轴调度、信号总线、全局状态管理。

**时间轴**：
- 9:24:50 准备阶段
- 9:25:00 板块扫描
- 9:29:50 监控池初始化
- 9:30:00 监控启动
- 9:45:00 监控结束
- 全天风控检查（每分钟）

---

## 4. 配置说明

### 4.1 策略参数 (`config.py`)

**板块强度因子权重**：
```python
SECTOR_SS_WEIGHTS = {
    'W1': 0.4,  # SR（涨停共振因子）
    'W2': 0.4,  # OR（封单强度比）
    'W3': 0.2,  # CR（抗撤单因子）
}
```

**个股池初始化参数**：
```python
STOCK_POOL_INIT = {
    'min_change': 2.0,     # 最小开盘涨幅（%）
    'max_change': 5.0,     # 最大开盘涨幅（%）
    'top_n_per_sector': 20,  # 每个板块取前 N 只
}
```

**监控轮询频率**：
```python
MONITOR_POLL_INTERVAL = 15  # 秒
```

**风控参数**：
```python
RISK_CONTROL = {
    'single_stock_position': 0.05,    # 单只个股仓位（5%）
    'max_daily_stocks': 3,            # 单日最大开仓个股数
    'max_sector_exposure': 0.15,      # 单一板块最大暴露仓位（15%）
    'account_circuit_breaker': 0.03,  # 账户熔断阈值（3%）
    'max_holding_days': 3,            # 最大持仓天数（T+3）
}
```

### 4.2 MiniQMT 配置

需要在 `config.py` 中填写：
```python
MINIQMT_CONFIG = {
    'account_id': '',     # 账户 ID
    'session_id': '',     # 会话 ID
    'data_path': '',      # 数据路径
}
```

---

## 5. 使用说明

### 5.1 环境准备

1. **安装依赖**：
   ```bash
   pip install schedule
   pip install xtquant  # MiniQMT 环境
   ```

2. **配置参数**：
   - 编辑 `config.py`，填写 MiniQMT 配置
   - 根据需要调整策略参数

3. **创建交易日历**（可选）：
   - 在 `config/` 目录下创建 `trading_calendar.json`
   - 格式：
     ```json
     {
       "trading_days": ["2026-02-11", "2026-02-12", ...],
       "holidays": ["2026-02-01", "2026-02-02", ...]
     }
     ```

### 5.2 运行策略

**方式一：直接运行**
```bash
cd /home/mslovedl/.openclaw/workspace/workspace/ea
python main.py
```

**方式二：后台运行**
```bash
nohup python main.py > output.log 2>&1 &
```

### 5.3 测试模块

**测试数据适配器**：
```bash
python tests/test_data_adapter.py
```

**测试板块扫描**：
```bash
python tests/test_sector_scanner.py
```

**测试个股监控**：
```bash
python tests/test_stock_monitor.py
```

---

## 6. 数据流量优化

| 指标 | 原策略（理想） | 降级版（现实） | 优化效果 |
| :--- | :--- | :--- | :--- |
| **9:25 数据请求** | 5190 只股 × 竞价数据 | **相同**（必须） | 0% |
| **9:30-9:45 监控股数** | 300+ 只（全板块） | **60 只**（智能采样） | ↓80% |
| **请求频率** | 实时（秒级） | **15 秒/次** | ↓93% |
| **总数据流量** | ~50-100MB/日 | **~5-10MB/日** | ↓80-90% |

**核心优化手段**：
1. 批量请求：所有数据请求都用批量接口
2. 智能采样：监控池从 300+ 缩减到 60 只
3. 频率控制：15 秒轮询一次
4. 数据复用：买卖五档同时用于 SPP 和 MCP
5. 缓存机制：9:25 的竞价数据缓存

---

## 7. 注意事项

### 7.1 数据接口

1. **L2 数据字段**：`get_l2_quote` 返回的字段名需实际验证（`bid_prices`、`bid_volumes`、`ask_prices`、`ask_volumes`、`last_price`、`volume`）。

2. **板块分类**：`get_sector_list()` 和 `get_stock_list_in_sector()` 的板块名称需与 MiniQMT 实际接口一致。

3. **历史快照**：CR（抗撤单因子）需要 9:19 的封单快照，需盘前预加载。

### 7.2 实盘对接

当前代码**只实现了信号生成和持仓管理**，**未实现实际下单**。需要在以下位置添加 xttrader 下单代码：

1. **买入信号处理**（`main.py` 的 `_on_buy_signal` 方法）：
   ```python
   # 执行买入
   from xtquant.xttrader import XtQuantTrader
   trader = XtQuantTrader(...)
   trader.order_stock(stock_code, 'buy', quantity, price)
   ```

2. **卖出信号处理**（`main.py` 的 `_on_sell_signal` 方法）：
   ```python
   # 执行卖出
   trader.order_stock(stock_code, 'sell', quantity, price)
   ```

### 7.3 风险提示

1. **数据延迟**：15 秒轮询可能在急拉/急跌行情中错过最佳点，可考虑动态调整频率。

2. **板块协同**：TS（板块协同）用板块指数代替个股统计，可能存在偏差，需实盘验证。

3. **止损逻辑**：MA5 止损和炸板监控需要实时数据，当前代码为简化实现，需完善。

---

## 8. 下一步计划

### 8.1 开发阶段（已完成）

- [x] 搭建项目框架
- [x] 实现数据适配层
- [x] 实现板块扫描模块
- [x] 实现个股监控模块
- [x] 实现风控执行模块
- [x] 实现主控层
- [x] 编写测试文件

### 8.2 测试阶段（待进行）

- [ ] 单元测试（各模块独立测试）
- [ ] 集成测试（完整流程测试）
- [ ] 回测验证（使用历史数据模拟）
  - 测试日期：2025-07-10（涨停潮）、2025-08-15（震荡市）
  - 评估指标：胜率、盈亏比、最大回撤、信号捕捉率

### 8.3 实盘模拟（待进行）

- [ ] 小资金实盘模拟（1 万元）
- [ ] 验证下单速度、滑点、系统稳定性
- [ ] 优化参数和风控规则

### 8.4 实盘部署（待进行）

- [ ] 对接 xttrader 下单接口
- [ ] 完善止损逻辑（MA5、炸板监控）
- [ ] 添加监控告警（钉钉、微信等）
- [ ] 正式上线运行

---

## 9. 文件清单（需上传到 Quant-Node）

### 9.1 核心文件（必须）

```
ea/
├── main.py                    # 主入口
├── config.py                  # 配置文件
├── modules/
│   ├── __init__.py
│   ├── data_adapter.py
│   ├── sector_scanner.py
│   ├── stock_monitor.py
│   └── risk_manager.py
└── utils/
    ├── __init__.py
    ├── logger.py
    ├── trading_calendar.py
    └── signal_bus.py
```

### 9.2 测试文件（可选）

```
ea/tests/
├── test_data_adapter.py
├── test_sector_scanner.py
└── test_stock_monitor.py
```

### 9.3 配置文件（需手动创建）

```
ea/config/
└── trading_calendar.json      # 交易日历数据
```

### 9.4 文档文件

```
workspace/notes/
├── sentiment_arbitrage_ea_architecture.md  # 架构设计文档
└── sentiment_arbitrage_ea_development.md   # 开发说明文档（本文件）
```

---

## 10. 联系方式

如有问题，请联系开发者。

**文档版本**: v1.0  
**生成日期**: 2026-02-11  
**状态**: 开发完成，待测试

*"纪律是策略的灵魂" —— 代码已完成，准备进入测试阶段。*
