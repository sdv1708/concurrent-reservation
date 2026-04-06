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

    # ── Routers ─────────────────────────────────────────────────────────────────
    from app.routers import auth
    app.include_router(auth.router)

    from app.routers import users;           app.include_router(users.router)
    from app.routers import hotels_admin;    app.include_router(hotels_admin.router)
    from app.routers import rooms_admin;     app.include_router(rooms_admin.router)
    from app.routers import inventory_admin; app.include_router(inventory_admin.router)
    from app.routers import hotels_browse;   app.include_router(hotels_browse.router)
    from app.routers import bookings;        app.include_router(bookings.router)
    from app.routers import webhooks;        app.include_router(webhooks.router)

    # ── Exception handlers ──────────────────────────────────────────────────
    # Note: Global exception handlers can be configured here.
    #   from app.exceptions.handlers import (not_found_handler, unauthorized_handler,
    #                                         access_denied_handler, generic_handler)
    #   from app.exceptions.custom import (ResourceNotFoundError, UnauthorizedError, AccessDeniedError)
    #   app.add_exception_handler(ResourceNotFoundError, not_found_handler)
    #   app.add_exception_handler(UnauthorizedError,     unauthorized_handler)
    #   app.add_exception_handler(AccessDeniedError,     access_denied_handler)
    #   app.add_exception_handler(Exception,             generic_handler)

    return app


app = create_app()
