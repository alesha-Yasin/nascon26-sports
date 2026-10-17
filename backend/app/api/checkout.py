"""
POST /audit/v1/checkout — Concurrency-safe merchandise purchase
GET  /audit/v1/inventory/{variant_id} — Current stock
"""
import uuid
import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from app.core.database import get_db
from app.core.signing import sign_payload, canonical_json
from app.models.models import ProductVariant, Order, DiscountCode
from app.services.pdf import generate_receipt_pdf

router = APIRouter()

# In-memory lock for concurrency safety (per variant)
_locks: dict = {}
_locks_lock = asyncio.Lock()


async def _get_variant_lock(variant_id: str) -> asyncio.Lock:
    async with _locks_lock:
        if variant_id not in _locks:
            _locks[variant_id] = asyncio.Lock()
        return _locks[variant_id]


@router.post("/audit/v1/checkout")
async def checkout(body: dict, db: AsyncSession = Depends(get_db)):
    order_id = body.get("order_id")
    customer_id = body.get("customer_id")
    items = body.get("items", [])
    discount_code_str = body.get("discount_code")
    payment = body.get("payment", {})
    payment_token = payment.get("token", "")

    # Validation
    if not order_id or not customer_id or not items:
        raise HTTPException(status_code=400, detail={"error": {
            "code": "VALIDATION_ERROR", "message": "order_id, customer_id, items required",
            "details": {"fields": ["order_id", "customer_id", "items"]}
        }})

    if not (1 <= len(items) <= 10):
        raise HTTPException(status_code=400, detail={"error": {
            "code": "VALIDATION_ERROR", "message": "items must be 1-10",
            "details": {"fields": ["items"]}
        }})

    # Idempotency: check existing order
    existing_order = await db.get(Order, order_id)
    if existing_order:
        body_items = sorted(items, key=lambda x: x["variant_id"])
        stored_items = sorted(existing_order.items, key=lambda x: x["variant_id"])
        if (existing_order.customer_id == customer_id and stored_items == body_items and
                existing_order.payment_token == payment_token):
            # Same request — return stored result
            return _build_order_response(existing_order)
        raise HTTPException(status_code=409, detail={"error": {
            "code": "DUPLICATE_ORDER_ID",
            "message": f"Order {order_id} already exists with different body",
            "details": {"order_id": order_id}
        }})

    # Validate variant ids and discount
    variant_ids = [item["variant_id"] for item in items]
    if len(set(variant_ids)) != len(variant_ids):
        raise HTTPException(status_code=400, detail={"error": {
            "code": "VALIDATION_ERROR", "message": "Duplicate variant_ids",
            "details": {"fields": ["items"]}
        }})

    variants = {}
    for item in items:
        vid = item["variant_id"]
        qty = item.get("quantity", 1)
        if not isinstance(qty, int) or not (1 <= qty <= 10):
            raise HTTPException(status_code=400, detail={"error": {
                "code": "VALIDATION_ERROR", "message": f"quantity must be 1-10 for {vid}",
                "details": {"fields": ["items"]}
            }})
        v = await db.get(ProductVariant, vid)
        if not v:
            raise HTTPException(status_code=404, detail={"error": {
                "code": "VARIANT_NOT_FOUND", "message": f"Variant {vid} not found",
                "details": {"variant_id": vid}
            }})
        variants[vid] = (v, qty)

    # Validate discount code
    discount_pct = 0
    if discount_code_str:
        dc = await db.get(DiscountCode, discount_code_str)
        if not dc:
            raise HTTPException(status_code=400, detail={"error": {
                "code": "INVALID_DISCOUNT_CODE",
                "message": f"Unknown discount code: {discount_code_str}",
                "details": {}
            }})
        discount_pct = dc.discount_percent

    # Compute totals
    item_details = []
    subtotal = 0
    for item in items:
        vid = item["variant_id"]
        qty = item["quantity"]
        v, _ = variants[vid]
        unit_price = v.price_minor
        subtotal += unit_price * qty
        item_details.append({
            "variant_id": vid, "quantity": qty, "unit_price_minor": unit_price
        })

    discount_minor = subtotal * discount_pct // 100
    total_minor = subtotal - discount_minor

    # ── Concurrency-safe stock reservation using DB-level locking ──
    # Lock variants alphabetically to avoid deadlocks
    sorted_vids = sorted(variant_ids)

    from sqlalchemy import text
    async with db.begin():
        # Lock all rows FOR UPDATE
        for vid in sorted_vids:
            qty = variants[vid][1]
            result = await db.execute(
                select(ProductVariant).where(ProductVariant.variant_id == vid).with_for_update()
            )
            v = result.scalar_one_or_none()
            if not v or v.stock < qty:
                await db.rollback()
                raise HTTPException(status_code=409, detail={"error": {
                    "code": "OUT_OF_STOCK",
                    "message": f"Variant {vid} has no stock left.",
                    "details": {"variant_id": vid}
                }})

        # Mock payment gateway
        auth_id = f"auth_{uuid.uuid4().hex[:8]}"
        cap_id = None

        if payment_token == "tok_declined":
            await db.rollback()
            raise HTTPException(status_code=402, detail={"error": {
                "code": "PAYMENT_DECLINED", "message": "Payment declined by gateway", "details": {}
            }})
        elif payment_token == "tok_capture_fail":
            # Auth succeeds, capture fails — release stock
            await db.rollback()
            raise HTTPException(status_code=402, detail={"error": {
                "code": "PAYMENT_CAPTURE_FAILED",
                "message": "Payment capture failed", "details": {}
            }})

        # tok_success — commit reservation
        cap_id = f"cap_{uuid.uuid4().hex[:8]}"
        for vid in sorted_vids:
            qty = variants[vid][1]
            await db.execute(
                update(ProductVariant)
                .where(ProductVariant.variant_id == vid)
                .values(stock=ProductVariant.stock - qty)
            )

        paid_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        receipt_payload = {
            "order_id": order_id,
            "customer_id": customer_id,
            "items": item_details,
            "subtotal_minor": subtotal,
            "discount_minor": discount_minor,
            "total_minor": total_minor,
            "currency": "PKR",
            "paid_at": paid_at
        }
        sig = sign_payload(order_id, receipt_payload)
        pdf_b64 = generate_receipt_pdf(order_id, total_minor, "PKR", item_details)

        order = Order(
            order_id=order_id, customer_id=customer_id, status="paid",
            currency="PKR", subtotal_minor=subtotal, discount_minor=discount_minor,
            total_minor=total_minor, items=item_details,
            payment_token=payment_token, authorization_id=auth_id,
            capture_id=cap_id, payment_state="captured",
            receipt_payload=receipt_payload, receipt_signature=sig,
            receipt_pdf_base64=pdf_b64, paid_at=datetime.now(timezone.utc)
        )
        db.add(order)
        await db.flush()

    return _build_order_response(order)


def _build_order_response(order: Order) -> dict:
    return {
        "order_id": order.order_id,
        "status": order.status,
        "currency": order.currency,
        "items": order.items,
        "subtotal_minor": order.subtotal_minor,
        "discount_minor": order.discount_minor,
        "total_minor": order.total_minor,
        "payment": {
            "authorization_id": order.authorization_id,
            "capture_id": order.capture_id,
            "state": order.payment_state
        },
        "receipt": {
            "payload": order.receipt_payload,
            "signature": order.receipt_signature,
            "pdf_base64": order.receipt_pdf_base64
        }
    }


@router.get("/audit/v1/inventory/{variant_id}")
async def get_inventory(variant_id: str, db: AsyncSession = Depends(get_db)):
    v = await db.get(ProductVariant, variant_id)
    if not v:
        raise HTTPException(status_code=404, detail={"error": {
            "code": "VARIANT_NOT_FOUND", "message": f"Variant {variant_id} not found",
            "details": {"variant_id": variant_id}
        }})
    return {"variant_id": variant_id, "stock": v.stock, "reserved": 0}
