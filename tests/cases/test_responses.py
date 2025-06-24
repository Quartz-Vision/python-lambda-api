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
async def test_responses(app: LambdaAPI):
    assert await app.run(
        ParsedRequest(
            headers={},
            path="/example",
            method=Method.GET,
            params={"name": "test name"},
            body={},
            provider_data={},
        )
    ) == Response(status=200, body="test name")

    assert await app.run(
        ParsedRequest(
            headers={},
            path="/example2",
            method=Method.PATCH,
            params={"name": "test name"},
            body={},
            provider_data={},
        )
    ) == Response(status=200, body={"message": "test name"})

    assert await app.run(
        ParsedRequest(
            headers={"x_custom_header": "test header"},
            path="/example3",
            method=Method.GET,
            params={},
            body={},
            provider_data={},
        )
    ) == Response(status=200, body="test header")

    assert await app.run(
        ParsedRequest(
            headers={"x_custom_header": "test header"},
            path="/example3",
            method=Method.POST,
            params={},
            body={},
            provider_data={},
        )
    ) == Response(status=200, body="test header")
