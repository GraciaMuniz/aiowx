import asyncio
import json

from .exception import (
    AioWxTimeoutError,
    AioWxMessageError,
)


class AioWxMessage:

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
            async with self._session.post(url, json=data,
                                          timeout=self.timeout) as resp:
                if resp.status != 200:
                    raise AioWxMessageError()
                body = await resp.text(encoding='utf-8')
                json_body = json.loads(body)
                errcode = json_body.get('errcode')
                if errcode > 0:
                    raise AioWxMessageError(json.dumps(json_body))
                return {'msgid': json_body.get('msgid')}
        except asyncio.TimeoutError:
            raise AioWxTimeoutError()
