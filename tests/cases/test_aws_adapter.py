from unittest.mock import AsyncMock

import pytest

from lambda_api.adapters import AWSAdapter
from lambda_api.app import LambdaAPI, ParsedRequest, Response
from lambda_api.schema import Method
from lambda_api.utils import json_dumps


@pytest.fixture
def mock_app():
    app = LambdaAPI(prefix="/api", schema_id="example", tags=["example", "test"])
    app.run = AsyncMock(
        return_value=Response(status=200, body={"message": "test name"})
    )
    return app


@pytest.fixture
def mock_adapter(mock_app: LambdaAPI):
    return AWSAdapter(mock_app)


class MockRequest:
    def __init__(
        self, path: str, method: Method, params: dict, body: dict, headers: dict
    ):
        path = path or "/"
        self.raw = {
            "resource": "/api/{proxy+}",
            "httpMethod": method.value,
            "pathParameters": {"proxy": path},
            "queryStringParameters": params,
            "body": body,
            "headers": headers,
        }
        self.parsed = ParsedRequest(
            provider_data=self.raw,
            headers=headers,
            path=path,
            method=method,
            params=params,
            body=body,
        )


@pytest.mark.asyncio
async def test_request_response_general_parsing(
    mock_app: LambdaAPI, mock_adapter: AWSAdapter
):
    request = MockRequest(
        path="/example",
        method=Method.GET,
        params={"name": "test name"},
        body={},
        headers={},
    )

    assert mock_adapter.parse_request(request.raw) == request.parsed
    assert await mock_adapter.run(request.raw) == {
        "statusCode": 200,
        "body": json_dumps({"message": "test name"}),
        "headers": {"Content-Type": "application/json"},
    }

    mock_app.run.assert_awaited_once_with(request.parsed)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mock_request",
    [
        MockRequest(
            path="/",
            method=Method.GET,
            params={"name": "test name"},
            body={},
            headers={},
        ),
        MockRequest(
            path="",
            method=Method.GET,
            params={"name": "test name"},
            body={},
            headers={},
        ),
        MockRequest(
            path="/test/",
            method=Method.GET,
            params={"name": "test name"},
            body={},
            headers={},
        ),
    ],
)
async def test_request_root_and_empty_paths(
    mock_app: LambdaAPI, mock_adapter: AWSAdapter, mock_request: MockRequest
):
    mock_request_parsed = mock_adapter.parse_request(mock_request.raw)
    assert mock_request_parsed == mock_request.parsed
