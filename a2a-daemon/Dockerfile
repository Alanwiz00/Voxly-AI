FROM node:24-slim

RUN apt-get update && apt-get install -y curl ca-certificates && rm -rf /var/lib/apt/lists/*

RUN npm install -g @okxweb3/a2a-node@0.2.16

# Pin the release binary by checksum (from the release's checksums.txt) so a
# replaced or tampered asset fails the build instead of landing in the image.
ARG ONCHAINOS_VERSION=v4.6.4
ARG ONCHAINOS_SHA256=4de08bf964590168cb7fc4f5547a8b84408fea71b5ab7ba842191f0d2dc86fa6
RUN curl -fsSL "https://github.com/okx/onchainos-skills/releases/download/${ONCHAINOS_VERSION}/onchainos-x86_64-unknown-linux-gnu" \
      -o /usr/local/bin/onchainos \
    && echo "${ONCHAINOS_SHA256}  /usr/local/bin/onchainos" | sha256sum -c - \
    && chmod +x /usr/local/bin/onchainos

RUN mkdir -p /root/.onchainos

CMD ["okx-a2a", "run"]
