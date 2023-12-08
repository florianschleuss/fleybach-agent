
from typing import Dict


class ReturnObject:
    def __init__(self, data=None, message=None, error_code=None, status_code=None) -> None:
        self.data = data
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        return

    def to_dict(self) -> Dict:
        return {
            'data': self.data,
            'message': self.message,
            'errorCode': self.error_code,
            'statusCode': self.status_code
        }
