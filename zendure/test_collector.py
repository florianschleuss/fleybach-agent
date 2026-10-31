import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from collector import load_config, read_report, Collector


class CollectorTests(unittest.TestCase):
    def config(self, sources=None, **kwargs):
        data = {'sources': sources if sources is not None else [dict(host='192.168.1.2', expectedSerial='TEST', kind='smart_meter')]}
        data.update(kwargs)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'config.json'
            path.write_text(json.dumps(data))
            return load_config(path)

    def test_optional_sources_and_config_limits(self):
        self.assertEqual(self.config([])['sources'], [])
        self.assertEqual(self.config([{'enabled': False}])['sources'], [])
        for host in ['https://example.com', '8.8.8.8', '127.0.0.1', '169.254.169.254', '0.0.0.0']:
            with self.subTest(host=host), self.assertRaises(ValueError):
                self.config([dict(host=host, expectedSerial='TEST', kind='battery')])
        for override in [{'pollIntervalSeconds': 0}, {'pollIntervalSeconds': True},
                         {'pollIntervalSeconds': 30, 'staleAfterSeconds': 60}]:
            with self.assertRaises(ValueError):
                self.config(**override)

    def session(self, report, status=200):
        session = MagicMock()
        response = session.get.return_value.__enter__.return_value
        response.status_code = status
        response.iter_content.return_value = [json.dumps(report).encode()]
        return session

    def test_reader_only_gets_fixed_read_path_and_checks_identity(self):
        source = self.config()['sources'][0]
        report = dict(timestamp=int(time.time()), deviceId='TEST', total_power=123)
        session = self.session(report)
        _, parsed = read_report(source, 5, session)
        self.assertEqual(parsed['metrics']['grid_power']['value'], 123)
        self.assertEqual(session.get.call_args.args[0], 'http://192.168.1.2/properties/report')
        self.assertFalse(session.get.call_args.kwargs['allow_redirects'])
        session.post.assert_not_called()
        report['deviceId'] = 'OTHER_DEVICE'
        with self.assertRaises(ValueError):
            read_report(source, 5, self.session(report))

    def test_no_redirect_or_oversized_report(self):
        source = self.config()['sources'][0]
        with self.assertRaises(ValueError):
            read_report(source, 5, self.session({}, 302))
        session = self.session({})
        session.get.return_value.__enter__.return_value.iter_content.return_value = [b'x'*60001]
        with self.assertRaises(ValueError):
            read_report(source, 5, session)

    def test_https_only_api_and_authentication_retry(self):
        with self.assertRaises(ValueError):
            Collector(self.config(), 'http://api.example.com', 'domain', 'secret')
        collector = Collector(self.config(), 'https://dev.example.com/api', 'domain', 'secret')
        token = MagicMock(_token='test-token', exp=time.time()+600, customer_id='customer')
        def refresh():
            token.exp = time.time()+600
        collector.auth = MagicMock(token=token)
        collector.auth.v.side_effect = refresh
        session = MagicMock()
        unauthorized = MagicMock(status_code=401)
        accepted = MagicMock(status_code=200)
        accepted.json.return_value = {'data': {'accepted': True}}
        session.post.side_effect = [unauthorized, accepted]
        self.assertTrue(collector.upload(session, {'report': {}})['accepted'])
        self.assertEqual(session.post.call_count, 2)
        self.assertEqual(session.post.call_args.args[0], 'https://dev.example.com/api/sensor/telemetry/zendure')

    def test_source_failure_does_not_upload_fabricated_values(self):
        collector = Collector(self.config(), 'https://api.example.com', 'domain', 'secret')
        collector.upload = MagicMock()
        with patch('collector.read_report', side_effect=ValueError('offline')):
            self.assertFalse(collector.run_source(self.config()['sources'][0], once=True))
        collector.upload.assert_not_called()


if __name__ == '__main__':
    unittest.main()
