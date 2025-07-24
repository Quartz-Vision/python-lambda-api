import inspect
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from lambda_api.app import LambdaAPI, RouteWrapper
from lambda_api.utils import json_dumps, json_loads


@dataclass
class EndpointContext:
    template: Any
    func_schema_alias: dict


class OpenApiGenerator:
    def __init__(self, app: LambdaAPI):
        self.app = app
        self.schema_id = app.schema_id
        self.route_table = app.route_table
        self.prefix = app.prefix
        self._schema_cache: dict[str, Any] | None = None
        self.schema: dict[str, Any]
        self.components_alias: dict[str, Any]

    def get_schema(self) -> dict[str, Any]:
        if self._schema_cache is not None:
            return self._schema_cache

        self.schema = {
            "paths": defaultdict(lambda: defaultdict(dict)),
            "components": {"schemas": {}},
        }
        self.components_alias = self.schema["components"]["schemas"]

        if self.schema_id:
            self.schema["id"] = self.schema_id

        for path, endpoint in self.route_table.items():
            for method, func in endpoint.items():
                self._add_endpoint_to_schema(path, method, func)

        txt_schema = json_dumps(self.schema).replace("$defs", "components/schemas")
        self._schema_cache = json_loads(txt_schema)
        return self._schema_cache

    def _add_endpoint_to_schema(self, path: str, method: str, route: RouteWrapper):
        ctx = EndpointContext(
            template=self.app.get_invoke_template(route),
            func_schema_alias=self.schema["paths"][self.prefix + path][method.lower()],
        )
        self._add_description(ctx, route)
        self._add_request_details(ctx)
        self._add_query_params(ctx)
        self._add_body(ctx)
        self._add_response(ctx)
        self._add_tags(ctx)

    def _add_description(self, ctx: EndpointContext, route: RouteWrapper):
        if route.handler.__doc__:
            ctx.func_schema_alias["description"] = inspect.getdoc(route.handler)

    def _add_request_details(self, ctx: EndpointContext):
        if not ctx.template.request:
            return

        # Handle headers
        headers = (
            ctx.template.request.model_fields["headers"].annotation
        ).model_json_schema()  # type: ignore
        required_keys = headers.get("required", [])

        ctx.func_schema_alias["parameters"] = ctx.func_schema_alias.get(
            "parameters", []
        ) + [
            {
                "in": "header",
                "name": k.replace("_", "-").title(),
                "schema": v,
            }
            | ({"required": True} if k in required_keys else {})
            for k, v in headers["properties"].items()
        ]

        # Handle the request config
        if config := ctx.template.request.request_config:
            if auth_name := config.auth_name:
                ctx.func_schema_alias["security"] = [{auth_name: []}]

    def _add_query_params(self, ctx: EndpointContext):
        if not ctx.template.params:
            return
        params = ctx.template.params.model_json_schema()
        required_keys = params.get("required", [])

        self.components_alias.update(params.pop("$defs", {}))

        ctx.func_schema_alias["parameters"] = ctx.func_schema_alias.get(
            "parameters", []
        ) + [
            {"in": "query", "name": k, "schema": v}
            | ({"required": True} if k in required_keys else {})
            for k, v in params["properties"].items()
        ]

    def _add_body(self, ctx: EndpointContext):
        if not ctx.template.body:
            return
        body = ctx.template.body.model_json_schema()
        comp_title = body["title"]

        self.components_alias[comp_title] = body
        self.components_alias.update(body.pop("$defs", {}))

        ctx.func_schema_alias["requestBody"] = {
            "content": {
                "application/json": {
                    "schema": {"$ref": f"#/components/schemas/{comp_title}"}
                }
            }
        }

    def _add_response(self, ctx: EndpointContext):
        if ctx.template.response:
            response = ctx.template.response.model_json_schema(mode="serialization")
            comp_title = response["title"]

            self.components_alias[comp_title] = response
            self.components_alias.update(response.pop("$defs", {}))

            ctx.func_schema_alias["responses"] = {
                str(ctx.template.status): {
                    "content": {
                        "application/json": {
                            "schema": {"$ref": f"#/components/schemas/{comp_title}"}
                        }
                    }
                }
            }
        else:
            ctx.func_schema_alias["responses"] = {
                str(ctx.template.status): {"description": "No response body"}
            }

    def _add_tags(self, ctx: EndpointContext):
        if ctx.template.tags:
            ctx.func_schema_alias["tags"] = ctx.template.tags
