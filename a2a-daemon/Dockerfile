FROM node:22-slim

RUN apt-get update && apt-get install -y curl ca-certificates && rm -rf /var/lib/apt/lists/*

RUN npm install -g @okxweb3/a2a-node

RUN curl -fsSL "https://github.com/okx/onchainos-skills/releases/download/v4.3.0/onchainos-x86_64-unknown-linux-gnu" \
      -o /usr/local/bin/onchainos \
    && chmod +x /usr/local/bin/onchainos

RUN mkdir -p /root/.onchainos

CMD ["okx-a2a", "run"]
