import importlib.util
import io
import os
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location('temperature_under_test', os.environ.get('TEMPERATURE_MODULE', 'temperature.py'))
temperature = importlib.util.module_from_spec(spec)
spec.loader.exec_module(temperature)


class StopPolling(BaseException):
    pass


class SerialStream(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class TemperaturePollingTests(unittest.TestCase):
    def setUp(self):
        from utils.sensor import Sensor
        self.sensor = Sensor('good', 'water', serial_connected=True)
        self.config = SimpleNamespace(sensors=[self.sensor], get_sensor=lambda key: self.sensor if key == 'good' else None)
        self.config_patch = patch.object(temperature, 'config', self.config)
        self.config_patch.start()
        self.addCleanup(self.config_patch.stop)

    def test_bad_frame_is_discarded_and_next_valid_frame_is_uploaded(self):
        damaged = b'{"sensors": []}{"extra":true}\n'
        valid = b'{"sensors":[null,{"id":"good","value":"bad"},{"id":"good","value":15.5}]}\n'
        with patch.object(temperature.serial, 'Serial', return_value=SerialStream(damaged+valid)):
            self.assertEqual(temperature.update_temperature_by_serial(), [{'id':'good','value':15.5}])
        self.assertEqual(self.sensor.value, 15.5)

    def test_local_reading_matches_existing_batch_without_duplicate_offset(self):
        self.sensor.offset = 2
        with patch('utils.site_store.publish') as publish:
            updates = temperature.serial_sensor_updates('{"sensors":[{"id":"good","value":14.5}]}')
        self.assertEqual(updates, [{'id': 'good', 'value': 14.5}])
        self.assertEqual(publish.call_args.args[3], 14.5)

    def test_invalid_values_and_missing_sensor_lists_do_not_crash(self):
        self.assertIsNone(temperature.serial_sensor_updates('{"other":[]}'))
        self.assertEqual(temperature.serial_sensor_updates('{"sensors":[{},null,{"id":"good","value":true},{"id":"good","value":NaN}]}'), [])

    def test_polling_recovers_after_unexpected_read_error(self):
        with patch.object(temperature, 'update_temperature_by_serial', side_effect=[ValueError('bad frame'), []]) as read, \
             patch.object(temperature, 'batch_update_sensor') as upload, \
             patch.object(temperature, 'check_routines') as routines, \
             patch.object(temperature.logger, 'exception'), \
             patch.object(temperature.time, 'sleep', side_effect=[None, StopPolling()]):
            with self.assertRaises(StopPolling):
                temperature.update_loop()
        self.assertEqual(read.call_count, 2)
        routines.assert_called_once()
        upload.assert_called_once_with(sensors_list=[])


if __name__ == '__main__':
    unittest.main()
