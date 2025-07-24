from inspect import _empty
from uuid import uuid4

import pytest
from pydantic import BaseModel, Field, RootModel

from lambda_api.utils import arbitrary_type_to_pydantic


class MockModel(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = "test"


@pytest.mark.parametrize(
    "type_, expected",
    [
        (str, (RootModel[str], True)),
        (dict, (RootModel[dict], True)),
        (dict[str, int], (RootModel[dict[str, int]], True)),
        (list, (RootModel[list], True)),
        (list[int], (RootModel[list[int]], True)),
        (int, (RootModel[int], True)),
        (bool, (RootModel[bool], True)),
        (MockModel, (MockModel, False)),
        (_empty, (None, False)),
        (None, (None, False)),
    ],
)
def test_arbitrary_type_to_pydantic(type_, expected):
    result = arbitrary_type_to_pydantic(type_)
    assert result == expected
