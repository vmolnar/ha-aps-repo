ARG BUILD_FROM
FROM $BUILD_FROM

# Install dependencies
RUN apk add --no-cache \
    bash \
    curl \
    nginx \
    php8 \
    php8-fpm \
    php8-gd \
    php8-json \
    php8-mbstring \
    php8-mysqlnd \
    php8-opcache \
    php8-xml \
    php8-zip \
    php8-zlib \
    php8-curl \
    php8-dom \
    php8-fileinfo \
    php8-ctype \
    php8-iconv \
    php8-session \
    php8-simplexml \
    php8-tokenizer \
    php8-xmlreader \
    php8-xmlwriter \
    php8-pdo \
    php8-pdo_mysql \
    php8-openssl \
    php8-pdo_sqlite \
    supervisor

# Install Nextcloud
RUN mkdir -p /var/www/html && \
    curl -sS https://download.nextcloud.com/server/releases/latest.tar.gz | tar -xz -C /var/www/html --strip-components=1 && \
    chown -R www-data:www-data /var/www/html && \
    mkdir -p /var/lib/nginx/tmp

# Copy configuration files
COPY config.php /var/www/html/config/
COPY nginx.conf /etc/nginx/http.d/default.conf
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Copy run script
COPY run.sh /
RUN chmod a+x /run.sh

EXPOSE 80

CMD ["/run.sh"]