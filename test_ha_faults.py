"""Execute only reporting methods with mocked HTTP, never load hardware modules."""
import ast,json,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
import requests
from utils.faults import FaultReporter

def method(file,name,reporter):
 tree=ast.parse(Path(file).read_text())
 node=next(n for c in tree.body if isinstance(c,ast.ClassDef) and (name!='_set_hardware_io' or c.name=='HomeAssistantDevice') for n in c.body if isinstance(n,ast.FunctionDef) and n.name==name)
 scope=dict(requests=requests,json=json,ha_faults=reporter,
            HomeAssistantDeviceType=SimpleNamespace(LGWATERHEATER=1,LGHEATPUMP=2))
 exec(compile(ast.Module(body=[node],type_ignores=[]),file,'exec',flags=0x1000000),scope)
 return scope[name]

class Tests(unittest.TestCase):
 def test_setpoint_http_error_timeout_and_recovery(self):
  emit=Mock(return_value=True);reporter=FaultReporter('Home Assistant',emit)
  send=method('utils/switchable/dynamicPowerSwitchable.py','_send_setpoint_to_homeassistant',reporter)
  device=SimpleNamespace(name='heat-pump',ha_base_url='http://ha.invalid',ha_setpoint_webhook='test',ha_token='',heat_pump_return_setpoint=42.5,heat_pump_heat_wait=True)
  with patch.object(requests,'post',return_value=SimpleNamespace(status_code=500,text='private response')) as post:
   send(device);self.assertEqual(emit.call_args.args[0],'HA_SETPOINT');self.assertEqual(emit.call_args.args[2],'fault')
   self.assertNotIn('private response',str(emit.call_args))
   post.return_value.status_code=200;send(device);self.assertEqual(emit.call_args.args[2],'recovered')
   post.side_effect=requests.Timeout('private URL');send(device);self.assertEqual(emit.call_args.args[2],'fault')
   self.assertNotIn('private URL',str(emit.call_args))
 def test_switch_http_status_retains_control_result(self):
  emit=Mock(return_value=True);reporter=FaultReporter('Home Assistant',emit)
  send=method('utils/switchable/powerSwitchable.py','_set_hardware_io',reporter)
  device=SimpleNamespace(name='heat-pump',_device_type=2,_entity_id='test')
  with patch.object(requests,'post',return_value=SimpleNamespace(status_code=503)) as post:
   self.assertFalse(send(device,True));self.assertEqual(emit.call_args.args[2],'fault')
   post.return_value.status_code=200;self.assertTrue(send(device,True));self.assertEqual(emit.call_args.args[2],'recovered')
   post.side_effect=requests.Timeout('private URL');self.assertFalse(send(device,True))

if __name__=='__main__':unittest.main(verbosity=2)
