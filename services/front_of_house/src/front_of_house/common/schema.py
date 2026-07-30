from drf_spectacular.extensions import OpenApiAuthenticationExtension


class JWTRoleAuthenticationScheme(OpenApiAuthenticationExtension):  # type: ignore[no-untyped-call]
    target_class = "front_of_house.common.authentication.JWTRoleAuthentication"
    name = "bearerAuth"

    def get_security_definition(self, auto_schema: object) -> dict[str, str]:
        return {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
