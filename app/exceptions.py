# -*- coding: utf-8 -*-


class APIException(Exception):
    """
    API异常
    """
    ERRORS = {
        1000: 'Internal Server Error',
        1100: 'Bad Request',
        1101: 'Unauthorized',
        1103: 'Forbidden',
        1104: 'Not Found',
        1201: u'GET方法url参数不完整',
        1202: u'GET方法url参数值不正确',
        1401: u'POST/PUT方法json数据不完整',
        1402: u'POST/PUT方法json数据值或类型不正确',
        1601: u'DELETE方法url参数不完整',
        1602: u'DELETE方法url参数值不正确'
    }
    status_code = 200

    def __init__(self, code, status_code=None):
        Exception.__init__(self)
        self.code = code
        self.message = self.ERRORS.get(code)
        if status_code is not None:
            self.status_code = status_code

    def to_dict(self):
        """
        转换为dict表示
        :return:
        """
        return {'code': self.code, 'message': self.message, 'data': {}}
