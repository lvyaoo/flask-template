# -*- coding: utf-8 -*-

import datetime

from flask import current_app
from peewee import *
from playhouse.shortcuts import model_to_dict
from werkzeug.security import generate_password_hash, check_password_hash

from . import db
from .constants import DEFAULT_PER_PAGE
from utils.key_util import generate_random_key


_to_set = (lambda r: set(r) if r else set())
_nullable_strip = (lambda s: s.strip() or None if s else None)


class BaseModel(Model):
    """
    所有model的基类
    """
    id = PrimaryKeyField()  # 主键
    create_time = DateTimeField(default=datetime.datetime.now)  # 创建时间
    update_time = DateTimeField(default=datetime.datetime.now)  # 更新时间
    weight = IntegerField(default=0)  # 排序权重

    class Meta:
        database = db
        only_save_dirty = True

    @classmethod
    def _exclude_fields(cls):
        """
        转换为dict表示时排除在外的字段
        :return:
        """
        return {'create_time', 'update_time'}

    @classmethod
    def _extra_attributes(cls):
        """
        转换为dict表示时额外增加的属性
        :return:
        """
        return {'iso_create_time', 'iso_update_time'}

    @classmethod
    def query_by_id(cls, _id):
        """
        根据id查询
        :param _id:
        :return:
        """
        obj = None
        try:
            obj = cls.get(cls.id == _id)
        finally:
            return obj

    @classmethod
    def count(cls, select_query=None):
        """
        根据查询条件计数
        :param select_query: [SelectQuery or None]
        :return:
        """
        cnt = 0
        try:
            if select_query is None:
                select_query = cls.select()
            cnt = select_query.count()
        finally:
            return cnt

    @classmethod
    def iterator(cls, select_query=None, order_by=None, page=None, per_page=None):
        """
        根据查询条件返回迭代器
        :param select_query: [SelectQuery or None]
        :param order_by: [iterable or None]
        :param page:
        :param per_page:
        :return:
        """
        try:
            if select_query is None:
                select_query = cls.select()

            if order_by:
                _fields = cls._meta.fields
                clauses = []
                for item in order_by:
                    desc, attr = item.startswith('-'), item.lstrip('+-')
                    if attr in cls._exclude_fields():
                        continue
                    if attr in cls._extra_attributes():
                        attr = attr.split('_', 1)[-1]
                    if attr in _fields:
                        clauses.append(_fields[attr].desc() if desc else _fields[attr])
                if clauses:
                    select_query = select_query.order_by(*clauses)

            if page or per_page:
                select_query = select_query.paginate(int(page or 1), int(per_page or DEFAULT_PER_PAGE))

            return select_query.naive().iterator()

        except Exception, e:
            current_app.logger.error(e)
            return iter([])

    def to_dict(self, only=None, exclude=None, recurse=False, backrefs=False, max_depth=None):
        """
        转换为dict表示
        :param only: [iterable or None]
        :param exclude: [iterable or None]
        :param recurse: [bool]
        :param backrefs: [bool]
        :param max_depth:
        :return:
        """
        try:
            only = _to_set(only)
            exclude = _to_set(exclude) | self._exclude_fields()

            _fields = self._meta.fields
            only_fields = {_fields[k] for k in only if k in _fields}
            exclude_fields = {_fields[k] for k in exclude if k in _fields}
            extra_attrs = self._extra_attributes() - exclude
            if only:
                extra_attrs &= only
                if not only_fields:
                    exclude_fields = _fields.values()

            return model_to_dict(self, recurse=recurse, backrefs=backrefs, only=only_fields, exclude=exclude_fields,
                                 extra_attrs=extra_attrs, max_depth=max_depth)

        except Exception, e:
            current_app.logger.error(e)
            return {}

    def modified_fields(self, exclude=None):
        """
        与数据库中对应的数据相比，数值有变动的字段名称列表
        :param exclude: [iterable or None]
        :return:
        """
        try:
            exclude = _to_set(exclude)
            db_obj = self.query_by_id(self.id)
            return filter(lambda f: getattr(self, f) != getattr(db_obj, f) and f not in exclude,
                          self._meta.sorted_field_names)

        except Exception, e:
            current_app.logger.error(e)

    def change_weight(self, weight):
        """
        修改排序权重
        :param weight:
        :return:
        """
        try:
            self.weight = weight
            self.save()
            return self

        except Exception, e:
            current_app.logger.error(e)

    def iso_create_time(self):
        return self.create_time.isoformat()

    def iso_update_time(self):
        return self.update_time.isoformat()


