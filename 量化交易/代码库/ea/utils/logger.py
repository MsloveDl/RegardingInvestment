"""
日志工具模块
提供统一的日志记录功能
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime
import sys

class Logger:
    """日志管理器"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.initialized = True
            self.logger = None
            
    def setup(self, log_file='logs/ea_strategy.log', log_level='INFO', 
              max_bytes=10*1024*1024, backup_count=5):
        """
        初始化日志系统
        
        Args:
            log_file: 日志文件路径
            log_level: 日志级别
            max_bytes: 单个日志文件最大大小
            backup_count: 日志文件备份数量
        """
        # 创建日志目录
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # 创建 logger
        self.logger = logging.getLogger('SentimentArbitrageEA')
        self.logger.setLevel(getattr(logging, log_level.upper()))
        
        # 清除已有的 handlers
        self.logger.handlers.clear()
        
        # 创建格式化器
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 文件处理器（带轮转）
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(getattr(logging, log_level.upper()))
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        
        # 控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, log_level.upper()))
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        self.logger.info("=" * 60)
        self.logger.info("情绪套利策略 EA 启动")
        self.logger.info(f"日志文件: {log_file}")
        self.logger.info(f"日志级别: {log_level}")
        self.logger.info("=" * 60)
    
    def get_logger(self):
        """获取 logger 实例"""
        if self.logger is None:
            self.setup()
        return self.logger
    
    def info(self, msg):
        """记录 INFO 级别日志"""
        self.get_logger().info(msg)
    
    def debug(self, msg):
        """记录 DEBUG 级别日志"""
        self.get_logger().debug(msg)
    
    def warning(self, msg):
        """记录 WARNING 级别日志"""
        self.get_logger().warning(msg)
    
    def error(self, msg, exc_info=False):
        """记录 ERROR 级别日志"""
        self.get_logger().error(msg, exc_info=exc_info)
    
    def critical(self, msg, exc_info=False):
        """记录 CRITICAL 级别日志"""
        self.get_logger().critical(msg, exc_info=exc_info)


# 全局 logger 实例
logger = Logger()


def get_logger():
    """获取全局 logger 实例"""
    return logger.get_logger()
