from django.urls import include, path
from rest_framework.routers import DefaultRouter

from wingz.interface.rest.views import RideViewSet

router = DefaultRouter()
router.register("rides", RideViewSet, basename="ride")

urlpatterns = [
    path("", include(router.urls)),
]
