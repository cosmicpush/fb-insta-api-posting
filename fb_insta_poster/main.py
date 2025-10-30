import logging
import os
import sys
import time
from typing import Optional

import requests

from .oci_storage import (
    OCIStorageClient,
    OCIStorageError,
    ObjectRef,
    PreauthenticatedRequest,
    choose_random_object,
)
from .claude_caption import (
    ClaudeCaptionError,
    generate_caption_with_type,
)
from .config import load_settings
from .image_utils import ImageProcessingError, convert_png_to_jpeg, derive_jpeg_key
from .meta_api import (
    MetaApiError,
    check_instagram_container,
    create_instagram_media,
    get_facebook_page_details,
    get_instagram_user_details,
    post_facebook_photo,
    publish_instagram_media,
)


def _format_instagram_label(details: Optional[dict], user_id: Optional[str]) -> Optional[str]:
    if not details and not user_id:
        return None

    name = details.get("name") if details else None
    username = details.get("username") if details else None
    handle = f"@{username}" if username else None
    identifier = handle or user_id

    if name and identifier and name != identifier:
        return f"{name} ({identifier})"
    return name or identifier


def _format_facebook_label(details: Optional[dict], page_id: Optional[str]) -> Optional[str]:
    if not details and not page_id:
        return None

    name = details.get("name") if details else None
    if name and page_id and name != page_id:
        return f"{name} ({page_id})"
    return name or page_id


