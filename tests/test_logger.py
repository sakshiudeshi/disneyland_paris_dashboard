import logging

from src.utils.logger import setup_logger


def test_setup_logger_reuses_handlers():
    """Calling setup_logger twice should not duplicate handlers."""
    logger = setup_logger("test_logger_reuse")
    initial_handlers = list(logger.handlers)

    logger_again = setup_logger("test_logger_reuse")

    assert logger_again is logger
    assert logger.handlers == initial_handlers

    # Cleanup to avoid leaking handlers to other tests
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()


def test_setup_logger_with_file(tmp_path):
    """Optional log file should create a FileHandler."""
    log_file = tmp_path / "sample.log"
    logger = setup_logger("test_logger_file", log_file=str(log_file))

    logger.info("write to file handler")

    assert log_file.exists()
    contents = log_file.read_text().strip()
    assert "write to file handler" in contents

    # Cleanup
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
