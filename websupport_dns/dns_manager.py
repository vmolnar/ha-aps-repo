"""DNS Manager for Websupport.sk API."""

import argparse
import hashlib
import hmac
import logging
import sys
import time
from datetime import datetime, timezone

import requests

logger = logging.getLogger(__name__)


class WebsupportDNSManager:
    """Manage DNS records via Websupport REST API v1."""

    def __init__(self, api_key: str, api_secret: str, base_url: str = "rest.websupport.sk"):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url

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

    def _request(self, method: str, path: str, data: dict = None) -> dict:
        """Make an authenticated API request."""
        url = f"https://{self.base_url}{path}"
        headers, signature = self._auth(method, path)
        resp = requests.request(
            method, url, headers=headers, json=data,
            auth=(self.api_key, signature), timeout=15,
        )
        if resp.status_code == 204:
            return {}
        body = resp.json()
        if resp.status_code >= 400:
            raise Exception(f"API {method} {path} returned {resp.status_code}: {body}")
        return body

    def get_public_ip(self) -> str:
        """Get current public IP via ipify."""
        resp = requests.get("https://api.ipify.org", timeout=10)
        return resp.text.strip()

    def list_records(self, domain: str) -> list[dict]:
        """List all DNS records for a domain."""
        resp = self._request("GET", f"/v1/user/self/zone/{domain}/record")
        return resp.get("items", [])

    def create_record(self, domain: str, name: str, ip: str, ttl: int) -> dict:
        """Create a new A record."""
        return self._request(
            "POST",
            f"/v1/user/self/zone/{domain}/record",
            {"type": "A", "name": name, "content": ip, "ttl": ttl},
        )

    def update_record(self, domain: str, record_id: int, ip: str, ttl: int) -> dict:
        """Update an existing A record."""
        return self._request(
            "PUT",
            f"/v1/user/self/zone/{domain}/record/{record_id}",
            {"content": ip, "ttl": ttl},
        )

    def update_dns_records_for_subdomains(
        self, domain: str, subdomains: list[str], ttl: int = 3600
    ) -> list[dict]:
        """Update A records for all configured subdomains."""
        ip = self.get_public_ip()
        logger.info("Public IP: %s", ip)

        existing = self.list_records(domain)
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
                    self.update_record(domain, rec["id"], ip, ttl)
                else:
                    self.create_record(domain, sub, ip, ttl)
                results.append({"subdomain": sub, "success": True})
            except Exception as e:
                logger.error("Failed to update %s: %s", sub, e)
                results.append({"subdomain": sub, "success": False, "error": str(e)})

        return results


def main():
    """CLI entry point for updating DNS records."""
    parser = argparse.ArgumentParser(description='Run WebsupportDNSManager to update DNS records for subdomains.')
    
    # Add required CLI arguments
    parser.add_argument('--api-key', required=True, type=str, help='Websupport API key')
    parser.add_argument('--api-secret', required=True, type=str, help='Websupport API secret')
    parser.add_argument('--domain', required=True, type=str, help='Domain name (e.g., example.com)')
    parser.add_argument('--subdomains', required=True, type=str, help='Comma-separated list of subdomains (e.g., www,api,blog)')
    parser.add_argument('--ttl', type=int, default=3600, help='TTL for DNS records (default: 3600)')
    
    args = parser.parse_args()
    
    # Initialize WebsupportDNSManager with CLI arguments
    dns_manager = WebsupportDNSManager(api_key=args.api_key, api_secret=args.api_secret)
    
    # Parse subdomains from comma-separated string
    subdomains_list = [s.strip() for s in args.subdomains.split(',')]
    
    # Update DNS records for subdomains
    try:
        results = dns_manager.update_dns_records_for_subdomains(
            domain=args.domain,
            subdomains=subdomains_list,
            ttl=args.ttl
        )
        
        # Print results
        print("DNS update results:")
        for result in results:
            status = "SKIPPED" if result.get("skipped") else "UPDATED" if result.get("success") else "FAILED"
            print(f"  {result['subdomain']}: {status}")
            
        print("\nSuccessfully updated DNS records for subdomains.")
    except Exception as e:
        print(f"Error updating DNS records: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
