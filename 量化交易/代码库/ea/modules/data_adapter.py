"""
数据适配层
封装 MiniQMT 接口，实现批量请求、缓存、降级策略
"""

from typing import List, Dict, Any
from datetime import datetime
import time

try:
    from xtquant import xtdata
    XTDATA_AVAILABLE = True
except ImportError:
    XTDATA_AVAILABLE = False
    print("警告: xtquant 未安装，使用模拟数据模式")

from utils.logger import logger


class DataAdapter:
    """数据适配器"""
    
    def __init__(self, cache_enabled=True, max_cache_size=1000):
        """
        初始化数据适配器
        
        Args:
            cache_enabled: 是否启用缓存
            max_cache_size: 最大缓存条目数
        """
        self.cache_enabled = cache_enabled
        self.max_cache_size = max_cache_size
        self.cache: Dict[str, Any] = {}
        self.request_count = 0
        self.cache_hit_count = 0
        
        if not XTDATA_AVAILABLE:
            logger.warning("xtquant 未安装，数据适配器将使用模拟模式")
    
    def _get_cache_key(self, *args) -> str:
        """生成缓存键"""
        return "_".join(str(arg) for arg in args)
    
    def _get_from_cache(self, cache_key: str) -> Any:
        """从缓存获取数据"""
        if not self.cache_enabled:
            return None
        
        if cache_key in self.cache:
            self.cache_hit_count += 1
            logger.debug(f"缓存命中: {cache_key}")
            return self.cache[cache_key]
        
        return None
    
    def _save_to_cache(self, cache_key: str, data: Any):
        """保存数据到缓存"""
        if not self.cache_enabled:
            return
        
        # 如果缓存已满，删除最旧的条目
        if len(self.cache) >= self.max_cache_size:
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]
        
        self.cache[cache_key] = data
    
    def clear_cache(self):
        """清空缓存"""
        self.cache.clear()
        logger.info("缓存已清空")
    
    def get_all_stocks(self) -> List[str]:
        """
        获取全市场股票列表
        
        Returns:
            股票代码列表
        """
        cache_key = self._get_cache_key("all_stocks")
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached
        
        if not XTDATA_AVAILABLE:
            # 模拟数据
            return ['000001.SZ', '000002.SZ', '600000.SH', '600001.SH']
        
        try:
            stocks = xtdata.get_stock_list_in_sector('沪深A股')
            self._save_to_cache(cache_key, stocks)
            self.request_count += 1
            logger.info(f"获取全市场股票列表: {len(stocks)} 只")
            return stocks
        except Exception as e:
            logger.error(f"获取全市场股票列表失败: {e}")
            return []
    
    def get_stocks_in_sector(self, sector: str) -> List[str]:
        """
        获取板块内股票列表
        
        Args:
            sector: 板块名称
        
        Returns:
            股票代码列表
        """
        cache_key = self._get_cache_key("sector_stocks", sector)
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached
        
        if not XTDATA_AVAILABLE:
            # 模拟数据
            return ['000001.SZ', '000002.SZ']
        
        try:
            stocks = xtdata.get_stock_list_in_sector(sector)
            self._save_to_cache(cache_key, stocks)
            self.request_count += 1
            logger.debug(f"获取板块 {sector} 股票列表: {len(stocks)} 只")
            return stocks
        except Exception as e:
            logger.error(f"获取板块 {sector} 股票列表失败: {e}")
            return []
    
    def get_market_data_batch(self, stocks: List[str], fields: List[str], 
                              period='1d', start_time=None, end_time=None) -> Dict[str, Dict[str, Any]]:
        """
        批量请求行情数据
        
        Args:
            stocks: 股票代码列表
            fields: 字段列表（如 ['open', 'close', 'high', 'low', 'volume']）
            period: 周期（'1d', '1m', '5m' 等）
            start_time: 开始时间（支持 'HH:MM:SS' 或 'YYYYMMDD' 或 'YYYYMMDD HH:MM:SS' 格式）
            end_time: 结束时间
        
        Returns:
            {stock_code: {field: value}}
        """
        if not stocks:
            return {}
        
        # 修复时间格式：根据 period 类型决定是否需要时间部分
        if start_time:
            if period == '1d':
                # 日线数据只需要日期，不需要时间
                if len(start_time) <= 8 and ':' in start_time:
                    # 'HH:MM:SS' 格式，转换为今天的日期
                    from datetime import datetime
                    today = datetime.now().strftime('%Y%m%d')
                    start_time = today
                elif len(start_time) > 8 and ' ' in start_time:
                    # 'YYYYMMDD HH:MM:SS' 格式，只取日期部分
                    start_time = start_time.split()[0]
            else:
                # 分钟线数据需要完整的日期时间
                if len(start_time) <= 8 and ':' in start_time:
                    # 'HH:MM:SS' 格式，添加今天的日期
                    from datetime import datetime
                    today = datetime.now().strftime('%Y%m%d')
                    start_time = f"{today} {start_time}"
        
        if end_time:
            if period == '1d':
                # 日线数据只需要日期
                if len(end_time) <= 8 and ':' in end_time:
                    from datetime import datetime
                    today = datetime.now().strftime('%Y%m%d')
                    end_time = today
                elif len(end_time) > 8 and ' ' in end_time:
                    end_time = end_time.split()[0]
            else:
                # 分钟线数据需要完整的日期时间
                if len(end_time) <= 8 and ':' in end_time:
                    from datetime import datetime
                    today = datetime.now().strftime('%Y%m%d')
                    end_time = f"{today} {end_time}"
        
        cache_key = self._get_cache_key("market_data", ",".join(stocks[:5]), 
                                       ",".join(fields), period, start_time, end_time)
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached
        
        if not XTDATA_AVAILABLE:
            # 模拟数据
            result = {}
            for stock in stocks:
                result[stock] = {
                    'open': 10.0,
                    'close': 10.5,
                    'high': 11.0,
                    'low': 9.8,
                    'volume': 1000000,
                    'pre_close': 10.0
                }
            return result
        
        try:
            data = xtdata.get_market_data(
                stock_list=stocks,
                field_list=fields,
                period=period,
                start_time=start_time or '',
                end_time=end_time or ''
            )
            
            # 转换数据格式
            result = {}
            for stock in stocks:
                result[stock] = {}
                for field in fields:
                    if field in data:
                        if isinstance(data[field], dict) and stock in data[field]:
                            # 字典格式：{field: {stock: value}}
                            result[stock][field] = data[field][stock]
                        elif hasattr(data[field], 'get'):
                            # DataFrame 格式
                            try:
                                result[stock][field] = data[field].get(stock, 0)
                            except:
                                pass
            
            self._save_to_cache(cache_key, result)
            self.request_count += 1
            logger.debug(f"批量请求行情数据: {len(stocks)} 只股票, {len(fields)} 个字段")
            return result
        except Exception as e:
            logger.error(f"批量请求行情数据失败: {e}")
            return {}
    
    def get_realtime_quote_batch(self, stocks: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        批量请求实时行情数据（免费接口，不使用 L2）
        
        Args:
            stocks: 股票代码列表
        
        Returns:
            {stock_code: {
                'last_price': float,      # 最新价
                'volume': int,            # 成交量
                'amount': float,          # 成交额
                'open': float,            # 开盘价
                'high': float,            # 最高价
                'low': float,             # 最低价
                'pre_close': float,       # 前收盘价
                'change_rate': float,     # 涨跌幅
            }}
        """
        if not stocks:
            return {}
        
        if not XTDATA_AVAILABLE:
            # 模拟数据
            result = {}
            for stock in stocks:
                result[stock] = {
                    'last_price': 10.5,
                    'volume': 1000000,
                    'amount': 10500000,
                    'open': 10.0,
                    'high': 11.0,
                    'low': 9.8,
                    'pre_close': 10.0,
                    'change_rate': 5.0
                }
            return result
        
        try:
            # 使用免费的 get_full_tick 或 get_market_data 接口
            data = xtdata.get_full_tick(stocks)
            
            # 转换数据格式
            result = {}
            for stock in stocks:
                if stock in data:
                    tick = data[stock]
                    pre_close = tick.get('lastClose', 0) or tick.get('preClose', 0)
                    last_price = tick.get('lastPrice', 0) or tick.get('price', 0)
                    
                    result[stock] = {
                        'last_price': last_price,
                        'volume': tick.get('volume', 0),
                        'amount': tick.get('amount', 0),
                        'open': tick.get('open', 0),
                        'high': tick.get('high', 0),
                        'low': tick.get('low', 0),
                        'pre_close': pre_close,
                        'change_rate': ((last_price / pre_close - 1) * 100) if pre_close > 0 else 0
                    }
            
            self.request_count += 1
            logger.debug(f"批量请求实时行情: {len(stocks)} 只股票")
            return result
        except Exception as e:
            logger.error(f"批量请求实时行情失败: {e}")
            return {}
    
    def get_sector_list(self) -> List[str]:
        """
        获取板块列表
        
        Returns:
            板块名称列表
        """
        cache_key = self._get_cache_key("sector_list")
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached
        
        if not XTDATA_AVAILABLE:
            # 模拟数据
            return ['电力设备', '通信', '计算机', '电子', '医药生物']
        
        try:
            # 获取申万一级行业
            sectors = xtdata.get_sector_list()
            self._save_to_cache(cache_key, sectors)
            self.request_count += 1
            logger.info(f"获取板块列表: {len(sectors)} 个板块")
            return sectors
        except Exception as e:
            logger.error(f"获取板块列表失败: {e}")
            return []
    
    def get_stats(self) -> Dict[str, int]:
        """
        获取统计信息
        
        Returns:
            统计信息字典
        """
        return {
            'request_count': self.request_count,
            'cache_hit_count': self.cache_hit_count,
            'cache_size': len(self.cache),
            'cache_hit_rate': self.cache_hit_count / max(self.request_count, 1)
        }
