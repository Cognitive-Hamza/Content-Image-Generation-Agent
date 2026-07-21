from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app.auth import CurrentUser

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def render(request: Request, template_name: str, *, user: CurrentUser | None = None, **context):
    """Every template render goes through here so `user` is always available
    for the persistent 'Signed in as X' element, without each route remembering."""
    return templates.TemplateResponse(request=request, name=template_name, context={"user": user, **context})
