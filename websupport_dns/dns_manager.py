"""DNS Manager for Websupport integration."""

import logging
import asyncio
import hmac
import hashlib
import time
from typing import Any, Dict, List

import aiohttp
from datetime import datetime, timezone

_LOGGER = logging.getLogger(__name__)


class WebsupportDNSManager:
    """Class to manage DNS records on Websupport."""
    
    def __init__(self, api_key: str, api_secret: str, base_url: str = "rest.websupport.sk"):
        """Initialize the DNS manager with API credentials."""
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url
        self.session = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create an aiohttp session."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15)
            )
        return self.session
    
    def _create_auth_headers(self, method: str, path: str) -> tuple[Dict[str, str], str]:
        """Create authentication headers for Websupport API."""
        timestamp = int(time.time())
        canonical_request = "%s %s %s" % (method, path, timestamp)
        
        # Create HMAC-SHA1 signature
        signature = hmac.new(
            bytes(self.api_secret, 'UTF-8'), 
            bytes(canonical_request, 'UTF-8'), 
            hashlib.sha1
        ).hexdigest()
        
        # Create headers
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Date": datetime.fromtimestamp(timestamp, timezone.utc).isoformat()
        }
        
        return headers, signature
    
    async def _make_request(self, method: str, endpoint: str, data: Dict[str, Any] = None, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make an API request with correct authentication."""
        url = f"https://{self.base_url}{endpoint}"
        headers, signature = self._create_auth_headers(method, endpoint)
        
        session = await self._get_session()
        
        try:
            if method.upper() == 'GET':
                async with session.get(url, headers=headers, auth=aiohttp.BasicAuth(self.api_key, signature), params=params) as response:
                    return await self._handle_response(response)
            elif method.upper() == 'POST':
                async with session.post(url, headers=headers, auth=aiohttp.BasicAuth(self.api_key, signature), json=data) as response:
                    return await self._handle_response(response)
            elif method.upper() == 'PUT':
                async with session.put(url, headers=headers, auth=aiohttp.BasicAuth(self.api_key, signature), json=data) as response:
                    return await self._handle_response(response)
            elif method.upper() == 'DELETE':
                async with session.delete(url, headers=headers, auth=aiohttp.BasicAuth(self.api_key, signature)) as response:
                    return await self._handle_response(response)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
                
        except aiohttp.ClientError as e:
            raise Exception(f"API request failed: {str(e)}")
    
    async def _handle_response(self, response: aiohttp.ClientResponse) -> Any:
        """Handle API response."""
        try:
            if response.status == 204:  # No content
                return None
            
            content_type = response.headers.get('Content-Type', '').lower()
            if 'application/json' in content_type:
                return await response.json()
            else:
                text = await response.text()
                return {"status": response.status, "content": text}
                
        except Exception as e:
            raise Exception(f"Failed to parse response: {str(e)}")
    
    async def test_authentication(self) -> bool:
        """Test if authentication works."""
        try:
            response = await self._make_request('GET', '/v2/check')
            return response.get('status', 200) == 200
        except Exception:
            return False

    async def get_service_id_from_domain(self, domain: str) -> str:
        """Get service ID from domain name."""
        try:
            # Try to list all services to find the one matching the domain
            response = await self._make_request('GET', '/v2/service')
            services = response.get('data', [])
            
            # Look for service with matching domain
            for service in services:
                if service.get('domain') == domain:
                    return service.get('id')
            
            # If not found, try to get service by domain directly
            # This is a fallback approach - Websupport API might have a direct endpoint
            response = await self._make_request('GET', f'/v2/service/domain/{domain}')
            if response.get('data'):
                return response.get('data').get('id')
            
            raise Exception(f"Could not find service ID for domain: {domain}")
            
        except Exception as e:
            raise Exception(f"Failed to get service ID for domain {domain}: {str(e)}")
    
    async def get_public_ip(self) -> str:
        """Get the current public IP address."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get('https://api.ipify.org', timeout=10) as response:
                    return (await response.text()).strip()
        except Exception as e:
            raise Exception(f"Failed to get public IP: {str(e)}")
    
    async def list_dns_records(self, service_id: str) -> List[Dict[str, Any]]:
        """List all DNS records for a service."""
        try:
            response = await self._make_request('GET', f'/v2/service/{service_id}/dns/record')
            return response.get('data', [])
        except Exception as e:
            raise Exception(f"Failed to list DNS records: {str(e)}")
    
    async def get_dns_record_by_name(self, service_id: str, record_name: str) -> Dict[str, Any]:
        """Get a specific DNS record by name."""
        try:
            records = await self.list_dns_records(service_id)
            for record in records:
                if record['name'] == record_name:
                    return record
            return None
        except Exception as e:
            raise Exception(f"Failed to get DNS record: {str(e)}")
    
    async def create_dns_record(self, service_id: str, record_name: str, ip_address: str, ttl: int = 3600) -> Dict[str, Any]:
        """Create a new DNS A record."""
        try:
            data = {
                'type': 'A',
                'name': record_name,
                'content': ip_address,
                'ttl': ttl
            }
            
            response = await self._make_request('POST', f'/v2/service/{service_id}/dns/record', data=data)
            return response
                
        except Exception as e:
            raise Exception(f"Failed to create DNS record: {str(e)}")
    
    async def update_dns_record(self, service_id: str, record_id: int, ip_address: str, ttl: int = 3600) -> Dict[str, Any]:
        """Update an existing DNS A record."""
        try:
            data = {
                'content': ip_address,
                'ttl': ttl
            }
            
            response = await self._make_request('PUT', f'/v2/service/{service_id}/dns/record/{record_id}', data=data)
            return response
                
        except Exception as e:
            raise Exception(f"Failed to update DNS record: {str(e)}")
    
    async def create_or_update_dns_record(self, service_id: str, record_name: str, ip_address: str, ttl: int = 3600) -> Dict[str, Any]:
        """Create or update a DNS A record."""
        try:
            # Check if record already exists
            existing_record = await self.get_dns_record_by_name(service_id, record_name)
            
            if existing_record:
                _LOGGER.info(f"Updating existing DNS record for {record_name}")
                return await self.update_dns_record(service_id, existing_record['id'], ip_address, ttl)
            else:
                _LOGGER.info(f"Creating new DNS record for {record_name}")
                return await self.create_dns_record(service_id, record_name, ip_address, ttl)
                
        except Exception as e:
            raise Exception(f"Failed to create or update DNS record: {str(e)}")
    
    async def update_dns_records_for_subdomains(self, domain: str, subdomains: List[str], ttl: int = 3600) -> List[Dict[str, Any]]:
        """Update DNS records for multiple subdomains."""
        try:
            # Get service ID from domain
            service_id = await self.get_service_id_from_domain(domain)
            _LOGGER.info(f"Using service ID {service_id} for domain {domain}")
            
            # Get current public IP
            ip_address = await self.get_public_ip()
            _LOGGER.info(f"Current public IP: {ip_address}")
            
            results = []
            
            for subdomain in subdomains:
                try:
                    result = await self.create_or_update_dns_record(service_id, subdomain, ip_address, ttl)
                    results.append({'subdomain': subdomain, 'success': True, 'result': result})
                    _LOGGER.info(f"Successfully updated DNS record for {subdomain}")
                except Exception as e:
                    results.append({'subdomain': subdomain, 'success': False, 'error': str(e)})
                    _LOGGER.error(f"Failed to update DNS record for {subdomain}: {str(e)}")
            
            return results
            
        except Exception as e:
            raise Exception(f"Failed to update DNS records: {str(e)}")
    
    async def close(self):
        """Close the aiohttp session."""
        if self.session and not self.session.closed:
            await self.session.close()