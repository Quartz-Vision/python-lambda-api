from unittest.mock import Mock, call

import pytest

from lambda_api.app import LambdaAPI
from lambda_api.base import RouteParams
from lambda_api.router import Router
from lambda_api.schema import Method


@pytest.fixture
def mock_app():
    app = LambdaAPI(prefix="/api", schema_id="example", tags=["example", "test"])
    app.decorate_route = Mock(side_effect=app.decorate_route)
    return app


@pytest.fixture
def router_api1():
    router = Router()
    test_routes_api1 = [
        (lambda: "test", "", Method.GET, RouteParams(status=200)),
        (lambda: "test", "/", Method.GET, RouteParams(status=200)),
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
        (lambda: "test", "", Method.GET, RouteParams(status=200)),
        (lambda: "test", "/", Method.GET, RouteParams(status=200)),
        (lambda: "test", "/test3", Method.GET, RouteParams(status=200)),
        (lambda: "test", "/test4", Method.POST, RouteParams(status=200)),
        (lambda: "test", "/test4", Method.GET, RouteParams(status=200)),
    ]
    prefixed_routes_api2 = [
        (fn, "/api2" + path, method, config)
        for fn, path, method, config in test_routes_api2
    ]
    return "/api2", router, test_routes_api2, prefixed_routes_api2


@pytest.fixture
def router_empty():
    router = Router()
    test_routes = [
        (lambda: "test", "/test-empty", Method.GET, RouteParams(status=200)),
    ]
    prefixed_routes = [
        (fn, "" + path, method, config) for fn, path, method, config in test_routes
    ]
    return "", router, test_routes, prefixed_routes


@pytest.mark.parametrize(
    "test_router_data", ["router_api1", "router_api2", "router_empty"]
)
def test_routers_lvl1(test_router_data, request):
    expected_prefix, router, test_routes, prefixed_routes = request.getfixturevalue(
        test_router_data
    )

    for conf in test_routes:
        router.decorate_route(*conf)

    found_routes = []
    for route in router.get_routes(expected_prefix):
        assert route in prefixed_routes
        assert route not in found_routes
        found_routes.append(route)

    assert len(found_routes) == len(prefixed_routes)


@pytest.mark.parametrize(
    "router_pair",
    [
        ("router_api1", "router_api2"),
        ("router_empty", "router_api1"),
        ("router_api1", "router_empty"),
    ],
)
def test_routers_lvl2(router_pair, request):
    expected_prefix1, router1, test_routes1, prefixed_routes1 = request.getfixturevalue(
        router_pair[0]
    )
    expected_prefix2, router2, test_routes2, prefixed_routes2 = request.getfixturevalue(
        router_pair[1]
    )

    prefixed_routes1_2 = [
        (fn, expected_prefix1 + path, method, config)
        for fn, path, method, config in prefixed_routes2
    ]

    all_prefixed_routes = prefixed_routes1 + prefixed_routes1_2

    for conf in test_routes1:
        router1.decorate_route(*conf)

    for conf in test_routes2:
        router2.decorate_route(*conf)

    router1.add_router(expected_prefix2, router2)

    found_routes = []
    for route in router1.get_routes(expected_prefix1):
        assert route in all_prefixed_routes
        assert route not in found_routes
        found_routes.append(route)

    assert len(found_routes) == len(all_prefixed_routes)


@pytest.mark.parametrize(
    "test_router_data", ["router_api1", "router_api2", "router_empty"]
)
def test_routers_app_integration(mock_app, test_router_data, request):
    expected_prefix, router, test_routes, prefixed_routes = request.getfixturevalue(
        test_router_data
    )

    for conf in test_routes:
        router.decorate_route(*conf)

    mock_app.add_router(expected_prefix, router)

    calls = [call(*conf) for conf in prefixed_routes]
    mock_app.decorate_route.assert_has_calls(calls)

    found_routes = []
    for route in mock_app.get_routes(""):
        assert route in prefixed_routes
        assert route not in found_routes
        found_routes.append(route)

    assert len(found_routes) == len(prefixed_routes)
