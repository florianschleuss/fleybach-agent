import time
import unittest
import sys
import os

# Get the parent directory
parent_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

# Add the parent directory to sys.path
sys.path.append(parent_dir)

# fmt: off
from utils.switchable import Switchable  # noqa
# fmt: on


def dummy_true(*args, **kwargs) -> bool:
    return True


Switchable._set_hardware_io = dummy_true  # type: ignore


class TestSwitchable(unittest.TestCase):
    def get_time(self):
        return self.emulated_time

    def setUp(self):
        self.sw = Switchable(name='Test widget',
                             dependencies=[
                                  Switchable('Dependency')
                             ])
        self.time_method = time.time
        self.emulated_time = self.time_method()
        time.time = self.get_time
        return

    def tearDown(self):
        time.time = self.time_method
        return

    def test_name(self):
        self.assertEqual(self.sw.name, 'Test widget')

    def test_default_values(self):
        self.assertFalse(self.sw.state)
        self.assertEqual(self.sw.active_time, 0)

    def test_state_change(self):
        # Default user
        self.assertFalse(self.sw.state)
        self.assertFalse(all(x.state for x in self.sw._dependencies))
        self.sw.set_state(True)
        self.assertTrue(self.sw.state)
        self.assertTrue(all(x.state for x in self.sw._dependencies))
        self.sw.set_state(False)
        self.assertFalse(self.sw.state)
        self.assertFalse(all(x.state for x in self.sw._dependencies))
        # Multi user
        self.sw.set_state(True, user='1')
        self.assertTrue(self.sw.state)
        self.assertTrue(all(x.state for x in self.sw._dependencies))
        self.sw.set_state(True, user='2')
        self.assertTrue(self.sw.state)
        self.assertTrue(all(x.state for x in self.sw._dependencies))
        self.sw.set_state(False, user='1')
        self.assertTrue(self.sw.state)
        self.assertTrue(all(x.state for x in self.sw._dependencies))
        self.sw.set_state(False, user='2')
        self.assertFalse(self.sw.state)
        self.assertFalse(all(x.state for x in self.sw._dependencies))

    def test_active_time(self,):
        self.sw.set_state(True)
        self.emulated_time += 20
        self.assertEqual(self.sw.active_time, 20)
        self.emulated_time += 30
        self.sw.set_state(False)
        self.assertEqual(self.sw.active_time, 50)

    def test_dependencies(self):
        self.assertFalse(all(x.state for x in self.sw._dependencies))
        self.sw.set_state(True)
        self.assertTrue(all(x.state for x in self.sw._dependencies))
        self.sw.set_state(False)
        self.assertFalse(all(x.state for x in self.sw._dependencies))

    def test_shutdown_timer(self):
        self.sw._shutdown_time = 1
        self.sw.set_state(True)
        time.sleep(0.9)
        self.assertTrue(self.sw.state)
        self.assertTrue(all(x.state for x in self.sw._dependencies))
        time.sleep(0.2)
        self.assertFalse(self.sw.state)
        self.assertFalse(all(x.state for x in self.sw._dependencies))


if __name__ == '__main__':
    unittest.main(verbosity=2)
