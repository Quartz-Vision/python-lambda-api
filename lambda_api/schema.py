from enum import StrEnum
from typing import Any, ClassVar, TypedDict

from pydantic import BaseModel, ConfigDict


class Method(StrEnum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"


class Headers(BaseModel):
    model_config = ConfigDict(extra="allow")


class RequestConfigDict(TypedDict, total=False):
    auth_name: str | None


class Request(BaseModel):
    request_config: ClassVar[RequestConfigDict | None] = None

    headers: Headers
    path: str
    method: Method
    params: dict[str, str]
    body: dict[str, Any]
    provider_data: Any


class BearerAuthRequest(Request):
    request_config = RequestConfigDict(auth_name="BearerAuth")
