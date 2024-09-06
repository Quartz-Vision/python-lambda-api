from dataclasses import dataclass
from inspect import _empty, signature
from typing import Any, Callable, NamedTuple, NotRequired, Type, TypedDict, Unpack

from pydantic import BaseModel, RootModel

from lambda_api.schema import Method, Request


class Response(NamedTuple):
    """
    Internal response type
    """

    status: int
    body: Any
    headers: dict[str, str] = {}
    raw: bool = False


class InvokeTemplate(NamedTuple):
    """
    Specifies the main info about the endpoint function as its parameters, response type etc.
    """

    params: Type[BaseModel] | None
    body: Type[BaseModel] | None
    request: Type[Request] | None
    response: Type[BaseModel] | None
    status: int
    tags: list[str]


class RouteParams(TypedDict):
    """
    Additional parameters for the routes
    """

    status: NotRequired[int]
    tags: NotRequired[list[str] | None]


@dataclass(slots=True)
class CORSConfig:
    allow_origins: list[str]
    allow_methods: list[str]
    allow_headers: list[str]
    max_age: int = 3000


class LambdaAPI:
    class MethodDecorator:
        __slots__ = ("api", "method")

        def __init__(
            self,
            api: "LambdaAPI",
            method: Method,
        ):
            self.api = api
            self.method = method

        def decorate(self, func, path: str, config: RouteParams):
            endpoint = self.api.route_table[path] = self.api.route_table.get(path, {})
            endpoint[self.method] = func

            func_signature = signature(func)
            params = func_signature.parameters
            return_type = func_signature.return_annotation

            if return_type is not _empty and return_type is not None:
                if not isinstance(return_type, type) or not issubclass(
                    return_type, BaseModel
                ):
                    return_type = RootModel[return_type]
            else:
                return_type = None

            func.__invoke_template__ = InvokeTemplate(
                params=params["params"].annotation if "params" in params else None,
                body=params["body"].annotation if "body" in params else None,
                request=params["request"].annotation if "request" in params else None,
                response=return_type,
                status=config.get("status", 200),
                tags=config.get("tags", self.api.default_tags) or [],
            )

            return func

        def __call__(self, path: str, **config: Unpack[RouteParams]):
            return lambda fn: self.decorate(fn, path, config)

    def __init__(
        self,
        prefix="",
        schema_id: str | None = None,
        cors: CORSConfig | None = None,
        tags: list[str] | None = None,
    ):
        # dict[path, dict[method, function]]
        self.route_table: dict[str, dict[str, Callable]] = {}

        self.prefix = prefix
        self.schema_id = schema_id
        self.cors_config = cors
        self.cors_headers = {}
        self.default_tags = tags or []

        self._bake_cors_headers()

        self.post = self.MethodDecorator(self, Method.POST)
        self.get = self.MethodDecorator(self, Method.GET)
        self.put = self.MethodDecorator(self, Method.PUT)
        self.delete = self.MethodDecorator(self, Method.DELETE)
        self.patch = self.MethodDecorator(self, Method.PATCH)

    def _bake_cors_headers(self):
        if self.cors_config:
            self.cors_headers = {
                "Access-Control-Allow-Origin": ",".join(self.cors_config.allow_origins),
                "Access-Control-Allow-Methods": ",".join(
                    self.cors_config.allow_methods
                ),
                "Access-Control-Allow-Headers": ",".join(
                    self.cors_config.allow_headers
                ),
                "Access-Control-Max-Age": str(self.cors_config.max_age),
            }
