import unittest
from unittest.mock import patch
from utils.sensor import Routine

class Tests(unittest.TestCase):
 def test_http_latency_does_not_halve_history_frequency(self):
  r=Routine('power','cycle',['total'],10);r.last_run=100
  r.completed(110.2)
  self.assertEqual(r.last_run,110)
  with patch('utils.sensor.time.time',return_value=120.2):self.assertTrue(r.due())
  r.completed(120.2);self.assertEqual(r.last_run,120)
 def test_long_outage_skips_missed_intervals_without_replay(self):
  r=Routine('temperature','cycle',['air'],30);r.last_run=100
  r.completed(407);self.assertEqual(r.last_run,400)
  with patch('utils.sensor.time.time',return_value=408):self.assertFalse(r.due())
  with patch('utils.sensor.time.time',return_value=431):self.assertTrue(r.due())

if __name__=='__main__':unittest.main(verbosity=2)
