from enum import Enum
from datetime import datetime
import os
from typing import List, Optional

import requests
from utils.auth import JWTValidator

from utils.logging import get_module_logger

logger = get_module_logger(linebreak=True)

CUSTOMER_DOMAIN = os.environ.get('CUSTOMER_DOMAIN', "default")
CUSTOMER_SECRET = os.environ.get('CUSTOMER_SECRET', "")
AUTH_URL = os.environ.get('AUTH_URL', "")
jwt: JWTValidator = JWTValidator(AUTH_URL, CUSTOMER_DOMAIN, CUSTOMER_SECRET)


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
                 details: Optional[List[str]] = None):
        """
        Initialize an Event object.

        :param comment: A description or comment about the event.
        :param event_severity: The severity of the event.
        :param event_type: The type of the event.
        """
        self.timestamp: datetime = datetime.now()
        self.initiator: str = initiator
        self.comment: str = comment
        self.details: Optional[List[str]] = details
        self.event_severity: EventSeverity = event_severity
        self.event_type: EventType = event_type
        self._stored: bool = False
        self._tags: List[str] = []

    @property
    def tags(self):
        tags = [str(self.event_severity.value.lower())]
        if self.event_type != EventType.DEFAULT:
            tags.append(str(self.event_type.value.lower()))
        tags.append(self.initiator.lower())
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
            details_strings: List[str] = []
            if self.event_type is EventType.REASONFLOW:
                for i, d in enumerate(self.details):
                    if i == len(self.details)-1:
                        details_strings.append('  ⤷ ' + d)
                    else:
                        details_strings.append('  ↓ ' + d)
            else:
                details_strings = self.details
            details_string = '\n'.join(details_strings)
            return f"{formatted_str}\n{details_string}\n~ {self.initiator}"
        return f"{formatted_str} ~ {self.initiator}"

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
            if self.event_severity in [EventSeverity.INFO, EventSeverity.NEUTRAL, EventSeverity.IMPORTANT, EventSeverity.CRITICAL]:
                self._post_event()
        self._stored = True
        return

    def _post_event(self) -> bool:
        """
        POST the event to the backend.

        :return: Success of POST
        """
        jwt.v()
        data = {
            'comment': self.comment,
            'initiator': self.initiator,
            'timestamp': self.timestamp.timestamp(),
            'severity': self.event_severity.value.capitalize(),
            'type': self.event_type.value.capitalize(),
            'tags': self.tags
        }
        if self.details is not None:
            data['details'] = self.details
        try:
            post = requests.post(f'http://{CUSTOMER_DOMAIN}/event/events?customer_id={jwt.token.customer_id}',
                                 json=data, headers={'x-access-token': jwt.token._token})
            return post.status_code == 200
        except requests.exceptions.ConnectionError:
            pass
        return False
