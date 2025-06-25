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
        self.raw = {
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
async def test_request_root_and_empty_paths(
    mock_app: LambdaAPI, mock_adapter: AWSAdapter
):
    root_request = MockRequest(
        path="/", method=Method.GET, params={"name": "test name"}, body={}, headers={}
    )
    empty_path_request = MockRequest(
        path="", method=Method.GET, params={"name": "test name"}, body={}, headers={}
    )

    adapter_parsed_root = mock_adapter.parse_request(root_request.raw)
    adapter_parsed_empty_path = mock_adapter.parse_request(empty_path_request.raw)

    assert adapter_parsed_root == root_request.parsed
    assert adapter_parsed_empty_path == empty_path_request.parsed

    assert adapter_parsed_root.path == "/"
    assert adapter_parsed_empty_path.path == ""
