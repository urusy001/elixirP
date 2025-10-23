from fastapi import APIRouter, Request, Depends, HTTPException

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

@router.get("/amocrm")
async def get_webhook(request: Request):
    print(await request.json())

@router.post("/amocrm")
async def get_webhook(request: Request):
    print(await request.json())

@router.put("/amocrm")
async def get_webhook(request: Request):
    print(await request.json())

@router.delete("/amocrm")
async def get_webhook(request: Request):
    print(await request.json())
