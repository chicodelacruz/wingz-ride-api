from django.urls import include, path
from rest_framework.routers import DefaultRouter

from wingz.interface.rest.views import RideEventViewSet, RideViewSet, UserViewSet

router = DefaultRouter()
router.register("rides", RideViewSet, basename="ride")
router.register("ride-events", RideEventViewSet, basename="rideevent")
router.register("users", UserViewSet, basename="user")

urlpatterns = [
    path("", include(router.urls)),
]
