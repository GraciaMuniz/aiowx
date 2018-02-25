import asyncio
import datetime
import time
import urllib.parse

from .exception import (
    AioWxTimeoutError,
    AioWxPayError,
)
from .util import (
    gen_sign,
    gen_nonce,
    dict_to_xml,
    xml_to_dict,
)


class AioWxPay:

    WXPAY_HOST = 'https://api.mch.weixin.qq.com'

    async def _do_pay_post(self, path, params):
        headers = {
            'Content-type': 'application/xml',
        }
        common_params = {
            'appid': self.app_id,
            'mch_id': self.mch_id,
            'nonce_str': gen_nonce(),
            'sign_type': 'MD5',
        }
        common_params.update(params)
        common_params['sign'] = gen_sign(common_params, self.key)

        url = urllib.parse.urljoin(self.WXPAY_HOST, path)
        body = dict_to_xml(common_params)

        try:
            async with self.session.post(url, headers=headers, data=body,
                                         timeout=self.timeout) as resp:
                if resp.status != 200:
                    raise AioWxPayError()
                body = await resp.text(encoding='utf-8')
        except asyncio.TimeoutError:
            raise AioWxTimeoutError()

        return self.parse_response(body)

    def _is_sign_valid(self, data):
        if 'sign' not in data:
            return False
        sign = gen_sign(data, self.key)
        if sign != data['sign']:
            return False
        return True

    def parse_response(self, resp):
        resp_dict = xml_to_dict(resp)
        return_code = resp_dict.get('return_code')
        if not return_code:
            raise AioWxPayError('no return_code in response: {}'.format(resp))
        if return_code == 'FAIL':
            raise AioWxPayError('wxpay fail: {}'.format(resp))
        if not self._is_sign_valid(resp_dict):
            raise AioWxPayError('sign error, {}'.format(resp))
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
        return await self._do_pay_post(path, params)

    async def orderquery(self, out_trade_no=None, transaction_id=None,
                         **kwargs):
        if out_trade_no and transaction_id:
            raise AioWxPayError('out_trade_no or transaction_id, '
                                'only choose one')
        path = '/pay/orderquery'
        params = {}
        if out_trade_no:
            params['out_trade_no'] = out_trade_no
        if transaction_id:
            params['transaction_id'] = transaction_id
        params.update(**kwargs)
        return await self._do_pay_post(path, params)

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
            'nonceStr': gen_nonce(),
            'package': 'prepay_id={}'.format(prepay_id),
            'signType': 'MD5',
        }
        param['paySign'] = gen_sign(param, self.key)
        return param

    async def app_order_params(self, out_trade_no, total_fee, body,
                               notify_url, spbill_create_ip, time_expire,
                               **kwargs):
        result = await self.unifiedorder(
            out_trade_no=out_trade_no, total_fee=total_fee, body=body,
            notify_url=notify_url, time_expire=time_expire,
            spbill_create_ip=spbill_create_ip, trade_type='APP',
            **kwargs,
        )
        prepay_id = result.get('prepay_id')
        now = int(time.time())
        nonce = gen_nonce()
        to_sign_param = {
            'appid': self.app_id,
            'partnerid': self.mch_id,
            'prepayid': prepay_id,
            'package': 'Sign=WXPay',
            'noncestr': nonce,
            'timestamp': now,
        }
        sign = gen_sign(to_sign_param, self.key)
        param = {
            'partnerId': self.mch_id,
            'prepayId': prepay_id,
            'package': 'Sign=WXPay',
            'nonceStr': nonce,
            'timeStamp': now,
            'sign': sign,
        }
        return param
