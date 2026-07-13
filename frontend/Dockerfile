FROM node:22-alpine AS deps
WORKDIR /app
COPY package*.json ./
RUN npm ci

FROM deps AS build
ARG VITE_API_BASE_URL=http://127.0.0.1:8000
ARG VITE_KAKAO_MAP_JS_KEY=
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_KAKAO_MAP_JS_KEY=$VITE_KAKAO_MAP_JS_KEY
COPY . .
RUN npm run build

EXPOSE 4173
CMD ["npm", "run", "preview", "--", "--host", "0.0.0.0", "--port", "4173"]
