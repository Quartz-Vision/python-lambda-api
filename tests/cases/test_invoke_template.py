from typing import Any

import pytest
from pydantic import BaseModel, RootModel, ValidationError

from lambda_api.app import InvokeTemplate, ParsedRequest, Response
from lambda_api.schema import Request


class ParamsModel(BaseModel):
    a: int
    b: str


class BodyModel(BaseModel):
    c: float
    d: bool


class RootParamsModel(RootModel[list[int]]):
    pass


class RootBodyModel(RootModel[str]):
    pass


class ResponseModel(BaseModel):
    e: int
    f: str


def create_parsed_request(
    params: Any | None = None,
    body: Any | None = None,
) -> ParsedRequest:
    return ParsedRequest(
        params=params if params is not None else {},
        body=body if body is not None else {},
        headers={},
        path="/test",
        method="GET",
        provider_data={},
    )


@pytest.mark.parametrize(
    "template_config, request_data, expected_args",
    [
        # Test with params
        (
            {"params": ParamsModel, "params_root": False},
            {"params": {"a": 1, "b": "test"}},
            {"params": ParamsModel(a=1, b="test")},
        ),
        # Test with root params
        (
            {"params": RootParamsModel, "params_root": True},
            {"params": [1, 2, 3]},
            {"params": [1, 2, 3]},
        ),
        # Test with body
        (
            {"body": BodyModel, "body_root": False},
            {"body": {"c": 1.1, "d": True}},
            {"body": BodyModel(c=1.1, d=True)},
        ),
        # Test with root body
        (
            {"body": RootBodyModel, "body_root": True},
            {"body": "hello"},
            {"body": "hello"},
        ),
        # Test with request model
        (
            {"request": Request},
            {},
            {"request": Request.model_validate(create_parsed_request())},
        ),
        # Test with all args
        (
            {
                "params": ParamsModel,
                "body": BodyModel,
                "request": Request,
            },
            {
                "params": {"a": 1, "b": "test"},
                "body": {"c": 1.1, "d": True},
            },
            {
                "params": ParamsModel(a=1, b="test"),
                "body": BodyModel(c=1.1, d=True),
                "request": Request.model_validate(
                    create_parsed_request(
                        params={"a": 1, "b": "test"},
                        body={"c": 1.1, "d": True},
                    )
                ),
            },
        ),
    ],
)
def test_prepare_method_args(template_config, request_data, expected_args):
    template = InvokeTemplate(
        params=template_config.get("params"),
        params_root=template_config.get("params_root", False),
        body=template_config.get("body"),
        body_root=template_config.get("body_root", False),
        request=template_config.get("request"),
        response=None,
        status=200,
        tags=[],
    )
    request = create_parsed_request(**request_data)
    args = template.prepare_method_args(request)
    assert args == expected_args


@pytest.mark.parametrize(
    "template_config, request_data",
    [
        # Params validation error
        (
            {"params": ParamsModel},
            {"params": {"a": "wrong", "b": "test"}},
        ),
        # Root Params validation error
        (
            {"params": RootParamsModel, "params_root": True},
            {"params": [1, "a", 3]},
        ),
        # Body validation error
        (
            {"body": BodyModel},
            {"body": {"c": 1.1, "d": "wrong"}},
        ),
        # Root body validation error
        (
            {"body": RootBodyModel, "body_root": True},
            {"body": 123},
        ),
    ],
)
def test_prepare_method_args_validation_error(template_config, request_data):
    template = InvokeTemplate(
        params=template_config.get("params"),
        params_root=template_config.get("params_root", False),
        body=template_config.get("body"),
        body_root=template_config.get("body_root", False),
        request=None,
        response=None,
        status=200,
        tags=[],
    )
    request = create_parsed_request(**request_data)
    with pytest.raises(ValidationError):
        template.prepare_method_args(request)


@pytest.mark.parametrize(
    "template_config, result, expected_response",
    [
        # Response with a Pydantic model
        (
            {"response": ResponseModel, "status": 201},
            ResponseModel(e=1, f="test"),
            Response(status=201, body={"e": 1, "f": "test"}),
        ),
        # Response with a dict that validates against the model
        (
            {"response": ResponseModel, "status": 200},
            {"e": 2, "f": "test2"},
            Response(status=200, body={"e": 2, "f": "test2"}),
        ),
        # No response model, should return empty body
        (
            {"response": None, "status": 204},
            {"e": 1, "f": "test"},
            Response(status=204, body=None),
        ),
    ],
)
def test_prepare_response(template_config, result, expected_response):
    template = InvokeTemplate(
        params=None,
        params_root=False,
        body=None,
        body_root=False,
        request=None,
        response=template_config.get("response"),
        status=template_config.get("status"),
        tags=[],
    )
    response = template.prepare_response(result)
    # We can't directly compare headers dict because of default factory
    assert response.status == expected_response.status
    assert response.body == expected_response.body


@pytest.mark.parametrize(
    "template_config, result",
    [
        # Response validation error
        (
            {"response": ResponseModel},
            {"e": "wrong", "f": "test"},
        )
    ],
)
def test_prepare_response_validation_error(template_config, result):
    template = InvokeTemplate(
        params=None,
        params_root=False,
        body=None,
        body_root=False,
        request=None,
        response=template_config.get("response"),
        status=200,
        tags=[],
    )
    with pytest.raises(ValidationError):
        template.prepare_response(result)
