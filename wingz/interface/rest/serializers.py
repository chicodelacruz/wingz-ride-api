from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from wingz.domain.core.models import User
from wingz.domain.rides.models import Ride, RideEvent


class RideUserSerializer(serializers.ModelSerializer):
    """The rider/driver representation embedded in a ride.

    Deliberately excludes password, permissions and staff flags: this is participant
    information attached to a ride, not an account management payload.
    """

    class Meta:
        model = User
        fields = ["id_user", "role", "first_name", "last_name", "email", "phone_number"]
        read_only_fields = fields


class UserSerializer(serializers.ModelSerializer):
    """Full representation for the user endpoint.

    Distinct from RideUserSerializer, which is the read-only view embedded in a ride.
    This one accepts writes, so it has to deal with passwords: write-only on the way
    in, hashed through the manager rather than assigned to the field, and never
    present on the way out.
    """

    password = serializers.CharField(
        write_only=True,
        required=False,
        style={"input_type": "password"},
        validators=[validate_password],
    )

    class Meta:
        model = User
        fields = [
            "id_user",
            "role",
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "password",
            "is_active",
        ]
        read_only_fields = ["id_user"]

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        return User.objects.create_user(password=password, **validated_data)

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        user = super().update(instance, validated_data)

        if password:
            user.set_password(password)
            user.save(update_fields=["password"])

        return user


class RideEventSerializer(serializers.ModelSerializer):
    """Ride event representation.

    Writable, so the ride event endpoint can create and update events. Where it is
    embedded in a ride it is declared read_only by the parent serializer, so writes
    are not reachable through that path.
    """

    class Meta:
        model = RideEvent
        fields = ["id_ride_event", "id_ride", "description", "created_at"]
        read_only_fields = ["id_ride_event"]


class RideReadSerializer(serializers.ModelSerializer):
    """Ride representation for list and retrieve.

    `todays_ride_events` is not a model field. It is populated by the filtered
    Prefetch in RideViewSet.get_queryset, which attaches the last 24 hours of events
    to each ride as a plain list attribute. Reading it here is therefore an attribute
    access, not a query — which is the whole point. A SerializerMethodField that
    filtered `obj.ride_events` instead would look equivalent and quietly issue one
    query per ride.
    """

    id_rider = RideUserSerializer(read_only=True)
    id_driver = RideUserSerializer(read_only=True)
    todays_ride_events = RideEventSerializer(many=True, read_only=True)
    distance_km = serializers.SerializerMethodField()

    class Meta:
        model = Ride
        fields = [
            "id_ride",
            "status",
            "id_rider",
            "id_driver",
            "pickup_latitude",
            "pickup_longitude",
            "dropoff_latitude",
            "dropoff_longitude",
            "pickup_time",
            "todays_ride_events",
            "distance_km",
        ]
        read_only_fields = fields

    def get_distance_km(self, obj):
        """Distance from the point supplied when ordering by distance.

        Read from the annotation with getattr, so this stays an attribute access and
        costs no query. Absent unless the request asked for a distance ordering.
        """
        distance = getattr(obj, "distance_km", None)
        return None if distance is None else round(distance, 3)

    def to_representation(self, instance):
        representation = super().to_representation(instance)

        # Only meaningful when the request supplied a point to measure from. Omitting
        # it entirely is clearer than returning null on every ordinary list request.
        if representation.get("distance_km") is None:
            representation.pop("distance_km", None)

        return representation


class RideWriteSerializer(serializers.ModelSerializer):
    """Ride representation for create and update.

    Separate from the read serializer for two reasons: writes take participant ids
    rather than nested objects, and a freshly created instance has no
    `todays_ride_events` attribute, since the prefetch that supplies it only runs on
    list and retrieve. Reusing the read serializer here would raise AttributeError on
    every successful POST.
    """

    class Meta:
        model = Ride
        fields = [
            "id_ride",
            "status",
            "id_rider",
            "id_driver",
            "pickup_latitude",
            "pickup_longitude",
            "dropoff_latitude",
            "dropoff_longitude",
            "pickup_time",
        ]
        read_only_fields = ["id_ride"]

    def validate(self, attrs):
        rider = attrs.get("id_rider", getattr(self.instance, "id_rider", None))
        driver = attrs.get("id_driver", getattr(self.instance, "id_driver", None))

        if rider and driver and rider == driver:
            raise serializers.ValidationError({"id_driver": "A ride's driver and rider cannot be the same user."})

        return attrs
