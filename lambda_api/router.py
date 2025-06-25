import logging
from typing import Callable, Iterable

from lambda_api.base import AbstractRouter, RouteParams
from lambda_api.schema import Method

logger = logging.getLogger(__name__)


class Router(AbstractRouter):
    def __init__(self, tags: list[str] | None = None):
        self.tags = tags or []
        self.routes: dict[str, dict[Method, tuple[Callable, RouteParams]]] = {}
        self.routers: set[tuple[str, AbstractRouter]] = set()

    def decorate_route(
        self,
        fn: Callable,
        path: str,
        method: Method,
        config: RouteParams,
    ) -> Callable:
        path = "/" + path.lstrip("/") if path else ""
        if path not in self.routes:
            self.routes[path] = {}
        self.routes[path][method] = (fn, config)
        return fn

    def add_router(self, prefix: str, router: AbstractRouter):
        self.routers.add(("/" + prefix.lstrip("/") if prefix else "", router))

    def get_routes(
        self, prefix: str
    ) -> Iterable[tuple[Callable, str, Method, RouteParams]]:
        prefix = "/" + prefix.lstrip("/") if prefix else ""

        for path, methods in self.routes.items():
            for method, (fn, config) in methods.items():
                yield fn, prefix + path, method, config

        for router_prefix, router in self.routers:
            yield from router.get_routes(prefix + router_prefix)
