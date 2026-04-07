import asyncio
from datetime import datetime, timedelta, timezone
from dateutil import parser
import httpx
import json
import logging
import os

API_ROOT = "https://api.torbox.app/v1/api"
API_KEY = os.getenv("API_KEY") or ""

logger = logging.getLogger("clean_torbox")
logger.setLevel(logging.DEBUG)


def get_timedelta_from_env(
    env_var_name: str, default_value: timedelta, unit: str
) -> timedelta:
    """
    Reads a timedelta value from an environment variable, falling back to a default.

    Args:
        env_var_name: The name of the environment variable.
        default_value: The default timedelta to use if the env var is not set or invalid.
        unit: The unit of time for the environment variable ('days' or 'hours').

    Returns:
        The timedelta value.
    """
    env_value_str = os.getenv(env_var_name)
    if env_value_str:
        try:
            if unit == "days":
                value = int(env_value_str)
                result = timedelta(days=value)
                logger.info(f"Using {env_var_name} from environment: {result}")
            elif unit == "hours":
                value = float(env_value_str)  # Use float to allow for fractional hours
                result = timedelta(hours=value)
                logger.info(f"Using {env_var_name} from environment: {result}")
            else:
                logger.warning(
                    f"Unsupported unit '{unit}' for environment variable {env_var_name}. Using default."
                )
                return default_value
            return result
        except ValueError:
            logger.warning(
                f"Invalid value for {env_var_name}: '{env_value_str}'. Expected a number. Using default: {default_value}"
            )
            return default_value
    else:
        logger.debug(f"{env_var_name} not set. Using default: {default_value}")
        return default_value


# Configure expiry and ETA times from environment variables with fallbacks
DOWNLOAD_EXPIRY = get_timedelta_from_env(
    env_var_name="DOWNLOAD_EXPIRY_DAYS", default_value=timedelta(days=14), unit="days"
)
UPLOAD_EXPIRY = get_timedelta_from_env(
    env_var_name="UPLOAD_EXPIRY_HOURS", default_value=timedelta(hours=1), unit="hours"
)
DOWNLOAD_MAX_ETA = get_timedelta_from_env(
    env_var_name="DOWNLOAD_MAX_ETA_HOURS",
    default_value=timedelta(hours=1),
    unit="hours",
)

client = httpx.AsyncClient(
    base_url=API_ROOT,
    headers={"Content-Type": "application/json", "Authorization": "bearer " + API_KEY},
    timeout=30.0,
)

deletion_semaphore = asyncio.Semaphore(10)


async def delete_res(res_attr, res_id, res_url):
    async with deletion_semaphore:
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
        elif timedelta(seconds=res.get("eta", 0)) > DOWNLOAD_MAX_ETA:
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
        if r.status_code < 200 or r.status_code > 299:
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
