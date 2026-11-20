# VendorPulse production image (Render / any Docker host).
#
#   docker build -t vendorpulse .
#   docker run --rm -p 10000:10000 --env-file Backend/.env vendorpulse
#
# Stage 1 builds the React SPA with Vite base=/static/ so Django can serve it.
# Stage 2 compiles the Python wheels (mysqlclient needs a C toolchain).
# Stage 3 is the runtime: Django + Gunicorn, no compilers, WhiteNoise instead
# of Nginx for /static/.

FROM node:22-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS pybuild
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential default-libmysqlclient-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /wheels
COPY Backend/requirements.txt ./
RUN pip wheel --wheel-dir /wheels -r requirements.txt

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# libmariadb3 is the runtime library mysqlclient was linked against; the
# toolchain stays in the pybuild stage so the final image has no compilers.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libmariadb3 tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=pybuild /wheels /wheels
COPY Backend/requirements.txt ./
RUN pip install --no-index --find-links=/wheels -r requirements.txt \
    && rm -rf /wheels requirements.txt

COPY Backend/ ./Backend/
# Vite output becomes static files (STATICFILES_DIRS includes Backend/spa).
COPY --from=frontend /build/dist/ ./Backend/spa/
COPY deploy/entrypoint.sh ./entrypoint.sh

RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && chmod +x ./entrypoint.sh \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 10000
CMD ["./entrypoint.sh"]
