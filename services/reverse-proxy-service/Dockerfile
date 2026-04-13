# Minimal auth/mTLS proxy for worker API
# Alternative to Caddy for environments that prefer nginx
FROM nginx:alpine

# Install required packages
RUN apk add --no-cache \
    openssl \
    curl

# Copy nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf
COPY config.yaml /etc/gateway/config.yaml

# Create SSL directory
RUN mkdir -p /etc/nginx/ssl

# Create startup script
COPY start.sh /start.sh
RUN chmod +x /start.sh

# Expose port
EXPOSE 8443

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8443/health || exit 1

# Start nginx with custom configuration
CMD ["/start.sh"]
