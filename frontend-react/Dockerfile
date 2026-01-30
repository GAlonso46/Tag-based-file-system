# Dockerfile para Frontend React
# Etapa 1: Build
FROM node:20-alpine AS build

WORKDIR /app

# Copiar package files
COPY package.json yarn.lock ./

# Instalar dependencias
RUN yarn install --frozen-lockfile

# Copiar código fuente
COPY . .

# Argumento para la URL del API (ahora usa ruta relativa)
ARG VITE_API_URL=/api
ENV VITE_API_URL=${VITE_API_URL}

# Build para producción
RUN yarn build

# Etapa 2: Servidor Nginx
FROM nginx:alpine

# Copiar build al servidor
COPY --from=build /app/dist /usr/share/nginx/html

# Copiar configuración personalizada de nginx
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Exponer puerto
EXPOSE 80

# Comando por defecto
CMD ["nginx", "-g", "daemon off;"]
