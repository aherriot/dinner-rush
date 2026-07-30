from drf_spectacular.utils import extend_schema
from rest_framework.generics import ListAPIView, get_object_or_404
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from front_of_house.catalog.models import MenuItem
from front_of_house.catalog.serializers import MenuAvailabilitySerializer, MenuItemSerializer
from front_of_house.common.permissions import IsManager


class MenuListView(ListAPIView[MenuItem]):
    """`GET /menu` — every item, `available` included so a shortage scenario
    can grey items out client-side rather than removing them."""

    queryset = MenuItem.objects.all()
    serializer_class = MenuItemSerializer
    permission_classes = [AllowAny]


class MenuAvailabilityView(APIView):
    """`POST /admin/menu/{sku}/availability` — manager only, SPEC.md §3.2."""

    permission_classes = [IsManager]

    @extend_schema(request=MenuAvailabilitySerializer, responses=MenuItemSerializer)
    def post(self, request: Request, sku: str) -> Response:
        item = get_object_or_404(MenuItem, sku=sku)
        serializer = MenuAvailabilitySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item.available = serializer.validated_data["available"]
        item.save(update_fields=["available"])
        return Response(MenuItemSerializer(item).data)
