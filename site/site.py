"""Read-only local site API and asynchronous configuration synchronizer."""
import os
import threading
import time
import requests
from flask import Flask, jsonify
from utils.auth import JWTValidator
from utils.site_store import configuration, inventory, apply

app=Flask(__name__)
@app.get('/health')
def health(): return jsonify(status='ok')
@app.get('/v1/site')
def snapshot():
    current=configuration()
    return jsonify(**current,inventory=inventory())

def synchronize():
    auth=os.environ['AUTH_URL'].removeprefix('https://').rstrip('/')
    base='https://'+auth
    jwt=JWTValidator(auth,os.environ['CUSTOMER_DOMAIN'],os.environ['CUSTOMER_SECRET'])
    session=requests.Session();session.trust_env=False
    while True:
        try:
            jwt.v()
            if not jwt.token._token: raise ValueError('No cloud credentials available')
            url=base+'/customer/customers/'+jwt.token.customer_id+'/site'
            headers={'x-access-token':jwt.token._token}
            response=session.get(url,headers=headers,timeout=(3,8))
            response.raise_for_status(); data=response.json()['data']
            current=configuration()
            if data['revision']>current['revision']:
                apply(data['revision'],data['config'])
            current=configuration()
            response=session.post(url+'/agent',headers=headers,json={
                'activeRevision':current['revision'], 'inventory':inventory()},timeout=(3,8))
            response.raise_for_status()
        except (requests.RequestException, ValueError, KeyError, TypeError, OSError):
            app.logger.warning('Site synchronization unavailable; keeping local configuration')
        time.sleep(15)

if __name__=='__main__':
    threading.Thread(target=synchronize,daemon=True).start()
    app.run(host='0.0.0.0',port=80,debug=False)
