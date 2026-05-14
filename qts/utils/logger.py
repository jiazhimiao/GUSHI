"""Structured logging setup."""
import sys
from pathlib import Path
from loguru import logger as _logger

# Force UTF-8 on Windows terminals to avoid garbled Chinese output
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

_logger.remove()
_logger.add(
    sys.stderr,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level="INFO",
    colorize=False,  # disable ANSI on Windows to avoid double-encoding issues
)


def setup_file_log(log_dir: str = "data") -> None:
    """Add a rotating file sink for persistent logs."""
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    _logger.add(
        Path(log_dir) / "qts_{time:YYYY-MM-DD}.log",
        rotation="10 MB",
        retention="30 days",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG",
    )


logger = _logger
