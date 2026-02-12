# 情绪套利策略 EA - L2 数据移除说明

**日期**: 2026-02-11  
**版本**: v1.1  
**重要变更**: 完全移除 Level-2 数据接口依赖

---

## 问题说明

### 原始问题
在初次代码审查中，项目使用了 `xtdata.get_l2_quote()` 接口获取买卖五档数据，这是 **MiniQMT 的收费接口**，违反了项目要求：

> 由于咱们的 MiniQMT 不支持收费接口(Level-2 数据接口)

### 修复方案
已将所有 L2 数据接口替换为免费的实时行情接口：

**修改前**：
```python
# 使用 L2 买卖五档（收费）
l2_data = xtdata.get_l2_quote(stocks)
bid_volumes = data['bid_volumes']  # 买一到买五量
ask_volumes = data['ask_volumes']  # 卖一到卖五量
```

**修改后**：
```python
# 使用免费实时行情
realtime_data = xtdata.get_full_tick(stocks)
change_rate = data['change_rate']  # 涨跌幅
volume = data['volume']            # 成交量
amplitude = (high - low) / pre_close  # 振幅
```

---

## 修改内容

### 1. data_adapter.py
- ❌ 删除：`get_l2_quote_batch()` 方法
- ✅ 新增：`get_realtime_quote_batch()` 方法
- 使用 `xtdata.get_full_tick()` 替代 `xtdata.get_l2_quote()`

### 2. stock_monitor.py
- ✅ 修改：`_check_selling_pressure()` - SPP 抛压探测
  - 原方案：买卖盘失衡比（需要 L2 买卖五档）
  - 新方案：涨跌幅 + 成交量 + 振幅
  
- ✅ 修改：`_check_sector_synergy()` - TS 板块协同
  - 使用 `get_realtime_quote_batch()` 替代 `get_l2_quote_batch()`
  
- ✅ 修改：`_check_momentum_confirmation()` - MCP 动量确认
  - 使用免费行情数据的价格和成交量

### 3. config.py
- ✅ 修改：`SPP_PARAMS` 参数
  - 删除：`bid_ask_imbalance_threshold`（需要 L2）
  - 新增：`max_drop_rate`、`min_volume_ratio`、`max_amplitude`

### 4. 测试文件
- ✅ 修改：`test_data_adapter.py` - 测试实时行情接口
- ✅ 修改：`test_stock_monitor.py` - 使用免费数据

---

## 降级版策略调整

### SPP 抛压探测（降级版）

**原方案**（需要 L2）：
```python
# 买卖盘失衡比
bid_total = sum(bid_volumes[:5])  # 买一到买五总量
ask_total = sum(ask_volumes[:5])  # 卖一到卖五总量
imbalance = bid_total / ask_total
if imbalance < 1.5:  # 卖盘压力大
    剔除
```

**新方案**（免费接口）：
```python
# 1. 涨跌幅检查
if change_rate < -2.0:  # 跌幅超过 2%
    剔除

# 2. 成交量检查
if volume < prev_volume * 0.5:  # 成交量萎缩超过 50%
    剔除

# 3. 振幅检查
amplitude = (high - low) / pre_close * 100
if amplitude > 8.0:  # 振幅超过 8%（波动剧烈）
    剔除
```

### TS 板块协同（降级版）

**原方案**（需要 L2）：
```python
# 对比前后两次快照的价格变化
if current_price > prev_price:
    up_count += 1
```

**新方案**（免费接口）：
```python
# 直接使用涨跌幅
if change_rate > 0:  # 涨幅为正
    up_count += 1
```

### MCP 动量确认（降级版）

**原方案**（需要 L2）：
```python
# 使用 L2 最新价和成交量
price_break = l2_data['last_price'] > prev_price
volume_surge = l2_data['volume'] > prev_volume * 1.5
```

**新方案**（免费接口）：
```python
# 使用免费行情的最新价和成交量
price_break = realtime_data['last_price'] > prev_price
volume_surge = realtime_data['volume'] > prev_volume * 1.5
```

---

## 数据接口对比

| 功能 | L2 接口（收费） | 免费接口 | 可用性 |
| :--- | :--- | :--- | :--- |
| 最新价 | ✅ | ✅ | 相同 |
| 成交量 | ✅ | ✅ | 相同 |
| 涨跌幅 | ✅ | ✅ | 相同 |
| 买卖五档 | ✅ | ❌ | **L2 独有** |
| 大单流向 | ✅ | ❌ | **L2 独有** |
| 开高低收 | ✅ | ✅ | 相同 |

---

## 策略效果评估

### 优势
- ✅ **完全免费**：不需要 Level-2 数据权限
- ✅ **合规性**：符合 MiniQMT 免费版限制
- ✅ **稳定性**：不依赖收费接口，避免权限问题

### 劣势
- ⚠️ **精度下降**：无法使用买卖五档判断抛压
- ⚠️ **信号质量**：SPP 抛压探测的准确性可能降低
- ⚠️ **捕捉率**：可能错过一些细微的买卖盘变化

### 建议
1. **参数调优**：根据实盘表现调整 SPP 参数（跌幅、成交量、振幅阈值）
2. **回测验证**：对比有无 L2 数据的策略表现差异
3. **逐步优化**：如果效果不佳，考虑其他免费指标（如换手率、量比等）

---

## 验证清单

- [x] 移除所有 `get_l2_quote` 调用
- [x] 替换为 `get_full_tick` 或 `get_market_data`
- [x] 更新 SPP 抛压探测逻辑
- [x] 更新 TS 板块协同逻辑
- [x] 更新 MCP 动量确认逻辑
- [x] 修改配置参数
- [x] 更新测试文件
- [x] 代码编译通过

---

## 总结

项目已经**完全移除 Level-2 数据接口依赖**，改用 MiniQMT 免费的实时行情接口。虽然精度有所下降，但符合项目要求，且完全免费可用。

**下一步**：运行测试，验证免费接口的数据质量和策略效果。

---

**修复人**: Kiro (AI Coding Specialist)  
**修复时间**: 2026-02-11 16:00 UTC
