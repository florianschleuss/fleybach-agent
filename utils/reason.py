import copy
from typing import List, Optional, TypeVar
from utils.delayTimer import DelayTimer

from utils.event import Event, EventCategory, EventType

ReasonFlow = TypeVar('ReasonFlow')  # type: ignore


class Reason:
    def __init__(self, comment: str, depth: int):
        """
        Represents a reason with a comment and its depth in the flow.

        :param comment: A description or comment for the reason.
        :param depth: The depth (length) of the reason in the ReasonFlow.
        """
        self.comment: str = comment
        self.depth: int = depth
        # Pointer to the next reason in the flow
        self.next: Optional[Reason] = None


class ReasonFlow:
    def __init__(self,
                 name: str,
                 initial_comment: Optional[str] = None,
                 auto_store_seconds: Optional[int] = 1,
                 auto_store_event_category: EventCategory = EventCategory.NEUTRAL):
        """
        Initializes ReasonFlow

        :param name:
        :param initial_comment:
        :param auto_store_seconds: If 'None' disables auto-store. Else seconds of no-reason-add until auto-store
        :param auto_store_event_category: Category in which the event will be auto-stored
        """
        # Name to describe the reason
        self.name = name

        # First element of the ReasonFlow as an entry point.
        self.head: Optional[Reason] = None

        self._event: Optional[Event] = None

        # Initialized DelayTimer for auto-save
        self._auto_store_timer: Optional[DelayTimer] = None
        if auto_store_seconds is not None:
            self._auto_store_timer = DelayTimer(timeout=auto_store_seconds,
                                                userHandler=self.to_event,
                                                kwargs={
                                                    'event_category': auto_store_event_category}
                                                )

        # Initiate with immediate reason
        if initial_comment is not None:
            self.add_reason(initial_comment)

    def __str__(self) -> str:
        """
        Convert the ReasonFlow to a human-readable string representation.

        :return: A string representation of the ReasonFlow.
        """
        result = [self.name]
        current_reason = self.head
        while current_reason:
            if current_reason.next is not None:
                result.append('  ↓ ' + current_reason.comment)
            else:
                result.append('  ⤷ ' + current_reason.comment)
            current_reason = current_reason.next
        return '\n'.join(result)

    @property
    def last_reason(self) -> Optional[Reason]:
        """
        Get the last reason in the ReasonFlow.

        :return: The last reason in the ReasonFlow,
                 or None if the flow is empty.
        """
        if self.head is None:
            return None  # Return None if the flow is empty

        current_reason = self.head
        while current_reason.next is not None:
            current_reason = current_reason.next

        return current_reason

    def add_reason(self, comment: str) -> ReasonFlow:
        """
        Add a new reason to the ReasonFlow.

        :param comment: A description or comment for the new reason.
        """
        depth: int = self._get_depth()
        new_reason: Reason = Reason(comment, depth)
        if not self.head:
            self.head = new_reason
        else:
            current_reason: Reason = self.head
            while current_reason.next:
                current_reason = current_reason.next
            current_reason.next = new_reason
        if self._auto_store_timer is not None:
            self._auto_store_timer.reset()
        return self

    def update_name(self) -> ReasonFlow:
        """
        Sets the last comment as the new name of the RF
        """
        if self.last_reason is not None:
            self.name = self.last_reason.comment
        return self

    def _get_depth(self) -> int:
        """
        Get the depth (length) of the ReasonFlow.

        :return: The depth of the ReasonFlow.
        """
        depth: int = 0
        current_reason = self.head
        while current_reason:
            depth += 1
            current_reason = current_reason.next
        return depth

    def remove_reason(self, count: int = 1) -> None:
        """
        Remove one or more reasons from the end of the ReasonFlow.

        :param count: The number of reasons to remove.
        """
        if self.head is None:
            return  # Nothing to remove

        if count >= self._get_depth():
            self.head = None
        else:
            current_reason: Reason = self.head
            while count < self._get_depth() - 1:
                if current_reason.next is None:
                    return
                current_reason = current_reason.next
                count += 1
            current_reason.next = None

    def split(self, split_comment: Optional[str] = None) -> ReasonFlow:
        """
        Create a deep copy of the ReasonFlow instance.

        :param split_comment: Optional comment to be added to the ReasonFlow
                              after splitting.

        :return: A deep copy of the ReasonFlow instance.
        """
        if restore_timer := self._auto_store_timer is not None:
            self._auto_store_timer.stop()
            timer_seconds = self._auto_store_timer.timeout
            timer_handler = self._auto_store_timer.handler
            timer_args = self._auto_store_timer._args
            timer_kwargs = self._auto_store_timer._kwargs
        self._auto_store_timer = None
        cp = copy.deepcopy(self)
        if restore_timer:
            self._auto_store_timer = DelayTimer(timeout=timer_seconds,  # type: ignore
                                                userHandler=self.to_event,  # type: ignore
                                                args=timer_args,  # type: ignore
                                                kwargs=timer_kwargs)  # type: ignore
            cp._auto_store_timer = DelayTimer(timeout=timer_seconds,  # type: ignore
                                              userHandler=cp.to_event,  # type: ignore
                                              args=timer_args,  # type: ignore
                                              kwargs=timer_kwargs)  # type: ignore
        if split_comment is not None:
            cp.add_reason(split_comment)
        return cp

    def to_event(self,
                 event_category: EventCategory,
                 immediate_store: bool = True) -> Event:
        """
        Create an Event from the ReasonFlow.

        :param event_category: Set the event type of the result.

        :return: An Event object combining all reasons.
        """
        comment: str = self.name
        details: List[str] = []
        current_reason = self.head
        while current_reason:
            if current_reason.next is not None:
                details.append('  ↓ ' + current_reason.comment)
            else:
                details.append('  ⤷ ' + current_reason.comment)
            current_reason = current_reason.next
        if self._event is None:
            self._event = Event(comment=comment,
                                details='\n'.join(details),
                                event_category=event_category,
                                event_type=EventType.REASONFLOW)
        else:
            self._event.comment = comment
            self._event.details = '\n'.join(details)
            self._event.event_category = event_category
        if immediate_store:
            self._event.store()
            if self._auto_store_timer is not None:
                self._auto_store_timer.stop()
        return self._event