class Admin(BaseModel):
    """
    管理员
    """
    name = CharField(max_length=32, unique=True)  # 用户名
    password = CharField()  # 密码
    phone = CharField(null=True)  # 手机号码
    openid = CharField(null=True)  # 微信服务号openid
    last_login = DateTimeField(null=True)  # 最近登录时间
    last_ip = CharField(null=True)  # 最近登录IP
    authority = BigIntegerField(default=0)  # 权限

    class Meta:
        db_table = 'admin'

    @classmethod
    def _exclude_fields(cls):
        return BaseModel._exclude_fields() | {'password', 'last_login'}

    @classmethod
    def _extra_attributes(cls):
        return BaseModel._extra_attributes() | {'iso_last_login'}

    @classmethod
    def query_by_name(cls, name):
        """
        根据用户名查询
        :param name:
        :return:
        """
        admin = None
        try:
            admin = cls.get(cls.name == name)
        finally:
            return admin

    @classmethod
    def create_admin(cls, name, password, phone=None, openid=None, authority=0):
        """
        创建管理员
        :param name:
        :param password:
        :param phone:
        :param openid:
        :param authority:
        :return:
        """
        try:
            return cls.create(
                name=name.strip(),
                password=generate_password_hash(password),
                phone=_nullable_strip(phone),
                openid=_nullable_strip(openid),
                authority=authority
            )

        except Exception, e:
            current_app.logger.error(e)

    def check_password(self, password):
        """
        核对密码
        :param password:
        :return:
        """
        return check_password_hash(self.password, password)

    def change_password(self, password):
        """
        修改密码
        :param password:
        :return:
        """
        try:
            self.password = generate_password_hash(password)
            self.update_time = datetime.datetime.now()
            self.save()
            return self

        except Exception, e:
            current_app.logger.error(e)

    def login(self, ip):
        """
        登录
        :param ip:
        :return:
        """
        try:
            self.last_login = datetime.datetime.now()
            self.last_ip = ip
            self.save()
            return self

        except Exception, e:
            current_app.logger.error(e)

    def iso_last_login(self):
        return self.last_login.isoformat() if self.last_login else None


