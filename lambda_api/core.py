import logging
from dataclasses import dataclass, field
from inspect import _empty, signature
from typing import Any, Callable, NotRequired, Type, TypedDict, Unpack

from pydantic import BaseModel, RootModel, ValidationError

from lambda_api.error import APIError
from lambda_api.schema import Method, Request

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class Response:
    """
    Internal response type
    """

    status: int
    body: Any
    headers: dict[str, str] = field(default_factory=dict)
    raw: bool = False


@dataclass(slots=True)
class ParsedRequest:
    """
    Internal request type for the adapters
    """

    headers: dict[str, str]
    path: str
    method: Method
    params: dict[str, Any]
    body: dict[str, Any]
    provider_data: dict[str, Any]

    def __repr__(self) -> str:
        return f"Request({self.method} {self.path})"

    def __str__(self) -> str:
        """
        Format the request data into a string for logging.
        """
        request_str = f"{self.method} {self.path}"
        if self.params:
            request_str += (
                "?"
                + "&".join(f"{k}={v}" for k, v in self.params.items())
                + f"\nparams: {self.params}"
            )

        if self.body:
            request_str += f"\body: {self.body}"

        if self.headers:
            request_str += f"\nheaders: {self.headers}"
        return request_str


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

    def prepare_method_args(self, request: ParsedRequest):
        args = {}

        if self.request:
            args["request"] = self.request.model_validate(request)
        if self.params:
            args["params"] = self.params.model_validate(request.params)
        if self.body:
            args["body"] = self.body.model_validate(request.body)

        return args

    def prepare_response(self, result: Any) -> Response:
        if self.response:
            if isinstance(result, BaseModel):
                return Response(self.status, result.model_dump(mode="json"))
            return Response(
                self.status,
                self.response.model_validate(result).model_dump(mode="json"),
            )
        return Response(self.status, body=None)


class RouteParams(TypedDict):
    """
    Additional parameters for the routes. This is a type hint only.
    Don't change to a dataclass.
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
            if path not in self.api.route_table:
                endpoint = self.api.route_table[path] = {}
            else:
                endpoint = self.api.route_table[path]

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

    async def run(self, request: ParsedRequest) -> Response:
        endpoint = self.route_table.get(request.path)
        method = request.method

        match (endpoint, method):
            case (None, _):
                response = Response(status=404, body={"error": "Not Found"})
            case (_, Method.OPTIONS):
                response = Response(status=200, body=None, headers=self.cors_headers)
            case (_, _) if method in endpoint:
                try:
                    response = await self.run_endpoint_handler(
                        endpoint[method], request
                    )
                except APIError as e:
                    response = Response(status=e._status, body={"error": str(e)})
                except ValidationError as e:
                    response = Response(
                        status=400, body=f'{{"error": {e.json()}}}', raw=True
                    )
                except Exception as e:
                    logger.error(
                        f"Unhandled exception.\nREQUEST:\n{request}\nERROR:",
                        exc_info=e,
                    )
                    response = Response(
                        status=500, body={"error": "Internal Server Error"}
                    )
            case _:
                response = Response(status=405, body={"error": "Method Not Allowed"})

        return response

    async def run_endpoint_handler(
        self, func: Callable, request: ParsedRequest
    ) -> Response:
        template: InvokeTemplate = func.__invoke_template__  # type: ignore

        # this ValidationError is raised when the request data is invalid
        # we can return it to the client
        try:
            args = template.prepare_method_args(request)
        except ValidationError as e:
            return Response(status=400, body={"error": e.json()})

        result = await func(**args)

        # this ValidationError is raised when the response data is invalid
        # we can log it and return a generic error to the client to avoid leaking
        try:
            return template.prepare_response(result)
        except ValidationError as e:
            logger.error(
                f"Response data is invalid.\nREQUEST:\n{request}\nERROR:",
                exc_info=e,
            )
            return Response(status=500, body={"error": "Internal Server Error"})
