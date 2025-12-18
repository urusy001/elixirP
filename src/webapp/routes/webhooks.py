from fastapi import APIRouter, Request

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.get("/amocrm")
async def get_webhook(request: Request):
    try: print(await request.json())
    except: print(await request.body())



@router.post("/amocrm")
async def get_webhook(request: Request):
    try: print(await request.json())
    except: print(await request.body())


@router.put("/amocrm")
async def get_webhook(request: Request):
    try: print(await request.json())
    except: print(await request.body())


@router.delete("/amocrm")
async def get_webhook(request: Request):
    try: print(await request.json())
    except: print(await request.body())
