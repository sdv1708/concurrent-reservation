import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.config import settings
from app.services import booking_service

router = APIRouter(prefix="/webhook", tags=["Webhook"])


@router.post("/payment", status_code=204)
async def capture_payment(
    request: Request,
    stripe_signature: str = Header(alias="Stripe-Signature"),
    db: Session = Depends(get_db),
):
    """Handles Stripe webhook events.

    This endpoint is called asynchronously by Stripe. It reads the raw request
    body, verifies the cryptographic signature to ensure authenticity, and processes
    the `checkout.session.completed` event to finalize bookings.

    Args:
        request (Request): The raw incoming HTTP request (required for signature verification).
        stripe_signature (str): The Stripe-Signature header.
        db (Session): The database session.

    Raises:
        HTTPException: If the signature verification fails (400).
    """
    # Raw bytes, not .json() — signature verification hashes the exact body Stripe sent.
    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, settings.stripe_webhook_secret
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(400, "Invalid Stripe signature")

    if event["type"] == "checkout.session.completed":
        session_id = event["data"]["object"]["id"]
        booking_service.confirm_booking(db, session_id)

    # Other event types fall through to here — Stripe requires a 2xx or it retries delivery.
