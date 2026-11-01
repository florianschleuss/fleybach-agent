"""Exercise actual controller read functions without importing GPIO/device startup."""
import ast,os,tempfile,time,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from utils.site_store import publish
class ControllerReads(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.env=patch.dict(os.environ,{'SITE_STATE_PATH':str(Path(self.tmp.name)/'site.db')});self.env.start()
  module=ast.parse(Path('device/device.py').read_text(encoding='utf-8'))
  functions=[n for n in module.body if isinstance(n,ast.FunctionDef) and n.name in ('get_power_consumption','get_temperatures')]
  self.request=Mock();self.jwt=Mock();self.ns=dict(os=os,time=time,Dict=dict,local_power_component=True,local_temperature_component=True,requests=self.request,jwt=self.jwt,AUTH_URL='unused',faults=Mock())
  exec(compile(ast.Module(body=functions,type_ignores=[]),'device/device.py','exec'),self.ns)
 def tearDown(self):self.env.stop();self.tmp.cleanup()
 def test_local_matches_legacy_inputs_without_network(self):
  now=time.time();publish('power:total','total','W',-123,now,'power');publish('temperature:air','air','°C',15,now,'temperature')
  response=Mock(status_code=200);response.json.return_value={'sensors':{'total':-123}}
  self.request.get.return_value=response
  with patch.dict(os.environ,{'SITE_LOCAL_CONTROL':'0'}):old_power=self.ns['get_power_consumption']()
  response.json.return_value={'data':[{'name':'air','value':15,'lastModified':now}]}
  with patch.dict(os.environ,{'SITE_LOCAL_CONTROL':'0'}):old_temperatures=self.ns['get_temperatures']()
  self.request.get.side_effect=AssertionError('Cloud/network forbidden')
  self.jwt.v.side_effect=AssertionError('Cloud JWT forbidden')
  with patch.dict(os.environ,{'SITE_LOCAL_CONTROL':'1'}):
   self.assertEqual(self.ns['get_power_consumption'](),old_power)
   self.assertEqual(self.ns['get_temperatures'](),old_temperatures)
 def test_missing_power_blocks_without_cloud_fallback(self):
  self.request.get.side_effect=AssertionError('Unexpected fallback')
  with patch.dict(os.environ,{'SITE_LOCAL_CONTROL':'1'}):
   with self.assertRaises(ConnectionError):self.ns['get_power_consumption']()
if __name__=='__main__':unittest.main()
