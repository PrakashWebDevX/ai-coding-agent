"""
Centralized rich logging. Import get_logger(name) anywhere in the codebase.
Provides color-coded logs per subsystem (agent / browser / execution / retry).
"""
import logging

from rich.logging import RichHandler

_CONFIGURED = False


def _configure_root(level: str = "INFO") -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True, show_path=False, markup=True)],
    )
    _CONFIGURED = True


def get_logger(name: str, level: str = "INFO") -> logging.Logger:
    _configure_root(level)
    logger = logging.getLogger(name)
    logger.setLevel(level)
    return logger


def log_agent(logger: logging.Logger, agent_name: str, message: str) -> None:
    logger.info(f"[bold cyan]\\[{agent_name}][/bold cyan] {message}")


def log_browser(logger: logging.Logger, message: str) -> None:
    logger.info(f"[bold magenta]\\[browser][/bold magenta] {message}")


def log_retry(logger: logging.Logger, attempt: int, message: str) -> None:
    logger.warning(f"[bold yellow]\\[retry #{attempt}][/bold yellow] {message}")


def log_execution(logger: logging.Logger, message: str) -> None:
    logger.info(f"[bold green]\\[execution][/bold green] {message}")
