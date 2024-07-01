import json

from pydantic import BaseModel

from lambda_api.core import LambdaAPI
from lambda_api.docsgen import OpenApiGenerator


class ExampleSchema(BaseModel):
    name: str


class ExampleResponse(BaseModel):
    message: str


app = LambdaAPI(prefix="/api", schema_id="example", tags=["example", "test"])


@app.get("/example", status=200)
async def get_example(params: ExampleSchema) -> str:
    return "Hello, " + params.name


@app.get("/example2", status=200, tags=None)
async def get_example2(params: ExampleSchema) -> ExampleResponse:
    """
    Some test description
    """
    return ExampleResponse(message="Hello, " + params.name)


@app.get("/example3", status=200, tags=None)
async def get_example3(params: ExampleSchema):
    pass


schema_gen = OpenApiGenerator(app)
print(json.dumps(schema_gen.get_schema(), indent=4, sort_keys=True))
