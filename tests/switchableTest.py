import time
from typing import Dict
import unittest
import sys
import os
from unittest import mock
from unittest.mock import MagicMock, Mock, patch

import RPi.GPIO as GPIO
# Get the parent directory
parent_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

# Add the parent directory to sys.path
sys.path.append(parent_dir)

# fmt: off
from utils.switchable import Switchable  # noqa
from utils.switchable.powerSwitchable import PowerSwitchable, LocalDevice, RemoteDevice, RemoteDeviceType  # noqa
# fmt: on


def dummy_true(*args, **kwargs) -> bool:
    return True


DEBUG: bool = True


class TestSwitchable(unittest.TestCase):
    # TODO: restart timer, what happens if timers are canceled by new action
    def get_time(self):
        return self.emulated_time

    def setUp(self):
        Switchable._set_hardware_io = dummy_true  # type: ignore
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
        self.sw.set_state(True, user='Test')
        self.assertTrue(self.sw.state)
        self.assertTrue(all(x.state for x in self.sw._dependencies))
        self.sw.set_state(False, user='Test')
        self.assertFalse(self.sw.state)
        self.assertFalse(all(x.state for x in self.sw._dependencies))

    def test_state_change_doubled(self):
        self.sw.set_state(False, user='Test')
        self.assertFalse(self.sw.state)
        self.assertFalse(all(x.state for x in self.sw._dependencies))

    def test_multi_user_state_change(self):
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
        self.sw.set_state(True, user='Test')
        self.emulated_time += 20
        self.assertEqual(self.sw.active_time, 20)
        self.emulated_time += 30
        self.sw.set_state(False, user='Test')
        self.assertEqual(self.sw.active_time, 50)

    def test_dependencies(self):
        self.assertFalse(all(x.state for x in self.sw._dependencies))
        self.sw.set_state(True, user='Test')
        self.assertTrue(all(x.state for x in self.sw._dependencies))
        self.sw.set_state(False, user='Test')
        self.assertFalse(all(x.state for x in self.sw._dependencies))

    # @mock.patch.dict(os.environ, {"TESTING_ENV": str(DEBUG)})
    def test_timer(self):
        # Test automatic and manual timer
        self.sw._shutdown_time = 1
        self.swT = Switchable(name='Test widget true')
        self.swF = Switchable(name='Test widget false')
        self.swF.set_state(True, user='TestFalse')
        self.sw.set_state(True, user='Test')
        self.swT.set_state(True, user='TestTrue', timer=1)
        self.swF.set_state(False, user='TestFalse', timer=1)
        time.sleep(0.5)
        self.assertTrue(self.sw.state)
        self.assertTrue(all(x.state for x in self.sw._dependencies))
        self.assertTrue(self.swT.state)
        self.assertFalse(self.swF.state)
        time.sleep(0.5)
        self.assertFalse(self.sw.state)
        self.assertFalse(all(x.state for x in self.sw._dependencies))
        self.assertFalse(self.swT.state)
        self.assertTrue(self.swF.state)


class TestPowerSwitchable(unittest.TestCase):
    def setUp(self):
        PowerSwitchable._set_hardware_io = dummy_true  # type: ignore
        self.sw = PowerSwitchable(name='Test widget',
                                  power=100,
                                  dependencies=[
                                      PowerSwitchable('Dependency', 50)])
        return

    def tearDown(self):
        return

    def test_name(self):
        self.assertEqual(self.sw.name, 'Test widget')

    def test_default_values(self):
        self.assertFalse(self.sw.state)
        self.assertEqual(self.sw.active_time, 0)
        self.assertEqual(self.sw.power, 100)

    def test_power_calc(self):
        self.assertEqual(self.sw.power_all, 150)
        self.sw._dependencies.append(PowerSwitchable('Dependency2', 20))
        self.assertEqual(self.sw.power_all, 170)

    def test_state(self):
        self.sw.set_state(True, user='Test')
        self.assertTrue(self.sw.state)


class TestLocalDevice(unittest.TestCase):
    def setUp(self):
        GPIO.setmode(GPIO.BCM)  # type: ignore
        PowerSwitchable._set_hardware_io = dummy_true  # type: ignore
        self.sw = LocalDevice(name='Test widget',
                              power=100,
                              gpio=23,
                              dependencies=[
                                  PowerSwitchable('Dependency', 50)])
        return

    def tearDown(self):
        GPIO.cleanup()  # type: ignore
        return

    def test_gpio(self):
        self.sw.set_state(True, user='Test')
        self.assertTrue(self.sw.state)
        self.sw.set_state(False, user='Test')
        self.assertFalse(self.sw.state)

    def test_from_dict(self):
        obj: Dict = {
            'name': "TestDevice",
            'power': 123,
        }
        osw: LocalDevice
        with self.assertRaises(Exception) as e:
            osw = LocalDevice.from_object(obj)
        self.assertEqual('No gpio given', str(e.exception))
        obj['gpio'] = 50
        osw = LocalDevice.from_object(obj)
        self.assertEqual(osw.name, "TestDevice")
        self.assertEqual(osw.power, 123)
        self.assertEqual(osw.power_all, 123)
        self.assertEqual(osw._gpio, 50)


class TestRemoteDevice(unittest.TestCase):
    def setUp(self):
        PowerSwitchable._set_hardware_io = dummy_true
        self.sw = RemoteDevice(name='Test widget',
                               power=100,
                               host="iot-1",
                               device_type=RemoteDeviceType.SONOFF,
                               dependencies=[
                                   PowerSwitchable('Dependency', 50)])
        return

    def tearDown(self):
        return

    @patch('requests.get')
    def test_state(self, mock_post):
        self.assertFalse(self.sw.set_state(True, user='Test'))
        self.assertFalse(self.sw.state)
        self.sw.set_state(False, user='Test')

        # Mock the 'get' method of the requests library
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        self.sw.set_state(True, user='Test')
        self.assertTrue(self.sw.state)
        mock_post.assert_called_with("http://iot-1/control?cmd=GPIO,12,1")

        self.sw.set_state(False, user='Test')
        self.assertFalse(self.sw.state)
        mock_post.assert_called_with("http://iot-1/control?cmd=GPIO,12,0")

    def test_from_dict(self):
        obj: Dict = {
            'name': "TestDevice",
            'power': 123,
            'host': "no-host"
        }
        osw: RemoteDevice
        with self.assertRaises(Exception) as e:
            osw = RemoteDevice.from_object(obj)
        self.assertEqual('No device_type given', str(e.exception))
        obj['device_type'] = "tasmota"
        osw = RemoteDevice.from_object(obj)
        self.assertEqual(osw.name, "TestDevice")
        self.assertEqual(osw.power, 123)
        self.assertEqual(osw.power_all, 123)
        self.assertEqual(osw._host, "no-host")
        self.assertEqual(osw._devcive_type, RemoteDeviceType.TASMOTA)

        # Test dependency injection
        osw = RemoteDevice.from_object(obj, dependencies=[
            PowerSwitchable(name="Dependency",
                            power=1)])
        self.assertEqual(osw.power_all, 124)


if __name__ == '__main__':
    unittest.main(verbosity=2)
