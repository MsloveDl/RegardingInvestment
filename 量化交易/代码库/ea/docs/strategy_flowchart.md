# 情绪套利策略 v3.0 流程图

```mermaid
graph TD
    Start[交易日开始] --> Prep[环境准备 9:24:50<br>加载全局参数]

    Prep --> EnvCheck{全局熔断检查 9:25:00}
    EnvCheck -->|通过| CalcSS[板块强度计算 9:25:01<br>计算所有一级行业SS因子]
    EnvCheck -->|不通过| Stop[停止当日交易]

    CalcSS --> FilterSec[板块筛选 9:25:30<br>选取SS排名前三且SR≥3, CR>0.5的板块]
    
    FilterSec --> InitPool[个股池初始化 9:29:50<br>开盘涨幅+2%~+5%<br>竞价成交额>5日均值10%]

    InitPool --> ProbeStart[全市场探针启动 9:30:00<br>启动并行监控线程]

    ProbeStart --> MonitorLoop[动态监控循环 9:30-9:45]
    
    subgraph MonitorLoop [个股动态监控]
        direction LR
        SPPMon[持续更新SPP抛压状态]
        TSMon[监控板块TS(t)协同性]
        MCPCheck{检查MCP触发条件?}
    end

    SPPMon -->|SPP=True| Exclude[剔除高抛压个股]
    TSMon -->|TS(t)<60%| StopSector[停止该板块监控]

    MCPCheck -->|条件满足| BuySignal[生成买入信号]
    
    MCPCheck -->|条件未满足| Continue[继续监控]
    
    BuySignal --> VolCheck{板块龙头炸板保护?}
    VolCheck -->|龙头炸板且未回封| StopSector
    VolCheck -->|正常| Execute[执行买入<br>单只仓位5%<br>单日≤3只]

    Execute --> WindowClose[交易窗口关闭 9:45:00]

    WindowClose --> HoldMonitor[持仓监控与退出]
    
    subgraph HoldMonitor [T+1/T+2退出机制]
        direction TB
        T1Check{T+1日9:25状态}
        T1Check -->|封死涨停| HoldT2[持有至T+2竞价]
        T1Check -->|未涨停| SellT1[T+1日9:25竞价卖出]
        
        HoldT2 --> T2Sell[T+2日竞价卖出]
        
        IntradayCheck{T+1日盘中炸板?}
        IntradayCheck -->|是| ImmediateSell[炸板瞬间立即卖出]
        
        StopLossCheck{T日收盘价跌破5日均线<br>或分时均线?}
        StopLossCheck -->|是| NextDaySell[次日竞价卖出]
        
        TimeStop[持仓最长不超过T+3日]
    end

    StopSector --> MonitorLoop

    Exclude --> MonitorLoop
    Continue --> MonitorLoop

    %% 全局风控
    subgraph GlobalRisk [全局风控]
        Account[账户熔断: 总浮动亏损≥3%<br>停止新买入]
        Sector[板块熔断: 龙头炸板保护]
        Position[仓位管理: 单板块≤15%]
    end

    Account --> Stop
    Sector --> StopSector
    Position --> Execute

    style Start fill:#e1f5fe
    style EnvCheck fill:#ffebee
    style BuySignal fill:#c8e6c9
    style Execute fill:#c8e6c9
    style Stop fill:#ffccbc
    style StopSector fill:#ffccbc
```

## 流程图说明

### 核心流程
1. **环境检查**：9:25判断市场是否具备可交易条件（跌停家数≤5，指数在20日均线上）。
2. **板块筛选**：通过SS因子（涨停共振、封单强度、抗撤单）锁定前三强板块。
3. **个股池构建**：在目标板块内筛选开盘涨幅适中、成交活跃的个股。
4. **动态监控**：9:30-9:45并行监控个股抛压（SPP）、板块协同性（TS）和动量突破（MCP）。
5. **信号触发**：当MCP条件满足且板块环境健康时，触发买入。
6. **退出管理**：严格执行T+1/T+2竞价卖出、炸板即时卖出、动态止损等多重退出规则。

### 关键风控
- **全局熔断**：市场环境恶化时停止当日所有交易。
- **账户熔断**：单日亏损≥3%时停止新开仓。
- **板块熔断**：龙头炸板后立即放弃该板块。
- **仓位控制**：单股5%，单日3只，单板块15%上限。

### 策略特点
- **不预测，只跟随**：利用9:30实时数据作为全市场探针。
- **高周转、低回撤**：T+1/T+2极速滚动，多重风控保护。
- **动态适应性**：盘中实时监控抛压与板块热度，及时调整。

*“纪律是策略的灵魂” —— 请Workstation严格按此流程执行。*