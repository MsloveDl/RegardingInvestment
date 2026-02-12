"""
板块扫描模块
9:25 锁定全市场最强的 1-3 个板块
"""

from typing import List, Dict, Tuple
from datetime import datetime

from modules.data_adapter import DataAdapter
from utils.logger import logger
from utils.signal_bus import signal_bus, SignalType
import config


class SectorScanner:
    """板块扫描器"""
    
    def __init__(self, data_adapter: DataAdapter):
        """
        初始化板块扫描器
        
        Args:
            data_adapter: 数据适配器
        """
        self.data_adapter = data_adapter
        self.sector_list = []
        self.last_scan_result = {}
    
    def scan_at_925(self) -> List[str]:
        """
        9:25 板块扫描
        
        Returns:
            目标板块列表（最多 3 个）
        """
        logger.info("=" * 60)
        logger.info("开始板块扫描（9:25）")
        logger.info("=" * 60)
        
        # 1. 获取板块列表
        self.sector_list = self.data_adapter.get_sector_list()
        if not self.sector_list:
            logger.warning("未获取到板块列表")
            return []
        
        logger.info(f"共 {len(self.sector_list)} 个板块待扫描")
        
        # 2. 获取全市场竞价数据
        all_stocks = self.data_adapter.get_all_stocks()
        if not all_stocks:
            logger.warning("未获取到股票列表")
            return []
        
        logger.info(f"获取全市场 {len(all_stocks)} 只股票的竞价数据...")
        
        # 使用昨天的数据进行测试（非交易时间）
        from datetime import datetime, timedelta
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
        logger.info(f"使用日期: {yesterday} (非交易时间使用昨天数据)")
        
        quote_data = self.data_adapter.get_market_data_batch(
            stocks=all_stocks,
            fields=['open', 'pre_close'],
            period='1d',
            start_time=yesterday,
            end_time=yesterday
        )
        
        if not quote_data:
            logger.warning("未获取到竞价数据")
            return []
        
        # 3. 计算每个板块的 SS 因子
        sector_ss = {}
        for sector in self.sector_list:
            ss_score = self._calculate_sector_ss(sector, quote_data)
            if ss_score > 0:
                sector_ss[sector] = ss_score
        
        # 4. 筛选目标板块
        top_sectors = self._filter_top_sectors(sector_ss, quote_data)
        
        # 5. 保存扫描结果
        self.last_scan_result = {
            'timestamp': datetime.now(),
            'sector_ss': sector_ss,
            'top_sectors': top_sectors
        }
        
        # 6. 发送信号
        signal_bus.emit(SignalType.SECTOR_SCANNED, {
            'top_sectors': top_sectors,
            'sector_ss': sector_ss
        })
        
        logger.info("=" * 60)
        logger.info(f"板块扫描完成，目标板块: {top_sectors}")
        logger.info("=" * 60)
        
        return top_sectors
    
    def _calculate_sector_ss(self, sector: str, quote_data: Dict) -> float:
        """
        计算板块强度因子 SS
        
        Args:
            sector: 板块名称
            quote_data: 竞价数据
        
        Returns:
            SS 评分
        """
        # 获取板块内股票
        stocks = self.data_adapter.get_stocks_in_sector(sector)
        if not stocks:
            return 0.0
        
        # 计算涨幅
        changes = []
        for stock in stocks:
            if stock in quote_data:
                data = quote_data[stock]
                if 'open' in data and 'pre_close' in data:
                    open_price = data['open']
                    pre_close = data['pre_close']
                    if pre_close > 0:
                        change = (open_price / pre_close - 1) * 100
                        changes.append(change)
        
        if not changes:
            return 0.0
        
        # SR（涨停共振因子）：涨幅 > 9.5% 的个股数量
        sr = sum(1 for c in changes if c > config.SECTOR_FILTER['limit_up_threshold'])
        
        # OR（封单强度比）：降级版用开盘涨幅代替
        # 计算涨幅 > 5% 的个股平均涨幅
        strong_changes = [c for c in changes if c > 5.0]
        or_score = sum(strong_changes) / len(stocks) if strong_changes else 0.0
        
        # CR（抗撤单因子）：降级版暂时省略，使用默认值
        cr = 1.0
        
        # 计算 SS
        weights = config.SECTOR_SS_WEIGHTS
        ss = weights['W1'] * sr + weights['W2'] * or_score + weights['W3'] * cr
        
        logger.debug(f"板块 {sector}: SR={sr}, OR={or_score:.2f}, CR={cr:.2f}, SS={ss:.2f}")
        
        return ss
    
    def _filter_top_sectors(self, sector_ss: Dict[str, float], quote_data: Dict) -> List[str]:
        """
        筛选目标板块
        
        Args:
            sector_ss: 板块 SS 评分字典
            quote_data: 竞价数据
        
        Returns:
            目标板块列表
        """
        if not sector_ss:
            return []
        
        # 按 SS 排序
        sorted_sectors = sorted(sector_ss.items(), key=lambda x: x[1], reverse=True)
        
        # 筛选条件：SS 前三且 SR >= 3
        top_sectors = []
        for sector, ss_score in sorted_sectors[:config.SECTOR_FILTER['top_n']]:
            # 计算 SR
            stocks = self.data_adapter.get_stocks_in_sector(sector)
            sr = 0
            for stock in stocks:
                if stock in quote_data:
                    data = quote_data[stock]
                    if 'open' in data and 'pre_close' in data:
                        open_price = data['open']
                        pre_close = data['pre_close']
                        if pre_close > 0:
                            change = (open_price / pre_close - 1) * 100
                            if change > config.SECTOR_FILTER['limit_up_threshold']:
                                sr += 1
            
            # 检查 SR 是否满足条件
            if sr >= config.SECTOR_FILTER['min_sr']:
                top_sectors.append(sector)
                logger.info(f"✓ 板块 {sector}: SS={ss_score:.2f}, SR={sr}")
            else:
                logger.info(f"✗ 板块 {sector}: SS={ss_score:.2f}, SR={sr} (不满足 SR>={config.SECTOR_FILTER['min_sr']})")
        
        return top_sectors
    
    def get_last_scan_result(self) -> Dict:
        """
        获取上次扫描结果
        
        Returns:
            扫描结果字典
        """
        return self.last_scan_result
