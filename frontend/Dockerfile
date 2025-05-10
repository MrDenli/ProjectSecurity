FROM node:20
WORKDIR /app
COPY package.json .
RUN npm install express axios
COPY frontend.js .
EXPOSE 3000
CMD ["node", "frontend.js"]