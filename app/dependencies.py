# Convenience re-exports so routers can import from one place
# instead of importing from both database.py and security/guards.py

from app.database import get_db           # noqa — re-exported
from app.security.guards import get_current_user, require_hotel_manager  # noqa — re-exported
