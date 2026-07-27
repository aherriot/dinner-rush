from dataclasses import dataclass
from typing import cast

from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken

VALID_ROLES = {"customer", "manager", "kitchen"}


@dataclass(frozen=True)
class Actor:
    """The authenticated principal on `request.user` — never a Django `User`.

    Customers have no login credentials of their own (SPEC.md §1.1 has no
    `user_id` on `customer`); staff wrap `django.contrib.auth.User`. Both end
    up as one of these after token verification, so views and permissions
    only ever deal with `role` + the relevant id claim.
    """

    role: str
    customer_id: str | None = None
    staff_id: str | None = None
    scope: tuple[str, ...] = ()

    @property
    def is_authenticated(self) -> bool:
        return True


def get_actor(request: Request) -> Actor:
    """`request.user` is typed `User | AnonymousUser` by the DRF stubs since
    that's the ordinary case; `JWTRoleAuthentication` always puts an `Actor`
    there instead, so every view reads it through this cast in one place."""
    return cast(Actor, request.user)


class JWTRoleAuthentication(BaseAuthentication):
    """Verifies the access token and exposes its claims as `request.user`."""

    def authenticate(self, request: Request) -> tuple[Actor, AccessToken] | None:
        header = get_authorization_header(request).split()
        if not header or header[0].lower() != b"bearer":
            return None
        if len(header) != 2:
            raise AuthenticationFailed("malformed Authorization header")

        try:
            # simplejwt's own type hint for `token` is `Token | None`, but the
            # documented and actual runtime usage is a raw token string.
            access = AccessToken(header[1].decode())  # type: ignore[arg-type]
        except TokenError as exc:
            raise AuthenticationFailed(str(exc)) from exc

        role = access.get("role")
        if role not in VALID_ROLES:
            raise AuthenticationFailed("token is missing a valid role claim")

        actor = Actor(
            role=role,
            customer_id=access.get("customer_id"),
            staff_id=access.get("staff_id"),
            scope=tuple(access.get("scope", [])),
        )
        return (actor, access)
