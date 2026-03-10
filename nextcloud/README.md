# Nextcloud Home Assistant Addon

This is a simple Nextcloud addon for Home Assistant that provides a basic Nextcloud installation using the official Nextcloud Docker setup.

## Features

- Simple setup with MySQL/MariaDB database support
- Automatic configuration through Home Assistant addon options
- Basic security configuration
- Supervised services (PHP-FPM and Nginx)

## Configuration

Configure the addon through the Home Assistant UI with these options:

- `mysql_host`: Database host (default: "db")
- `mysql_database`: Database name (default: "nextcloud")
- `mysql_user`: Database username (default: "nextcloud")
- `mysql_password`: Database password
- `nextcloud_admin_user`: Nextcloud admin username (default: "admin")
- `nextcloud_admin_password`: Nextcloud admin password
- `trusted_domains`: Space-separated list of trusted domains

## Installation

1. Add this repository to your Home Assistant addon store
2. Install the Nextcloud addon
3. Configure the addon with your database and admin credentials
4. Start the addon

## Notes

- This addon expects a separate MySQL/MariaDB database container/service to be available
- The addon uses the share directory for persistent storage
- For production use, consider adding SSL/TLS termination through a reverse proxy
- This is a basic setup - for advanced features, consider using the official Nextcloud Docker image directly

## License

This addon is provided as-is under the MIT license. Nextcloud itself is licensed under AGPL-3.0.