class WeixinUser(BaseModel):
    """
    微信用户
    """
    openid = CharField()
    unionid = CharField(null=True)
    nickname = CharField(null=True)
    sex = IntegerField(null=True)
    country = CharField(null=True)
    province = CharField(null=True)
    city = CharField(null=True)
    headimgurl = CharField(null=True)
    subscribe = IntegerField(null=True)
    subscribe_time = IntegerField(null=True)
    language = CharField(null=True)
    remark = CharField(null=True)
    groupid = IntegerField(null=True)
    tagid_list = TextField(null=True)

    class Meta:
        db_table = 'weixin_user'

    @classmethod
    def _exclude_fields(cls):
        return BaseModel._exclude_fields() | {'tagid_list'}

    @classmethod
    def _extra_attributes(cls):
        return BaseModel._extra_attributes() | {'array_tagid_list'}

    @classmethod
    def query_by_openid(cls, openid):
        """
        根据openid查询
        :param openid:
        :return:
        """
        weixin_user = None
        try:
            weixin_user = cls.get(cls.openid == openid)
        finally:
            return weixin_user

    @classmethod
    def create_weixin_user(cls, openid, unionid=None, nickname=None, sex=None, country=None, province=None, city=None,
                           headimgurl=None, subscribe=None, subscribe_time=None, language=None, remark=None,
                           groupid=None, tagid_list=None, **kwargs):
        """
        创建微信用户
        :param openid:
        :param unionid:
        :param nickname:
        :param sex:
        :param country:
        :param province:
        :param city:
        :param headimgurl:
        :param subscribe:
        :param subscribe_time:
        :param language:
        :param remark:
        :param groupid:
        :param tagid_list: [iterable or None]
        :param kwargs:
        :return:
        """
        try:
            return cls.create(
                openid=openid.strip(),
                unionid=_nullable_strip(unionid),
                nickname=_nullable_strip(nickname),
                sex=sex,
                country=_nullable_strip(country),
                province=_nullable_strip(province),
                city=_nullable_strip(city),
                headimgurl=_nullable_strip(headimgurl),
                subscribe=subscribe,
                subscribe_time=subscribe_time,
                language=_nullable_strip(language),
                remark=_nullable_strip(remark),
                groupid=groupid,
                tagid_list=','.join(map(str, tagid_list)) if tagid_list else None
            )

        except Exception, e:
            current_app.logger.error(e)

    def update_weixin_user(self, subscribe, unionid=None, nickname=None, sex=None, country=None, province=None,
                           city=None, headimgurl=None, subscribe_time=None, language=None, remark=None, groupid=None,
                           tagid_list=None, **kwargs):
        """
        更新微信用户
        :param subscribe:
        :param unionid:
        :param nickname:
        :param sex:
        :param country:
        :param province:
        :param city:
        :param headimgurl:
        :param subscribe_time:
        :param language:
        :param remark:
        :param groupid:
        :param tagid_list: [iterable or None]
        :param kwargs:
        :return:
        """
        try:
            self.subscribe = subscribe
            if subscribe:
                self.unionid = _nullable_strip(unionid)
                self.nickname = _nullable_strip(nickname)
                self.sex = sex
                self.country = _nullable_strip(country)
                self.province = _nullable_strip(province)
                self.city = _nullable_strip(city)
                self.headimgurl = _nullable_strip(headimgurl)
                self.subscribe_time = subscribe_time
                self.language = _nullable_strip(language)
                self.remark = _nullable_strip(remark)
                self.groupid = groupid
                self.tagid_list = ','.join(map(str, tagid_list)) if tagid_list else None
            if self.modified_fields():
                self.update_time = datetime.datetime.now()
                self.save()
            return self

        except Exception, e:
            current_app.logger.error(e)

    def array_tagid_list(self):
        return map(int, self.tagid_list.split(',')) if self.tagid_list else []


