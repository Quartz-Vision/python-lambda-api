from enum import StrEnum
from typing import Any, ClassVar, NamedTuple

from pydantic import BaseModel, ConfigDict


class Method(StrEnum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    OPTIONS = "OPTIONS"


class Headers(BaseModel):
    model_config = ConfigDict(extra="allow")


class RequestConfigBase(NamedTuple):
    auth_name: str | None
    """
    Name of the authentication method to use for this request.
    See https://swagger.io/docs/specification/authentication/
    """


class Request(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    request_config: ClassVar[RequestConfigBase | None] = None

    headers: Headers
    path: str
    method: Method
    params: dict[str, Any]
    body: Any
    provider_data: Any


class BearerAuthRequest(Request):
    request_config = RequestConfigBase(auth_name="BearerAuth")
