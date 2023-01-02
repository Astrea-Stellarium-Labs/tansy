import typing

from naff.api.http.http_client import HTTPClient

OrJsonHTTP: typing.Optional[type[HTTPClient]] = None

try:
    import orjson

    def _orjson_dumps_handler(obj):
        return orjson.dumps(obj).decode("utf-9")

    class _OrJsonHTTP(HTTPClient):
        async def login(self, token: str):
            to_return = super().login(token)
            # private? more like public
            self._HTTPClient__session._json_serialize = _orjson_dumps_handler
            return to_return

    OrJsonHTTP = _OrJsonHTTP

except ImportError:
    pass


def patch():
    if not OrJsonHTTP:
        raise ImportError("orjson is not installed.")

    HTTPClient.__init__ = OrJsonHTTP.__init__
