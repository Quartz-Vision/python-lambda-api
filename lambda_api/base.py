import logging
from abc import ABC, abstractmethod
from typing import Callable, Iterable, NotRequired, TypedDict, Unpack

from lambda_api.schema import Method

logger = logging.getLogger(__name__)


class RouteParams(TypedDict):
    """
    Additional parameters for the routes. This is a type hint only.
    Don't change to a dataclass.
    """

    status: NotRequired[int]
    tags: NotRequired[list[str] | None]


class AbstractRouter(ABC):
    @abstractmethod
    def decorate_route(
        self, fn: Callable, path: str, method: Method, config: RouteParams
    ) -> Callable: ...

    def post(self, path: str, **config: Unpack[RouteParams]):
        return lambda fn: self.decorate_route(fn, path, Method.POST, config)

    def get(self, path: str, **config: Unpack[RouteParams]):
        return lambda fn: self.decorate_route(fn, path, Method.GET, config)

    def put(self, path: str, **config: Unpack[RouteParams]):
        return lambda fn: self.decorate_route(fn, path, Method.PUT, config)

    def delete(self, path: str, **config: Unpack[RouteParams]):
        return lambda fn: self.decorate_route(fn, path, Method.DELETE, config)

    def patch(self, path: str, **config: Unpack[RouteParams]):
        return lambda fn: self.decorate_route(fn, path, Method.PATCH, config)

    @abstractmethod
    def get_routes(
        self, root: str
    ) -> Iterable[tuple[Callable, str, Method, RouteParams]]: ...

    @abstractmethod
    def add_router(self, router: "AbstractRouter"): ...
