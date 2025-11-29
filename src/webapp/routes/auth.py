from fastapi import APIRouter, Request

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/")
async def auth(request: Request):
    print('AUTHAUTHAUTHAUTHAUTH')
    print(await request.json())
