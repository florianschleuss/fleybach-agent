import logging


LOGGING_LEVEL = logging.DEBUG
FLASK_LOGGING_LEVEL = logging.DEBUG


werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.setLevel(FLASK_LOGGING_LEVEL)


class NewlineRemovingFormatter(logging.Formatter):
    def format(self, record):
        record.msg = str(record.msg)
        record.msg = record.msg.replace('\n', ' ')
        return super(NewlineRemovingFormatter, self).format(record)


class NewlineFormatter(logging.Formatter):
    def format(self, record):
        record.msg = str(record.msg)
        record.msg = ('\n'+record.msg).replace('\n', '\n    ')
        return super(NewlineFormatter, self).format(record)


logger: logging.Logger = logging.getLogger('agent')
linebreak_logger: logging.Logger = logging.getLogger('agent_lb')
handler = logging.StreamHandler()
linebreak_handler = logging.StreamHandler()
formatter = NewlineRemovingFormatter(
    '[%(asctime)s] %(levelname)-8s: %(message)s',
    datefmt="%d/%b/%Y %H:%M:%S")
linebreak_formatter = NewlineFormatter(
    '[%(asctime)s] %(levelname)-8s: %(message)s',
    datefmt="%d/%b/%Y %H:%M:%S")
handler.setFormatter(formatter)
linebreak_handler.setFormatter(linebreak_formatter)
logger.addHandler(handler)
linebreak_logger.addHandler(linebreak_handler)
logger.setLevel(logging.DEBUG)
linebreak_logger.setLevel(logging.DEBUG)


def get_module_logger(linebreak=False) -> logging.Logger:
    if linebreak:
        return linebreak_logger
    return logger


def format_seconds_to_mm_ss(total_seconds: float) -> str:
    """
    Convert total seconds to "mm:ss" format.

    :param total_seconds: Total seconds to be converted.

    :return: Formatted time in "mm:ss" format.
    """
    minutes = int(total_seconds // 60)
    seconds = int(total_seconds % 60)
    return f"{minutes:02d}:{seconds:02d} min."
