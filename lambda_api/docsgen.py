import inspect
from collections import defaultdict
from typing import Any, Callable

from lambda_api.core import InvokeTemplate, LambdaAPI
from lambda_api.utils import json_dumps, json_loads


class OpenApiGenerator:
    def __init__(self, app: LambdaAPI):
        self.schema_id = app.schema_id
        self.route_table = app.route_table
        self.prefix = app.prefix

    def get_schema(self):
        schema = {
            "paths": defaultdict(lambda: defaultdict(dict)),
            "components": {"schemas": {}},
        }

        if self.schema_id:
            schema["id"] = self.schema_id

        for path, endpoint in self.route_table.items():
            for method, func in endpoint.items():
                self._add_endpoint_to_schema(schema, path, method, func)

        txt_schema = json_dumps(schema).replace("$defs", "components/schemas")
        return json_loads(txt_schema)

    def _add_endpoint_to_schema(
        self, schema: dict[str, Any], path: str, method: str, func: Callable
    ):
        components = schema["components"]["schemas"]

        template: InvokeTemplate = func.__invoke_template__  # type: ignore
        full_path = self.prefix + path
        func_schema = schema["paths"][full_path][method.lower()]

        if func.__doc__:
            func_schema["description"] = inspect.getdoc(func)

        if template.request:
            # Handle headers
            headers = (
                template.request.model_fields["headers"].annotation
            ).model_json_schema()  # type: ignore
            required_keys = headers.get("required", [])

            func_schema["parameters"] = func_schema.get("parameters", []) + [
                {
                    "in": "header",
                    "name": k.replace("_", "-").title(),
                    "schema": v,
                }
                | ({"required": True} if k in required_keys else {})
                for k, v in headers["properties"].items()
            ]

            # Handle the request config
            if config := template.request.request_config:
                if auth_name := config.auth_name:
                    func_schema["security"] = [{auth_name: []}]

        # Handle QUERY parameters
        if template.params:
            params = template.params.model_json_schema()
            required_keys = params.get("required", [])

            components.update(params.pop("$defs", {}))

            func_schema["parameters"] = func_schema.get("parameters", []) + [
                {"in": "query", "name": k, "schema": v}
                | ({"required": True} if k in required_keys else {})
                for k, v in params["properties"].items()
            ]

        # Handle BODY parameters
        if template.body:
            body = template.body.model_json_schema()
            comp_title = body["title"]

            components[comp_title] = body
            components.update(body.pop("$defs", {}))

            func_schema["requestBody"] = {
                "content": {
                    "application/json": {
                        "schema": {"$ref": f"#/components/schemas/{comp_title}"}
                    }
                }
            }

        # Handle response schema
        if template.response:
            response = template.response.model_json_schema(mode="serialization")
            comp_title = response["title"]

            components[comp_title] = response
            components.update(response.pop("$defs", {}))

            func_schema["responses"] = {
                str(template.status): {
                    "content": {
                        "application/json": {
                            "schema": {"$ref": f"#/components/schemas/{comp_title}"}
                        }
                    }
                }
            }
        else:
            func_schema["responses"] = {
                str(template.status): {"description": "No response body"}
            }

        # Handle tags
        if template.tags:
            func_schema["tags"] = template.tags
