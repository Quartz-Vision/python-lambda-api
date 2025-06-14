from unittest.mock import AsyncMock

import pytest

from lambda_api.adapters import AWSAdapter
from lambda_api.core import LambdaAPI, ParsedRequest, Response
from lambda_api.schema import Method
from lambda_api.utils import json_dumps


@pytest.fixture
def mock_app():
    app = LambdaAPI(prefix="/api", schema_id="example", tags=["example", "test"])
    app.run = AsyncMock(
        return_value=Response(status=200, body={"message": "test name"})
    )
    return app


@pytest.mark.asyncio
async def test_parsing(mock_app):
    # Mock the api .run method

    adapter = AWSAdapter(mock_app)

    raw_data = {
        "httpMethod": "GET",
        "pathParameters": {"proxy": "example"},
        "queryStringParameters": {"name": "test name"},
        "body": "{}",
        "headers": {},
    }
    parsed_request = ParsedRequest(
        headers={},
        path="/example",
        method=Method.GET,
        params={"name": "test name"},
        body={},
        provider_data=raw_data,
    )

    assert adapter.parse_request(raw_data) == parsed_request

    assert await adapter.run(raw_data) == {
        "statusCode": 200,
        "body": json_dumps({"message": "test name"}),
        "headers": {"Content-Type": "application/json"},
    }

    mock_app.run.assert_awaited_once_with(parsed_request)
