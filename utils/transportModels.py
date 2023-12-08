
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
            'data': from_dict_to_json(self.data),
            'message': self.message,
            'errorCode': self.error_code,
            'statusCode': self.status_code
        }


def from_dict_to_json(input_dict):
    """
    Convert keys from snake_case to camelCase in a nested dictionary.

    :param input_dict: The input dictionary.

    :return: The dictionary with keys in camelCase.
    """
    if isinstance(input_dict, dict):
        camel_case_dict = {}
        for key, value in input_dict.items():
            camel_case_key = _snake_case_to_camel_case(key)
            camel_case_value = from_dict_to_json(value)
            camel_case_dict[camel_case_key] = camel_case_value
        return camel_case_dict
    elif isinstance(input_dict, list):
        return [from_dict_to_json(item) for item in input_dict]
    else:
        return input_dict


def _snake_case_to_camel_case(snake_case_str):
    """
    Convert a snake_case string to camelCase.

    :param snake_case_str: The input snake_case string.

    :return: The string converted to camelCase.
    """
    words = snake_case_str.split('_')
    return words[0] + ''.join(word.title() for word in words[1:])
