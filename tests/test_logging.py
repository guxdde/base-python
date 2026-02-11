import logging
from app.common.logging_utils import get_logger

def test_logging_adapter():
    logger = get_logger("test", trace_id="trace-123")
    assert isinstance(logger, logging.LoggerAdapter)
