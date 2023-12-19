from enum import Enum
from datetime import datetime
import os
from typing import List, Optional

from utils.logging import get_module_logger

logger = get_module_logger(linebreak=True)


class EventSeverity(Enum):
    """
    Severity of the event
    """
    CRITICAL = "CRITICAL"
    IMPORTANT = "IMPORTANT"
    NEUTRAL = "NEUTRAL"
    INFO = "INFO"
    DEBUG = "DEBUG"


class EventType(Enum):
    """
    More specific information about what the event contains
    """
    DEFAULT = "DEFAULT"
    REASONFLOW = "REASONFLOW"
    ERROR = "ERROR"


class Event:
    def __init__(self,
                 comment: str,
                 initiator: str,
                 event_severity: EventSeverity,
                 event_type: EventType = EventType.DEFAULT,
                 details: Optional[str] = None):
        """
        Initialize an Event object.

        :param comment: A description or comment about the event.
        :param event_severity: The severity of the event.
        :param event_type: The type of the event.
        """
        self.timestamp: datetime = datetime.now()
        self.initiator: str = initiator
        self.comment: str = comment
        self.details: Optional[str] = details
        self.event_severity: EventSeverity = event_severity
        self.event_type: EventType = event_type
        self._stored: bool = False
        self._tags: List[str] = []

    @property
    def tags(self):
        tags = [str(self.event_severity.value.capitalize())]
        if self.event_type != EventType.DEFAULT:
            tags.append(str(self.event_type.value.capitalize()))
        tags.append(self.initiator)
        return self._tags + tags

    def add_tag(self, tag: str):
        self._tags.append(tag)

    def __str__(self) -> str:
        return self.to_string()

    def to_string(self, details: bool = False) -> str:
        """
        Get a human-readable representation of the Event with translated icons.

        :param details: Enrich output with more details if present.

        :return: A formatted string with event information and icons.
        """
        ICONS = {
            "CRITICAL": "⛔",
            "IMPORTANT": "⚠",
            "NEUTRAL": "•",
            "INFO": "ℹ",
        }
        # formatted_time = self.timestamp.strftime("%d.%m.%Y %H:%M:%S")
        # Default to ﹖ for unknown types
        event_severity_icon = ICONS.get(self.event_severity.value, "﹖")
        formatted_str: str = f"{event_severity_icon}"
        if self.event_type is EventType.REASONFLOW:
            formatted_str += f" ReasonFlow:"
        elif self.event_type is EventType.ERROR:
            formatted_str += f" Error:"
        formatted_str += f" {self.comment}"

        if details and self.details is not None:
            return f'{formatted_str}\n{self.details}\n~ {self.initiator}'
        return formatted_str

    def store(self) -> None:
        """
        Store event to intendend place.
        Disable store ability after storing once.
        """
        if self._stored:
            return
        if os.environ.get('TESTING_ENV') == 'True':
            # Triggered by unittest -> print to console with detail
            logger.debug(self.to_string(details=True))
        else:
            if self.event_severity == EventSeverity.DEBUG:
                logger.debug(self.to_string(details=True))
            elif self.event_severity == EventSeverity.INFO:
                logger.info(self.to_string(details=True))
            elif self.event_severity == EventSeverity.NEUTRAL:
                logger.info(self.to_string(details=True))
            elif self.event_severity == EventSeverity.IMPORTANT:
                logger.warning(self.to_string(details=True))
            elif self.event_severity == EventSeverity.CRITICAL:
                logger.critical(self.to_string(details=True))
        # TODO store to db or print for debug
        self._stored = True
        return
