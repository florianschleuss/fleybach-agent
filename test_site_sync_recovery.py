import ast,copy,os,sqlite3,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
import requests
from utils.site_schema import DEFAULT

class StopLoop(BaseException):pass

class SyncRecoveryTests(unittest.TestCase):
    def test_transient_readonly_error_does_not_kill_sync_or_change_revision(self):
        tree=ast.parse(Path('site/site.py').read_text(encoding='utf-8'))
        function=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='synchronize')
        hardware={'schemaVersion':1,'sources':[]}
        state={'revision':4,'config':copy.deepcopy(DEFAULT),'services':{},'hardware':hardware}
        session=Mock();session.get.return_value.json.return_value={'data':state}
        session.post.return_value.json.return_value={'data':{'hardwareTasks':[]}}
        auth=SimpleNamespace(v=Mock(),token=SimpleNamespace(_token='test-only',customer_id='fixture'))
        config=Mock(side_effect=[sqlite3.OperationalError('attempt to write a readonly database'),state,state])
        manager=Mock();manager.outgoing.return_value=[];manager.report.return_value={}
        apply=Mock()
        scope=dict(os=SimpleNamespace(environ={'AUTH_URL':'fixture.invalid','CUSTOMER_DOMAIN':'fixture','CUSTOMER_SECRET':'fixture'}),
                   requests=SimpleNamespace(Session=lambda:session,RequestException=requests.RequestException),JWTValidator=lambda *args:auth,
                   sqlite3=sqlite3,configuration=config,apply=apply,hardware_manager=manager,inventory=lambda:[],app=SimpleNamespace(logger=Mock()),
                   time=SimpleNamespace(sleep=Mock(side_effect=[None,StopLoop()])))
        exec(compile(ast.Module(body=[function],type_ignores=[]),'actual_sync_loop','exec'),scope)
        with self.assertRaises(StopLoop):scope['synchronize']()
        self.assertEqual(session.get.call_count,2);self.assertEqual(session.post.call_count,1)
        self.assertEqual(session.post.call_args.kwargs['json']['activeRevision'],4)
        apply.assert_not_called()

    def test_failed_database_setup_always_closes_connection(self):
        from utils.site_store import database
        connection=Mock();connection.execute.side_effect=sqlite3.OperationalError('temporary failure')
        with patch.dict(os.environ,{'SITE_STATE_PATH':str(Path(os.environ.get('TEMP','/tmp'))/'site-test-no-create.sqlite3')}),patch('utils.site_store.sqlite3.connect',return_value=connection):
            with self.assertRaises(sqlite3.OperationalError):
                with database():pass
        connection.close.assert_called_once()

if __name__=='__main__':unittest.main(verbosity=2)
