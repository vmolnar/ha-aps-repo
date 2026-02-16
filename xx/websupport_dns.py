#!/usr/bin/env python3
"""
Websupport DNS Addon for Home Assistant
Handles DNS record updates for Websupport.sk domains
"""

import hmac
import hashlib
import time
import requests
import json
import sys
import os
from datetime import datetime, timezone
import urllib.request

def get_public_ip():
    """Get the public IP address using ipify API."""
    try:
        with urllib.request.urlopen('https://api.ipify.org', timeout=10) as response:
            return response.read().decode('utf-8').strip()
    except Exception as e:
        print(f"Error getting public IP: {e}", file=sys.stderr)
        return None

def generate_signature(method, path, timestamp, api_secret):
    """Generate HMAC-SHA1 signature for Websupport API."""
    canonical_request = f"{method} {path} {timestamp}"
    return hmac.new(
        bytes(api_secret, 'UTF-8'), 
        bytes(canonical_request, 'UTF-8'), 
        hashlib.sha1
    ).hexdigest()

def make_authenticated_request(method, path, api_key, api_secret, base_url="https://rest.websupport.sk", data=None):
    """Make an authenticated request to Websupport API."""
    timestamp = int(time.time())
    signature = generate_signature(method, path, timestamp, api_secret)
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Date": datetime.fromtimestamp(timestamp, timezone.utc).isoformat()
    }
    
    url = f"{base_url}{path}"
    
    try:
        if method.upper() == "GET":
            response = requests.get(url, headers=headers, auth=(api_key, signature), timeout=30)
        elif method.upper() == "POST":
            response = requests.post(url, headers=headers, auth=(api_key, signature), json=data, timeout=30)
        elif method.upper() == "PUT":
            response = requests.put(url, headers=headers, auth=(api_key, signature), json=data, timeout=30)
        else:
            return None, f"Unsupported HTTP method: {method}"
        
        return response, None
    except Exception as e:
        return None, f"Request failed: {str(e)}"

def get_dns_records(service, api_key, api_secret):
    """Get all DNS records for a service/domain."""
    path = f"/v2/service/{service}/dns/record"
    response, error = make_authenticated_request("GET", path, api_key, api_secret)
    
    if error:
        return None, error
    
    if response.status_code == 200:
        return response.json(), None
    elif response.status_code == 404:
        # Domain/service not found - return empty list
        return {"items": []}, None
    else:
        return None, f"Failed to get DNS records: {response.status_code} - {response.text}"

def find_dns_record_by_name(records, record_name):
    """Find a DNS record by name in the records list."""
    if records and 'items' in records:
        for record in records['items']:
            if record.get('name') == record_name:
                return record
    return None

def create_dns_record(service, api_key, api_secret, record_name, record_type="A", content=None, ttl=3600):
    """Create a new DNS record."""
    path = f"/v2/service/{service}/dns/record"
    
    data = {
        "type": record_type,
        "name": record_name,
        "content": content,
        "ttl": ttl
    }
    
    response, error = make_authenticated_request("POST", path, api_key, api_secret, data=data)
    
    if error:
        return False, error
    
    if response.status_code == 204:
        return True, "DNS record created successfully"
    else:
        return False, f"Failed to create DNS record: {response.status_code} - {response.text}"

def update_dns_record(service, record_id, api_key, api_secret, record_name, content=None, ttl=3600):
    """Update an existing DNS record."""
    path = f"/v2/service/{service}/dns/record/{record_id}"
    
    data = {
        "name": record_name,
        "content": content,
        "ttl": ttl
    }
    
    response, error = make_authenticated_request("PUT", path, api_key, api_secret, data=data)
    
    if error:
        return False, error
    
    if response.status_code == 204:
        return True, "DNS record updated successfully"
    else:
        return False, f"Failed to update DNS record: {response.status_code} - {response.text}"

def ensure_dns_record(service, api_key, api_secret, record_name, target_ip, record_type="A", ttl=3600):
    """Ensure a DNS record exists and is up to date."""
    # Get current DNS records
    records, error = get_dns_records(service, api_key, api_secret)
    
    if error:
        return False, f"Failed to get current DNS records: {error}"
    
    # Find existing record
    existing_record = find_dns_record_by_name(records, record_name)
    
    if existing_record:
        # Record exists, check if it needs updating
        current_content = existing_record.get('content', '')
        if current_content == target_ip:
            return True, f"DNS record {record_name} already up to date with IP {target_ip}"
        else:
            # Update existing record
            record_id = existing_record.get('id')
            if record_id:
                success, message = update_dns_record(
                    service, record_id, api_key, api_secret, 
                    record_name, target_ip, ttl
                )
                return success, message
            else:
                return False, f"Existing record {record_name} has no ID"
    else:
        # Create new record
        success, message = create_dns_record(
            service, api_key, api_secret, record_name, record_type, target_ip, ttl
        )
        return success, message

def update_multiple_subdomains(service, api_key, api_secret, subdomains, record_type="A", ttl=3600):
    """Update multiple subdomains to point to the current public IP."""
    public_ip = get_public_ip()
    
    if not public_ip:
        return False, "Failed to get public IP address"
    
    print(f"Current public IP: {public_ip}")
    print(f"Updating subdomains for domain: {service}")
    
    results = []
    for subdomain in subdomains:
        full_record_name = f"{subdomain}.{service}" if subdomain != "@" else service
        
        print(f"Processing {subdomain} -> {full_record_name}")
        
        success, message = ensure_dns_record(
            service, api_key, api_secret, full_record_name, public_ip, record_type, ttl
        )
        
        results.append({
            'subdomain': subdomain,
            'success': success,
            'message': message
        })
        
        print(f"  Result: {'SUCCESS' if success else 'FAILURE'}")
        print(f"  Message: {message}")
    
    # Check if all operations were successful
    all_successful = all(result['success'] for result in results)
    
    return all_successful, results

def load_config(config_file="/data/options.json"):
    """Load configuration from Home Assistant addon options."""
    try:
        with open(config_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Config file {config_file} not found")
        return None
    except Exception as e:
        print(f"Error loading config: {e}")
        return None

def main():
    """Main function for the Websupport DNS addon."""
    # Load configuration from Home Assistant
    config = load_config()
    
    if not config:
        print("Failed to load configuration")
        return 1
    
    # Get configuration values
    api_key = config.get("api_key")
    api_secret = config.get("api_secret")
    domain = config.get("domain")
    subdomains = config.get("subdomains", [])
    record_type = config.get("record_type", "A")
    ttl = config.get("ttl", 3600)
    
    if not all([api_key, api_secret, domain, subdomains]):
        print("Missing required configuration values")
        return 1
    
    print("Websupport DNS Addon")
    print(f"Domain: {domain}")
    print(f"Subdomains: {', '.join(subdomains)}")
    print(f"Record Type: {record_type}")
    print(f"TTL: {ttl}")
    print("=" * 60)
    
    # Update all subdomains
    success, results = update_multiple_subdomains(domain, api_key, api_secret, subdomains, record_type, ttl)
    
    print("=" * 60)
    if success:
        print("All DNS records updated successfully!")
        return 0
    else:
        print("Some DNS record updates failed:")
        for result in results:
            if not result['success']:
                print(f"  - {result['subdomain']}: {result['message']}")
        return 1

if __name__ == "__main__":
    sys.exit(main())