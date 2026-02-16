ARG BUILD_FROM
FROM $BUILD_FROM

RUN apk add --no-cache python3 py3-pip

COPY requirements.txt /app/
RUN pip install --no-cache-dir --break-system-packages -r /app/requirements.txt

COPY run.sh /
RUN chmod a+x /run.sh

COPY dns_manager.py run.py /app/
WORKDIR /app

CMD ["/run.sh"]