def _send_telegram_message(
    bot_token: Optional[str],
    chat_id: Optional[str],
    message: str,
    logger: logging.Logger,
) -> None:
    if not bot_token or not chat_id:
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        response = requests.post(
            url,
            json={
                "chat_id": chat_id,
                "text": message,
            },
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException as exc:  # pragma: no cover - network failure
        logger.warning("Failed to send Telegram notification: %s", exc)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    logger = logging.getLogger("fb_insta_poster")

    telegram_bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    telegram_chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    try:
        settings = load_settings()
    except (RuntimeError, ValueError) as exc:
        logger.error("Configuration error: %s", exc)
        _send_telegram_message(
            telegram_bot_token,
            telegram_chat_id,
            "\n".join(
                [
                    "❌ Instagram & Facebook poster failed",
                    f"Error: {exc}",
                ]
            ),
            logger,
        )
        return 1

    telegram_bot_token = settings.telegram_bot_token or telegram_bot_token
    telegram_chat_id = settings.telegram_chat_id or telegram_chat_id

    instagram_details: Optional[dict] = None
    facebook_details: Optional[dict] = None

    if settings.meta_access_token:
        if settings.instagram_user_id:
            try:
                instagram_details = get_instagram_user_details(
                    settings.meta_access_token,
                    settings.instagram_user_id,
                )
            except MetaApiError as exc:
                logger.warning("Failed to fetch Instagram account details: %s", exc)

        if settings.facebook_page_id:
            try:
                facebook_details = get_facebook_page_details(
                    settings.meta_access_token,
                    settings.facebook_page_id,
                )
            except MetaApiError as exc:
                logger.warning("Failed to fetch Facebook page details: %s", exc)

    instagram_label = _format_instagram_label(instagram_details, settings.instagram_user_id)
    facebook_label = _format_facebook_label(facebook_details, settings.facebook_page_id)

    caption: Optional[str] = None
    storage: Optional[OCIStorageClient] = None
    selected_object: Optional[ObjectRef] = None
    jpeg_object: Optional[ObjectRef] = None
    par_request: Optional[PreauthenticatedRequest] = None
    instagram_success = False
    facebook_success = False
    instagram_error: Optional[str] = None
    facebook_error: Optional[str] = None
    instagram_media_id: Optional[str] = None
    facebook_post_id: Optional[str] = None

    def finish(result_code: int, *, error: Optional[str] = None) -> int:
        nonlocal par_request

        if par_request and storage:
            try:
                storage.revoke_preauthenticated_request(par_request)
            except OCIStorageError as exc:
                logger.warning("Failed to revoke pre-authenticated request: %s", exc)
            finally:
                par_request = None

        if telegram_bot_token and telegram_chat_id:
            if instagram_success and facebook_success:
                heading = "✅ Instagram & Facebook posts published"
            elif instagram_success or facebook_success:
                heading = "⚠️ Instagram/Facebook poster partially completed"
            else:
                heading = "❌ Instagram & Facebook poster failed"

            lines = [heading]

            if selected_object:
                lines.append(f"Object Key: {selected_object.key}")

            if settings.instagram_user_id and settings.meta_access_token:
                descriptor = instagram_label or settings.instagram_user_id
                if instagram_success:
                    lines.append(f"Instagram: Posted to {descriptor}")
                    if instagram_media_id:
                        lines.append(f"Instagram Media ID: {instagram_media_id}")
                else:
                    lines.append(f"Instagram: Failed for {descriptor}")
                    if instagram_error:
                        lines.append(f"Instagram Error: {instagram_error}")
            else:
                lines.append("Instagram: Skipped (not configured)")

            if settings.facebook_page_id and settings.meta_access_token:
                descriptor = facebook_label or settings.facebook_page_id
                if facebook_success:
                    lines.append(f"Facebook: Posted to {descriptor}")
                    if facebook_post_id:
                        lines.append(f"Facebook Post ID: {facebook_post_id}")
                else:
                    lines.append(f"Facebook: Failed for {descriptor}")
                    if facebook_error:
                        lines.append(f"Facebook Error: {facebook_error}")
            else:
                lines.append("Facebook: Skipped (not configured)")

            if error:
                lines.append(f"Error: {error}")

            message = "\n".join(lines)
            _send_telegram_message(telegram_bot_token, telegram_chat_id, message, logger)

        return result_code

    try:
        storage = OCIStorageClient(
            settings.oci_namespace,
            region=settings.oci_region,
            profile=settings.oci_profile,
        )
    except OCIStorageError as exc:
        logger.error("Failed to initialize OCI storage client: %s", exc)
        return finish(1, error=str(exc))

    logger.info("Selecting random PNG from bucket %s", settings.bucket)

    try:
        objects = storage.list_png_objects(settings.bucket, settings.object_prefix)
        selected_object = choose_random_object(objects)
        logger.info("Selected %s", selected_object.key)
        png_bytes = storage.download_object(selected_object)
        logger.info("Downloaded %s bytes", len(png_bytes))
    except OCIStorageError as exc:
        logger.error("OCI operation failed: %s", exc)
        return finish(1, error=str(exc))

    try:
        jpeg_bytes = convert_png_to_jpeg(png_bytes)
    except ImageProcessingError as exc:
        logger.error("Failed to convert PNG to JPEG: %s", exc)
        return finish(1, error=str(exc))

    jpeg_key = derive_jpeg_key(selected_object.key, settings.jpeg_prefix)
    jpeg_object = ObjectRef(bucket=settings.bucket, key=jpeg_key)

    try:
        storage.upload_bytes(jpeg_object, jpeg_bytes, "image/jpeg")
        logger.info("Uploaded converted JPEG to %s", jpeg_object.key)
        par_request = storage.generate_presigned_url(
            jpeg_object, settings.presign_expiration_seconds
        )
        presigned_url = par_request.url
        logger.info(
            "Generated pre-authenticated URL valid for %s seconds",
            settings.presign_expiration_seconds,
        )
    except OCIStorageError as exc:
        logger.error("OCI operation failed during JPEG upload: %s", exc)
        return finish(1, error=str(exc))

    if settings.enable_captioning:
        try:
            caption = generate_caption_with_type(settings, presigned_url, "image/jpeg")
            logger.info("Generated caption for %s", selected_object.key)
        except ClaudeCaptionError as exc:
            logger.error("Failed to generate caption via Claude: %s", exc)
            caption = ""
            logger.info("Caption generation failed; posting without caption")
    else:
        caption = ""
        logger.info("Caption generation disabled; posting without caption")

    instagram_success = False
    instagram_caption = caption or ""
    facebook_caption = caption if caption else None

    if settings.instagram_user_id and settings.meta_access_token:
        try:
            container_id = create_instagram_media(
                settings.meta_access_token,
                settings.instagram_user_id,
                presigned_url,
                instagram_caption,
            )
            logger.info("Created Instagram media container %s", container_id)
            wait_seconds = max(settings.media_wait_seconds, 0)
            if wait_seconds:
                logger.info(
                    "Waiting %s seconds for Instagram media processing", wait_seconds
                )
                time.sleep(wait_seconds)

            try:
                status_payload = check_instagram_container(
                    settings.meta_access_token,
                    container_id,
                )
            except MetaApiError as exc:
                logger.warning(
                    "Could not confirm Instagram container status: %s", exc
                )
                status_payload = None

            if status_payload:
                status = status_payload.get("status")
                status_code = status_payload.get("status_code")
                if status:
                    logger.info("Instagram container status: %s", status)
                if status_code and status_code.upper() == "ERROR":
                    logger.warning(
                        "Instagram container returned error payload: %s",
                        status_payload,
                    )
                    raise MetaApiError(
                        "Instagram reported media error during processing"
                    )

            media_id = publish_instagram_media(
                settings.meta_access_token,
                settings.instagram_user_id,
                container_id,
            )
            logger.info("Published Instagram media %s", media_id)
            instagram_media_id = media_id
            instagram_success = True
        except MetaApiError as exc:
            instagram_error = str(exc)
            logger.error("Instagram posting failed: %s", exc)
    else:
        logger.warning("Instagram credentials not configured; skipping Instagram post")

    facebook_success = False
    if settings.facebook_page_id and settings.meta_access_token:
        try:
            post_id = post_facebook_photo(
                settings.meta_access_token,
                settings.facebook_page_id,
                presigned_url,
                facebook_caption,
            )
            logger.info("Published Facebook post %s", post_id)
            facebook_post_id = post_id
            facebook_success = True
        except MetaApiError as exc:
            facebook_error = str(exc)
            logger.error("Facebook posting failed: %s", exc)
    else:
        logger.warning("Facebook credentials not configured; skipping Facebook post")

    try:
        storage.delete_object(jpeg_object)
        logger.info("Deleted converted JPEG %s", jpeg_object.key)
    except OCIStorageError as exc:
        logger.warning("Failed to delete JPEG %s: %s", jpeg_object.uri, exc)

    if instagram_success and facebook_success:
        try:
            storage.delete_object(selected_object)
            logger.info(
                "Deleted original PNG %s from bucket %s",
                selected_object.key,
                settings.bucket,
            )
        except OCIStorageError as exc:
            logger.warning(
                "Posts succeeded but failed to delete %s: %s",
                selected_object.uri,
                exc,
            )
        return finish(0)

    if not instagram_success and not facebook_success:
        logger.error("Failed to publish to both platforms")
    else:
        logger.error("Publishing succeeded on only one platform")

    return finish(1)


if __name__ == "__main__":
    sys.exit(main())