class WeixinPayOrder(BaseModel):
    """
    微信支付订单
    """
    TRADE_TYPE_CHOICES = (
        ('JSAPI', u'公众号支付'),
        ('NATIVE', u'原生扫码支付'),
        ('APP', u'APP支付'),
        ('MICROPAY', u'刷卡支付')
    )
    body = CharField()
    out_trade_no = CharField(max_length=32, unique=True)
    total_fee = IntegerField()
    spbill_create_ip = CharField()
    trade_type = CharField(choices=TRADE_TYPE_CHOICES)
    device_info = CharField(null=True)
    detail = TextField(null=True)
    attach = CharField(null=True)
    fee_type = CharField(null=True)
    time_start = CharField(null=True)
    time_expire = CharField(null=True)
    goods_tag = CharField(null=True)
    product_id = CharField(null=True)
    limit_pay = CharField(null=True)
    openid = CharField(null=True)
    auth_code = CharField(null=True)

    order_result = TextField(null=True)  # 统一下单/提交刷卡支付响应结果
    order_result_code = CharField(null=True)
    prepay_id = CharField(null=True)
    code_url = CharField(null=True)
    transaction_id = CharField(null=True)

    notify_result = TextField(null=True)  # 支付结果通知（统一下单）
    notify_result_code = CharField(null=True)

    query_result = TextField(null=True)  # 查询订单响应结果
    query_result_code = CharField(null=True)
    trade_state = CharField(null=True)
    trade_state_desc = CharField(null=True)

    cancel_result = TextField(null=True)  # 关闭/撤销订单响应结果
    cancel_result_code = CharField(null=True)
    recall = CharField(null=True)

    class Meta:
        db_table = 'weixin_pay_order'

    @classmethod
    def _exclude_fields(cls):
        return BaseModel._exclude_fields() | {'order_result', 'notify_result', 'query_result', 'cancel_result'}

    @classmethod
    def _extra_attributes(cls):
        return BaseModel._extra_attributes() | {'dict_order_result', 'dict_notify_result', 'dict_query_result',
                                                'dict_cancel_result'}

    @classmethod
    def query_by_out_trade_no(cls, out_trade_no):
        """
        根据out_trade_no查询
        :param out_trade_no:
        :return:
        """
        order = None
        try:
            order = cls.get(cls.out_trade_no == out_trade_no)
        finally:
            return order

    @classmethod
    def create_weixin_pay_order(cls, body, total_fee, spbill_create_ip, trade_type, device_info=None, detail=None,
                                attach=None, fee_type=None, time_start=None, time_expire=None, goods_tag=None,
                                product_id=None, limit_pay=None, openid=None, auth_code=None):
        """
        创建微信支付订单
        :param body:
        :param total_fee:
        :param spbill_create_ip:
        :param trade_type:
        :param device_info:
        :param detail:
        :param attach:
        :param fee_type:
        :param time_start:
        :param time_expire:
        :param goods_tag:
        :param product_id:
        :param limit_pay:
        :param openid:
        :param auth_code:
        :return:
        """
        try:
            return cls.create(
                body=body.strip(),
                out_trade_no=generate_random_key(24, datetime.date.today().strftime('%Y%m%d'), 'd'),
                total_fee=total_fee,
                spbill_create_ip=spbill_create_ip.strip(),
                trade_type=trade_type.strip(),
                device_info=_nullable_strip(device_info),
                detail=_nullable_strip(detail),
                attach=_nullable_strip(attach),
                fee_type=_nullable_strip(fee_type),
                time_start=_nullable_strip(time_start),
                time_expire=_nullable_strip(time_expire),
                goods_tag=_nullable_strip(goods_tag),
                product_id=_nullable_strip(product_id),
                limit_pay=_nullable_strip(limit_pay),
                openid=_nullable_strip(openid),
                auth_code=_nullable_strip(auth_code)
            )

        except Exception, e:
            current_app.logger.error(e)

    def update_order_result(self, result):
        """
        更新统一下单/提交刷卡支付响应结果
        :param result: [dict]
        :return:
        """
        try:
            self.order_result = repr(result) if result else None
            self.order_result_code = result.get('result_code')
            if self.order_result_code == 'SUCCESS':
                self.prepay_id = _nullable_strip(result.get('prepay_id'))
                self.code_url = _nullable_strip(result.get('code_url'))
                self.transaction_id = _nullable_strip(result.get('transaction_id'))
            self.update_time = datetime.datetime.now()
            self.save()
            return self

        except Exception, e:
            current_app.logger.error(e)

    def update_notify_result(self, result):
        """
        更新支付结果通知（统一下单）
        :param result: [dict]
        :return:
        """
        try:
            self.notify_result = repr(result) if result else None
            self.notify_result_code = result.get('result_code')
            self.transaction_id = result.get('transaction_id')
            self.update_time = datetime.datetime.now()
            self.save()
            return self

        except Exception, e:
            current_app.logger.error(e)

    def update_query_result(self, result):
        """
        更新查询订单响应结果
        :param result: [dict]
        :return:
        """
        try:
            self.query_result = repr(result) if result else None
            self.query_result_code = result.get('result_code')
            if self.query_result_code == 'SUCCESS':
                self.transaction_id = _nullable_strip(result.get('transaction_id'))
                self.trade_state = _nullable_strip(result.get('trade_state'))
                self.trade_state_desc = _nullable_strip(result.get('trade_state_desc'))
            self.update_time = datetime.datetime.now()
            self.save()
            return self

        except Exception, e:
            current_app.logger.error(e)

    def update_cancel_result(self, result):
        """
        更新关闭/撤销订单响应结果
        :param result: [dict]
        :return:
        """
        try:
            self.cancel_result = repr(result) if result else None
            self.cancel_result_code = result.get('result_code')
            self.recall = result.get('recall')
            self.update_time = datetime.datetime.now()
            self.save()
            return self

        except Exception, e:
            current_app.logger.error(e)

    def dict_order_result(self):
        return eval(self.order_result) if self.order_result else {}

    def dict_notify_result(self):
        return eval(self.notify_result) if self.notify_result else {}

    def dict_query_result(self):
        return eval(self.query_result) if self.query_result else {}

    def dict_cancel_result(self):
        return eval(self.cancel_result) if self.cancel_result else {}


