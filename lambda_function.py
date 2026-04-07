import asyncio
from datetime import datetime, timedelta, timezone
from dateutil import parser
import httpx
import json
import logging
import os


API_ROOT = "https://api.torbox.app/v1/api"
API_KEY = os.getenv("API_KEY") or ""
DOWNLOAD_EXPIRY = timedelta(days=14)
DOWNLOAD_MAX_ETA = 3600  # 1 hour in seconds
UPLOAD_EXPIRY = timedelta(seconds=3600)


logger = logging.getLogger("clean_torbox")
logger.setLevel(logging.DEBUG)

client = httpx.AsyncClient(
    base_url=API_ROOT,
    headers={"Content-Type": "application/json", "Authorization": "bearer " + API_KEY},
    timeout=30.0,
)


async def delete_res(res_attr, res_id, res_url):
    logger.info(f"deleting {res_attr}={res_id}")
    payload = {res_attr: str(res_id), "operation": "delete"}
    logger.debug(f"request: {json.dumps(payload)}")
    r = await client.post(
        res_url,
        json=payload,
    )
    logger.debug(f"response: {r.content}")


def should_delete_download(res):
    now = datetime.now(tz=timezone.utc)
    created_at = parser.isoparse(res["created_at"])
    download_state = res.get("download_state")

    if download_state in ("completed", "cached"):
        if now - created_at > DOWNLOAD_EXPIRY:
            logger.info(f"{res['id']} [EXPIRED] {res.get('name')}")
            return True
        else:
            logger.info(
                f"{res['id']} [{download_state.upper()} TTL={DOWNLOAD_EXPIRY - (now - created_at)}] {res.get('name')}"
            )
            return False

    if download_state == "downloading":
        if res.get("download_speed") == 0:
            logger.info(f"{res['id']} [STALLED] {res.get('name')}")
            return True
        elif res.get("eta") > DOWNLOAD_MAX_ETA:
            logger.info(f"{res['id']} [SLOW] {res.get('name')}")
            return True
        else:
            logger.info(
                f"{res['id']} [{download_state.upper()} PROGRESS={res.get('progress') * 100:.1f}% ETA={res.get('eta')}s] {res.get('name')}"
            )
            return False

    if download_state == "uploading":
        if now - created_at > UPLOAD_EXPIRY:
            logger.info(f"{res['id']} [UPLOAD TIMEOUT] {res.get('name')}")
            return True
        else:
            logger.info(
                f"{res['id']} [{download_state.upper()} TTL={UPLOAD_EXPIRY - (now - created_at)}] {res.get('name')}"
            )
            return False

    # unhandled download state...delete by default
    logger.warning(f"{res['id']} [{download_state.upper()}] {res.get('name')}")
    return True


def should_delete_queued(res):
    logger.info(f"{res['id']} [QUEUED] {res.get('name')}")
    return True


async def async_lambda_handler():
    resources = [
        (
            "torrents",
            "/torrents/mylist?bypass_cache=true",
            should_delete_download,
            "torrent_id",
            "/torrents/controltorrent",
        ),
        (
            "webDL",
            "/webdl/mylist?bypass_cache=true",
            should_delete_download,
            "webdl_id",
            "/webdl/controlwebdownload",
        ),
        (
            "queued",
            "/queued/getqueued?bypass_cache=true",
            should_delete_queued,
            "queued_id",
            "/queued/controlqueued",
        ),
    ]

    results = await asyncio.gather(*[
        client.get(res_url_path)
        for res_type, res_url_path, res_should_del_fn, res_del_attr, res_del_url_path in resources
    ])

    deletions = []
    for r, (
        res_type,
        res_url_path,
        res_should_del_fn,
        res_del_attr,
        res_del_url_path,
    ) in zip(results, resources):
        if 200 < r.status_code > 299:
            logger.error(
                f"Error retrieving {res_type} from {res_url_path}: {r.content}"
            )
            continue
        r = r.json()
        logger.debug(f"Found {len(r['data'])} {res_type}")
        for res in r["data"]:
            if res_should_del_fn(res):
                deletions.append(delete_res(res_del_attr, res["id"], res_del_url_path))

    await asyncio.gather(*deletions)

    await client.aclose()


def lambda_handler(event, context):
    if not API_KEY:
        logger.error("API_KEY environment variable is not set")
        return
    asyncio.run(async_lambda_handler())


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler()],
    )
    logging.getLogger("httpcore").setLevel(logging.INFO)
    lambda_handler(None, None)
