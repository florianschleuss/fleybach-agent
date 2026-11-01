"""Legacy sensor API adapter used exclusively by a background worker."""
import time
import requests


class SensorUploader:
    def __init__(self, auth, base):
        self.auth, self.base = auth, 'https://'+base.removeprefix('https://').rstrip('/')
        self.registered = set()
        self.session = requests.Session()
        self.session.trust_env = False

    def upload(self, readings):
        self.auth.v()
        token = self.auth.token
        if not token._token or token.exp <= time.time():
            raise ConnectionError('Cloud authentication unavailable')
        headers = {'x-access-token': token._token}
        params = {'customer_id': token.customer_id}
        fresh = [row for row in readings if 0 <= time.time()-row['sampledAt'] < 60]
        if not fresh:
            return False
        for row in fresh:
            if row['id'] in self.registered:
                continue
            if time.time()-row['sampledAt'] >= 60:
                continue
            response = self.session.patch(self.base+'/sensor/sensors/'+row['id'],
                params=params, headers=headers, json={'value': row['value']}, timeout=(3, 8))
            if response.status_code == 404:
                response = self.session.post(self.base+'/sensor/sensors', params=params,
                    headers=headers, json={key: row[key] for key in ('id','name','value','unit','type')}, timeout=(3, 8))
            if response.status_code == 401:
                token.exp = 0
            response.raise_for_status()
            self.registered.add(row['id'])
        fresh = [row for row in fresh if time.time()-row['sampledAt'] < 60]
        if not fresh:
            return False
        response = self.session.patch(self.base+'/sensor/sensors', params=params, headers=headers,
            json={'sensors': [{'id':row['id'], 'value':row['value'], 'name':row['name']} for row in fresh]}, timeout=(3, 8))
        if response.status_code == 401:
            token.exp = 0
        if response.status_code == 404:
            self.registered.clear()
        response.raise_for_status()
        return True
