# -*- coding: utf-8 -*-

from flask import request, g, abort, jsonify

from . import db


def handle_api_exception(e):
    """
    处理APIException异常
    :param e:
    :return:
    """
    return jsonify(e.to_dict()), e.status_code


def before_app_request():
    """
    请求前全局钩子函数
    :return:
    """
    if not (request.blueprint and request.endpoint):
        abort(404)

    environ = request.environ
    g.ip = environ.get('HTTP_X_FORWARDED_FOR', environ.get('REMOTE_ADDR'))  # g.ip
    db.connect()


def after_app_request(response):
    """
    请求后全局钩子函数
    :param response:
    :return:
    """
    if not db.is_closed():
        db.close()
