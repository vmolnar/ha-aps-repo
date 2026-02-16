# Websupport DNS - Home Assistant Add-on

This add-on automatically updates DNS A records on Websupport.sk when your public IP address changes.

## Features

- **Automatic DNS Updates**: Keeps your DNS records up-to-date with your current public IP
- **Multiple Subdomains**: Update multiple subdomains with a single configuration
- **Configurable Interval**: Set how often to check for IP changes
- **TTL Control**: Configure DNS record TTL values
- **Error Handling**: Graceful error handling and logging

## Installation

1. Add this repository to your Home Assistant add-on store
2. Install the "Websupport DNS" add-on
3. Configure the add-on with your Websupport API credentials
4. Start the add-on

## First Run

On the first run, the add-on will:
- Test your API credentials
- Get your current public IP address
- Update all configured DNS records
- Then enter a loop to check and update records at the configured interval

## Logs

You can monitor the add-on's activity through the Home Assistant logs. The add-on will log:
- Successful DNS updates
- Connection test results
- Any errors encountered
- Public IP address changes

## Configuration

Configure the add-on by editing the configuration in the Home Assistant UI or by creating an `options.json` file:

```json
{
  "api_key": "your_websupport_api_key",
  "api_secret": "your_websupport_api_secret",
  "domain": "example.com",
  "subdomains": ["home", "www", "api"],
  "base_url": "rest.websupport.sk",
  "scan_interval": 10,
  "ttl": 3600
}
```

### Configuration Options

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `api_key` | Yes | - | Your Websupport API key |
| `api_secret` | Yes | - | Your Websupport API secret |
| `domain` | Yes | - | Your domain name (e.g., example.com) |
| `subdomains` | Yes | - | Array of subdomains to update |
| `base_url` | No | rest.websupport.sk | Websupport API base URL |
| `scan_interval` | No | 10 | Update interval in minutes (1-1440) |
| `ttl` | No | 3600 | DNS TTL in seconds (60-86400) |

## Usage

1. **Get API Credentials**: Obtain your Websupport API key and secret from your Websupport account
2. **Configure Add-on**: Set up the add-on with your credentials and domain information
3. **Start Add-on**: The add-on will automatically start updating your DNS records
4. **Monitor Logs**: Check the add-on logs to verify successful operation

## Troubleshooting

### Authentication Failed
- Verify your API key and secret are correct
- Check that your Websupport account has DNS management permissions
- Ensure the API base URL is correct

### DNS Update Failed
- Verify the domain exists in your Websupport account
- Check that the subdomains are valid
- Ensure your public IP is accessible

### Connection Issues
- Check your internet connection
- Verify Websupport API is available
- Test with a longer update interval

## Support

For issues and feature requests, please open an issue on the GitHub repository.

## License

This add-on is open source and available under the MIT License.