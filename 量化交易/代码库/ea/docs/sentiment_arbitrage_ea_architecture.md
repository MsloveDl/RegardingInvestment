# 情绪套利策略 EA 架构设计

**版本**: v1.0  
**生成日期**: 2026-02-11  
**状态**: Architecture Design  
**基于**: Final_Sentiment_Arbitrage_Strategy_V3.0 + sentiment_arbitrage_lite_v3

---

## 1. 整体架构（分层设计）

```
┌─────────────────────────────────────────────────────────┐
│                    策略主控层 (Main Controller)          │
│  - 时间轴调度（9:25/9:30/9:45 触发）                     │
│  - 全局状态管理（交易日历、持仓、熔断状态）               │
│  - 信号总线（汇总各模块信号，做最终决策）                 │
└─────────────────────────────────────────────────────────┘
           ↓                ↓                ↓
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ 板块扫描模块  │  │ 个股监控模块  │  │ 风控执行模块  │
│ (9:25)       │  │ (9:30-9:45)  │  │ (全天)       │
└──────────────┘  └──────────────┘  └──────────────┘
       ↓                  ↓                  ↓
┌─────────────────────────────────────────────────────────┐
│                    数据适配层 (Data Adapter)             │
│  - 批量请求封装（get_market_data/get_l2_quote）          │
│  - 数据缓存（避免重复请求）                               │
│  - 降级策略（智能采样、频率控制）                         │
└─────────────────────────────────────────────────────────┘
       ↓
┌─────────────────────────────────────────────────────────┐
│                    MiniQMT 接口层                        │
│  xtdata (行情) + xttrader (交易)                         │
└─────────────────────────────────────────────────────────┘
```

---

## 2. 核心模块设计

### 2.1 板块扫描模块 (`SectorScanner`)

**职责**：9:25 锁定全市场最强的 1-3 个板块。

**输入**：
- 全市场竞价数据（5190 只股）
- 板块分类字典（预加载）

**输出**：
- `top_sectors: List[str]`（如 `['电力设备', '通信', '计算机']`）
- `sector_ss: Dict[str, float]`（每个板块的 SS 评分）

**核心逻辑**：
```python
class SectorScanner:
    def scan_at_925(self) -> List[str]:
        # 1. 批量请求全市场竞价数据
        all_stocks = self.data_adapter.get_all_stocks()
        quote = self.data_adapter.get_market_data_batch(
            stocks=all_stocks,
            fields=['open', 'pre_close'],
            time='09:25:00'
        )
        
        # 2. 计算每个板块的 SS
        sector_ss = {}
        for sector in self.sector_list:
            stocks = self.get_stocks_in_sector(sector)
            
            # SR（涨停共振数）
            changes = [(quote[s]['open'] / quote[s]['pre_close'] - 1) * 100 
                       for s in stocks]
            sr = sum(1 for c in changes if c > 9.5)
            
            # OR（封单强度比）- 降级版：用开盘涨幅代替
            or_score = sum(c for c in changes if c > 5) / len(stocks)
            
            # CR（抗撤单）- 降级版：暂时省略（需要 9:19 历史快照）
            cr = 1.0  # 默认值
            
            ss = 0.4 * sr + 0.4 * or_score + 0.2 * cr
            sector_ss[sector] = ss
        
        # 3. 筛选：SS 前三且 SR >= 3
        top = sorted(sector_ss.items(), key=lambda x: x[1], reverse=True)
        return [s for s, score in top[:3] if self._calc_sr(s) >= 3]
```

**数据量**：1 次批量请求（~10KB），9:25 执行一次。

---

### 2.2 个股监控模块 (`StockMonitor`)

**职责**：9:30-9:45 动态监控目标板块内的补涨个股，触发买入信号。

**输入**：
- `top_sectors`（来自板块扫描模块）
- 实时 L2 数据（买卖五档、最新价、成交量）

**输出**：
- `buy_signals: List[BuySignal]`（包含股票代码、触发时间、触发价格）

