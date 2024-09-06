import orjson


def _json_arbitrary_serializer(obj):
    if type(obj).__str__ is not object.__str__:
        # We need only the custom __str__ method,
        # to not accidentally serialize objects that are not meant to be serialized.
        return str(obj)

    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


ORJSON_DEFAULT_OPTIONS = orjson.OPT_SERIALIZE_UUID | orjson.OPT_OMIT_MICROSECONDS


def json_dumps(data, indent=False) -> str:
    if not indent:
        return orjson.dumps(
            data, option=ORJSON_DEFAULT_OPTIONS, default=_json_arbitrary_serializer
        ).decode()

    return orjson.dumps(
        data,
        option=ORJSON_DEFAULT_OPTIONS | orjson.OPT_INDENT_2,
        default=_json_arbitrary_serializer,
    ).decode()


def json_loads(data: str):
    return orjson.loads(data)
