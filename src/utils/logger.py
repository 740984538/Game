"""
日志配置
使用 loguru 进行结构化日志记录
"""
import sys

try:
    from loguru import logger

    def setup_logger(level: str = "DEBUG") -> None:
        """初始化日志系统，输出到控制台和文件"""
        logger.remove()
        logger.add(
            sys.stderr,
            level=level,
            format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        )
        logger.add(
            "logs/game_{time:YYYY-MM-DD}.log",
            rotation="10 MB",
            retention="7 days",
            level="INFO",
            encoding="utf-8",
        )

except ImportError:
    import logging

    def setup_logger(level: str = "DEBUG") -> None:  # type: ignore[misc]
        """loguru 不可用时降级为标准 logging"""
        logging.basicConfig(
            level=getattr(logging, level),
            format="%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d - %(message)s",
        )

    logger = logging.getLogger("roguelike")  # type: ignore[assignment]
