from rest_framework import serializers

from gateway.customers.models import Address, Customer


class AddressSerializer(serializers.ModelSerializer[Address]):
    class Meta:
        model = Address
        fields = ["id", "label", "line1", "grid_x", "grid_y", "notes"]


class CustomerSerializer(serializers.ModelSerializer[Customer]):
    addresses = AddressSerializer(many=True, read_only=True)

    class Meta:
        model = Customer
        fields = ["id", "name", "email", "phone", "addresses"]
