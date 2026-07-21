from fastapi import APIRouter, Depends
from fastapi.requests import Request

from app.auth import CurrentUser, get_current_user
from app.templating import render

router = APIRouter()


@router.get("/")
def landing(request: Request, user: CurrentUser = Depends(get_current_user)):
    return render(request, "landing.html", user=user)
