#!/usr/bin/python3

import routeros_api
import requests
import csv
import io
import sys
import ipaddress
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# --- Configuration ---
# Address List Names
ADDRESS_LIST_NAME_FINAL = 'RUSSIAN_IPS'         # The name the firewall rule references
LIST_COMMENT = 'AUTOMATED_BLOCKLIST'            # NEW: Consistent comment for entries managed by the script

FIREWALL_RULE_COMMENT = 'BLOCK_INCOMING_RUSSIAN_IPS'
IP_DATA_URL = 'https://www.nirsoft.net/countryip/ru.csv'
# ---------------------

# --- Data Fetching Function (Unchanged) ---
def get_russian_ip_ranges(url: str) -> list[str]:
    """Downloads the NirSoft CSV file, parses it, and returns a list of IP ranges."""
    logger.info(f"Downloading IP list from: {url}")
    ip_ranges = []
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status() 
        
        csv_file = io.StringIO(response.text)
        csv_reader = csv.reader(csv_file)
        next(csv_reader) # Skip header row
        
        for row in csv_reader:
            if len(row) >= 2:
                start_ip = row[0].strip()
                end_ip = row[1].strip()
                # Check for simple single IP (start and end are the same)
                if start_ip == end_ip:
                    ip_ranges.append(start_ip)
                else:
                    ip_ranges.append(f"{start_ip}-{end_ip}")
            elif len(row) == 1:
                start_ip = row[0].strip()
                ip_ranges.append(f"{start_ip}")
        
        logger.info(f"Downloaded and parsed {len(ip_ranges)} IP range entries.")
        return ip_ranges
        
    except requests.RequestException as e:
        logger.error(f"Error downloading IP list: {e}")
        return []
    except Exception as e:
        logger.error(f"Error parsing CSV data: {e}")
        return []

# --- Firewall Rule Check/Create Function (Unchanged) ---
def check_and_create_firewall_rule(api_connection):
    """Ensures firewall filter rules exist to drop traffic from the address list."""
    firewall_resource = api_connection.get_resource('/ip/firewall/filter')
    
    # Check for the INPUT rule
    if not firewall_resource.get(comment=FIREWALL_RULE_COMMENT):
        logger.info(f"Creating INPUT chain firewall rule: blocking traffic aimed at the router...")
        firewall_resource.add(
            chain='input',
            action='drop',
            src_address_list=ADDRESS_LIST_NAME_FINAL,
            comment=FIREWALL_RULE_COMMENT
        )
    else:
        logger.info(f"INPUT rule found.")

    # Check for the FORWARD rule
    forward_comment = FIREWALL_RULE_COMMENT + '_FORWARD'
    if not firewall_resource.get(comment=forward_comment):
        logger.info(f"Creating FORWARD chain firewall rule: blocking transit traffic...")
        firewall_resource.add(
            chain='forward',
            action='drop',
            src_address_list=ADDRESS_LIST_NAME_FINAL,
            comment=forward_comment
        )
    else:
        logger.info(f"FORWARD rule found.")
        
    logger.info("Firewall rule check complete.")

# --- Helper Function for Deduplication and Reduction (Unchanged from previous update) ---
def process_ip_lists(ip_ranges: list[str], ip_addresses: list[str]) -> list[str]:
    """
    Deduplicates IP ranges/addresses, removes individual IPs covered by a range, 
    and only processes IPv4 entries.
    Returns a unified, cleaned list of strings (CIDR or single IPv4 addresses).
    """
    all_networks = []
    ipv6_skipped = 0
    
    # Helper to check if a parsed object is IPv4
    def add_if_ipv4(network_obj):
        nonlocal ipv6_skipped
        if network_obj.version == 4:
            all_networks.append(network_obj)
        else:
            ipv6_skipped += 1

    # Process IP Ranges
    for entry in ip_ranges:
        try:
            if '-' in entry:
                start_ip, end_ip = entry.split('-')
                start_addr = ipaddress.ip_address(start_ip)
                end_addr = ipaddress.ip_address(end_ip)
                
                if start_addr.version == 4 and end_addr.version == 4:
                    for network in ipaddress.summarize_address_range(start_addr, end_addr):
                        add_if_ipv4(network)
                else:
                    ipv6_skipped += 1
            else:
                add_if_ipv4(ipaddress.ip_network(entry, strict=False))
        except ValueError:
            pass 

    # Process Single IP addresses
    for entry in ip_addresses:
        try:
            ip_obj = ipaddress.ip_address(entry)
            add_if_ipv4(ipaddress.ip_network(f'{entry}/32'))
        except ValueError:
            try:
                add_if_ipv4(ipaddress.ip_network(entry, strict=False))
            except ValueError:
                pass

    logger.info(f"Found {len(all_networks)} IPv4 network objects for processing.")
    if ipv6_skipped > 0:
        logger.info(f"Skipped {ipv6_skipped} IPv6 entries.")

    # Deduplication and Aggregation
    final_networks = list(ipaddress.collapse_addresses(all_networks))
    logger.info(f"Reduced to {len(final_networks)} unique, non-overlapping IPv4 networks.")

    # Final Formatting
    final_list = []
    for network in final_networks:
        if network.prefixlen == 32:
            final_list.append(str(network.network_address))
        else:
            final_list.append(str(network))
            
    return final_list

