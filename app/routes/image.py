from fastapi import APIRouter, Depends, Form, Request

from app.auth import CurrentUser, get_current_user
from app.db import repo_content, repo_images
from app.db.audit import log_action
from app.db.models import GeneratedPost
from app.deps import DbDep, StorageDep
from app.templating import render
from imagegen import config as igcfg
from imagegen.credentials import resolve_api_key
from imagegen.logos import get_accreditation_logos, get_sector_logo
from imagegen.prompting import build_image_prompt, build_system_prompt
from imagegen.providers import generate_image
from pipeline.brief import parse_content_design_brief

router = APIRouter(prefix="/image", tags=["image"])


@router.post("/logo-preview")
def logo_preview(
    request: Request,
    sector: str = Form(...),
    selected_accreds: list[str] = Form([]),
    user: CurrentUser = Depends(get_current_user),
):
    """HTMX fragment: live logo preview, triggered on sector/accreditation changes."""
    return render(
        request, "partials/_logo_preview.html", user=user,
        sector_logo=get_sector_logo(sector), accred_logos=get_accreditation_logos(selected_accreds),
    )


@router.get("/new")
def new_image_form(
    request: Request,
    db: DbDep,
    user: CurrentUser = Depends(get_current_user),
    from_generation_id: int | None = None,
):
    prefill = {}
    source_generation = None
    if from_generation_id:
        source_generation = repo_content.get_generation(db, from_generation_id)
        if source_generation and source_generation.final_content:
            brief = parse_content_design_brief(source_generation.final_content)
            prefill = {
                "headline": brief.headline, "hook": brief.hook_line, "title": brief.title,
            }
    return render(
        request, "image_new.html", user=user,
        sectors=igcfg.ALNAFI_SECTORS, post_types=igcfg.POST_TYPES, badges=igcfg.SESSION_BADGES,
        platform_targets=igcfg.PLATFORM_TARGETS, canvas_presets=igcfg.CANVAS_PRESETS,
        providers=igcfg.PROVIDERS, prefill=prefill, source_generation=source_generation,
    )


@router.post("/generate")
def generate_image_route(
    request: Request,
    db: DbDep,
    storage: StorageDep,
    user: CurrentUser = Depends(get_current_user),
    sector: str = Form(...),
    post_type: str = Form(...),
    badge: str = Form("None"),
    platforms: list[str] = Form([]),
    headline: str = Form(""),
    hook: str = Form(""),
    title: str = Form(""),
    subtitle: str = Form(""),
    body: str = Form(""),
    canvas_size: str = Form("1080x1080"),
    provider_label: str = Form(...),
    quality_tier: str = Form("medium"),
    contact_info: str = Form(""),
    website: str = Form(""),
    cta_text: str = Form(""),
    selected_accreds: list[str] = Form([]),
    generation_id: int | None = Form(None),
):
    provider_id = igcfg.PROVIDERS[provider_label]
    sector_info = igcfg.ALNAFI_SECTORS[sector]
    colors = {"primary": sector_info["color_primary"], "secondary": sector_info["color_secondary"],
              "accent": sector_info["color_accent"]}

    api_key, _source = resolve_api_key(provider_id)

    form_data = {
        "sector": sector, "colors": colors, "canvas_size": canvas_size, "post_type": post_type,
        "platforms": platforms, "badge": badge, "headline": headline, "hook": hook, "title": title,
        "subtitle": subtitle, "body": body, "contact_info": contact_info, "website": website,
        "cta_text": cta_text, "selected_accreds": selected_accreds,
    }
    system_prompt = build_system_prompt(sector_info, colors)
    image_prompt = build_image_prompt(form_data)

    result = generate_image(
        api_key, image_prompt, system_prompt, provider_id, provider_label, quality_tier, canvas_size,
        headline, post_type, sector, selected_accreds, has_contact=bool(contact_info or website),
        storage=storage,
    )

    post = None
    if result.success and result.storage_key:
        post = repo_images.save_post_to_db(
            db, storage_key=result.storage_key, byte_size=len(result.image_bytes or b""),
            image_prompt=image_prompt, system_prompt=system_prompt,
            meta={
                "created_by_user_id": user.id, "sector": sector, "post_type": post_type,
                "canvas_size": canvas_size, "provider": provider_label, "quality": quality_tier,
                "headline": headline, "platforms": platforms, "generation_id": generation_id,
            },
        )
        log_action(db, user_id=user.id, action="post.create", entity_type="generated_post", entity_id=post.id)

    return render(
        request, "partials/_image_result.html", user=user, result=result, post=post,
        image_url=storage.get_url(result.storage_key) if result.storage_key else None,
        image_prompt=image_prompt,
    )


@router.get("/{post_id}")
def image_detail(request: Request, post_id: int, db: DbDep, storage: StorageDep, user: CurrentUser = Depends(get_current_user)):
    post = db.get(GeneratedPost, post_id)
    image_url = storage.get_url(post.storage_key) if post else None
    return render(request, "image_result.html", user=user, post=post, image_url=image_url)
