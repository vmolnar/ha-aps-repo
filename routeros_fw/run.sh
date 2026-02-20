#!/usr/bin/with-contenv bashio

# Create main config
HOST=$(bashio::config 'host')
PORT=$(bashio::config 'port')
USER=$(bashio::config 'user')
PASSWD=$(bashio::config 'passwd')

while [ true ];
do
    echo "--- Starting mikrotik-block-ip.py"
    python3 /app/mikrotik-block-ip.py  "${HOST}" "${PORT}" "${USER}" "${PASSWD}"

    sleep 43200
done
