# The Next.js prototype. Built once; the demo path serves committed reports.
FROM node:20-slim
WORKDIR /app
# Lockfile included so the image installs the same tree scripts/ui.sh does. The `|| npm install`
# keeps the build working if the lockfile is ever absent.
COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund
COPY . .
RUN npm run build
EXPOSE 3000
CMD ["npm", "run", "start"]
