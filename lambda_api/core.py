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


@dataclass(slots=True)
class InvokeTemplate:
    """
    Specifies the main info about the endpoint function as its parameters, response type etc.
    """

    params: Type[BaseModel] | None
    body: Type[BaseModel] | None
    request: Type[Request] | None
    response: Type[BaseModel] | None
    status: int
    tags: list[str]

    # means that we have a simple type like dict/int/str etc
    user_root_response: bool


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

        self.bake_cors_headers()

    def bake_cors_headers(self):
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

    def get_decorator(self, method, path, **kwargs: Unpack[RouteParams]):
        def decorator(func):
            endpoint = self.route_table[path] = self.route_table.get(path, {})
            endpoint[method] = func

            func_signature = signature(func)
            params = func_signature.parameters
            return_type = func_signature.return_annotation
            user_root_response = False

            if return_type is not _empty and return_type is not None:
                if not isinstance(return_type, type) or not issubclass(
                    return_type, BaseModel
                ):
                    return_type = RootModel[return_type]
                    user_root_response = True
            else:
                return_type = None

            func.__invoke_template__ = InvokeTemplate(
                params=params["params"].annotation if "params" in params else None,
                body=params["body"].annotation if "body" in params else None,
                request=params["request"].annotation if "request" in params else None,
                response=return_type,
                user_root_response=user_root_response,
                status=kwargs.get("status", 200),
                tags=kwargs.get("tags", self.default_tags) or [],
            )

            return func

        return decorator

    def post(self, path, **kwargs: Unpack[RouteParams]):
        return self.get_decorator(Method.POST, path, **kwargs)

    def get(self, path, **kwargs: Unpack[RouteParams]):
        return self.get_decorator(Method.GET, path, **kwargs)

    def put(self, path, **kwargs: Unpack[RouteParams]):
        return self.get_decorator(Method.PUT, path, **kwargs)

    def delete(self, path, **kwargs: Unpack[RouteParams]):
        return self.get_decorator(Method.DELETE, path, **kwargs)

    def patch(self, path, **kwargs: Unpack[RouteParams]):
        return self.get_decorator(Method.PATCH, path, **kwargs)
