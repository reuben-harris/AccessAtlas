from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from io import BytesIO
from pathlib import Path

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify
from PIL import Image, ImageOps, UnidentifiedImageError
from simple_history.utils import update_change_reason

from .models import SitePhoto

THUMBNAIL_SIZE = (640, 640)
EXIF_DATE_TAGS = (36867, 36868, 306)


@dataclass(frozen=True)
class SitePhotoGroup:
    label: str
    photos: list[SitePhoto]
    missing_taken_date: bool = False


@dataclass(frozen=True)
class ThumbnailResult:
    file: ContentFile
    width: int
    height: int


def extract_taken_date(image_file):
    """Return the EXIF taken date when an uploaded photo contains one."""

    try:
        image_file.seek(0)
        with Image.open(image_file) as image:
            exif = image.getexif()
            for tag in EXIF_DATE_TAGS:
                raw_value = exif.get(tag)
                if not raw_value:
                    continue
                try:
                    return datetime.strptime(str(raw_value), "%Y:%m:%d %H:%M:%S").date()
                except ValueError:
                    continue
    except UnidentifiedImageError:
        return None
    except OSError:
        return None
    finally:
        image_file.seek(0)
    return None


def build_thumbnail_file(image_file) -> ThumbnailResult:
    """Build a JPEG thumbnail and capture original dimensions for the viewer."""

    image_file.seek(0)
    with Image.open(image_file) as image:
        image = ImageOps.exif_transpose(image)
        width, height = image.size
        image.thumbnail(THUMBNAIL_SIZE)
        if image.mode not in {"RGB", "L"}:
            image = image.convert("RGB")
        output = BytesIO()
        image.save(output, format="JPEG", quality=82, optimize=True)
        output.seek(0)
        content = ContentFile(output.read())
    image_file.seek(0)
    return ThumbnailResult(file=content, width=width, height=height)


def thumbnail_name_for(filename: str) -> str:
    stem = slugify(Path(filename).stem) or "photo"
    return f"{stem}-thumbnail.jpg"


@transaction.atomic
def create_site_photo(*, site, user, image_file) -> SitePhoto:
    """Create a site photo with metadata and its gallery thumbnail."""

    taken_date = extract_taken_date(image_file)
    thumbnail = build_thumbnail_file(image_file)
    photo = SitePhoto(
        site=site,
        image=image_file,
        image_width=thumbnail.width,
        image_height=thumbnail.height,
        taken_date=taken_date,
        uploaded_by=user,
    )
    photo.thumbnail.save(
        thumbnail_name_for(image_file.name), thumbnail.file, save=False
    )
    photo._change_reason = "Uploaded site photo"
    photo.save()
    return photo


def group_visible_site_photos(photos: list[SitePhoto]) -> list[SitePhotoGroup]:
    """Group gallery photos by taken date, keeping unknown metadata at the end."""

    dated_groups: dict[date, list[SitePhoto]] = {}
    unknown_date_photos: list[SitePhoto] = []
    for photo in photos:
        if photo.taken_date is None:
            unknown_date_photos.append(photo)
        else:
            dated_groups.setdefault(photo.taken_date, []).append(photo)

    groups = [
        SitePhotoGroup(label=taken_date.strftime("%d %b %Y"), photos=group_photos)
        for taken_date, group_photos in sorted(dated_groups.items(), reverse=True)
    ]
    if unknown_date_photos:
        groups.append(
            SitePhotoGroup(
                label="Unknown date",
                photos=unknown_date_photos,
                missing_taken_date=True,
            )
        )
    return groups


@transaction.atomic
def hide_site_photo(*, photo: SitePhoto, user) -> SitePhoto:
    photo.hidden = True
    photo.hidden_at = timezone.now()
    photo.hidden_by = user
    photo.save(update_fields=["hidden", "hidden_at", "hidden_by"])
    update_change_reason(photo, "Hidden site photo")
    return photo