**核心逻辑**：
```python
class StockMonitor:
    def __init__(self, top_sectors: List[str]):
        # 智能采样：每个板块只取开盘涨幅 Top 20
        self.monitor_pool = self._init_pool(top_sectors)
        self.prev_snapshot = {}  # 缓存上一次快照（用于 MCP 计算）
        
    def _init_pool(self, sectors: List[str]) -> List[str]:
        """9:29:50 初始化监控池"""
        pool = []
        for sector in sectors:
            stocks = self.get_stocks_in_sector(sector)
            # 筛选：开盘涨幅 +2% ~ +5%
            filtered = [s for s in stocks if 2 <= self._get_change(s) <= 5]
            # 取涨幅最大的 20 只
            top20 = sorted(filtered, key=self._get_change, reverse=True)[:20]
            pool.extend(top20)
        return pool  # 总共 ~60 只
    
    def monitor_loop(self):
        """9:30-9:45 循环监控"""
        while self._is_in_window():
            # 批量请求 60 只股的 L2 数据
            l2_batch = self.data_adapter.get_l2_quote_batch(self.monitor_pool)
            
            for stock in self.monitor_pool:
                data = l2_batch[stock]
                
                # 1. SPP 抛压探测
                if self._check_selling_pressure(data):
                    continue  # 剔除
                
                # 2. TS 板块协同（用板块指数代替）
                if not self._check_sector_synergy(stock):
                    continue
                
                # 3. MCP 动量确认
                if self._check_momentum_confirmation(stock, data):
                    self.emit_buy_signal(stock, data)
            
            time.sleep(15)  # 15 秒轮询一次
    
    def _check_selling_pressure(self, data: dict) -> bool:
        """抛压探测（SPP）"""
        bid_total = sum(data['bid_volumes'][:5])
        ask_total = sum(data['ask_volumes'][:5])
        imbalance = bid_total / ask_total if ask_total > 0 else 0
        return imbalance < 1.5  # True = 高抛压，剔除
    
    def _check_momentum_confirmation(self, stock: str, data: dict) -> bool:
        """动量确认（MCP）"""
        if stock not in self.prev_snapshot:
            self.prev_snapshot[stock] = data
            return False
        
        prev = self.prev_snapshot[stock]
        # 价格突破 + 量比放大
        price_break = data['last_price'] > prev['last_price']
        volume_surge = data['volume'] > prev['volume'] * 1.5
        
        self.prev_snapshot[stock] = data  # 更新缓存
        return price_break and volume_surge
```

**数据量**：每 15 秒约 60 只股 × L2 快照 ≈ 3-5KB，9:30-9:45 共约 60 次请求。

---

### 2.3 风控执行模块 (`RiskManager`)

**职责**：全天监控持仓，执行 T+1/T+2 退出逻辑，管理全局熔断。

**输入**：
- 当前持仓列表
- 实时行情数据

**输出**：
- `sell_orders: List[SellOrder]`（卖出指令）
- `circuit_breaker_status: bool`（熔断状态）

**核心逻辑**：
```python
class RiskManager:
    def __init__(self):
        self.positions = {}  # {stock: {'buy_date', 'buy_price', 'quantity'}}
        self.circuit_breaker = False
        
    def check_exit_conditions(self):
        """每日 9:25 + 盘中实时检查"""
        for stock, pos in self.positions.items():
            # T+1 竞价卖出（常规止盈）
            if self._is_t1_auction(pos):
                self.emit_sell_order(stock, 'T+1竞价止盈')
            
            # 涨停持有（T+1 封死涨停 → 持有至 T+2）
            elif self._is_limit_up_sealed(stock):
                continue  # 持有
            
            # 炸板卖出（T+1 盘中涨停后开板）
            elif self._is_limit_up_broken(stock):
                self.emit_sell_order(stock, '炸板卖出', urgent=True)
            
            # 动态止损（跌破 5 日均线）
            elif self._is_below_ma5(stock):
                self.emit_sell_order(stock, '动态止损')
            
            # 时间止损（T+3 强制卖出）
            elif self._is_t3_expired(pos):
                self.emit_sell_order(stock, '时间止损')
    
    def check_circuit_breaker(self):
        """账户熔断检查"""
        total_loss = sum(self._calc_floating_loss(s) for s in self.positions)
        if total_loss / self.total_capital >= 0.03:
            self.circuit_breaker = True
            logger.warning("触发账户熔断！停止所有新买入。")
```

**退出规则表**：

| 情景 | 退出规则 | 执行时间 |
| :--- | :--- | :--- |
| **常规止盈** | T+1 日 9:25 集合竞价全仓卖出 | T+1日 9:25:00 |
| **涨停持有** | T+1 日竞价封死涨停（≥9.8%）→ 持有至 T+2 竞价 | T+1日 9:25后 |
| **炸板卖出** | T+1 日盘中涨停后开板（炸板）→ 开板瞬间立即卖出 | T+1日盘中 |
| **动态止损** | 买入当日收盘价跌破 5日移动平均线 或 当日分时均线 → 次日竞价卖出 | T日收盘判断，T+1日执行 |
| **时间止损** | 持仓最长不超过 T+3 个交易日 | T+3日 9:25 |

**全局风控**：
- **账户熔断**：当日总浮动亏损 ≥ 3% → 停止所有新买入。
- **板块熔断**：龙头股在 10:00 前炸板且 5 分钟内未回封 → 放弃该板块。
- **仓位管理**：单股 5%，单日 ≤ 3 只，单板块 ≤ 15%。

---

### 2.4 数据适配层 (`DataAdapter`)

