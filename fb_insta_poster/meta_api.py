from __future__ import annotations

import logging
from typing import Optional

import requests

GRAPH_API_BASE = "https://graph.facebook.com/v18.0"

logger = logging.getLogger(__name__)


class MetaApiError(RuntimeError):
    """Raised when the Meta Graph API returns an error response."""


def _handle_response(response: requests.Response) -> dict:
    try:
        data = response.json()
    except requests.JSONDecodeError as exc:  # pragma: no cover - defensive guard
        raise MetaApiError("Failed to parse Graph API response as JSON") from exc

    if response.status_code >= 400:
        message = data.get("error", {}).get("message", response.text)
        raise MetaApiError(f"Graph API error ({response.status_code}): {message}")

    return data


def create_instagram_media(
    access_token: str,
    user_id: str,
    image_url: str,
    caption: str,
    timeout: int = 30,
) -> str:
    url = f"{GRAPH_API_BASE}/{user_id}/media"
    payload = {
        "image_url": image_url,
        "caption": caption,
        "access_token": access_token,
    }
    response = requests.post(url, data=payload, timeout=timeout)
    data = _handle_response(response)
    container_id = data.get("id")
    if not container_id:
        raise MetaApiError("Instagram media creation response did not include an ID")

    logger.debug("Created Instagram media container %s", container_id)
    return container_id


def publish_instagram_media(
    access_token: str,
    user_id: str,
    container_id: str,
    timeout: int = 30,
) -> str:
    url = f"{GRAPH_API_BASE}/{user_id}/media_publish"
    payload = {
        "creation_id": container_id,
        "access_token": access_token,
    }
    response = requests.post(url, data=payload, timeout=timeout)
    data = _handle_response(response)
    media_id = data.get("id")
    if not media_id:
        raise MetaApiError("Instagram publish response did not include an ID")

    logger.debug("Published Instagram container %s as media %s", container_id, media_id)
    return media_id


def check_instagram_container(
    access_token: str,
    container_id: str,
    timeout: int = 30,
) -> Optional[dict]:
    url = f"{GRAPH_API_BASE}/{container_id}"
    params = {
        "fields": "status,status_code",
        "access_token": access_token,
    }
    response = requests.get(url, params=params, timeout=timeout)
    data = _handle_response(response)
    logger.debug("Container %s status payload %s", container_id, data)
    return data


def post_facebook_photo(
    access_token: str,
    page_id: str,
    image_url: str,
    caption: Optional[str],
    timeout: int = 30,
) -> str:
    url = f"{GRAPH_API_BASE}/{page_id}/photos"
    payload = {
        "access_token": access_token,
        "url": image_url,
    }
    if caption:
        payload["message"] = caption

    response = requests.post(url, data=payload, timeout=timeout)
    data = _handle_response(response)
    post_id = data.get("post_id") or data.get("id")
    if not post_id:
        raise MetaApiError("Facebook photo response did not include a post ID")

    logger.debug("Published Facebook post %s", post_id)
    return post_id


def get_facebook_page_details(
    access_token: str,
    page_id: str,
    timeout: int = 30,
) -> dict:
    url = f"{GRAPH_API_BASE}/{page_id}"
    params = {
        "fields": "id,name",
        "access_token": access_token,
    }
    response = requests.get(url, params=params, timeout=timeout)
    data = _handle_response(response)
    logger.debug("Fetched Facebook page details for %s: %s", page_id, data)
    return data


def get_instagram_user_details(
    access_token: str,
    user_id: str,
    timeout: int = 30,
) -> dict:
    url = f"{GRAPH_API_BASE}/{user_id}"
    params = {
        "fields": "id,username,name",
        "access_token": access_token,
    }
    response = requests.get(url, params=params, timeout=timeout)
    data = _handle_response(response)
    logger.debug("Fetched Instagram user details for %s: %s", user_id, data)
    return data
