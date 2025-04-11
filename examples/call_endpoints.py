import asyncio

from pydantic import BaseModel

from lambda_api.adapters import AWSAdapter
from lambda_api.core import LambdaAPI
from lambda_api.schema import Headers, Request


class ExampleSchema(BaseModel):
    name: str


class ExampleBody(BaseModel):
    name2: str


class ExampleResponse(BaseModel):
    message: str


app = LambdaAPI(prefix="/api", schema_id="example")


@app.patch("/example", status=200)
async def get_example(params: ExampleSchema, body: ExampleBody) -> str:
    return "Hello, " + params.name + " and " + body.name2


@app.get("/example2", status=200)
async def get_example2(params: ExampleSchema) -> ExampleResponse:
    return ExampleResponse(message="Hello, " + params.name)


@app.get("/example3", status=200)
async def get_example3(params: ExampleSchema):
    """Safe unhandled exceptions"""
    a = {}
    a["key"]


class MyHeaders(Headers):
    x_custom_header: str


class MyRequest(Request):
    headers: MyHeaders


@app.get("/example4", status=200)
async def get_example4(request: MyRequest) -> str:
    return "Hello, " + request.headers.x_custom_header


lambda_adapter = AWSAdapter(app)


async def main():
    print("EXAMPLE 1")
    print(
        await lambda_adapter.run(
            {
                "httpMethod": "PATCH",
                "pathParameters": {"proxy": "/example"},
                "queryStringParameters": {"name": "World"},
                "body": '{"name2": "World}',
            },
            None,
        )
    )

    print("\nEXAMPLE 2")
    print(
        "OPTIONS /example2?name=World:\n",
        await lambda_adapter.run(
            {
                "httpMethod": "OPTIONS",
                "pathParameters": {"proxy": "/example2"},
                "queryStringParameters": {"name": "World"},
            },
            None,
        ),
    )
    print(
        "GET /example2?name=World:\n",
        await lambda_adapter.run(
            {
                "httpMethod": "GET",
                "pathParameters": {"proxy": "/example2"},
                "queryStringParameters": {"name": "World"},
            },
            None,
        ),
    )

    print("\nEXAMPLE 3")
    print(
        "GET /example3?name=World:\n",
        await lambda_adapter.run(
            {
                "httpMethod": "GET",
                "pathParameters": {"proxy": "/example3"},
                "queryStringParameters": {"name": "World"},
            },
            None,
        ),
    )

    print("\nEXAMPLE 4")
    print(
        "GET /example4:\n",
        await lambda_adapter.run(
            {
                "httpMethod": "GET",
                "pathParameters": {"proxy": "/example4"},
                "headers": {"X-Custom-Header": "World from a header"},
            },
            None,
        ),
    )


asyncio.run(main())
