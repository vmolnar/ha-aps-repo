"""DNS Manager for Websupport.sk API."""

import hashlib
import hmac
import logging
import time
from datetime import datetime, timezone

import aiohttp

logger = logging.getLogger(__name__)


class WebsupportDNSManager:
    """Manage DNS records via Websupport REST API v1."""

    def __init__(self, api_key: str, api_secret: str, base_url: str = "rest.websupport.sk"):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url
        self.session = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15))
        return self.session

    def _auth(self, method: str, path: str) -> tuple[dict, str]:
        """Create HMAC-SHA1 auth headers for the Websupport API."""
        ts = int(time.time())
        canonical = f"{method} {path} {ts}"
        signature = hmac.new(
            self.api_secret.encode(),
            canonical.encode(),
            hashlib.sha1,
        ).hexdigest()
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Date": datetime.fromtimestamp(ts, timezone.utc).isoformat(),
        }
        return headers, signature

    async def _request(self, method: str, path: str, data: dict = None) -> dict:
        """Make an authenticated API request."""
        url = f"https://{self.base_url}{path}"
        headers, signature = self._auth(method, path)
        auth = aiohttp.BasicAuth(self.api_key, signature)
        session = await self._get_session()

        async with session.request(method, url, headers=headers, auth=auth, json=data) as resp:
            if resp.status == 204:
                return {}
            body = await resp.json()
            if resp.status >= 400:
                raise Exception(f"API {method} {path} returned {resp.status}: {body}")
            return body

    async def get_public_ip(self) -> str:
        """Get current public IP via ipify."""
        async with aiohttp.ClientSession() as s:
            async with s.get("https://api.ipify.org", timeout=aiohttp.ClientTimeout(total=10)) as resp:
                return (await resp.text()).strip()

    async def list_records(self, domain: str) -> list[dict]:
        """List all DNS records for a domain."""
        resp = await self._request("GET", f"/v1/user/self/zone/{domain}/record")
        return resp.get("items", [])

    async def create_record(self, domain: str, name: str, ip: str, ttl: int) -> dict:
        """Create a new A record."""
        return await self._request(
            "POST",
            f"/v1/user/self/zone/{domain}/record",
            {"type": "A", "name": name, "content": ip, "ttl": ttl},
        )

    async def update_record(self, domain: str, record_id: int, ip: str, ttl: int) -> dict:
        """Update an existing A record."""
        return await self._request(
            "PUT",
            f"/v1/user/self/zone/{domain}/record/{record_id}",
            {"content": ip, "ttl": ttl},
        )

    async def update_dns_records_for_subdomains(
        self, domain: str, subdomains: list[str], ttl: int = 3600
    ) -> list[dict]:
        """Update A records for all configured subdomains."""
        ip = await self.get_public_ip()
        logger.info("Public IP: %s", ip)

        # Fetch existing records once
        existing = await self.list_records(domain)
        record_map = {r["name"]: r for r in existing if r.get("type") == "A"}

        results = []
        for sub in subdomains:
            try:
                rec = record_map.get(sub)
                if rec:
                    if rec["content"] == ip:
                        logger.info("%s already points to %s, skipping", sub, ip)
                        results.append({"subdomain": sub, "success": True, "skipped": True})
                        continue
                    await self.update_record(domain, rec["id"], ip, ttl)
                else:
                    await self.create_record(domain, sub, ip, ttl)
                results.append({"subdomain": sub, "success": True})
            except Exception as e:
                logger.error("Failed to update %s: %s", sub, e)
                results.append({"subdomain": sub, "success": False, "error": str(e)})

        return results

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
