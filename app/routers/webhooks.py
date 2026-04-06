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
    """
    POST /webhook/payment — Phase 12. Called by Stripe after a successful payment.

    This endpoint has NO user authentication — it's called by Stripe's servers, not a user.
    Instead, it verifies the request using a webhook secret (cryptographic signature).

    === REFERENCE: Steps 1–3 are already implemented below. Your job is Step 4. ===

    Step 1: Read the raw request body.
      - MUST use `await request.body()` — NEVER `await request.json()`
      - Why? Stripe signs the raw bytes. If you parse JSON first, the bytes change
        and the signature check will fail.

    Step 2: Verify Stripe's signature.
      - stripe.Webhook.construct_event() validates the signature using your webhook secret
      - If tampered → raises SignatureVerificationError → we return 400

    Step 3: Check the event type.
      - We only care about "checkout.session.completed"
      - All other event types are safely ignored (Stripe expects a 2xx response)

    Step 4: YOUR TURN — call booking_service.confirm_booking(db, session_id).
      - session_id is already extracted for you below
      - The service will: find the booking, lock inventory with SELECT FOR UPDATE,
        move reserved_count → book_count, and set status = CONFIRMED

    Note: this endpoint returns 204 (no body). Stripe just needs to know we received it.
    """
    # Step 1: Read raw bytes — NEVER do request.json() here
    payload = await request.body()

    # Step 2: Verify Stripe signature — raises 400 if tampered
    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, settings.stripe_webhook_secret
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(400, "Invalid Stripe signature")

    # Step 3: Handle the event type we care about
    if event["type"] == "checkout.session.completed":
        session_id = event["data"]["object"]["id"]
        # Step 4: Confirm the booking — converts reserved_count → book_count, sets status = CONFIRMED
        booking_service.confirm_booking(db, session_id)

    # Return 204 (no content) for all other event types — Stripe expects a 2xx
