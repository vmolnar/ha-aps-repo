# Websupport DNS Addon for Home Assistant

Dynamic DNS (DDNS) service for Websupport.sk domains with automatic IP updates.

## Features

- Automatic DNS record updates for Websupport.sk domains
- Support for multiple subdomains
- Configurable update intervals
- HMAC-SHA1 authentication with Websupport API
- Public IP detection using ipify.org
- Comprehensive logging

## Installation

1. Add this repository to your Home Assistant addon store
2. Install the Websupport DNS addon
3. Configure the addon with your Websupport credentials

## Configuration

```yaml
api_key: "your-websupport-api-key"
api_secret: "your-websupport-api-secret"
domain: "your-domain.com"
subdomains:
  - "home"
  - "www"
  - "ha"
record_type: "A"
ttl: 3600
update_interval: 10
```

## Options

- `api_key` (required): Your Websupport API key
- `api_secret` (required): Your Websupport API secret
- `domain` (required): Your domain name (e.g., example.com)
- `subdomains` (required): List of subdomains to update
- `record_type`: DNS record type (A or AAAA), default: A
- `ttl`: Time to live in seconds, default: 3600
- `update_interval`: Update interval in minutes, default: 10

## Services

The addon provides a service to manually trigger DNS updates:

```yaml
service: websupport_dns.update
description: Update DNS records immediately
```

## How It Works

1. The addon starts and loads configuration from Home Assistant
2. It detects your public IP address using ipify.org
3. It authenticates with Websupport API using HMAC-SHA1 signatures
4. It checks existing DNS records for your subdomains
5. It creates or updates DNS records to point to your current public IP
6. It repeats this process at the configured interval

## Logging

Logs are written to `/data/websupport_dns.log` and include:
- Timestamped entries
- Update status (success/failure)
- Public IP addresses
- Error messages

## Troubleshooting

- Check the addon logs for error messages
- Verify your API credentials are correct
- Ensure your domain exists in your Websupport account
- Check network connectivity

## Support

For issues and questions, please refer to the Home Assistant community forums.