import asyncio
import hashlib
import json
import time

from .exception import (
    AioWxTimeoutError,
    AioWxAuthError,
)
from .util import (
    gen_nonce,
    gen_sign_sha1,
)


class AioWxAuth:

    async def _do_auth_get(self, url):
        try:
            async with self.session.get(url, timeout=self.timeout) as resp:
                if resp.status != 200:
                    raise AioWxAuthError()
                body = await resp.text(encoding='utf-8')
                json_body = json.loads(body)
                errcode = json_body.get('errcode')
                if errcode and errcode > 0:
                    raise AioWxAuthError(json.dumps(json_body))
                return json_body
        except asyncio.TimeoutError:
            raise AioWxTimeoutError()

    async def get_access_token(self):
        url = 'https://api.weixin.qq.com/cgi-bin/token' \
              '?grant_type=client_credential&appid={}&secret={}'.format(
                self.app_id, self.app_secret)
        json_body = await self._do_auth_get(url)
        return json_body.get('access_token')

    async def get_jsapi_ticket(self, access_token):
        url = 'https://api.weixin.qq.com/cgi-bin/ticket/getticket' \
              '?access_token={}&type=jsapi'.format(access_token)
        json_body = await self._do_auth_get(url)
        return json_body.get('ticket')

    def jsapi_init_param(self, ticket, url):
        to_signed = {
            'noncestr': gen_nonce(),
            'jsapi_ticket': ticket,
            'timestamp': int(time.time()),
            'url': url,
        }
        sign = gen_sign_sha1(to_signed)
        to_signed['signature'] = sign
        to_signed['appid'] = self.app_id
        return to_signed

    async def oauth2(self, code):
        params = {
            'appid': self.app_id,
            'secret': self.app_secret,
            'code': code,
            'grant_type': 'authorization_code',
        }

        wx_access_token_url = \
            'https://api.weixin.qq.com/sns/oauth2/access_token?' \
            'appid={appid}&secret={secret}&code={code}&' \
            'grant_type={grant_type}'.format(**params)

        try:
            async with self.session.get(wx_access_token_url, params=params,
                                        timeout=self.timeout) as resp:
                if resp.status != 200:
                    raise AioWxAuthError()
                resp_text = await resp.text()
                result = json.loads(resp_text)
                if 'errcode' in result:
                    raise AioWxAuthError('AuthenticationFailed')

                access_token = result.get('access_token')
                open_id = result.get('openid')
                union_id = result.get('unionid')
                return access_token, open_id, union_id
        except asyncio.TimeoutError:
            raise AioWxTimeoutError()