**职责**：封装 MiniQMT 接口，实现批量请求、缓存、降级策略。

```python
class DataAdapter:
    def __init__(self):
        self.cache = {}  # 数据缓存
        self.request_count = 0  # 请求计数（监控流量）
    
    def get_market_data_batch(self, stocks: List[str], fields: List[str], time: str):
        """批量请求行情数据"""
        cache_key = f"{','.join(stocks)}_{','.join(fields)}_{time}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        data = xtdata.get_market_data(
            stock_list=stocks,
            field_list=fields,
            period='1d',
            start_time=time,
            end_time=time
        )
        self.cache[cache_key] = data
        self.request_count += 1
        return data
    
    def get_l2_quote_batch(self, stocks: List[str]) -> Dict[str, dict]:
        """批量请求 L2 买卖五档"""
        data = xtdata.get_l2_quote(stocks)
        self.request_count += 1
        return data
    
    def get_all_stocks(self) -> List[str]:
        """获取全市场股票列表"""
        return xtdata.get_stock_list_in_sector('沪深A股')
    
    def get_stocks_in_sector(self, sector: str) -> List[str]:
        """获取板块内股票列表"""
        return xtdata.get_stock_list_in_sector(sector)
```

---

### 2.5 主控层 (`MainController`)

**职责**：时间轴调度、信号总线、全局状态管理。

```python
import schedule
import threading
import time
from datetime import datetime

class MainController:
    def __init__(self):
        self.data_adapter = DataAdapter()
        self.sector_scanner = SectorScanner(self.data_adapter)
        self.stock_monitor = None
        self.risk_manager = RiskManager()
        self.top_sectors = []
        
    def run(self):
        """策略主循环"""
        # 9:24:50 准备
        schedule.every().day.at("09:24:50").do(self._prepare)
        
        # 9:25:00 板块扫描
        schedule.every().day.at("09:25:00").do(self._scan_sectors)
        
        # 9:29:50 初始化监控池
        schedule.every().day.at("09:29:50").do(self._init_monitor)
        
        # 9:30:00 启动监控
        schedule.every().day.at("09:30:00").do(self._start_monitor)
        
        # 9:45:00 停止监控
        schedule.every().day.at("09:45:00").do(self._stop_monitor)
        
        # 全天风控检查（每分钟）
        schedule.every(60).seconds.do(self.risk_manager.check_exit_conditions)
        
        # 账户熔断检查（每 30 秒）
        schedule.every(30).seconds.do(self.risk_manager.check_circuit_breaker)
        
        logger.info("策略主控启动，等待交易时间...")
        while True:
            schedule.run_pending()
            time.sleep(1)
    
    def _prepare(self):
        """9:24:50 准备阶段"""
        logger.info("准备阶段：加载全局参数...")
        # 清空缓存
        self.data_adapter.cache.clear()
        # 检查交易日历
        if not self._is_trading_day():
            logger.info("今日非交易日，策略休眠。")
            return
    
    def _scan_sectors(self):
        """9:25 板块扫描"""
        logger.info("开始板块扫描...")
        self.top_sectors = self.sector_scanner.scan_at_925()
        logger.info(f"今日目标板块: {self.top_sectors}")
        
        if not self.top_sectors:
            logger.warning("未找到符合条件的板块，今日不交易。")
    
    def _init_monitor(self):
        """9:29:50 初始化监控池"""
        if not self.top_sectors:
            return
        
        logger.info("初始化监控池...")
        self.stock_monitor = StockMonitor(self.top_sectors, self.data_adapter)
        logger.info(f"监控池初始化完成，共 {len(self.stock_monitor.monitor_pool)} 只股票")
    
    def _start_monitor(self):
        """9:30 启动监控"""
        if not self.stock_monitor:
            return
        
        logger.info("启动个股监控...")
        # 在独立线程中运行监控循环
        threading.Thread(target=self.stock_monitor.monitor_loop, daemon=True).start()
    
    def _stop_monitor(self):
        """9:45 停止监控"""
        if self.stock_monitor:
            self.stock_monitor.stop()
            logger.info("监控窗口关闭，今日买入操作结束。")
    
    def _is_trading_day(self) -> bool:
        """检查是否为交易日"""
        # TODO: 实现交易日历检查
        return True
```

---

## 3. 时间轴总览

