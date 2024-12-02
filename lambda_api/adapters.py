import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, NamedTuple

from orjson import JSONDecodeError
from pydantic import BaseModel, ValidationError

from lambda_api.core import InvokeTemplate, LambdaAPI, Response
from lambda_api.error import APIError
from lambda_api.schema import Method
from lambda_api.utils import json_dumps, json_loads

logger = logging.getLogger(__name__)


class ParsedRequest(NamedTuple):
    headers: dict[str, str]
    path: str
    method: Method
    params: dict[str, Any]
    body: dict[str, Any]
    provider_data: dict[str, Any]


class BaseAdapter(ABC):
    @abstractmethod
    def parse_request(self, event: dict[str, Any]) -> ParsedRequest:
        """
        Parse the request data from the provider into a dictionary.
        """

    def format_request(self, request: ParsedRequest | None) -> str:
        """
        Format the request data into a string for logging.
        """
        if not request:
            return "None"

        request_str = f"{request.method} {request.path}"
        if request.params:
            request_str += (
                "?"
                + "&".join(f"{k}={v}" for k, v in request.params.items())
                + f"\nparams: {request.params}"
            )

        if request.body:
            request_str += f"\body: {request.body}"

        if request.headers:
            request_str += f"\nheaders: {request.headers}"
        return request_str

    @abstractmethod
    def prepare_response(self, response: Response) -> Any:
        """
        Prepare the response data to be returned to the provider.
        """

    @abstractmethod
    async def run_endpoint_handler(
        self, func: Callable, request: ParsedRequest
    ) -> Response:
        """
        Run the endpoint handler function.
        """

    @abstractmethod
    def gather_args(self, request: ParsedRequest, template: InvokeTemplate) -> dict:
        """
        Gather the arguments for the endpoint handler function.
        """

    @abstractmethod
    def validate_response(self, result: Any, template: InvokeTemplate) -> Response:
        """
        Validate the response data from the endpoint handler function.
        """


class AWSAdapter(BaseAdapter):
    def __init__(self, app: LambdaAPI):
        self.app = app

    def parse_request(self, event: dict[str, Any]) -> ParsedRequest:
        """
        Parse the AWS Lambda event into a request dictionary.
        """
        path = "/" + event.get("pathParameters", {}).get("proxy", "").strip("/")
        method = Method(event["httpMethod"])

        singular_params = event.get("queryStringParameters") or {}
        params = event.get("multiValueQueryStringParameters") or {}
        params.update(singular_params)

        try:
            body = event.get("body")
            request_body = json_loads(body) if body else {}
        except JSONDecodeError:
            raise APIError("Invalid JSON", status=400)

        headers = event.get("headers") or {}
        headers = {k.lower().replace("-", "_"): v for k, v in headers.items()}

        return ParsedRequest(
            headers=headers,
            path=path,
            method=method,
            params=params,
            body=request_body,
            provider_data=event,
        )

    def prepare_response(self, response: Response):
        """
        Prepare the response to be returned to the AWS Lambda handler.
        """
        return {
            "statusCode": response.status,
            "body": response.body if response.raw else json_dumps(response.body),
            "headers": {
                "Content-Type": "application/json",
                **response.headers,
            },
        }

    async def lambda_handler(
        self, event: dict[str, Any], context: Any = None
    ) -> dict[str, Any]:
        request = None
        try:
            request = self.parse_request(event)

            endpoint = self.app.route_table.get(request.path)
            method = request.method

            match (endpoint, method):
                case (None, _):
                    response = Response(status=404, body={"error": "Not Found"})
                case (_, Method.OPTIONS):
                    response = Response(
                        status=200, body=None, headers=self.app.cors_headers
                    )
                case (_, _) if method in endpoint:
                    response = await self.run_endpoint_handler(
                        endpoint[method], request
                    )
                case _:
                    response = Response(
                        status=405, body={"error": "Method Not Allowed"}
                    )

        except APIError as e:
            response = Response(status=e._status, body={"error": str(e)})
        except ValidationError as e:
            response = Response(status=400, body=f'{{"error": {e.json()}}}', raw=True)
        except Exception as e:
            logger.error(
                f"Unhandled exception.\nREQUEST:\n{self.format_request(request)}\nERROR:",
                exc_info=e,
            )
            response = Response(status=500, body={"error": "Internal Server Error"})

        return self.prepare_response(response)

    async def run_endpoint_handler(
        self, func: Callable, request: ParsedRequest
    ) -> Response:
        template: InvokeTemplate = func.__invoke_template__  # type: ignore

        # this ValidationError is raised when the request data is invalid
        # we can return it to the client
        try:
            args = self.gather_args(request, template)
        except ValidationError as e:
            return Response(status=400, body={"error": e.json()})

        result = await func(**args)

        # this ValidationError is raised when the response data is invalid
        # we can log it and return a generic error to the client to avoid leaking
        try:
            return self.validate_response(result, template)
        except ValidationError as e:
            logger.error(
                f"Response data is invalid.\nREQUEST:\n{self.format_request(request)}\nERROR:",
                exc_info=e,
            )
            return Response(status=500, body={"error": "Internal Server Error"})

    def gather_args(self, request: ParsedRequest, template: InvokeTemplate) -> dict:
        """
        Gather the arguments for the endpoint handler function.
        """
        args = {}

        if template.request:
            args["request"] = template.request.model_validate(request)
        if template.params:
            args["params"] = template.params.model_validate(request.params)
        if template.body:
            args["body"] = template.body.model_validate(request.body)

        return args

    def validate_response(self, result: Any, template: InvokeTemplate) -> Response:
        if template.response:
            model = template.response
            status = template.status

            if isinstance(result, BaseModel):
                response = Response(status, result.model_dump(mode="json"))
            else:
                response = Response(
                    status, model.model_validate(result).model_dump(mode="json")
                )
        else:
            response = Response(status=template.status, body=None)

        return response
