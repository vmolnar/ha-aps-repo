# Nextcloud Home Assistant Addon

This is a simple Nextcloud addon for Home Assistant that provides a basic Nextcloud installation using the official Nextcloud Docker setup.

## Features

- Simple setup with MySQL/MariaDB database support
- Automatic configuration through Home Assistant addon options
- Basic security configuration
- Supervised services (PHP-FPM and Nginx)

## Configuration

Configure the addon through the Home Assistant UI with these options:

- `database_type`: Database type (default: "sqlite", options: "sqlite" or "mysql")
- `mysql_host`: Database host (default: "db", only used if database_type is "mysql")
- `mysql_database`: Database name (default: "nextcloud", only used if database_type is "mysql")
- `mysql_user`: Database username (default: "nextcloud", only used if database_type is "mysql")
- `mysql_password`: Database password (only used if database_type is "mysql")
- `nextcloud_admin_user`: Nextcloud admin username (default: "admin")
- `nextcloud_admin_password`: Nextcloud admin password
- `trusted_domains`: Space-separated list of trusted domains

## Installation

1. Add this repository to your Home Assistant addon store
2. Install the Nextcloud addon
3. Configure the addon with your database and admin credentials
4. Start the addon

## Notes

- **SQLite (default)**: No external database required - simple and easy to set up
- **MySQL/MariaDB**: For better performance and scalability, requires a separate database container/service (mysql client not included in container)
- The addon uses internal storage for persistent data
- For production use, consider adding SSL/TLS termination through a reverse proxy
- This is a basic setup - for advanced features, consider using the official Nextcloud Docker image directly

## License

This addon is provided as-is under the MIT license. Nextcloud itself is licensed under AGPL-3.0.