# --- Main Script Logic (UPDATED for Diff Sync) ---
def main():
    ROUTER_HOST = sys.argv[1]
    ROUTER_PORT = sys.argv[2]
    ROUTER_USER = sys.argv[3]
    ROUTER_PASS = sys.argv[4]
    
    """Main function to perform the safe address list update and firewall check."""
    
    # 1. Collect and Consolidate New Data
    logger.info("Collecting data from internet sources...")
    ip_ranges = get_russian_ip_ranges(IP_DATA_URL)
    ip_ranges += get_russian_ip_ranges("https://www.nirsoft.net/countryip/cn.csv")
    ip_ranges += get_russian_ip_ranges("https://www.nirsoft.net/countryip/by.csv")
    ip_ranges += get_russian_ip_ranges("https://www.nirsoft.net/countryip/kz.csv")
    ip_ranges += get_russian_ip_ranges("https://www.nirsoft.net/countryip/in.csv")
    ip_ranges += get_russian_ip_ranges("https://www.nirsoft.net/countryip/tr.csv")
    
    ip_addresses = get_russian_ip_ranges("https://rules.emergingthreats.net/blockrules/compromised-ips.txt")
    ip_addresses += get_russian_ip_ranges("https://lists.blocklist.de/lists/all.txt")

    if not ip_ranges and not ip_addresses:
        logger.error("No IP ranges or addresses to process. Exiting.")
        return

    logger.info("Starting IP list deduplication, consolidation, and IPv4 filtering...")
    # new_ip_set is the source of truth from the internet
    new_ip_list = process_ip_lists(ip_ranges, ip_addresses)
    new_ip_set = set(new_ip_list)
    logger.info(f"Final consolidated list (Source of Truth) contains {len(new_ip_set)} IPv4 entries.")
    
    if not new_ip_set:
        logger.error("All entries were invalid or filtered out. Exiting.")
        return
    
    # 2. Connect to Router and Get Current Data
    api_pool = None
    try:
        api_pool = routeros_api.RouterOsApiPool(
            ROUTER_HOST, 
            username=ROUTER_USER, 
            password=ROUTER_PASS, 
            port=ROUTER_PORT, 
            plaintext_login=True
        )
        api = api_pool.get_api()
        logger.info(f"\nSuccessfully connected to MikroTik at {ROUTER_HOST}")

        address_list_resource = api.get_resource('/ip/firewall/address-list')

        logger.info(f"Retrieving current entries from '{ADDRESS_LIST_NAME_FINAL}' on MikroTik...")
        # Only retrieve entries that were added by this script (using the defined comment)
        mikrotik_entries = address_list_resource.get(
            list=ADDRESS_LIST_NAME_FINAL,
            comment=LIST_COMMENT # IMPORTANT: Only manage entries we created
        )
        
        # Create a set of addresses currently on the router and a dict for easy removal
        mikrotik_ip_set = set(entry['address'] for entry in mikrotik_entries)
        mikrotik_id_map = {entry['address']: entry['id'] for entry in mikrotik_entries}
        logger.info(f"Found {len(mikrotik_ip_set)} existing entries with comment '{LIST_COMMENT}'.")

        # 3. Calculate Differential Sync
        
        # Entries to REMOVE: addresses in mikrotik_ip_set but NOT in new_ip_set
        to_remove = mikrotik_ip_set.difference(new_ip_set)
        
        # Entries to ADD: addresses in new_ip_set but NOT in mikrotik_ip_set
        to_add = new_ip_set.difference(mikrotik_ip_set)
        
        logger.info(f"\nSync Plan:")
        logger.info(f"Entries to ADD: {len(to_add)}")
        logger.info(f"Entries to REMOVE: {len(to_remove)}")
        logger.info(f"Entries to KEEP (Unchanged): {len(new_ip_set.intersection(mikrotik_ip_set))}")

        # 4. Execute Sync Operations

        # A. Remove Stale Entries
        if to_remove:
            logger.info("Removing stale entries from MikroTik list...")
            remove_count = 0
            for address in to_remove:
                entry_id = mikrotik_id_map.get(address)
                if entry_id:
                    address_list_resource.remove(id=entry_id)
                    remove_count += 1
            logger.info(f"Successfully removed {remove_count} entries.")
        else:
            logger.info("No entries to remove.")

        # B. Add New Entries
        if to_add:
            logger.info("Adding new entries to MikroTik list...")
            add_count = 0
            for address in to_add:
                address_list_resource.add(
                    list=ADDRESS_LIST_NAME_FINAL, 
                    address=address, 
                    comment=LIST_COMMENT
                )
                add_count += 1
                if add_count % 500 == 0:
                    logger.info(f"Added {add_count} entries...")
            logger.info(f"Successfully added {add_count} entries.")
        else:
            logger.info("No entries to add.")

        # 5. Check/Create Firewall Rule
        logger.info("Firing up firewall check...")
        check_and_create_firewall_rule(api)
        
    except routeros_api.exceptions.RouterOsApiError as e:
        logger.error(f"RouterOS API Error: {e}")
    except ConnectionRefusedError:
        logger.error(f"Connection Refused: Check API port {ROUTER_PORT} access.")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
    finally:
        if api_pool:
            api_pool.disconnect()
            logger.info("\nConnection closed.")

if __name__ == "__main__":
    main()