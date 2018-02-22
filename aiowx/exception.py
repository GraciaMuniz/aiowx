
class AioWxError(Exception):
    pass


class AioWxTimeoutError(AioWxError):
    pass


class AioWxAuthError(AioWxError):
    pass


class AioWxPayError(AioWxError):
    pass


class AioWxMessageError(AioWxError):
    pass
