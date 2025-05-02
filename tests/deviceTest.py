import datetime
import os
from sqlite3 import Date
import sys
import time
import unittest
from unittest import mock
from dotenv import load_dotenv
import time_machine


import RPi.GPIO as GPIO

# Get the parent directory
parent_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

# Add the parent directory to sys.path
sys.path.append(parent_dir)

# fmt: off
from utils.reason import ReasonFlow
from utils.switchable.powerSwitchable import LocalDevice, PowerSwitchable, RemoteDevice  
import device.device  
# fmt: on

DEBUG: bool = True


# @mock.patch.dict(os.environ, {"TESTING_ENV": str(DEBUG)})
class TestDevice(unittest.TestCase):
    def setUp(self):
        self.dc = device.device.DeviceController()
        GPIO.setmode(GPIO.BCM)  # type: ignore
        return

    def tearDown(self):
        GPIO.cleanup()  # type: ignore
        return

    def test_load_from_yaml(self):
        self.dc = device.device.DeviceController(
            device_config_path=f'{os.path.dirname(os.path.realpath(__file__))}/test-device-config.yaml')
        self.assertIn('a', self.dc._devices)
        self.assertIn('b', self.dc._devices)
        self.assertIn('c', self.dc._devices)
        self.assertEqual(len(self.dc._devices['a']._dependencies), 0)
        self.assertEqual(len(self.dc._devices['b']._dependencies), 1)
        self.assertEqual(len(self.dc._devices['c']._dependencies), 0)
        self.assertIsInstance(self.dc._devices['b'], LocalDevice)
        self.assertIsInstance(self.dc._devices['c'], RemoteDevice)
        if not isinstance(self.dc._devices['b'], PowerSwitchable):
            return
        self.assertEqual(self.dc._devices['b'].power_all, 70)

    def test_devices_in_relevance_order(self):
        # Create test devices and add them to the controller
        device1 = LocalDevice(name='Device1', power=100,
                              gpio=50, min_active_time_seconds=10)
        device2 = LocalDevice(name='Device2', power=200,
                              gpio=51, min_active_time_seconds=20)
        self.dc._devices = {'Device1': device1, 'Device2': device2}

        # Test with state=False and reverse=False
        devices = self.dc._devices_in_relevance_order(
            state=False, reverse=False)
        self.assertEqual(devices, [device2, device1])

        device1.importance = 1
        devices = self.dc._devices_in_relevance_order(
            state=False, reverse=False)
        self.assertEqual(devices, [device1, device2])

    def test_tick(self):
        device1 = LocalDevice(name='Device1', power=100,
                              gpio=50, min_active_time_seconds=10)
        device2 = LocalDevice(name='Device2', power=200,
                              gpio=51, min_active_time_seconds=5,
                              dependencies=[device1])
        self.dc._devices = {'Device1': device1, 'Device2': device2}
        # Switch on if power excess
        self.dc.tick(current_power_consumption=-500)
        self.assertTrue(device1.state)
        self.assertTrue(device2.state)
        # Switch off if to much power draw
        self.dc._avrg_power_consumtion = {}
        self.dc.tick(current_power_consumption=500)
        self.assertFalse(device1.state)
        self.assertFalse(device2.state)

    # @mock.patch.dict(os.environ, {"TESTING_ENV": str(DEBUG)})
    def test_active_time_deadline_check(self,):
        with time_machine.travel("01.01.00 23:59:00"):
            device1 = LocalDevice(name='Device1', power=100,
                                  gpio=50, min_active_time_seconds=2)
            device2 = LocalDevice(name='Device2', power=200,
                                  gpio=51, min_active_time_seconds=1,
                                  dependencies=[device1])
            device3 = LocalDevice(name='Device3', power=200,
                                  gpio=51, min_active_time_seconds=0)
            device4 = LocalDevice(name='Device4', power=200,
                                  gpio=51, min_active_time_seconds=1)
            device4._active_time_seconds = 10
            self.dc._devices = {'Device1': device1,
                                'Device2': device2,
                                'Device3': device3,
                                'Device4': device4}
            self.dc.tick(current_power_consumption=0)
            self.assertTrue(device1.state)
            self.assertTrue(device2.state)
            time.sleep(1.1)
            self.assertTrue(device1.state)
            self.assertFalse(device2.state)
            time.sleep(1)
            self.assertFalse(device1.state)
            self.assertFalse(device2.state)


if __name__ == '__main__':
    unittest.main(verbosity=2)
