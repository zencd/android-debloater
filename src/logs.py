import logging

from src.defs import AUDIT_LOG_FILE, DEBUG, MAIN_LOG_FILE


def create_audit_logger():
    level = logging.INFO
    log_file = AUDIT_LOG_FILE
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger('audit_logger')
    logger.setLevel(level)
    if not logger.handlers:
        handler = logging.FileHandler(log_file, encoding='utf-8')
        handler.setLevel(level)
        handler.setFormatter(logging.Formatter('%(asctime)s %(message)s', '%Y-%m-%d %H:%M:%S'))
        logger.addHandler(handler)
    return logger


def create_main_logger():
    level = logging.DEBUG if DEBUG else logging.INFO
    # level = logging.INFO
    logger = logging.getLogger('main_logger')
    logger.setLevel(level)
    if not logger.handlers:
        formatter = logging.Formatter('%(asctime)s %(levelname)-7s %(message)s', '%Y-%m-%d %H:%M:%S')

        log_file = MAIN_LOG_FILE
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    return logger

def audit(msg):
    audit_logger.info(msg)

def audit_if(ok: bool, msg):
    if ok:
        audit_logger.info(msg)

audit_logger = create_audit_logger()
log = create_main_logger()