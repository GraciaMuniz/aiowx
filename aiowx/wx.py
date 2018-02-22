import ssl

import aiohttp

from .auth import AioWxAuth
from .message import AioWxMessage
from .pay import AioWxPay


class AioWx(AioWxAuth, AioWxPay, AioWxMessage):

    def __init__(self, app_id, app_secret, mch_id, key,
                 cert_pem_path=None, key_pem_path=None,
                 timeout=5):
        """
        :param app_id:  open.weixin.qq.com中的AppID
        :param app_secret:  open.weixin.qq.com中的AppSecret
        :param mch_id:  pay.weixin.qq.com中的微信支付商户号
        :param key:     pay.weixin.qq.com中的API安全中的API密钥
        :param cert_pem_path:  pay.weixin.qq.com下载
        :param key_pem_path:   pay.weixin.qq.com下载
        :param timeout: 连接微信网关超时事件，单位秒
        """
        if cert_pem_path and key_pem_path:
            ssl_context = ssl.create_default_context()
            ssl_context.load_cert_chain(cert_pem_path, key_pem_path)
            conn = aiohttp.TCPConnector(limit=1024, ssl_context=ssl_context)
        else:
            conn = aiohttp.TCPConnector(limit=1024)
        self.session = aiohttp.ClientSession(connector=conn,
                                             skip_auto_headers={'Content-Type'})
        self.app_id = app_id
        self.app_secret = app_secret
        self.mch_id = mch_id
        self.key = key
        self.timeout = timeout

    def __del__(self):
        self.session.close()
