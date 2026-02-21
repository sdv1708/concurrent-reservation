# Import all models so Alembic can discover them during autogenerate migrations.
# Also makes "from app.models import User" possible from anywhere.

from app.models.user import User, UserRole           # noqa
from app.models.hotel import Hotel                   # noqa
from app.models.room import Room                     # noqa
from app.models.inventory import Inventory           # noqa
from app.models.guest import Guest                   # noqa
from app.models.booking import Booking, booking_guest  # noqa
