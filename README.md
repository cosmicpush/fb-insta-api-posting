# Instagram & Facebook Image Poster

Automates Instagram and Facebook image posts by selecting a random PNG from an OCI Object Storage bucket, converting it to JPEG, publishing through the Meta Graph API, and deleting the source PNG once both posts succeed.

## Prerequisites
- Python 3.10+
- OCI credentials (via `~/.oci/config`) with access to the `FB_INSTA_BUCKET` (default: `12amstories`)
- Meta Graph API access tokens for the target Instagram business account and Facebook page
- Claude API key with access to the latest vision-capable model (default: `claude-sonnet-4-5-20250929`)

## Setup
1. Install dependencies:
   ```bash
   python -m venv .venv
   . .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Copy the sample environment file and fill in your values:
   ```bash
   cp .env.example .env
   ```
3. Ensure your OCI profile can list, read, write, create pre-authenticated requests, and delete objects within the configured bucket/prefix.
4. Provide your Meta and Anthropic credentials in `.env`.

## Usage
Run the poster manually:
```bash
python -m fb_insta_poster
```
The script:
1. Loads configuration and credentials from the environment
2. Lists all PNG files in the configured OCI bucket/prefix
3. Picks a random image and downloads it locally
4. Converts the PNG to JPEG, uploads the result, and creates a pre-authenticated URL
5. Sends the image to Claude Vision to craft a single-line caption
6. Creates and publishes Instagram and Facebook posts with the caption
7. Deletes the converted JPEG always, and removes the source PNG after both posts succeed

Logs are printed to stdout with timestamps to simplify automation and alerting.

## Scheduling
`cron/fb_insta_poster.cron` contains a ready-to-import crontab entry that runs the script every hour from 09:30 to 21:30 IST (04:00-16:00 UTC):
```bash
crontab cron/fb_insta_poster.cron
```
Adjust the repository path or Python interpreter in that file to match your environment before loading it.

## Environment Variables
The following variables are supported (see `.env.example`):

Required:
- `ANTHROPIC_API_KEY` (required when `FB_INSTA_ENABLE_CAPTIONING` is `true`)
- `FB_INSTA_BUCKET` (defaults to `12amstories`)
- `OCI_NAMESPACE`
- `OCI_REGION` (falls back to the region in `~/.oci/config` if omitted)

Instagram (optional, required to publish):
- `INSTAGRAM_USER_ID`

Facebook (optional, required to publish):
- `FACEBOOK_PAGE_ID`

Shared Meta token (required for either platform to post):
- `META_ACCESS_TOKEN` (also reads `INSTAGRAM_ACCESS_TOKEN` / `FACEBOOK_PAGE_ACCESS_TOKEN` for backwards compatibility)

Optional tuning:
- `FB_INSTA_PREFIX` to limit selection to a subfolder
- `FB_INSTA_JPEG_PREFIX` to control where converted JPEGs are stored (default: `converted`)
- `OCI_PROFILE` to select a non-default profile from `~/.oci/config`
- `FB_INSTA_MEDIA_WAIT_SECONDS` to adjust the Instagram processing delay
- `FB_INSTA_STATUS_POLL_SECONDS` to tweak Instagram status polling interval
- `FB_INSTA_PRESIGN_EXPIRATION_SECONDS` to adjust presigned URL validity
- `FB_INSTA_CLAUDE_MODEL` to target a different Claude vision model
- `FB_INSTA_CLAUDE_MAX_TOKENS` to change the caption response limit
- `FB_INSTA_CAPTION_FALLBACK` to set fallback text if Claude succeeds but returns no text
- `FB_INSTA_ENABLE_CAPTIONING` to toggle Claude caption generation (set to `false` for silent posts)
