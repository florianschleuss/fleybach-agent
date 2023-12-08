from cmath import exp
from datetime import datetime
import os
import sys
import unittest

# Get the parent directory
parent_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

# Add the parent directory to sys.path
sys.path.append(parent_dir)

# fmt: off
from utils.event import EventCategory  
from utils.reason import ReasonFlow  
# fmt: on


class TestReasonFlow(unittest.TestCase):
    def setUp(self):
        self.rf = ReasonFlow(name="Test Flow")

    def test_initial_reason(self):
        self.rf = ReasonFlow(
            name="Test Flow", initial_comment="Initial reason")
        self.assertEqual(str(self.rf), "Test Flow\n  ⤷ Initial reason")
        self.rf.add_reason("Reason 1")
        self.assertEqual(
            str(self.rf), "Test Flow\n  ↓ Initial reason\n  ⤷ Reason 1")

    def test_add_reason(self):
        self.rf.add_reason("Initial reason")
        self.assertEqual(str(self.rf), "Test Flow\n  ⤷ Initial reason")

    def test_remove_reason(self):
        self.rf.add_reason("Reason 1")
        self.rf.add_reason("Reason 2")
        self.rf.remove_reason()
        self.assertEqual(str(self.rf), "Test Flow\n  ⤷ Reason 1")

    def test_remove_multiple_reasons(self):
        self.rf.add_reason("Reason 1")
        self.rf.add_reason("Reason 2")
        self.rf.add_reason("Reason 3")
        self.rf.remove_reason(2)
        self.assertEqual(str(self.rf), "Test Flow\n  ⤷ Reason 1")

    def test_remove_all_reasons(self):
        self.rf.add_reason("Reason 1")
        self.rf.add_reason("Reason 2")
        self.rf.remove_reason(2)
        self.assertIsNone(self.rf.head)

    def test_remove_nonexistent_reason(self):
        self.rf.remove_reason()  # Removing from an empty ReasonFlow
        self.assertIsNone(self.rf.head)

    def test_to_string(self):
        self.rf.add_reason("Reason 1")
        self.rf.add_reason("Reason 2")
        self.assertEqual(str(self.rf), "Test Flow\n  ↓ Reason 1\n  ⤷ Reason 2")

    def test_to_event(self):
        self.rf.add_reason("Reason 1")
        self.rf.add_reason("Reason 2")
        event = self.rf.to_event(EventCategory.INFO, immediate_store=False)
        now = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
        expected_event_str = f"{now} ℹ ReasonFlow: Test Flow"
        self.assertEqual(event.to_string(), expected_event_str)
        expected_event_str += "\n  ↓ Reason 1\n  ⤷ Reason 2"
        self.assertEqual(event.to_string(True), expected_event_str)


if __name__ == '__main__':
    unittest.main(verbosity=2)