class WeixinPayRefund(BaseModel):
    """
    微信支付退款
    """
    weixin_pay_order = ForeignKeyField(WeixinPayOrder, on_delete='CASCADE')
    out_refund_no = CharField(max_length=32, unique=True)
    refund_fee = IntegerField()
    op_user_id = CharField()
    refund_fee_type = CharField(null=True)
    refund_account = CharField(null=True)

    refund_result = TextField(null=True)  # 申请退款响应结果
    refund_result_code = CharField(null=True)
    refund_id = CharField(null=True)

    query_result = TextField(null=True)  # 查询退款响应结果
    query_result_code = CharField(null=True)
    refund_status = CharField(null=True)

    class Meta:
        db_table = 'weixin_pay_refund'

    @classmethod
    def _exclude_fields(cls):
        return BaseModel._exclude_fields() | {'refund_result', 'query_result'}

    @classmethod
    def _extra_attributes(cls):
        return BaseModel._extra_attributes() | {'dict_refund_result', 'dict_query_result'}

    @classmethod
    def query_by_out_refund_no(cls, out_refund_no):
        """
        根据out_refund_no查询
        :param out_refund_no:
        :return:
        """
        refund = None
        try:
            refund = cls.get(cls.out_refund_no == out_refund_no)
        finally:
            return refund

    @classmethod
    def create_weixin_pay_refund(cls, weixin_pay_order, refund_fee, op_user_id, refund_fee_type=None,
                                 refund_account=None):
        """
        创建微信支付退款
        :param weixin_pay_order:
        :param refund_fee:
        :param op_user_id:
        :param refund_fee_type:
        :param refund_account:
        :return:
        """
        try:
            return cls.create(
                weixin_pay_order=weixin_pay_order,
                out_refund_no=generate_random_key(28, weixin_pay_order.out_trade_no, 'd'),
                refund_fee=refund_fee,
                op_user_id=op_user_id.strip(),
                refund_fee_type=_nullable_strip(refund_fee_type),
                refund_account=_nullable_strip(refund_account)
            )

        except Exception, e:
            current_app.logger.error(e)

    def update_refund_result(self, result):
        """
        更新申请退款响应结果
        :param result: [dict]
        :return:
        """
        try:
            self.refund_result = repr(result) if result else None
            self.refund_result_code = result.get('result_code')
            self.refund_id = result.get('refund_id')
            self.update_time = datetime.datetime.now()
            self.save()
            return self

        except Exception, e:
            current_app.logger.error(e)

    def update_query_result(self, result):
        """
        更新查询退款响应结果
        :param result: [dict]
        :return:
        """
        try:
            index = result.keys()[result.values().index(self.out_refund_no)].split('_')[-1]
            self.query_result = repr(result) if result else None
            self.query_result_code = result.get('result_code')
            self.refund_status = result.get('refund_status_%s' % index)
            self.update_time = datetime.datetime.now()
            self.save()
            return self

        except Exception, e:
            current_app.logger.error(e)

    def dict_refund_result(self):
        return eval(self.refund_result) if self.refund_result else {}

    def dict_query_result(self):
        return eval(self.query_result) if self.query_result else {}


