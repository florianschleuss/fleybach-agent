"""Read-only local site API and asynchronous configuration synchronizer."""
import os
import sqlite3
import threading
import time
import requests
from flask import Flask, jsonify
from utils.auth import JWTValidator
from utils.site_store import configuration, inventory, apply

from utils.hardware_manager import HardwareManager
hardware_manager=HardwareManager()
app=Flask(__name__)
@app.get('/health')
def health(): return jsonify(status='ok')
@app.get('/v1/site')
def snapshot():
    current=configuration()
    from utils.site_catalog import catalog
    return jsonify(**current,inventory=inventory(),definitions=catalog())

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
            hardware={'schemaVersion':1,'sources':data.get('hardware',{}).get('sources',[])}
            if data['revision']>current['revision'] or (data['revision']==current['revision'] and data.get('services')!=current.get('services')) or hardware!=current.get('hardware'):
                apply(data['revision'],data['config'],services=data.get('services'),hardware=hardware)
            current=configuration()
            results=hardware_manager.outgoing()
            payload={'activeRevision':current['revision'], 'inventory':inventory(),'hardwareStatus':hardware_manager.report(),'hardwareResults':results}
            path=os.environ.get('SITE_DEVICE_CONFIG')
            if path:
                try:
                    from utils.site_requirements import read_requirements
                    payload['requirements']=read_requirements(path)
                except Exception:
                    app.logger.warning('Device dependency report unavailable; retaining previous report')
            response=session.post(url+'/agent',headers=headers,json=payload,timeout=(3,8))
            response.raise_for_status()
            hardware_manager.acknowledge(results)
            hardware_manager.queue_tests(response.json()['data'].get('hardwareTasks',[]))
        except (requests.RequestException, ValueError, KeyError, TypeError, OSError, sqlite3.Error, RuntimeError) as exc:
            app.logger.warning('Site synchronization unavailable (%s); keeping local configuration and retrying',type(exc).__name__)
        time.sleep(15)

if __name__=='__main__':
    threading.Thread(target=hardware_manager.run,daemon=True).start()
    threading.Thread(target=synchronize,daemon=True).start()
    app.run(host='0.0.0.0',port=80,debug=False)
