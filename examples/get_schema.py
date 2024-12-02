from pydantic import BaseModel

from lambda_api.core import LambdaAPI
from lambda_api.docsgen import OpenApiGenerator
from lambda_api.schema import BearerAuthRequest, Headers, Request
from lambda_api.utils import json_dumps


class ExampleSchema(BaseModel):
    name: str


class ExampleResponse(BaseModel):
    message: str


app = LambdaAPI(prefix="/api", schema_id="example", tags=["example", "test"])


@app.get("/example", status=200)
async def get_example(params: ExampleSchema) -> str:
    return "Hello, " + params.name


@app.get("/example2", status=200, tags=None)
async def get_example2(
    params: ExampleSchema, request: BearerAuthRequest
) -> ExampleResponse:
    """
    Some test description
    """
    return ExampleResponse(message="Hello, " + params.name)


@app.get("/example3", status=200, tags=None)
async def get_example3(params: ExampleSchema):
    pass


class MyHeaders(Headers):
    x_custom_header: str


class MyRequest(Request):
    headers: MyHeaders


@app.get("/example4", status=200)
async def get_example4(request: MyRequest) -> str:
    return "Hello, " + request.headers.x_custom_header


schema_gen = OpenApiGenerator(app)
print(json_dumps(schema_gen.get_schema(), indent=True))
