FROM quay.io/oauth2-proxy/oauth2-proxy:v7.6.0

USER root
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
USER 65534
