import asyncio

from pydantic import BaseModel

from lambda_api.adapters import AWSAdapter
from lambda_api.core import LambdaAPI


class ExampleSchema(BaseModel):
    name: str


class ExampleResponse(BaseModel):
    message: str


app = LambdaAPI(prefix="/api", schema_id="example")


@app.get("/example", status=200)
async def get_example(params: ExampleSchema) -> str:
    return "Hello, " + params.name


@app.get("/example2", status=200)
async def get_example2(params: ExampleSchema) -> ExampleResponse:
    return ExampleResponse(message="Hello, " + params.name)


lambda_adapter = AWSAdapter(app)


async def main():
    print("EXAMPLE 1")
    print(
        await lambda_adapter.lambda_handler(
            {
                "httpMethod": "GET",
                "pathParameters": {"proxy": "/example"},
                "queryStringParameters": {"name": "World"},
            },
            None,
        )
    )

    print("EXAMPLE 2")
    print(
        "OPTIONS /example2?name=World:\n",
        await lambda_adapter.lambda_handler(
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
        await lambda_adapter.lambda_handler(
            {
                "httpMethod": "GET",
                "pathParameters": {"proxy": "/example2"},
                "queryStringParameters": {"name": "World"},
            },
            None,
        ),
    )


asyncio.get_event_loop().run_until_complete(main())
