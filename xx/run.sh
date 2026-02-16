#!/usr/bin/with-contenv bashio

# Ensure the configuration directory exists
mkdir -p /data

# Check if we should run the update service
if bashio::services.available "update"; then
    echo "Running DNS update service..."
    python3 /usr/local/bin/websupport_dns.py --config /data/options.json
    exit 0
fi

# Main addon execution
echo "Starting Websupport DNS addon..."

# Load configuration
API_KEY=$(bashio::config 'api_key')
API_SECRET=$(bashio::config 'api_secret')
DOMAIN=$(bashio::config 'domain')
SUBDOMAINS=$(bashio::config 'subdomains')
RECORD_TYPE=$(bashio::config 'record_type')
TTL=$(bashio::config 'ttl')
UPDATE_INTERVAL=$(bashio::config 'update_interval')

# Convert subdomains array to space-separated string
SUBDOMAINS_STR=""
for subdomain in $SUBDOMAINS; do
    SUBDOMAINS_STR="$SUBDOMAINS_STR $subdomain"
done

# Create a temporary config file for the Python script
cat > /tmp/websupport_config.json << EOF
{
  "api_key": "$API_KEY",
  "api_secret": "$API_SECRET",
  "domain": "$DOMAIN",
  "subdomains": $SUBDOMAINS,
  "record_type": "$RECORD_TYPE",
  "ttl": $TTL,
  "update_interval_minutes": $UPDATE_INTERVAL
}
EOF

# Start the periodic updater
echo "Configuration loaded, starting periodic updates..."
exec python3 /usr/local/bin/periodic_updater.py --config /tmp/websupport_config.json