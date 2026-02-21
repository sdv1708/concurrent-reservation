import stripe
from fastapi import FastAPI
from app.config import settings

# ── Stripe global init ───────────────────────────────────────────────────────
stripe.api_key = settings.stripe_secret_key


def create_app() -> FastAPI:
    app = FastAPI(
        title="AirBnb API",
        version="1.0.0",
        docs_url="/swagger-ui.html",
    )

    # ── Routers — uncomment each as you complete its phase ──────────────────
    from app.routers import auth
    app.include_router(auth.router)

    # TODO Phase 5:  from app.routers import users;           app.include_router(users.router)
    # TODO Phase 6:  from app.routers import hotels_admin;    app.include_router(hotels_admin.router)
    # TODO Phase 7:  from app.routers import rooms_admin;     app.include_router(rooms_admin.router)
    # TODO Phase 8:  from app.routers import inventory_admin; app.include_router(inventory_admin.router)
    # TODO Phase 9:  from app.routers import hotels_browse;   app.include_router(hotels_browse.router)
    # TODO Phase 11: from app.routers import bookings;        app.include_router(bookings.router)
    # TODO Phase 12: from app.routers import webhooks;        app.include_router(webhooks.router)

    # ── Exception handlers — add after Phase 13 ─────────────────────────────
    # TODO Phase 13:
    #   from app.exceptions.handlers import (not_found_handler, unauthorized_handler,
    #                                         access_denied_handler, generic_handler)
    #   from app.exceptions.custom import (ResourceNotFoundError, UnauthorizedError, AccessDeniedError)
    #   app.add_exception_handler(ResourceNotFoundError, not_found_handler)
    #   app.add_exception_handler(UnauthorizedError,     unauthorized_handler)
    #   app.add_exception_handler(AccessDeniedError,     access_denied_handler)
    #   app.add_exception_handler(Exception,             generic_handler)

    return app


app = create_app()
