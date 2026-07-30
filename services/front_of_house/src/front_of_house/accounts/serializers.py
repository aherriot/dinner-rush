from typing import Any

from rest_framework import serializers


class CustomerTokenRequestSerializer(serializers.Serializer[Any]):
    email = serializers.EmailField()


class StaffTokenRequestSerializer(serializers.Serializer[Any]):
    username = serializers.CharField()
    password = serializers.CharField()


class SpeedSerializer(serializers.Serializer[Any]):
    speed = serializers.IntegerField()


class TokenRequestSerializer(serializers.Serializer[Any]):
    """Schema-only shape for `POST /auth/token` — either `{email}` (customer)
    or `{username, password}` (staff); `TokenView` validates the real branch
    with `CustomerTokenRequestSerializer`/`StaffTokenRequestSerializer`."""

    email = serializers.EmailField(required=False)
    username = serializers.CharField(required=False)
    password = serializers.CharField(required=False)


class TokenResponseSerializer(serializers.Serializer[Any]):
    access = serializers.CharField()
    refresh = serializers.CharField()
