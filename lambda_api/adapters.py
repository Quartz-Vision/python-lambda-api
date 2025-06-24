from abc import ABC, abstractmethod
from typing import Any

from orjson import JSONDecodeError

from lambda_api.app import LambdaAPI, ParsedRequest, Response
from lambda_api.schema import Method
from lambda_api.utils import json_decode_error_fragment, json_dumps, json_loads


class BaseAdapter(ABC):
    @abstractmethod
    def __init__(self, app: LambdaAPI): ...

    @abstractmethod
    def parse_request(self, event: dict[str, Any]) -> ParsedRequest:
        """
        Parse the request data from the provider into a dictionary.
        """

    @abstractmethod
    def prepare_response(self, response: Response) -> Any:
        """
        Prepare the response data to be returned to the provider.
        """

    @abstractmethod
    async def run(self, *args, **kwargs) -> Any:
        """
        Run the adapter with the given request data.
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

        body = event.get("body")
        request_body = json_loads(body) if body else {}

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

    async def run(self, event: dict[str, Any], context: Any = None) -> dict[str, Any]:
        request = None
        try:
            request = self.parse_request(event)
        except JSONDecodeError as e:
            return self.prepare_response(
                Response(
                    status=400,
                    body={"error": "Invalid JSON:\n" + json_decode_error_fragment(e)},
                )
            )

        return self.prepare_response(await self.app.run(request))
