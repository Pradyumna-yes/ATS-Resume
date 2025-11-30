# Dockerfile.compile.tectonic
# Small image using prebuilt Tectonic binary to compile LaTeX.
# Replace ARG TECTONIC_URL if you want a different release.

FROM ubuntu:22.04 AS base
ENV DEBIAN_FRONTEND=noninteractive

# Install minimal runtime packages required by tectonic
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    xz-utils \
    libfontconfig1 \
    libfreetype6 \
    libx11-6 \
    libxext6 \
    libxrender1 \
  && rm -rf /var/lib/apt/lists/*

ARG TECTONIC_URL="https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic-0.13.2/tectonic-0.13.2-x86_64-unknown-linux-gnu.tar.gz"

# Download and extract tectonic
RUN mkdir -p /opt/tectonic \
  && curl -fsSL "$TECTONIC_URL" -o /tmp/tectonic.tar.gz \
  && tar -xzf /tmp/tectonic.tar.gz -C /opt/tectonic --strip-components=1 \
  && rm /tmp/tectonic.tar.gz \
  && chmod +x /opt/tectonic/tectonic

# Create unprivileged user
RUN useradd -m -s /bin/bash appuser
WORKDIR /home/appuser
ENV PATH="/opt/tectonic:${PATH}"

USER appuser
# Default entrypoint is to keep container interactive; we will run tectonic via 'docker run ... tectonic'
CMD ["bash"]
