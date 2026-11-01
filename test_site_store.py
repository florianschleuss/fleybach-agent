import copy,os,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from utils.site_store import publish,inventory,configuration,apply,role_value,temperatures
from utils.site_schema import DEFAULT,validate
class SiteTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.env=patch.dict(os.environ,{'SITE_STATE_PATH':str(Path(self.tmp.name)/'site.db')});self.env.start()
 def tearDown(self):self.env.stop();self.tmp.cleanup()
 def source(self,name='total',unit='W',value=123,source='power',stamp=None):
  publish(source+':'+name,name,unit,value,time.time() if stamp is None else stamp,source)
 def test_identity_and_freshness(self):
  self.source();self.source(value=321);self.assertEqual(len(inventory()),1);self.assertEqual(inventory()[0]['value'],321)
  self.source('unknown',stamp=0);self.assertEqual(inventory()[1]['quality'],'unavailable')
 def test_stale_rejected(self):
  self.source(stamp=time.time()-100)
  with self.assertRaises(ConnectionError):role_value('grid.main','total','power')
 def test_binding_conversion_persistence(self):
  self.source();self.source('other',value=-400,source='zendure')
  cfg=copy.deepcopy(DEFAULT);cfg['bindings']={'grid.main':'zendure:other'};cfg['measurements']={'zendure:other':{'scale':-1,'offset':5}}
  apply(1,cfg);self.assertEqual(configuration()['revision'],1);self.assertEqual(role_value('grid.main','total','power'),405)
  self.assertEqual(inventory()[1]['rawValue'],-400)
  with self.assertRaises(ValueError):apply(0,cfg)
 def test_bad_unit_missing_source(self):
  self.source('air','°C',15,'temperature');cfg=copy.deepcopy(DEFAULT);cfg['bindings']={'grid.main':'temperature:air'}
  with self.assertRaises(ValueError):apply(1,cfg)
  cfg['bindings']={'grid.main':'missing'}
  with self.assertRaises(ValueError):apply(1,cfg)
  self.assertEqual(configuration()['revision'],0)
 def test_temperature_alias_disabled(self):
  self.source('air','°C',15,'temperature');self.source('outside','°C',16,'temperature')
  cfg=copy.deepcopy(DEFAULT);cfg['bindings']={'temperature.air':'temperature:outside'};cfg['measurements']={'temperature:outside':{'enabled':False}}
  apply(1,cfg);self.assertNotIn('air',temperatures())
 def test_cloud_independent(self):
  with patch('socket.socket',side_effect=AssertionError('network forbidden')):
   self.source();self.assertEqual(role_value('grid.main','total','power'),123)
 def test_nan_not_published(self):
  self.source(value=float('nan'));self.assertEqual(inventory(),[])
 def test_secrets_and_zero_factor_rejected(self):
  self.source();cfg=copy.deepcopy(DEFAULT);cfg['secret']='bad'
  with self.assertRaises(ValueError):validate(cfg,inventory())
  cfg.pop('secret');cfg['measurements']={'power:total':{'scale':0}}
  with self.assertRaises(ValueError):apply(1,cfg)
 def test_customer_cache_cannot_cross_sites(self):
  with patch.dict(os.environ,{'CUSTOMER_DOMAIN':'one.example.com'}):self.source()
  with patch.dict(os.environ,{'CUSTOMER_DOMAIN':'two.example.com'}):
   with self.assertRaises(RuntimeError):configuration()
if __name__=='__main__':unittest.main()
