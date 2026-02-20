ARG BUILD_FROM
FROM $BUILD_FROM

RUN apk add --no-cache python3 py3-pip py3-matplotlib

WORKDIR /app

# Copy data for add-on
COPY run.sh /
RUN chmod a+x /run.sh

COPY meteo.py /app/

COPY icons.zip /app/
RUN mkdir /app/icons
RUN unzip /app/icons.zip -d /app/icons

CMD [ "/run.sh" ]
