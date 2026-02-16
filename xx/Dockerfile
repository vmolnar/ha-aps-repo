FROM homeassistant/amd64-base:3.20

# Install dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-requests \
    && rm -rf /var/lib/apt/lists/*

# Copy the application files
COPY websupport_dns.py /usr/local/bin/websupport_dns.py
COPY requirements.txt /usr/local/bin/requirements.txt

# Install Python dependencies
RUN pip3 install -r /usr/local/bin/requirements.txt

# Set up the entrypoint
COPY run.sh /
RUN chmod +x /run.sh

# Set up the configuration directory
RUN mkdir -p /data/options.json

# Set the entrypoint
ENTRYPOINT ["/run.sh"]