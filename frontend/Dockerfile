FROM node:22-alpine
WORKDIR /app
COPY package*.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm install
COPY . .

# NEXT_PUBLIC_* vars must be available at build time so Next.js can bake
# them into the client bundle. Pass them as build args from compose.
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

RUN npm run build
EXPOSE 3000
CMD ["npm", "start"]
