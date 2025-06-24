import logging
from dataclasses import dataclass, field
from inspect import _empty, signature
from typing import Any, Callable, Iterable, Type

from pydantic import BaseModel, RootModel, ValidationError

from lambda_api.base import AbstractRouter, RouteParams
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
            request_str += f"\nbody: {self.body}"

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


@dataclass(slots=True)
class CORSConfig:
    allow_origins: list[str]
    allow_methods: list[str]
    allow_headers: list[str]
    max_age: int = 3000


@dataclass(slots=True)
class RouteWrapper:
    handler: Callable
    config: RouteParams
    invoke_tamplate: InvokeTemplate | None = None


class LambdaAPI(AbstractRouter):
    def __init__(
        self,
        prefix="",
        schema_id: str | None = None,
        cors: CORSConfig | None = None,
        tags: list[str] | None = None,
    ):
        """
        Initialize the LambdaAPI instance.

        Args:
            prefix: Used to generate OpenAPI schema. Doesn't affect the actual path while running.
            schema_id: The id of the schema. Helpful when stitching multiple schemas together.
            cors: Response CORS configuration.
            tags: Tags to add to the endpoint.
        """

        # dict[path, dict[method, function]]
        self.route_table: dict[str, dict[Method, RouteWrapper]] = {}

        self.prefix = prefix
        self.schema_id = schema_id
        self.cors_config = cors
        self.common_response_headers = {}
        self.default_tags = tags or []

        self._bake_headers()

    def _bake_headers(self):
        if self.cors_config:
            self.common_response_headers = {
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
                response = Response(
                    status=200, body=None, headers=self.common_response_headers
                )
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
        self, route: RouteWrapper, request: ParsedRequest
    ) -> Response:
        template = self.get_invoke_template(route)

        # this ValidationError is raised when the request data is invalid
        # we can return it to the client
        try:
            args = template.prepare_method_args(request)
        except ValidationError as e:
            return Response(status=400, body={"error": e.json()})

        result = await route.handler(**args)

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

    def get_invoke_template(self, route: RouteWrapper):
        if route.invoke_tamplate:
            return route.invoke_tamplate

        fn_signature = signature(route.handler)
        params = fn_signature.parameters
        return_type = fn_signature.return_annotation

        if return_type is not _empty and return_type is not None:
            if not isinstance(return_type, type) or not issubclass(
                return_type, BaseModel
            ):
                return_type = RootModel[return_type]
        else:
            return_type = None

        route.invoke_tamplate = InvokeTemplate(  # type: ignore
            params=params["params"].annotation if "params" in params else None,
            body=params["body"].annotation if "body" in params else None,
            request=params["request"].annotation if "request" in params else None,
            response=return_type,
            status=route.config.get("status", 200),
            tags=route.config.get("tags", self.default_tags) or [],
        )
        return route.invoke_tamplate

    def decorate_route(
        self, fn: Callable, path: str, method: Method, config: RouteParams
    ) -> Callable:
        if path not in self.route_table:
            endpoint = self.route_table[path] = {}
        else:
            endpoint = self.route_table[path]

        endpoint[method] = RouteWrapper(handler=fn, config=config)
        return fn

    def get_routes(
        self, root: str = ""
    ) -> Iterable[tuple[Callable, str, Method, RouteParams]]:
        for path, methods in self.route_table.items():
            for method, route in methods.items():
                yield route.handler, path, method, route.config

    def add_router(self, router: AbstractRouter):
        for route_args in router.get_routes(""):
            self.decorate_route(*route_args)
