import json
from typing import Any, Callable

from pydantic import BaseModel, ValidationError

from lambda_api.core import InvokeTemplate, LambdaAPI, Response
from lambda_api.error import APIError
from lambda_api.schema import Method


class AWSAdapter:
    def __init__(self, app: LambdaAPI):
        self.app = app

    def request(self, event: dict[str, Any]) -> dict[str, Any]:
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

    def response(self, response: Response):
        return {
            "statusCode": response.status,
            "body": json.dumps(response.body),
            "headers": {
                "Content-Type": "application/json",
                **response.headers,
            },
        }

    async def lambda_handler(self, event: dict[str, Any], context: Any = None):
        try:
            request = self.request(event)

            endpoint = self.app.route_table.get(request["path"])
            method = request["method"]

            if endpoint:
                if method == Method.OPTIONS:
                    response = Response(
                        status=200, body=None, headers=self.app.cors_headers
                    )
                else:
                    func = endpoint.get(method)
                    if func:
                        response = await self.run_handler(func, request)
                    else:
                        response = Response(
                            status=405, body={"error": "Method Not Allowed"}
                        )
            else:
                response = Response(status=404, body={"error": "Not Found"})

        except APIError as e:
            response = Response(status=e.status, body={"error": str(e)})
        except ValidationError as e:
            response = Response(status=400, body={"error": e.errors()})
        except Exception as e:
            response = Response(status=500, body={"error": str(e)})

        return self.response(response)

    async def run_handler(self, func: Callable, request: dict[str, Any]) -> Response:
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
                response = Response(status, model(result).model_dump(mode="json"))
            else:
                return Response(status, model(**result).model_dump(mode="json"))
        else:
            response = Response(status=template.status, body=None)

        return response
