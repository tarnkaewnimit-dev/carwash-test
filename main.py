import os
import omise
from fastapi import FastAPI, Request
from pydantic import BaseModel

app = FastAPI()

# โหลด API KEY
omise.api_secret = os.getenv("OMISE_SECRET_KEY")
omise.api_public = os.getenv("OMISE_PUBLIC_KEY")

# เก็บสถานะชำระเงินใน memory
# production ให้ใช้ Redis / Database
payment_status = {}

class PaymentRequest(BaseModel):
    amount: int
    order_id: str


@app.post("/create_qr")
def create_qr(data: PaymentRequest):
    """
    สร้าง QR PromptPay ผ่าน Omise
    """
    charge = omise.Charge.create(
        amount=data.amount * 100,   # แปลงเป็นสตางค์
        currency="thb",
        description=f"carwash-{data.order_id}",
        source={
            "type": "promptpay"
        }
    )

   # ดึง QR code URL ที่ถูกต้อง
    qr_url = (
        charge.source.scannable_code.image.download_uri
        if charge.source and charge.source.scannable_code
        else None
    )

    if not qr_url:
        raise Exception("ERROR: No QR Code returned from Omise")

    # เก็บสถานะ
    payment_status[data.order_id] = {
        "paid": False,
        "charge_id": charge.id
    }

    return {
        "qr_image": qr_url,
        "charge_id": charge.id,
        "order_id": data.order_id
    }


@app.post("/webhook/omise")
async def omise_webhook(request: Request):
    payload = await request.json()

    if payload["object"] == "event" and payload["key"] == "charge.complete":
        charge = payload["data"]

        if charge["paid"]:
            # หา order_id จาก description
            desc = charge.get("description", "")
            if desc.startswith("carwash-"):
                order_id = desc.replace("carwash-", "")

                payment_status[order_id]["paid"] = True

    return {"status": "ok"}


@app.get("/payment_status")
def check(order_id: str):
    """
    Raspberry Pi เรียกเพื่อตรวจสอบว่าเงินเข้าแล้วหรือยัง
    """
    status = payment_status.get(order_id, {"paid": False})
    return status

