from dataclasses import dataclass, field
from typing import Callable

import pytest
from pydantic import BaseModel

from lambda_api.app import LambdaAPI
from lambda_api.base import RouteParams
from lambda_api.docsgen import OpenApiGenerator
from lambda_api.schema import Headers, Method, Request


class ExampleSchema(BaseModel):
    name: str


class ExampleResponse(BaseModel):
    message: str


class ExampleHeaders(Headers):
    x_custom_header: str


class ExampleRequest(Request):
    headers: ExampleHeaders


class ExampleParams(BaseModel):
    name: str


@dataclass
class EndpointSpec:
    path: str
    method: Method
    config: RouteParams
    description: str | None = None
    params: str | None = None
    body: str | None = None
    request: str | None = None
    response: str | None = None

    handler: Callable = field(init=False, repr=False)

    def __post_init__(self):
        scope = {}
        args = []
        if self.params:
            args.append(f"params: {self.params}")
        if self.body:
            args.append(f"body: {self.body}")
        if self.request:
            args.append(f"request: {self.request}")

        return_annotation = ""
        if self.response:
            return_annotation = f" -> {self.response}"

        func_str = f"def __handler({', '.join(args)}){return_annotation}: ...\n"

        exec(func_str, locals=scope)
        self.handler = scope["__handler"]

        if self.description:
            self.handler.__doc__ = self.description


def create_app(specs: list[EndpointSpec]) -> LambdaAPI:
    app = LambdaAPI(prefix="/api", schema_id="example", tags=["example", "test"])
    for spec in specs:
        app.decorate_route(spec.handler, spec.path, spec.method, spec.config)

    return app


api_apps_common = [
    # Empty vs root vs other paths
    [
        EndpointSpec(
            path="",
            method=Method.GET,
            config=RouteParams(status=200),
            description="@empty",
        ),
        EndpointSpec(
            path="/",
            method=Method.GET,
            config=RouteParams(status=200),
            description="@root",
        ),
        EndpointSpec(
            path="/example",
            method=Method.GET,
            config=RouteParams(status=200),
            description="@example",
        ),
    ],
    # Multiple methods
    [
        EndpointSpec(
            path="/example",
            method=method,
            config=RouteParams(status=200),
            description=f"@example-{method.value}",
        )
        for method in [Method.GET, Method.POST, Method.PUT, Method.DELETE, Method.PATCH]
    ],
]


@pytest.mark.parametrize(
    "specs",
    api_apps_common,
)
def test_docsgen_consistent(specs):
    app = create_app(specs)
    schema_gen = OpenApiGenerator(app)
    assert schema_gen.get_schema() == schema_gen.get_schema()


@pytest.mark.parametrize(
    "specs",
    api_apps_common,
)
def test_docsgen_paths_methods_exist(specs):
    app = create_app(specs)
    schema = OpenApiGenerator(app).get_schema()

    for spec in specs:
        assert app.prefix + spec.path in schema["paths"]
        assert spec.method.value.lower() in schema["paths"][app.prefix + spec.path]


@pytest.mark.parametrize(
    "specs",
    api_apps_common,
)
def test_docsgen_description(specs):
    app = create_app(specs)
    schema = OpenApiGenerator(app).get_schema()

    for spec in specs:
        assert (
            spec.description
            in schema["paths"][app.prefix + spec.path][spec.method.value.lower()][
                "description"
            ]
        )


def test_docsgen_headers():
    app = create_app(
        [
            EndpointSpec(
                path="/example",
                method=Method.GET,
                config=RouteParams(status=200),
                request="ExampleRequest",
            ),
        ]
    )
    schema = OpenApiGenerator(app).get_schema()

    assert (
        schema["paths"]["/api/example"]["get"]["parameters"][0]["name"]
        == "X-Custom-Header"
    )


@pytest.mark.parametrize(
    "specs",
    [
        EndpointSpec(
            path="/example", method=Method.GET, config=RouteParams(status=200), params=t
        )
        for t in [
            "ExampleParams",
            # "list[int]",
            # "dict[str, int]",
        ]
    ]
    + [
        EndpointSpec(
            path="/example",
            method=Method.POST,
            config=RouteParams(status=200),
            body=t,
        )
        for t in [
            "ExampleParams",
            # "list[int]",
            # "dict[str, int]",
        ]
    ],
)
def test_docsgen_params_body(specs):
    # it should just work
    app = create_app([specs])
    OpenApiGenerator(app).get_schema()
