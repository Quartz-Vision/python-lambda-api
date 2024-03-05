from pydantic import BaseModel

from mini_api.core import MiniAPI


class ExampleSchema(BaseModel):
    name: str


class ExampleResponse(BaseModel):
    message: str


app = MiniAPI(prefix="/api", schema_id="example")


@app.get("/example", status=200)
async def get_example(params: ExampleSchema) -> str:
    return "Hello, " + params.name


@app.get("/example2", status=200)
async def get_example2(params: ExampleSchema) -> ExampleResponse:
    return ExampleResponse(message="Hello, " + params.name)


print(app.get_schema())