| 时间 | 阶段 | 系统动作 | 数据源/计算 |
| :--- | :--- | :--- | :--- |
| **9:24:50** | 环境准备 | 加载全局参数，清空缓存，检查交易日历 | - |
| **9:25:00** | **板块扫描** | 1. 批量请求全市场竞价数据<br>2. 计算所有板块的 SS 因子<br>3. 选出 SS 排名前三的板块 | 全市场行情快照（~10KB） |
| **9:29:50** | 监控池初始化 | 在三个目标板块内，筛选开盘涨幅 +2%~+5% 的个股，取每板块 Top 20 | 复用 9:25 数据 |
| **9:30:00** | **监控启动** | 启动独立线程，开始 15 秒轮询监控 | - |
| **9:30-9:45** | **动态监控** | 每 15 秒批量请求 60 只股的 L2 数据，计算 SPP、TS、MCP，触发买入信号 | L2 实时数据（3-5KB/次） |
| **9:45:00** | 监控关闭 | 停止接受新的买入信号，今日买入操作结束 | - |
| **全天** | 持仓监控 | 每分钟检查退出条件（T+1/T+2 止盈止损），每 30 秒检查账户熔断 | 实时行情 |

---

## 4. 关键优化点

### 4.1 数据流量控制

| 指标 | 原策略（理想） | 降级版（现实） | 优化效果 |
| :--- | :--- | :--- | :--- |
| **9:25 数据请求** | 5190 只股 × 竞价数据 | **相同**（必须） | 0% |
| **9:30-9:45 监控股数** | 300+ 只（全板块） | **60 只**（智能采样） | ↓80% |
| **请求频率** | 实时（秒级） | **15 秒/次** | ↓93% |
| **每请求数据量** | 买卖五档 + 成交明细 | 买卖五档 + 最新价 | ↓30% |
| **总数据流量** | ~50-100MB/日 | **~5-10MB/日** | ↓80-90% |

### 4.2 核心技术手段

1. **批量请求**：所有数据请求都用批量接口（`get_market_data`、`get_l2_quote`），避免循环单票请求。
2. **智能采样**：监控池从全板块 300+ 只缩减到每板块 Top 20（共 60 只）。
3. **频率控制**：监控轮询从实时（秒级）降至 15 秒/次（可动态调整为 10 秒）。
4. **数据复用**：买卖五档数据同时用于 SPP（抛压探测）和 MCP（动量确认）。
5. **缓存机制**：9:25 的竞价数据缓存，避免重复请求。

---

## 5. 文件结构

```
sentiment_arbitrage_ea/
├── main.py                    # 主入口
├── config.py                  # 配置文件（参数、权重）
├── modules/
│   ├── __init__.py
│   ├── sector_scanner.py      # 板块扫描模块
│   ├── stock_monitor.py       # 个股监控模块
│   ├── risk_manager.py        # 风控执行模块
│   └── data_adapter.py        # 数据适配层
├── utils/
│   ├── __init__.py
│   ├── logger.py              # 日志工具
│   ├── trading_calendar.py   # 交易日历
│   └── signal_bus.py          # 信号总线
├── tests/
│   ├── test_sector_scanner.py
│   ├── test_stock_monitor.py
│   └── test_data_adapter.py
└── logs/                      # 日志目录
```

---

## 6. 下一步实施计划

### 6.1 开发阶段（预计 3-5 天）

1. **Day 1**：搭建项目框架，实现 `DataAdapter` 和 `SectorScanner`。
2. **Day 2**：实现 `StockMonitor` 核心逻辑（SPP、TS、MCP）。
3. **Day 3**：实现 `RiskManager` 和 `MainController`。
4. **Day 4**：单元测试 + 集成测试。
5. **Day 5**：回测验证（使用历史数据模拟）。

### 6.2 回测验证（预计 2-3 天）

- **测试日期**：
  - 2025-07-10（涨停潮）
  - 2025-08-15（震荡市）
  - 2025-09-20（调整市）
- **评估指标**：
  - 胜率、盈亏比
  - 最大回撤
  - 信号捕捉率（相比完整版）
  - 数据流量（实际消耗）

### 6.3 实盘模拟（预计 1-2 周）

- **资金规模**：1 万元
- **验证重点**：
  - 下单速度（9:30-9:45 高峰期）
  - 滑点真实情况
  - 系统稳定性（连续运行）
  - 风控触发准确性

---

## 7. 风险提示

1. **数据延迟**：15 秒轮询可能在急拉/急跌行情中错过最佳点，可考虑动态调整频率（如 9:35-9:40 调至 10 秒）。
2. **板块指数**：TS（板块协同）用板块指数代替个股统计，可能存在偏差，需实盘验证准确性。
3. **L2 数据字段**：`get_l2_quote` 返回的字段名需实际验证（`bid_prices`、`bid_volumes`、`ask_prices`、`ask_volumes`、`last_price`、`volume`）。
4. **历史快照**：CR（抗撤单因子）需要 9:19 的封单快照，需盘前预加载（通过 `xtdata.download_history_data`）。

---

**文档版本**: v1.0  
**生成日期**: 2026-02-11  
**状态**: Architecture Design  
**下一步**: 开始编码实现

*"纪律是策略的灵魂" —— 架构设计完成，准备进入开发阶段。*
