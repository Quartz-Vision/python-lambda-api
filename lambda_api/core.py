import json
from collections import defaultdict
from dataclasses import dataclass
from inspect import _empty, signature
from typing import Any, Callable, NamedTuple, NotRequired, Type, TypedDict, Unpack

from pydantic import BaseModel, RootModel, ValidationError

from lambda_api.error import APIError
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
    Specifies the main info aboud an endpoint function as its parameters, response type etc.
    """

    params: Type[BaseModel] | None
    body: Type[BaseModel] | None
    request: Type[Request] | None
    response: Type[BaseModel] | None
    status: int
    user_root_response: bool


class RouteParams(TypedDict):
    """
    Additional parameters for the routes
    """

    status: NotRequired[int]


@dataclass(slots=True)
class CORSConfig:
    allow_origins: list[str]
    allow_methods: list[str]
    allow_headers: list[str]
    max_age: int = 3000


class LambdaAPI:
    def __init__(
        self, prefix="", schema_id: str | None = None, cors: CORSConfig | None = None
    ):
        self.route_table: dict[str, dict[str, Callable]] = {}
        self.prefix = prefix
        self.schema_id = schema_id
        self.cors_config = cors
        self.cors_headers = {}

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

    def aws_get_request(self, event: dict[str, Any]) -> dict[str, Any]:
        path = "/" + event.get("pathParameters", {}).get("proxy", "").strip("/")
        method = event["httpMethod"]

        singular_params = event.get("queryStringParameters") or {}
        params = event.get("multiValueQueryStringParameters") or {}
        params.update(singular_params)

        try:
            body = event.get("body")
            request_body = json.loads(body) if body else {}
        except json.JSONDecodeError:
            raise APIError("Invalid JSON", status=400)

        headers = event.get("headers") or {}
        headers = {k.lower().replace("-", "_"): v for k, v in headers.items()}

        return {
            "headers": headers,
            "path": path,
            "method": method,
            "params": params,
            "body": request_body,
            "provider_data": event,
        }

    async def aws_lambda_handler(self, event: dict[str, Any], context: Any = None):
        try:
            request = self.aws_get_request(event)

            endpoint = self.route_table.get(request["path"])
            method = request["method"]
            func = None

            if endpoint:
                if method == Method.OPTIONS:
                    response = Response(
                        status=200, body=None, headers=self.cors_headers
                    )
                else:
                    func = endpoint.get(method)
                    if not func:
                        response = Response(
                            status=405, body={"error": "Method Not Allowed"}
                        )
            else:
                response = Response(status=404, body={"error": "Not Found"})

            if func:
                template: InvokeTemplate = func.__invoke_template__  # type: ignore
                args = {}

                if template.request:
                    args["request"] = template.request(**request)
                if template.params:
                    args["params"] = template.params(**request["params"])
                if template.body:
                    args["body"] = template.body(**request["body"])

                result = await func(**args)
                if template.response:
                    model = template.response
                    status = template.status

                    if isinstance(result, BaseModel):
                        response = Response(status, result.model_dump(mode="json"))
                    elif template.user_root_response:
                        response = Response(
                            status, model(result).model_dump(mode="json")
                        )
                    else:
                        response = Response(
                            status, model(**result).model_dump(mode="json")
                        )
                else:
                    response = Response(status=template.status, body=None)

        except APIError as e:
            response = Response(status=e.status, body={"error": str(e)})
        except ValidationError as e:
            response = Response(status=400, body={"error": e.errors()})
        except Exception as e:
            response = Response(status=500, body={"error": str(e)})

        return {
            "statusCode": response.status,
            "body": json.dumps(response.body),
            "headers": {
                "Content-Type": "application/json",
                **response.headers,
            },
        }

    def get_schema(self):
        schema = {
            "paths": defaultdict(lambda: defaultdict(dict)),
            "components": {"schemas": {}},
        }

        if self.schema_id:
            schema["id"] = self.schema_id

        for path, endpoint in self.route_table.items():
            for method, func in endpoint.items():
                self.add_endpoint_to_schema(schema, path, method, func)

        txt_schema = json.dumps(schema).replace("$defs", "components/schemas")
        return json.loads(txt_schema)

    def add_endpoint_to_schema(
        self, schema: dict[str, Any], path: str, method: str, func: Callable
    ):
        components = schema["components"]["schemas"]

        template: InvokeTemplate = func.__invoke_template__  # type: ignore
        full_path = self.prefix + path
        func_schema = schema["paths"][full_path][method.lower()]

        if func.__doc__:
            func_schema["summary"] = func.__doc__

        if template.request:
            # Handle headers
            headers = (
                template.request.model_fields["headers"].annotation
            ).model_json_schema()
            required_keys = headers.get("required", [])

            func_schema["parameters"] = func_schema.get("parameters", []) + [
                {
                    "in": "header",
                    "name": k.replace("_", "-").title(),
                    "schema": v,
                }
                | ({"required": True} if k in required_keys else {})
                for k, v in headers["properties"].items()
            ]

            # Handle the request config
            config = template.request.request_config
            if config:
                if auth_name := config.get("auth_name"):
                    func_schema["security"] = [{auth_name: []}]

        # Handle QUERY parameters
        if template.params:
            params = template.params.model_json_schema()
            required_keys = params.get("required", [])

            components.update(params.pop("$defs", {}))

            func_schema["parameters"] = func_schema.get("parameters", []) + [
                {"in": "query", "name": k, "schema": v}
                | ({"required": True} if k in required_keys else {})
                for k, v in params["properties"].items()
            ]

        # Handle BODY parameters
        if template.body:
            body = template.body.model_json_schema()
            comp_title = body["title"]

            components[comp_title] = body
            components.update(body.pop("$defs", {}))

            func_schema["requestBody"] = {
                "content": {
                    "application/json": {
                        "schema": {"$ref": f"#/components/schemas/{comp_title}"}
                    }
                }
            }

        # Handle response schema
        if template.response:
            response = template.response.model_json_schema()
            comp_title = response["title"]

            components[comp_title] = response
            components.update(response.pop("$defs", {}))

            func_schema["responses"] = {
                str(template.status): {
                    "content": {
                        "application/json": {
                            "schema": {"$ref": f"#/components/schemas/{comp_title}"}
                        }
                    }
                }
            }
