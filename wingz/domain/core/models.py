from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.db.models.functions import Upper

from wingz.domain.core.managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    """Application user.

    Column names follow the assessment's User table rather than Django's defaults,
    hence the explicit primary key name and db_table.
    """

    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        DRIVER = "driver", "Driver"
        RIDER = "rider", "Rider"

    id_user = models.AutoField(primary_key=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.RIDER)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=30, blank=True)

    # Not in the spec's table, but Django's auth machinery and admin need them.
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    class Meta:
        db_table = "user"
        indexes = [
            # The ride list filters by rider email case-insensitively. `unique=True`
            # already gives a plain btree index for exact matches, but Django's
            # `iexact` compiles to `UPPER("email"::text) = UPPER(%s)` on PostgreSQL,
            # which that index cannot serve — so the functional index has to use
            # Upper() to match the SQL the ORM actually emits.
            models.Index(Upper("email"), name="user_email_upper_idx"),
        ]

    def __str__(self):
        return f"{self.get_full_name()} <{self.email}>"

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def get_short_name(self):
        return self.first_name

    @property
    def is_admin_role(self):
        """Authorisation for this API is by `role`, deliberately not by is_staff.

        is_staff governs Django admin access, which is a different question from
        whether the user may call the API.
        """
        return self.role == self.Role.ADMIN
