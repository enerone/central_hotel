from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from app.auth.dependencies import require_auth
from app.auth.models import User
from app.core.templates import templates

router = APIRouter(prefix="/dashboard")


@router.get("", response_class=HTMLResponse)
async def dashboard_index(request: Request, user: User = Depends(require_auth)):
    return templates.TemplateResponse(
        request, "dashboard/index.html", {"user": user}
    )
