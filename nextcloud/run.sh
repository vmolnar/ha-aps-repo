#!/usr/bin/with-contenv bashio

# Get configuration from Home Assistant
DATABASE_TYPE=$(bashio::config 'database_type')
MYSQL_HOST=$(bashio::config 'mysql_host')
MYSQL_DATABASE=$(bashio::config 'mysql_database')
MYSQL_USER=$(bashio::config 'mysql_user')
MYSQL_PASSWORD=$(bashio::config 'mysql_password')
NEXTCLOUD_ADMIN_USER=$(bashio::config 'nextcloud_admin_user')
NEXTCLOUD_ADMIN_PASSWORD=$(bashio::config 'nextcloud_admin_password')
TRUSTED_DOMAINS=$(bashio::config 'trusted_domains')

# Wait for database to be ready if using MySQL
if [ "$DATABASE_TYPE" = "mysql" ]; then
    bashio::log.info "Waiting for MySQL database to be ready..."
    # Check if mysql client is available
    if command -v mysql >/dev/null 2>&1; then
        while ! mysql -h "$MYSQL_HOST" -u "$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE" -e "SELECT 1" >/dev/null 2>&1; do
            sleep 5
            bashio::log.info "Database not ready yet, retrying..."
        done
    else
        bashio::log.warning "mysql client not available, skipping database readiness check"
    fi
else
    bashio::log.info "Using SQLite database (built-in)"
fi

# Configure Nextcloud
bashio::log.info "Configuring Nextcloud..."
if [ "$DATABASE_TYPE" = "mysql" ]; then
    cat > /var/www/html/config/autoconfig.php <<EOL
<?php
"$AUTO_CONFIG" = array(
    "dbtype" => "mysql",
    "dbname" => "$MYSQL_DATABASE",
    "dbuser" => "$MYSQL_USER",
    "dbpass" => "$MYSQL_PASSWORD",
    "dbhost" => "$MYSQL_HOST",
    "dbtableprefix" => "oc_",
    "adminlogin" => "$NEXTCLOUD_ADMIN_USER",
    "adminpass" => "$NEXTCLOUD_ADMIN_PASSWORD",
    "directory" => "/var/www/html/data",
);
EOL
else
    cat > /var/www/html/config/autoconfig.php <<EOL
<?php
"$AUTO_CONFIG" = array(
    "dbtype" => "sqlite",
    "dbtableprefix" => "oc_",
    "adminlogin" => "$NEXTCLOUD_ADMIN_USER",
    "adminpass" => "$NEXTCLOUD_ADMIN_PASSWORD",
    "directory" => "/var/www/html/data",
);
EOL
fi

# Set trusted domains if provided
if [ -n "$TRUSTED_DOMAINS" ]; then
    IFS=' ' read -ra DOMAINS <<< "$TRUSTED_DOMAINS"
    for domain in "${DOMAINS[@]}"; do
        echo "  '$domain' => true," >> /var/www/html/config/config.php
    done
fi

# Start supervisor to manage services
bashio::log.info "Starting Nextcloud services..."
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf