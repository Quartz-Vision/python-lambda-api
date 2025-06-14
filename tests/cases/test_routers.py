from unittest.mock import Mock, call

import pytest

from lambda_api.core import LambdaAPI, RouteParams, Router
from lambda_api.schema import Method


@pytest.fixture
def mock_app():
    app = LambdaAPI(prefix="/api", schema_id="example", tags=["example", "test"])

    def add_route(fn, *args, **kwargs):
        return fn

    app.add_route = Mock(side_effect=add_route)
    return app


@pytest.fixture
def router_api1():
    router = Router("/api1")
    test_routes_api1 = [
        (lambda: "test", "/test", Method.GET, RouteParams(status=200)),
        (lambda: "test", "/test2", Method.POST, RouteParams(status=200)),
        (lambda: "test", "/test2", Method.GET, RouteParams(status=200)),
    ]
    based_test_routes_api1 = [
        (fn, "/api1" + path, method, config)
        for fn, path, method, config in test_routes_api1
    ]
    return router, test_routes_api1, based_test_routes_api1


@pytest.fixture
def router_api2():
    router = Router("/api2")
    test_routes_api2 = [
        (lambda: "test", "/test3", Method.GET, RouteParams(status=200)),
        (lambda: "test", "/test4", Method.POST, RouteParams(status=200)),
        (lambda: "test", "/test4", Method.GET, RouteParams(status=200)),
    ]
    based_test_routes_api2 = [
        (fn, "/api2" + path, method, config)
        for fn, path, method, config in test_routes_api2
    ]
    return router, test_routes_api2, based_test_routes_api2


def test_routers_lvl1(router_api1):
    router, test_routes_api1, based_test_routes_api1 = router_api1

    for conf in test_routes_api1:
        router.add_route(*conf)

    found_routes = []
    for route in router.get_routes():
        assert route in based_test_routes_api1
        assert route not in found_routes
        found_routes.append(route)

    assert len(found_routes) == len(based_test_routes_api1)


def test_routers_lvl2(router_api1, router_api2):
    router, test_routes_api1, based_test_routes_api1 = router_api1
    router2, test_routes_api2, based_test_routes_api2 = router_api2

    based_test_routes_api1_2 = [
        (fn, "/api1" + path, method, config)
        for fn, path, method, config in based_test_routes_api2
    ]

    all_based_routes = based_test_routes_api1 + based_test_routes_api1_2

    for conf in test_routes_api1:
        router.add_route(*conf)

    for conf in test_routes_api2:
        router2.add_route(*conf)

    router.add_router(router2)

    found_routes = []
    for route in router.get_routes():
        assert route in all_based_routes
        assert route not in found_routes
        found_routes.append(route)

    assert len(found_routes) == len(all_based_routes)


def test_routers_app_integration(mock_app, router_api1):
    router, test_routes_api1, based_test_routes_api1 = router_api1

    for conf in test_routes_api1:
        router.add_route(*conf)

    mock_app.add_router(router)

    calls = [call(*conf) for conf in based_test_routes_api1]
    mock_app.add_route.assert_has_calls(calls)
