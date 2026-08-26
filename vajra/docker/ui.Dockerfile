# The Next.js prototype. Built once; the demo path serves committed reports.
FROM node:20-slim
WORKDIR /app
COPY package.json ./
RUN npm install --no-audit --no-fund
COPY . .
RUN npm run build
EXPOSE 3000
CMD ["npm", "run", "start"]
