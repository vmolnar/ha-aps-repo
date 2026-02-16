#!/usr/bin/env python3
"""
Periodic DNS updater for Home Assistant Websupport DNS Addon
"""

import time
import subprocess
import sys
import json
import argparse
from datetime import datetime, timedelta

def load_config(config_file="/tmp/websupport_config.json"):
    """Load configuration from JSON file."""
    try:
        with open(config_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Config file {config_file} not found")
        return None
    except Exception as e:
        print(f"Error loading config: {e}")
        return None

def run_dns_update(config_file="/tmp/websupport_config.json"):
    """Run the DNS manager script."""
    try:
        result = subprocess.run([sys.executable, "/usr/local/bin/websupport_dns.py", "--config", config_file], 
                              capture_output=True, text=True, timeout=60)
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def log_message(message, log_file="/data/websupport_dns.log"):
    """Log a message to file with timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}\n"
    
    try:
        with open(log_file, "a") as f:
            f.write(log_entry)
    except Exception as e:
        print(f"Error writing to log file: {e}")

def main():
    """Main periodic execution loop."""
    parser = argparse.ArgumentParser(description="Periodic DNS Updater for Home Assistant")
    parser.add_argument("--config", default="/tmp/websupport_config.json", help="Configuration file path")
    parser.add_argument("--interval", type=int, default=10, help="Update interval in minutes")
    parser.add_argument("--max-runs", type=int, default=0, help="Maximum number of runs (0 for infinite)")
    parser.add_argument("--log-file", default="/data/websupport_dns.log", help="Log file path")
    
    args = parser.parse_args()
    
    # Load configuration
    config = load_config(args.config)
    if not config:
        print("Failed to load configuration")
        return 1
    
    # Get interval from config or command line
    interval_minutes = args.interval
    if 'update_interval_minutes' in config:
        interval_minutes = config['update_interval_minutes']
    
    interval_seconds = interval_minutes * 60
    
    print(f"Starting Websupport DNS Updater")
    print(f"Configuration: {args.config}")
    print(f"Update interval: {interval_minutes} minutes ({interval_seconds} seconds)")
    print(f"Log file: {args.log_file}")
    print(f"Max runs: {'infinite' if args.max_runs == 0 else args.max_runs}")
    print("=" * 60)
    
    run_count = 0
    
    try:
        while args.max_runs == 0 or run_count < args.max_runs:
            run_count += 1
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            print(f"\n[{timestamp}] Run #{run_count} - Starting DNS update...")
            log_message(f"Run #{run_count} - Starting DNS update...", args.log_file)
            
            # Run the DNS update
            success, stdout, stderr = run_dns_update(args.config)
            
            if success:
                print(f"[{timestamp}] ✅ DNS update completed successfully")
                log_message("DNS update completed successfully", args.log_file)
                
                # Extract public IP from output if available
                if "Current public IP:" in stdout:
                    ip_line = [line for line in stdout.split('\n') if "Current public IP:" in line][0]
                    public_ip = ip_line.split(":")[1].strip()
                    print(f"[{timestamp}] Public IP: {public_ip}")
                    log_message(f"Public IP: {public_ip}", args.log_file)
            else:
                print(f"[{timestamp}] ❌ DNS update failed")
                log_message("DNS update failed", args.log_file)
                if stderr:
                    print(f"Error: {stderr}")
                    log_message(f"Error: {stderr}", args.log_file)
            
            # Calculate next run time
            if args.max_runs == 0 or run_count < args.max_runs:
                next_run_time = datetime.now() + timedelta(seconds=interval_seconds)
                print(f"[{timestamp}] Next run scheduled for: {next_run_time.strftime('%Y-%m-%d %H:%M:%S')}")
                log_message(f"Next run scheduled for: {next_run_time.strftime('%Y-%m-%d %H:%M:%S')}", args.log_file)
                
                # Wait for the interval
                time.sleep(interval_seconds)
        
    except KeyboardInterrupt:
        print("\n🛑 DNS updater stopped by user")
        log_message("DNS updater stopped by user", args.log_file)
    except Exception as e:
        print(f"\n💥 DNS updater crashed: {e}")
        log_message(f"DNS updater crashed: {e}", args.log_file)
        return 1
    
    print(f"\n✅ DNS updater completed {run_count} runs")
    log_message(f"DNS updater completed {run_count} runs", args.log_file)
    return 0

if __name__ == "__main__":
    sys.exit(main())