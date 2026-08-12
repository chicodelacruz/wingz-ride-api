from django.contrib import admin

from wingz.domain.rides.models import Ride, RideEvent


class RideEventInline(admin.TabularInline):
    model = RideEvent
    extra = 0
    fields = ("description", "created_at")
    ordering = ("-created_at",)
    # A ride can accumulate a lot of events; the inline is for context, not for
    # scrolling through the whole history.
    max_num = 20


@admin.register(Ride)
class RideAdmin(admin.ModelAdmin):
    list_display = ("id_ride", "status", "id_rider", "id_driver", "pickup_time")
    list_filter = ("status", "pickup_time")
    search_fields = (
        "id_ride",
        "id_rider__email",
        "id_driver__email",
        "id_rider__last_name",
        "id_driver__last_name",
    )
    date_hierarchy = "pickup_time"
    # Autocomplete rather than a plain select: the user table is expected to be large,
    # and a select widget would load every row into the page.
    autocomplete_fields = ("id_rider", "id_driver")
    inlines = [RideEventInline]

    def get_queryset(self, request):
        # The changelist shows both participants, which would otherwise be a query
        # per row.
        return super().get_queryset(request).select_related("id_rider", "id_driver")


@admin.register(RideEvent)
class RideEventAdmin(admin.ModelAdmin):
    list_display = ("id_ride_event", "id_ride", "description", "created_at")
    list_filter = ("created_at",)
    search_fields = ("description", "id_ride__id_ride")
    date_hierarchy = "created_at"
    autocomplete_fields = ("id_ride",)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("id_ride")
