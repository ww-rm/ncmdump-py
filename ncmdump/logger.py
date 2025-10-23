import logging as _logging

from rich.console import Console as _Console
from rich.logging import RichHandler as _RichHandler

console = _Console(theme=None)

_logging.basicConfig(
    level="DEBUG",
    format="%(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[_RichHandler(
        console=console,
        markup=False,
        rich_tracebacks=True,
        show_path=True,
        show_level=True,
        show_time=True,
        log_time_format="%Y-%m-%d %H:%M:%S",
    )]
)

logger = _logging.getLogger("App")
logger.info("Logger initialized.")