class WeixinMchPay(BaseModel):
    """
    微信支付企业付款
    """
    CHECK_NAME_CHOICES = (
        ('NO_CHECK', u'不校验真实姓名'),
        ('FORCE_CHECK', u'强校验真实姓名'),
        ('OPTION_CHECK', u'针对已实名认证的用户才校验真实姓名')
    )
    partner_trade_no = CharField(max_length=32, unique=True)
    openid = CharField()
    check_name = CharField(choices=CHECK_NAME_CHOICES)
    amount = IntegerField()
    desc = CharField()
    spbill_create_ip = CharField()
    device_info = CharField(null=True)
    re_user_name = CharField(null=True)

    pay_result = TextField(null=True)  # 企业付款响应结果
    pay_result_code = CharField(null=True)
    payment_no = CharField(null=True)

    query_result = TextField(null=True)  # 查询企业付款响应结果
    query_result_code = CharField(null=True)
    status = CharField(null=True)

    class Meta:
        db_table = 'weixin_mch_pay'

    @classmethod
    def _exclude_fields(cls):
        return BaseModel._exclude_fields() | {'pay_result', 'query_result'}

    @classmethod
    def _extra_attributes(cls):
        return BaseModel._extra_attributes() | {'dict_pay_result', 'dict_query_result'}

    @classmethod
    def query_by_partner_trade_no(cls, partner_trade_no):
        """
        根据partner_trade_no查询
        :param partner_trade_no:
        :return:
        """
        pay = None
        try:
            pay = cls.get(cls.partner_trade_no == partner_trade_no)
        finally:
            return pay

    @classmethod
    def create_weixin_mch_pay(cls, openid, check_name, amount, desc, spbill_create_ip, device_info=None,
                              re_user_name=None):
        """
        创建微信支付企业付款
        :param openid:
        :param check_name:
        :param amount:
        :param desc:
        :param spbill_create_ip:
        :param device_info:
        :param re_user_name:
        :return:
        """
        try:
            return cls.create(
                partner_trade_no=generate_random_key(28, current_app.config['WEIXIN'].get('mch_id')
                                                     + datetime.date.today().strftime('%Y%m%d'), 'd'),
                openid=openid.strip(),
                check_name=check_name.strip(),
                amount=amount,
                desc=desc.strip(),
                spbill_create_ip=spbill_create_ip.strip(),
                device_info=_nullable_strip(device_info),
                re_user_name=_nullable_strip(re_user_name)
            )

        except Exception, e:
            current_app.logger.error(e)

    def update_pay_result(self, result):
        """
        更新企业付款响应结果
        :param result: [dict]
        :return:
        """
        try:
            self.pay_result = repr(result) if result else None
            self.pay_result_code = result.get('result_code')
            if self.pay_result_code == 'SUCCESS':
                self.payment_no = _nullable_strip(result.get('payment_no'))
            self.update_time = datetime.datetime.now()
            self.save()
            return self

        except Exception, e:
            current_app.logger.error(e)

    def update_query_result(self, result):
        """
        更新查询企业付款响应结果
        :param result: [dict]
        :return:
        """
        try:
            self.query_result = repr(result) if result else None
            self.query_result_code = result.get('result_code')
            if self.query_result_code == 'SUCCESS':
                self.payment_no = _nullable_strip(result.get('detail_id'))
                self.status = _nullable_strip(result.get('status'))
            self.update_time = datetime.datetime.now()
            self.save()
            return self

        except Exception, e:
            current_app.logger.error(e)

    def dict_pay_result(self):
        return eval(self.pay_result) if self.pay_result else {}

    def dict_query_result(self):
        return eval(self.query_result) if self.query_result else {}


