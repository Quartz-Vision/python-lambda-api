import logging
from typing import Callable, Iterable

from lambda_api.base import AbstractRouter, RouteParams
from lambda_api.schema import Method

logger = logging.getLogger(__name__)


class Router(AbstractRouter):
    def __init__(self, base="", tags: list[str] | None = None):
        self.base = base
        self.tags = tags or []
        self.routes: dict[str, dict[Method, tuple[Callable, RouteParams]]] = {}
        self.routers: set[AbstractRouter] = set()

    def decorate_route(
        self,
        fn: Callable,
        path: str,
        method: Method,
        config: RouteParams,
    ) -> Callable:
        if path not in self.routes:
            self.routes[path] = {}
        self.routes[path][method] = (fn, config)
        return fn

    def add_router(self, router: AbstractRouter):
        if router is self:
            raise ValueError("A router cannot be added to itself")

        self.routers.add(router)

    def get_routes(
        self, root: str = ""
    ) -> Iterable[tuple[Callable, str, Method, RouteParams]]:
        base = root + self.base

        for path, methods in self.routes.items():
            for method, (fn, config) in methods.items():
                yield fn, base + path, method, config

        for router in self.routers:
            yield from router.get_routes(base)
