import unittest
from utils.site_requirements import requirements_from_config
class RequirementsTests(unittest.TestCase):
 def test_no_buffer_needed_for_simple_site(self):
  req=requirements_from_config({'local_devices':[{'name':'lamp','disable_automatic_management':True}]})
  self.assertEqual(req[0]['roles'],[])
  self.assertNotIn('sensor',req[0]['features'])
 def test_dynamic_device_declares_existing_inputs(self):
  req=requirements_from_config({'dynamic_devices':[{'name':'lg','buffer_sensor':'bufferTop','outdoor_sensor':'air'}]})[0]
  self.assertEqual(req['roles'],['grid.main','temperature.air','temperature.bufferTop'])
  self.assertEqual(req['features']['sensor'],['airTemperature','bufferTop','power'])
 def test_safety_stays_required_even_with_automatic_management_disabled(self):
  req=requirements_from_config({'remote_devices':[{'name':'pump','disable_automatic_management':True,'temperature_safety':[{'sensor_name':'water'}]}]})[0]
  self.assertEqual(req['roles'],['temperature.water'])
if __name__=='__main__':unittest.main()
