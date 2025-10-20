from fastapi import HTTPException, Request

from src.config import API_KEY


async def ensure_api_key(request: Request, header_name: str = "X-Api-Key") -> None:
    api_key = request.headers.get(header_name)

    if api_key is None:
        raise HTTPException(status_code=401, detail=f"{header_name} header is missing")

    if api_key.startswith("Bearer "):
        api_key = api_key.split("Bearer ")[-1]

    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
