"""Independent optional Zendure reader. Never issues device control requests."""
import argparse
import concurrent.futures
import ipaddress
import json
import logging
import os
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

from utils.auth import JWTValidator
from utils.zendure import normalize, identifier

log = logging.getLogger('zendure')


def load_config(path):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data, dict) or not isinstance(data.get('sources'), list):
        raise ValueError('Config requires a sources list')
    interval = data.get('pollIntervalSeconds', 10)
    timeout = data.get('requestTimeoutSeconds', 5)
    stale = data.get('staleAfterSeconds', 60)
    for value, low, high in [(interval, 5, 300), (timeout, 1, 15), (stale, 30, 900)]:
        if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
            raise ValueError('Invalid interval, timeout or stale threshold')
    if stale < 3*interval:
        raise ValueError('staleAfterSeconds must cover at least three poll intervals')
    sources, seen = [], set()
    for entry in data['sources']:
        if not isinstance(entry, dict) or not isinstance(entry.get('enabled', True), bool):
            raise ValueError('Invalid source configuration')
        if not entry.get('enabled', True):
            continue
        address = ipaddress.ip_address(entry.get('host', ''))
        if address.version != 4 or not address.is_private or address.is_loopback or address.is_link_local or address.is_unspecified or address.is_multicast:
            raise ValueError('Source host must be a private LAN IPv4 address')
        # is_private includes reserved ranges on some Python versions: require RFC1918.
        if not any(address in ipaddress.ip_network(n) for n in ['10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16']):
            raise ValueError('Source host must be RFC1918')
        expected = identifier(entry.get('expectedSerial'))
        if expected in seen:
            raise ValueError('Duplicate source identifier')
        seen.add(expected)
        kind = entry.get('kind')
        if kind not in ('battery', 'smart_meter'):
            raise ValueError('Source kind must be battery or smart_meter')
        label = entry.get('label', expected)
        if not isinstance(label, str) or not 1 <= len(label) <= 120:
            raise ValueError('Invalid label')
        sources.append(dict(host=str(address), expectedSerial=expected, kind=kind, label=label))
    if len(sources) > 32:
        raise ValueError('At most 32 enabled sources are supported')
    return dict(sources=sources, interval=interval, timeout=timeout, stale=stale)


def read_report(source, timeout, session):
    # The URL is derived from a validated LAN IP and a fixed read-only path.
    with session.get('http://'+source['host']+'/properties/report',
                     timeout=(timeout, timeout), allow_redirects=False, stream=True) as response:
        response.raise_for_status()
        if response.status_code != 200:
            raise ValueError('Device did not return HTTP 200')
        body = bytearray()
        for chunk in response.iter_content(chunk_size=4096):
            body.extend(chunk)
            if len(body) > 60000:
                raise ValueError('Device report too large')
    report = json.loads(body)
    parsed = normalize(report)
    if parsed['serial'] != source['expectedSerial'] or parsed['kind'] != source['kind']:
        raise ValueError('Device identity/type differs from configured source')
    return report, parsed


class Collector:
    def __init__(self, config, base_url, domain, secret):
        parsed = urlparse(base_url)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('AUTH_URL must be an HTTPS API origin (optional /api path)')
        if parsed.path not in ('', '/', '/api', '/api/'):
            raise ValueError('Unsupported API base path')
        # Existing shared JWTValidator expects a scheme-less host plus base path.
        auth_host = parsed.netloc + parsed.path.rstrip('/')
        self.auth = JWTValidator(auth_host, domain, secret)
        self.base_url = base_url.rstrip('/')
        self.config = config
        self.auth_lock = threading.Lock()

    def upload(self, session, payload):
        # Shared customer login/token renewal, also serialize explicit 401 refresh.
        for attempt in range(2):
            with self.auth_lock:
                self.auth.v()
                token = self.auth.token
                if not token._token or token.exp <= time.time():
                    raise ValueError('Customer authentication unavailable')
                headers = {'x-access-token': token._token}
                customer_id = token.customer_id
            response = session.post(self.base_url+'/sensor/telemetry/zendure',
                                    params={'customer_id': customer_id}, json=payload,
                                    headers=headers, timeout=(5, 15), allow_redirects=False)
            if response.status_code == 401 and attempt == 0:
                with self.auth_lock:
                    self.auth.token.exp = 0
                continue
            response.raise_for_status()
            if response.status_code != 200:
                raise ValueError('Unexpected telemetry response')
            result = response.json()['data']
            if not isinstance(result, dict) or 'accepted' not in result:
                raise ValueError('Invalid telemetry acknowledgement')
            return result
        raise ValueError('Customer authentication rejected')

    def run_source(self, source, once=False):
        session = requests.Session()
        session.trust_env = False
        last_success = 0
        failed = False
        while True:
            start = time.monotonic()
            try:
                report, parsed = read_report(source, self.config['timeout'], session)
                result = self.upload(session, {'report': report, 'label': source['label'],
                                              'staleAfterSeconds': self.config['stale']})
                if failed or time.monotonic()-last_success >= 300 or once:
                    log.info('%s: %s, %d metrics, accepted=%s', source['label'], parsed['model'],
                             len(parsed['metrics']), result['accepted'])
                    last_success = time.monotonic()
                failed = False
            except (requests.RequestException, ValueError, KeyError, TypeError):
                # Never log URLs, response bodies or credentials; failures leave old
                # timestamps untouched so backend freshness correctly expires.
                log.warning('%s: read/upload failed; will retry', source['label'])
                failed = True
                if once:
                    return False
            if once:
                return True
            time.sleep(max(0.1, self.config['interval']-(time.monotonic()-start)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default=os.environ.get('ZENDURE_CONFIG', '/config/zendure.json'))
    parser.add_argument('--once', action='store_true', help='Read and upload one sample per enabled source')
    parser.add_argument('--check', action='store_true', help='Validate config and read devices, without login/upload')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    config = load_config(args.config)
    if args.check:
        session = requests.Session()
        session.trust_env = False
        for source in config['sources']:
            _, parsed = read_report(source, config['timeout'], session)
            print(json.dumps(parsed))
        return
    if not config['sources']:
        log.info('No enabled Zendure sources; exiting')
        return
    base = os.environ.get('AUTH_URL', '')
    if '://' not in base:
        base = 'https://'+base
    collector = Collector(config, base, os.environ['CUSTOMER_DOMAIN'], os.environ['CUSTOMER_SECRET'])
    # A blocked/offline device does not delay other sources or existing services.
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(config['sources'])) as executor:
        results = list(executor.map(lambda s: collector.run_source(s, args.once), config['sources']))
    if args.once and not all(results):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
