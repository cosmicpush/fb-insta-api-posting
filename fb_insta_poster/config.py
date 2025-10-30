import os
from dataclasses import dataclass
from typing import Optional

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    load_dotenv = None


if load_dotenv:  # pragma: no branch - simple optional load
    load_dotenv()


def _clean_optional(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _normalize_prefix(value: Optional[str]) -> Optional[str]:
    cleaned = _clean_optional(value)
    if cleaned is None:
        return None
    return cleaned.strip("/")


def _get_required(name: str, default: Optional[str] = None) -> str:
    value = os.environ.get(name, default)
    if value is None or value == "":
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _get_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    value = value.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Invalid boolean value for {name}: {value}")


@dataclass(frozen=True)
class Settings:
    bucket: str
    object_prefix: Optional[str]
    jpeg_prefix: Optional[str]
    presign_expiration_seconds: int
    media_wait_seconds: int
    media_poll_interval_seconds: int
    anthropic_api_key: str
    claude_model: str
    claude_max_tokens: int
    caption_fallback: str
    instagram_user_id: Optional[str]
    facebook_page_id: Optional[str]
    meta_access_token: Optional[str]
    telegram_bot_token: Optional[str]
    telegram_chat_id: Optional[str]
    enable_captioning: bool
    oci_namespace: str
    oci_region: Optional[str]
    oci_profile: Optional[str]


def load_settings() -> Settings:
    bucket = _get_required("FB_INSTA_BUCKET", "12amstories")
    object_prefix = _normalize_prefix(os.environ.get("FB_INSTA_PREFIX"))
    jpeg_prefix = _normalize_prefix(os.environ.get("FB_INSTA_JPEG_PREFIX") or "converted")

    presign_expiration_seconds = int(
        os.environ.get("FB_INSTA_PRESIGN_EXPIRATION_SECONDS", "900")
    )
    media_wait_seconds = int(os.environ.get("FB_INSTA_MEDIA_WAIT_SECONDS", "30"))
    media_poll_interval_seconds = int(os.environ.get("FB_INSTA_STATUS_POLL_SECONDS", "5"))
    claude_max_tokens = int(os.environ.get("FB_INSTA_CLAUDE_MAX_TOKENS", "120"))
    enable_captioning = _get_bool("FB_INSTA_ENABLE_CAPTIONING", True)

    anthropic_key = _clean_optional(os.environ.get("ANTHROPIC_API_KEY"))
    if enable_captioning and not anthropic_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY must be set when FB_INSTA_ENABLE_CAPTIONING is true"
        )

    anthropic_api_key = anthropic_key or ""

    return Settings(
        bucket=bucket,
        object_prefix=object_prefix,
        jpeg_prefix=jpeg_prefix,
        presign_expiration_seconds=presign_expiration_seconds,
        media_wait_seconds=media_wait_seconds,
        media_poll_interval_seconds=media_poll_interval_seconds,
        anthropic_api_key=anthropic_api_key,
        claude_model=os.environ.get(
            "FB_INSTA_CLAUDE_MODEL", "claude-3-5-sonnet-20241022"
        ),
        claude_max_tokens=claude_max_tokens,
        caption_fallback=os.environ.get(
            "FB_INSTA_CAPTION_FALLBACK", "Sharing today's inspiration ✨"
        ),
        instagram_user_id=_clean_optional(os.environ.get("INSTAGRAM_USER_ID")),
        facebook_page_id=_clean_optional(os.environ.get("FACEBOOK_PAGE_ID")),
        meta_access_token=_clean_optional(
            os.environ.get("META_ACCESS_TOKEN")
            or os.environ.get("INSTAGRAM_ACCESS_TOKEN")
            or os.environ.get("FACEBOOK_PAGE_ACCESS_TOKEN")
        ),
        telegram_bot_token=_clean_optional(os.environ.get("TELEGRAM_BOT_TOKEN")),
        telegram_chat_id=_clean_optional(os.environ.get("TELEGRAM_CHAT_ID")),
        enable_captioning=enable_captioning,
        oci_namespace=_get_required("OCI_NAMESPACE"),
        oci_region=_clean_optional(os.environ.get("OCI_REGION")),
        oci_profile=_clean_optional(os.environ.get("OCI_PROFILE")),
    )
