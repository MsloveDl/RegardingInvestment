# 情绪套利策略 EA

**版本**: v1.1  
**生成日期**: 2026-02-11  
**状态**: 开发完成，已移除 L2 数据依赖

---

## ⚠️ 重要说明

**本项目完全不使用 Level-2 数据接口（收费接口）**，仅使用 MiniQMT 免费的实时行情接口。

详见：[L2_REMOVAL_NOTES.md](L2_REMOVAL_NOTES.md)

---

## 项目概述

本项目是基于《情绪套利策略 v3.0》的 EA（Expert Advisor）实现，针对 MiniQMT（xtquant）免费版优化。

**核心理念**：不预测，只跟随。利用 9:25 竞价数据锁定最强板块，9:30-9:45 动态捕捉补涨个股。

**数据策略**：
- ✅ 使用免费实时行情（价格、成交量、涨跌幅）
- ❌ 不使用 L2 买卖五档（收费接口）
- ✅ 批量请求 + 缓存 + 智能采样

---

## 快速开始

### 1. 安装依赖

```bash
pip install schedule
pip install xtquant  # MiniQMT 环境
```

### 2. 配置参数

编辑 `config.py`，填写 MiniQMT 配置：

```python
MINIQMT_CONFIG = {
    'account_id': '',     # 账户 ID
    'session_id': '',     # 会话 ID
    'data_path': '',      # 数据路径
}
```

### 3. 运行策略

```bash
cd /home/mslovedl/.openclaw/workspace/workspace/ea
python main.py
```

### 4. 运行测试

```bash
# 测试数据适配器
python tests/test_data_adapter.py

# 测试板块扫描
python tests/test_sector_scanner.py

# 测试个股监控
python tests/test_stock_monitor.py
```

---

## 项目结构

```
ea/
├── main.py                    # 主入口
├── config.py                  # 配置文件
├── modules/                   # 核心模块
│   ├── data_adapter.py        # 数据适配层
│   ├── sector_scanner.py      # 板块扫描模块
│   ├── stock_monitor.py       # 个股监控模块
│   └── risk_manager.py        # 风控执行模块
├── utils/                     # 工具模块
│   ├── logger.py              # 日志工具
│   ├── trading_calendar.py   # 交易日历
│   └── signal_bus.py          # 信号总线
├── tests/                     # 测试文件
└── logs/                      # 日志目录
```

---

## 核心功能

### 1. 板块扫描（9:25）
- 计算全市场板块的 SS 因子（SR + OR + CR）
- 筛选出最强的 1-3 个板块

### 2. 个股监控（9:30-9:45）
- 智能采样：每个板块取开盘涨幅 Top 20
- 15 秒轮询监控
- SPP 抛压探测 + TS 板块协同 + MCP 动量确认

### 3. 风控管理（全天）
- T+1/T+2 滚动止盈止损
- 账户熔断（总浮动亏损 >= 3%）
- 仓位管理（单股 5%，单日 ≤ 3 只）

---

## 数据流量优化

| 指标 | 优化效果 |
| :--- | :--- |
| 监控股数 | 300+ → 60 只（↓80%） |
| 请求频率 | 实时 → 15 秒/次（↓93%） |
| 总数据流量 | 50-100MB/日 → 5-10MB/日（↓80-90%） |

---

## 注意事项

1. **数据接口**：L2 数据字段名需根据实际 MiniQMT API 调整
2. **实盘对接**：当前只实现信号生成，需添加 xttrader 下单代码
3. **风险提示**：15 秒轮询可能在急拉/急跌行情中错过最佳点

---

## 下一步计划

- [ ] 单元测试（各模块独立测试）
- [ ] 集成测试（完整流程测试）
- [ ] 回测验证（使用历史数据模拟）
- [ ] 实盘模拟（小资金测试）
- [ ] 实盘部署（对接 xttrader）

---

## 文档

- [架构设计](../notes/sentiment_arbitrage_ea_architecture.md)
- [开发说明](../notes/sentiment_arbitrage_ea_development.md)
- [降级版说明](../notes/sentiment_arbitrage_lite_v3.md)
- [原始策略](../../quant/strategy/ea/Final_Sentiment_Arbitrage_Strategy_V3.0.md)

---

**"纪律是策略的灵魂"**
