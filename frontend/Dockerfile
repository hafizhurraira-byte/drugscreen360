FROM node:20-alpine

WORKDIR /app

COPY frontend/package*.json /app/
RUN npm install

COPY frontend /app

ENV VITE_API_BASE_URL=http://127.0.0.1:8010

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
