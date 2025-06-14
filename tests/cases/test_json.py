from uuid import uuid4

from lambda_api.utils import json_dumps, json_loads


def test_json_dumps_and_loads():
    data = {"name": "John", "age": 30, "is_student": True}
    json_str = json_dumps(data)
    assert json_loads(json_str) == data


def test_json_dumps_and_loads_with_indent():
    data = {"name": "John", "age": 30, "is_student": True}
    json_str = json_dumps(data, indent=True)
    assert json_loads(json_str) == data


def test_json_dumps_arbitrary_objects():
    class ArbitraryClass:
        def __str__(self):
            return "my_arbitrary_class"

    data = {
        "name": "John",
        "age": 30,
        "is_student": True,
        "arbitrary": ArbitraryClass(),
        "other": uuid4(),
    }
    json_str = json_dumps(data)
    reconstructed = json_loads(json_str)

    assert reconstructed["arbitrary"] == "my_arbitrary_class"
    assert reconstructed["other"] == str(data["other"])
