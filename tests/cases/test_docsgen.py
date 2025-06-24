import pytest
from pydantic import BaseModel

from lambda_api.app import LambdaAPI
from lambda_api.docsgen import OpenApiGenerator
from lambda_api.schema import BearerAuthRequest, Headers, Request


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
        ...

    @app.patch("/example2", status=200, tags=None)
    async def get_example2(
        params: ExampleSchema, request: BearerAuthRequest
    ) -> ExampleResponse:
        """
        Some test description. @example2
        """
        ...

    @app.get("/example3", status=200, tags=None)
    async def get_example3(params: ExampleSchema):
        """@example3"""
        ...

    class MyHeaders(Headers):
        x_custom_header: str

    class MyRequest(Request):
        headers: MyHeaders  # type: ignore

    @app.get("/example4", status=200)
    async def get_example4(request: MyRequest) -> str:
        """@example4-get"""
        ...

    @app.post("/example4", status=200)
    async def post_example4(request: MyRequest) -> str:
        """@example4-post"""
        ...

    return app


def test_docsgen_consistent(app: LambdaAPI):
    schema_gen = OpenApiGenerator(app)

    assert schema_gen.get_schema() == schema_gen.get_schema()
    assert OpenApiGenerator(app).get_schema() == schema_gen.get_schema()


def test_docsgen_endpoints_map(app: LambdaAPI):
    schema = OpenApiGenerator(app).get_schema()

    assert "/api/example" in schema["paths"]
    assert "/api/example2" in schema["paths"]
    assert "/api/example3" in schema["paths"]
    assert "/api/example4" in schema["paths"]

    assert set(schema["paths"]["/api/example2"].keys()) == {"patch"}
    assert set(schema["paths"]["/api/example4"].keys()) == {"get", "post"}
    assert set(schema["paths"]["/api/example"].keys()) == {"get"}


def test_docsgen_description(app: LambdaAPI):
    schema = OpenApiGenerator(app).get_schema()

    assert "@example" in schema["paths"]["/api/example"]["get"]["description"]
    assert "@example2" in schema["paths"]["/api/example2"]["patch"]["description"]
    assert "@example3" in schema["paths"]["/api/example3"]["get"]["description"]
    assert "@example4-get" in schema["paths"]["/api/example4"]["get"]["description"]
    assert "@example4-post" in schema["paths"]["/api/example4"]["post"]["description"]


def test_docsgen_headers(app: LambdaAPI):
    schema = OpenApiGenerator(app).get_schema()

    assert (
        schema["paths"]["/api/example4"]["get"]["parameters"][0]["name"]
        == "X-Custom-Header"
    )
