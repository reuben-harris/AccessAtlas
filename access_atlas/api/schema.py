from drf_spectacular.extensions import OpenApiAuthenticationExtension


class ApiTokenAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "access_atlas.api.authentication.ApiTokenAuthentication"
    name = "TokenAuth"

    def get_security_definition(self, auto_schema):
        return {
            "type": "apiKey",
            "in": "header",
            "name": "Authorization",
            "description": "Use `Token <api token>`.",
        }