class WeixinRedPack(BaseModel):
    """
    微信支付现金红包
    """
    mch_billno = CharField(max_length=32, unique=True)
    send_name = CharField()
    re_openid = CharField()
    total_amount = IntegerField()
    total_num = IntegerField()
    wishing = CharField()
    act_name = CharField()
    remark = CharField()
    amt_type = CharField(null=True)
    client_ip = CharField(null=True)
    scene_id = CharField(null=True)
    risk_info = CharField(null=True)
    consume_mch_id = CharField(null=True)

    send_result = TextField(null=True)  # 发放红包响应结果
    send_result_code = CharField(null=True)
    send_listid = CharField(null=True)

    query_result = TextField(null=True)  # 查询红包记录响应结果
    query_result_code = CharField(null=True)
    status = CharField(null=True)

    class Meta:
        db_table = 'weixin_red_pack'

    @classmethod
    def _exclude_fields(cls):
        return BaseModel._exclude_fields() | {'send_result', 'query_result'}

    @classmethod
    def _extra_attributes(cls):
        return BaseModel._extra_attributes() | {'dict_send_result', 'dict_query_result'}

    @classmethod
    def query_by_mch_billno(cls, mch_billno):
        """
        根据mch_billno查询
        :param mch_billno:
        :return:
        """
        pack = None
        try:
            pack = cls.get(cls.mch_billno == mch_billno)
        finally:
            return pack

    @classmethod
    def create_weixin_red_pack(cls, send_name, re_openid, total_amount, total_num, wishing, act_name, remark,
                               amt_type=None, client_ip=None, scene_id=None, risk_info=None, consume_mch_id=None):
        """
        创建微信支付现金红包
        :param send_name:
        :param re_openid:
        :param total_amount:
        :param total_num:
        :param wishing:
        :param act_name:
        :param remark:
        :param amt_type:
        :param client_ip:
        :param scene_id:
        :param risk_info:
        :param consume_mch_id:
        :return:
        """
        try:
            return cls.create(
                mch_billno=generate_random_key(28, current_app.config['WEIXIN'].get('mch_id')
                                               + datetime.date.today().strftime('%Y%m%d'), 'd'),
                send_name=send_name.strip(),
                re_openid=re_openid.strip(),
                total_amount=total_amount,
                total_num=total_num,
                wishing=wishing.strip(),
                act_name=act_name.strip(),
                remark=remark.strip(),
                amt_type=_nullable_strip(amt_type),
                client_ip=_nullable_strip(client_ip),
                scene_id=_nullable_strip(scene_id),
                risk_info=_nullable_strip(risk_info),
                consume_mch_id=_nullable_strip(consume_mch_id)
            )

        except Exception, e:
            current_app.logger.error(e)

    def update_send_result(self, result):
        """
        更新发放红包响应结果
        :param result: [dict]
        :return:
        """
        try:
            self.send_result = repr(result) if result else None
            self.send_result_code = result.get('result_code')
            if self.send_result_code == 'SUCCESS':
                self.send_listid = _nullable_strip(result.get('send_listid'))
            self.update_time = datetime.datetime.now()
            self.save()
            return self

        except Exception, e:
            current_app.logger.error(e)

    def update_query_result(self, result):
        """
        更新查询红包记录响应结果
        :param result: [dict]
        :return:
        """
        try:
            self.query_result = repr(result) if result else None
            self.query_result_code = result.get('result_code')
            if self.query_result_code == 'SUCCESS':
                self.send_listid = _nullable_strip(result.get('detail_id'))
                self.status = _nullable_strip(result.get('status'))
            self.update_time = datetime.datetime.now()
            self.save()
            return self

        except Exception, e:
            current_app.logger.error(e)

    def dict_send_result(self):
        return eval(self.send_result) if self.send_result else {}

    def dict_query_result(self):
        return eval(self.query_result) if self.query_result else {}


class User(BaseModel):
    """
    用户
    """
    class Meta:
        db_table = 'user'


models = [Admin]
