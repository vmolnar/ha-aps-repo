#!/usr/bin/with-contenv bashio

LAT=$(bashio::config 'latitude')
LONG=$(bashio::config 'longitude')
LOCATION=$(bashio::config 'location_name')
TIMEZONE=$(bashio::config 'timezone')

while true; do
    echo "Starting meteo.py"
    
    # Run python and capture the exit code
    if python3 /app/meteo.py "${LAT}" "${LONG}" "${LOCATION}" "${TIMEZONE}"; then
        echo "Script finished successfully, waiting 5 minutes..."
        sleep 300
    else
        EXIT_STATUS=$?
        bashio::log.error "Python script crashed with exit code $EXIT_STATUS"
        
        # If it was killed (Signal 137), exit the addon so the Watchdog restarts it
        if [ $EXIT_STATUS -eq 137 ] || [ $EXIT_STATUS -eq 139 ]; then
            bashio::log.fatal "Out of Memory or Segfault detected. Exiting container."
            exit 1
        fi
        
        echo "Minor error, retrying in 30 seconds..."
        sleep 30
    fi
done
