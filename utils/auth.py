from datetime import datetime
from functools import wraps
from typing import Union

import requests as r
import jwt


class Token:
    def __init__(self, encoded_token, exp=None):
        if exp is None:
            data = jwt.decode(encoded_token, options={
                              "verify_signature": False})
        self.sub = data['sub'] if exp is None else ""
        self.iss = data['iss']if exp is None else ""
        self.exp = data['exp'] if exp is None else exp
        self.aud = data['aud']if exp is None else ""
        self.role = data['role']if exp is None else ""
        self.customer_id = self.sub.replace('cid:', '')if exp is None else ""
        self._token = encoded_token if exp is None else ""

    def _get_cid(self):
        return self.sub.replace('cid:', '')

    def _set_cid(self, customer_id):
        return

    customer_id = property(_get_cid, _set_cid)

    def __iter__(self):
        return iter({
            'sub': self.sub,
            'iss': self.iss,
            'exp': self.exp,
            'aud': self.aud,
            'role': self.role
        }.items())


def get_jwt(auth_url: str, domain: str, secret: str) -> Union[Token, None]:
    try:
        jwt = r.post(f'http://{auth_url}/customer/login', json={
            "domain": domain,
            "secret": secret
        })
        return Token(jwt.json().get('data'))
    except r.exceptions.ConnectionError:
        return None


class JWTValidator:
    def __init__(self, auth_url: str, domain: str, secret: str):
        self.auth_url = auth_url
        self.domain = domain
        self.secret = secret
        self.token = Token(None, exp=0)

    def v(self):
        if self.token.exp < datetime.now().timestamp():
            self.token = get_jwt(self.auth_url, self.domain, self.secret)
            return
