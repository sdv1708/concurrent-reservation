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
    REFERENCE — Stripe webhook endpoint.

    CRITICAL: Must read raw bytes (not request.json()).
    Stripe signs the raw payload — parsing it first would break signature verification.

    After successful payment:
      - Set booking.status = CONFIRMED
      - SELECT FOR UPDATE inventory rows
      - For each row: reserved_count = max(0, reserved_count - rooms_count)
                      book_count += rooms_count
      - COMMIT
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
        # TODO: Call booking_service.confirm_booking(db, session_id)
        # Hint:
        #   booking = db.query(Booking).filter(Booking.payment_session_id == session_id).first()
        #   SELECT FOR UPDATE inventory rows → move reserved_count to book_count
        #   Set booking.status = CONFIRMED
        #   COMMIT
        pass

    # Return 204 (no content) for all other event types — Stripe expects a 2xx
