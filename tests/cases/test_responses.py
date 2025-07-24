import pytest
from pydantic import BaseModel

from lambda_api.app import LambdaAPI, ParsedRequest, Response
from lambda_api.schema import BearerAuthRequest, Headers, Method, Request


class ExampleSchema(BaseModel):
    name: str


class ExampleResponse(BaseModel):
    message: str


@pytest.fixture
def app():
    app = LambdaAPI(prefix="/api", schema_id="example", tags=["example", "test"])

    @app.get("", status=200)
    async def get_empty_path() -> str:
        """@empty"""
        return "empty"

    @app.get("/", status=200)
    async def get_root() -> str:
        """@root"""
        return "root"

    @app.get("/example", status=200)
    async def get_example(params: ExampleSchema) -> str:
        """@example"""
        return params.name

    @app.patch("/example2", status=200, tags=None)
    async def get_example2(
        params: ExampleSchema, request: BearerAuthRequest
    ) -> ExampleResponse:
        """
        Some test description. @example2
        """
        return ExampleResponse(message=params.name)

    class MyHeaders(Headers):
        x_custom_header: str

    class MyRequest(Request):
        headers: MyHeaders  # type: ignore

    @app.get("/example3", status=200)
    async def get_example3(request: MyRequest) -> str:
        """@example3-get"""
        return request.headers.x_custom_header

    @app.post("/example3", status=200)
    async def post_example3(request: MyRequest) -> str:
        """@example3-post"""
        return request.headers.x_custom_header

    return app


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path, method, request_data, expected_response",
    [
        (
            "",
            Method.GET,
            {},
            Response(status=200, body="empty"),
        ),
        (
            "/",
            Method.GET,
            {},
            Response(status=200, body="root"),
        ),
        (
            "/example",
            Method.GET,
            {"params": {"name": "test name"}},
            Response(status=200, body="test name"),
        ),
        (
            "/example2",
            Method.PATCH,
            {"params": {"name": "test name"}},
            Response(status=200, body={"message": "test name"}),
        ),
        (
            "/example3",
            Method.GET,
            {"headers": {"x_custom_header": "test header"}},
            Response(status=200, body="test header"),
        ),
        (
            "/example3",
            Method.POST,
            {"headers": {"x_custom_header": "test header"}},
            Response(status=200, body="test header"),
        ),
    ],
)
async def test_endpoint_handler(
    app: LambdaAPI, path, method, request_data, expected_response
):
    route_wrapper = app.route_table[path][method]
    request = ParsedRequest(
        path=path,
        method=method,
        params=request_data.get("params", {}),
        body=request_data.get("body", {}),
        headers=request_data.get("headers", {}),
        provider_data={},
    )
    response = await app.run_endpoint_handler(route_wrapper, request)
    assert response.status == expected_response.status
    assert response.body == expected_response.body
