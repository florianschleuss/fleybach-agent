from enum import Enum
from datetime import datetime
import os
from typing import Optional


class EventCategory(Enum):
    CRITICAL = "CRITICAL"
    IMPORTANT = "IMPORTANT"
    NEUTRAL = "NEUTRAL"
    INFO = "INFO"


class EventType(Enum):
    DEFAULT = "DEFAULT"
    REASONFLOW = "REASONFLOW"
    ERROR = "ERROR"


class Event:
    def __init__(self,
                 comment: str,
                 event_category: EventCategory,
                 event_type: EventType = EventType.DEFAULT,
                 details: Optional[str] = None):
        """
        Initialize an Event object.

        :param comment: A description or comment about the event.
        :param event_category: The type of the event.
        """
        self.timestamp: datetime = datetime.now()
        self.comment: str = comment
        self.details: Optional[str] = details
        self.event_category: EventCategory = event_category
        self.event_type: EventType = event_type
        self._stored: bool = False

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
        formatted_time = self.timestamp.strftime("%d.%m.%Y %H:%M:%S")
        # Default to ﹖ for unknown types
        event_category_icon = ICONS.get(self.event_category.value, "﹖")
        formatted_str: str = f"{formatted_time} {event_category_icon}"
        if self.event_type is EventType.REASONFLOW:
            formatted_str += f" ReasonFlow:"
        elif self.event_type is EventType.ERROR:
            formatted_str += f" Error:"
        formatted_str += f" {self.comment}"

        if details and self.details is not None:
            return f'{formatted_str}\n{self.details}'
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
            print(self.to_string(details=True))
            return
        # TODO store to db or print for debug
        self._stored = True
        return
