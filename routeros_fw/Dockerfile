ARG BUILD_FROM
FROM $BUILD_FROM

RUN apk add --no-cache python3 py3-pip py3-requests
RUN pip install routeros-api --break-system-packages

WORKDIR /app

# Copy data for add-on
COPY run.sh /
RUN chmod a+x /run.sh

COPY mikrotik-block-ip.py /app/

CMD [ "/run.sh" ]
