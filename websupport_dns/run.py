#!/usr/bin/env python3
"""Websupport DNS - Home Assistant Add-on."""

import asyncio
import json
import logging
import signal
import sys

from dns_manager import WebsupportDNSManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("websupport-dns")


def load_config() -> dict:
    """Load configuration from options.json (written by HA Supervisor)."""
    with open("/data/options.json") as f:
        config = json.load(f)

    for field in ("api_key", "api_secret", "domain"):
        if not config.get(field):
            raise ValueError(f"Missing required config: {field}")

    subs = config.get("subdomains", [])
    if isinstance(subs, str):
        subs = [s.strip() for s in subs.split(",") if s.strip()]
    config["subdomains"] = subs

    if not config["subdomains"]:
        raise ValueError("At least one subdomain must be configured")

    return config


async def run(config: dict) -> None:
    """Main loop: update DNS records on an interval."""
    manager = WebsupportDNSManager(
        config["api_key"],
        config["api_secret"],
        config.get("base_url", "rest.websupport.sk"),
    )
    interval = config.get("scan_interval", 10) * 60
    domain = config["domain"]
    subdomains = config["subdomains"]
    ttl = config.get("ttl", 3600)

    try:
        while True:
            logger.info("Running DNS update for %s", domain)
            try:
                results = await manager.update_dns_records_for_subdomains(
                    domain, subdomains, ttl
                )
                for r in results:
                    if r["success"]:
                        logger.info("Updated %s", r["subdomain"])
                    else:
                        logger.error("Failed %s: %s", r["subdomain"], r["error"])
            except Exception:
                logger.exception("Error during DNS update")

            logger.info("Next update in %d minutes", interval // 60)
            await asyncio.sleep(interval)
    finally:
        await manager.close()


def main() -> None:
    config = load_config()
    logger.info(
        "Config loaded: domain=%s subdomains=%s interval=%dm",
        config["domain"],
        config["subdomains"],
        config.get("scan_interval", 10),
    )

    loop = asyncio.new_event_loop()

    def shutdown(sig):
        logger.info("Received %s, shutting down...", sig.name)
        for task in asyncio.all_tasks(loop):
            task.cancel()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, shutdown, sig)

    try:
        loop.run_until_complete(run(config))
    except asyncio.CancelledError:
        pass

    logger.info("Add-on stopped")


if __name__ == "__main__":
    main()
