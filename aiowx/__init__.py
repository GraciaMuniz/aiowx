import asyncio
import datetime
import hashlib
import json
import random
import ssl
import string
import time
import urllib.parse
import xml.etree.ElementTree as ElementTree

import aiohttp


class AioWx:
    """
    only support md5 sign
    """

    class TimeoutError(Exception):
        pass

    class WxAuthError(Exception):
        pass

    class WxPayError(Exception):
        pass

    class WxError(Exception):
        pass

    host = 'https://api.mch.weixin.qq.com'

    def __init__(self, app_id, mch_id, key, secret, cert_pem_path,
                 key_pem_path, timeout=5):
        if cert_pem_path and key_pem_path:
            ssl_context = ssl.create_default_context()
            ssl_context.load_cert_chain(cert_pem_path, key_pem_path)
            conn = aiohttp.TCPConnector(limit=1024, ssl_context=ssl_context)
        else:
            conn = aiohttp.TCPConnector(limit=1024)
        self.session = aiohttp.ClientSession(connector=conn,
                                             skip_auto_headers={'Content-Type'})
        self.app_id = app_id
        self.mch_id = mch_id
        self.key = key
        self.secret = secret
        self.timeout = timeout

    def sign(self, to_signed):
        keys = sorted(to_signed.keys())
        tmp_list = []
        for key in keys:
            if key == 'sign':
                continue
            value = to_signed[key]
            if not value:
                continue
            tmp_list.append('{}={}'.format(key, value))
        to_hash = '&'.join(tmp_list)
        to_hash += '&key={}'.format(self.key)
        return hashlib.md5(to_hash.encode()).hexdigest().upper()

    alphabet = string.digits + string.ascii_letters

    def gen_nonce(self):
        return ''.join(random.sample(self.alphabet, 32))

    @classmethod
    def _dict_to_xml(cls, d):
        root = ElementTree.Element('xml')
        for k in d:
            v = d[k]
            child = ElementTree.SubElement(root, k)
            child.text = str(v)
        return ElementTree.tostring(root, encoding='unicode')

    @classmethod
    def _xml_to_dict(cls, xml):
        root = ElementTree.fromstring(xml)
        result = {}
        for child in root:
            tag = child.tag
            text = child.text
            result[tag] = text
        return result

    async def _do_post(self, path, params):
        headers = {
            'Content-type': 'application/xml',
        }
        common_params = {
            'appid': self.app_id,
            'mch_id': self.mch_id,
            'nonce_str': self.gen_nonce(),
            'sign_type': 'MD5',
        }
        common_params.update(params)
        common_params['sign'] = self.sign(common_params)

        url = urllib.parse.urljoin(self.host, path)
        body = self._dict_to_xml(common_params)

        try:
            with aiohttp.Timeout(self.timeout):
                async with self.session.post(url, headers=headers,
                                             data=body) as resp:
                    if resp.status != 200:
                        raise self.WxPayError()
                    body = await resp.text(encoding='utf-8')
        except asyncio.TimeoutError:
            raise self.TimeoutError()

        return self.parse_response(body)

    def _is_sign_valid(self, data):
        if 'sign' not in data:
            return False
        sign = self.sign(data)
        if sign != data['sign']:
            return False
        return True

    def parse_response(self, resp):
        resp_dict = self._xml_to_dict(resp)
        return_code = resp_dict.get('return_code')
        if not return_code:
            raise self.WxPayError('no return_code in response: {}'.format(resp))
        if return_code == 'FAIL':
            raise self.WxPayError('wxpay fail: {}'.format(resp))
        if not self._is_sign_valid(resp_dict):
            raise self.WxPayError('sign error, {}'.format(resp))
        return resp_dict

    async def unifiedorder(self, out_trade_no, total_fee, body,
                           notify_url, spbill_create_ip, time_expire,
                           trade_type='MWEB', device_info='WEB',
                           fee_type='CNY', **kwargs):
        path = '/pay/unifiedorder'
        if isinstance(time_expire, datetime.datetime):
            time_expire = time_expire.strftime('%Y%m%d%H%M%S')
        params = {
            'out_trade_no': out_trade_no,
            'total_fee': total_fee,
            'body': body,
            'notify_url': notify_url,
            'spbill_create_ip': spbill_create_ip,
            'time_expire': time_expire,
            'trade_type': trade_type,
            'device_info': device_info,
            'fee_type': fee_type,
        }
        params.update(**kwargs)
        return await self._do_post(path, params)

    async def orderquery(self, out_trade_no=None, transaction_id=None,
                         **kwargs):
        if out_trade_no and transaction_id:
            raise self.WxPayError('out_trade_no or transaction_id, '
                                  'only choose one')
        path = '/pay/orderquery'
        params = {}
        if out_trade_no:
            params['out_trade_no'] = out_trade_no
        if transaction_id:
            params['transaction_id'] = transaction_id
        params.update(**kwargs)
        return await self._do_post(path, params)

    async def jsapi_order_params(self, out_trade_no, total_fee, body,
                                 notify_url, spbill_create_ip, time_expire,
                                 open_id, **kwargs):
        result = await self.unifiedorder(
            out_trade_no=out_trade_no, total_fee=total_fee, body=body,
            notify_url=notify_url, time_expire=time_expire,
            spbill_create_ip=spbill_create_ip, trade_type='JSAPI',
            openid=open_id,
            **kwargs,
        )
        prepay_id = result.get('prepay_id')
        param = {
            'appId': self.app_id,
            'timeStamp': int(time.time()),
            'nonceStr': self.gen_nonce(),
            'package': 'prepay_id={}'.format(prepay_id),
            'signType': 'MD5',
        }
        sign = self.sign(param)
        param['paySign'] = sign
        return param

    async def get_access_token(self):
        url = 'https://api.weixin.qq.com/cgi-bin/token''' \
              '?grant_type=client_credential&appid={}&secret={}'.format(
                self.app_id, self.secret)
        try:
            with aiohttp.Timeout(self.timeout):
                async with self.session.get(url) as resp:
                    if resp.status != 200:
                        raise self.WxAuthError()
                    body = await resp.text(encoding='utf-8')
                    json_body = json.loads(body)
                    return json_body.get('access_token')
        except asyncio.TimeoutError:
            raise self.TimeoutError()

    async def get_jsapi_ticket(self, access_token):
        url = 'https://api.weixin.qq.com/cgi-bin/ticket/getticket' \
              '?access_token={}&type=jsapi'.format(access_token)
        try:
            with aiohttp.Timeout(self.timeout):
                async with self.session.get(url) as resp:
                    if resp.status != 200:
                        raise self.WxAuthError()
                    body = await resp.text(encoding='utf-8')
                    json_body = json.loads(body)
                    return json_body.get('ticket')
        except asyncio.TimeoutError:
            raise self.TimeoutError()

    def sign_js_sdk(self, to_signed):
        keys = sorted(to_signed.keys())
        tmp_list = []
        for key in keys:
            if key == 'sign':
                continue
            value = to_signed[key]
            if not value:
                continue
            tmp_list.append('{}={}'.format(key, value))
        to_hash = '&'.join(tmp_list)
        print(to_hash)
        return hashlib.sha1(to_hash.encode()).hexdigest()

    def jsapi_init_param(self, ticket, url):
        to_signed = {
            'noncestr': self.gen_nonce(),
            'jsapi_ticket': ticket,
            'timestamp': int(time.time()),
            'url': url,
        }
        sign = self.sign_js_sdk(to_signed)
        to_signed['signature'] = sign
        to_signed['appid'] = self.app_id
        return to_signed

    async def oauth2(self, code):
        params = {
            'appid': self.app_id,
            'secret': self.secret,
            'code': code,
            'grant_type': 'authorization_code',
        }

        WX_ACCESS_TOKEN_URL = \
            'https://api.weixin.qq.com/sns/oauth2/access_token?' \
            'appid={appid}&secret={secret}&code={code}&' \
            'grant_type={grant_type}'.format(**params)

        try:
            with aiohttp.Timeout(self.timeout):
                async with self.session.get(WX_ACCESS_TOKEN_URL,
                                            params=params) as resp:
                    if resp.status != 200:
                        raise self.WxAuthError()
                    resp_text = await resp.text()
                    result = json.loads(resp_text)
                    if 'errcode' in result:
                        raise self.WxAuthError('AuthenticationFailed')

                    access_token = result.get('access_token')
                    open_id = result.get('openid')
                    union_id = result.get('unionid')
                    return access_token, open_id, union_id
        except asyncio.TimeoutError:
            raise self.TimeoutError()

    async def template_send(self, access_token, open_id, template_id,
                            template_params, redirect_url='',
                            topcolor='#FF0000'):
        url = 'https://api.weixin.qq.com/cgi-bin/message/template/send' \
              '?access_token={}'.format(access_token)
        data = {
            'touser': open_id,
            'template_id': template_id,
            'url': redirect_url,
            'topcolor': topcolor,
            'data': template_params,
        }

        try:
            with aiohttp.Timeout(self.timeout):
                async with self.session.post(url, json=data) as resp:
                    if resp.status != 200:
                        raise self.WxAuthError()
                    body = await resp.text(encoding='utf-8')
                    json_body = json.loads(body)
                    errcode = json_body.get('errcode')
                    if errcode > 0:
                        raise self.WxError(json.dumps(json_body))
                    return {'msgid': json_body.get('msgid')}
        except asyncio.TimeoutError:
            raise self.TimeoutError()

    def __del__(self):
        self.session.close()
