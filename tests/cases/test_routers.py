from unittest.mock import Mock, call

import pytest

from lambda_api.app import LambdaAPI
from lambda_api.base import RouteParams
from lambda_api.router import Router
from lambda_api.schema import Method


@pytest.fixture
def mock_app():
    app = LambdaAPI(prefix="/api", schema_id="example", tags=["example", "test"])

    def decorate_route(fn, *args, **kwargs):
        return fn

    app.decorate_route = Mock(side_effect=decorate_route)
    return app


@pytest.fixture
def router_api1():
    router = Router()
    test_routes_api1 = [
        (lambda: "test", "/test", Method.GET, RouteParams(status=200)),
        (lambda: "test", "/test2", Method.POST, RouteParams(status=200)),
        (lambda: "test", "/test2", Method.GET, RouteParams(status=200)),
    ]
    prefixed_routes_api1 = [
        (fn, "/api1" + path, method, config)
        for fn, path, method, config in test_routes_api1
    ]
    return "/api1", router, test_routes_api1, prefixed_routes_api1


@pytest.fixture
def router_api2():
    router = Router()
    test_routes_api2 = [
        (lambda: "test", "/test3", Method.GET, RouteParams(status=200)),
        (lambda: "test", "/test4", Method.POST, RouteParams(status=200)),
        (lambda: "test", "/test4", Method.GET, RouteParams(status=200)),
    ]
    prefixed_routes_api2 = [
        (fn, "/api2" + path, method, config)
        for fn, path, method, config in test_routes_api2
    ]
    return "/api2", router, test_routes_api2, prefixed_routes_api2


def test_routers_lvl1(router_api1):
    expected_prefix, router, test_routes_api1, prefixed_routes_api1 = router_api1

    for conf in test_routes_api1:
        router.decorate_route(*conf)

    found_routes = []
    for route in router.get_routes(expected_prefix):
        assert route in prefixed_routes_api1
        assert route not in found_routes
        found_routes.append(route)

    assert len(found_routes) == len(prefixed_routes_api1)


def test_routers_lvl2(router_api1, router_api2):
    expected_prefix1, router, test_routes_api1, prefixed_routes_api1 = router_api1
    expected_prefix2, router2, test_routes_api2, prefixed_routes_api2 = router_api2

    prefixed_routes_api1_2 = [
        (fn, expected_prefix1 + path, method, config)
        for fn, path, method, config in prefixed_routes_api2
    ]

    all_based_routes = prefixed_routes_api1 + prefixed_routes_api1_2

    for conf in test_routes_api1:
        router.decorate_route(*conf)

    for conf in test_routes_api2:
        router2.decorate_route(*conf)

    router.add_router(expected_prefix2, router2)

    found_routes = []
    for route in router.get_routes(expected_prefix1):
        assert route in all_based_routes
        assert route not in found_routes
        found_routes.append(route)

    assert len(found_routes) == len(all_based_routes)


def test_routers_app_integration(mock_app, router_api1):
    expected_prefix, router, test_routes_api1, prefixed_routes_api1 = router_api1

    for conf in test_routes_api1:
        router.decorate_route(*conf)

    mock_app.add_router(expected_prefix, router)

    calls = [call(*conf) for conf in prefixed_routes_api1]
    mock_app.decorate_route.assert_has_calls(calls)
