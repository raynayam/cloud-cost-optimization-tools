"""
Logging utilities for Cloud Cost Optimization Tools.
"""

import logging
import sys
from rich.logging import RichHandler

def setup_logger(log_level: int = logging.INFO) -> logging.Logger:
    """
    Set up logger with rich formatting.
    
    Args:
        log_level: Logging level (from logging module)
        
    Returns:
        Configured logger
    """
    # Configure rich handler
    rich_handler = RichHandler(
        rich_tracebacks=True,
        markup=True,
        show_time=True,
        omit_repeated_times=False,
    )
    
    # Configure logging format
    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[rich_handler]
    )
    
    # Get logger instance
    logger = logging.getLogger("cloud-cost-optimizer")
    
    return logger 