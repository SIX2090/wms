# Dependency downloads happen during image build, before any WMS code executes.
FROM node:24.22.1-bookworm-slim AS node
FROM python:3.11-slim-bookworm
ARG BROWSER=0
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && apt-get update && apt-get install -y --no-install-recommends git \
    && if [ "$BROWSER" = 1 ]; then apt-get install -y --no-install-recommends chromium fonts-noto-cjk; fi \
    && rm -rf /var/lib/apt/lists/*
COPY source/app/requirements*.txt /opt/requirements/
RUN pip install --no-cache-dir -r /opt/requirements/requirements-test.txt
COPY source/tools/browser_checks/package*.json /opt/wms/tools/browser_checks/
RUN npm ci --prefix /opt/wms/tools/browser_checks --ignore-scripts --no-audit --no-fund
COPY source/ /opt/wms/
COPY baseline/ /opt/wms-baseline/
COPY request.json /opt/wms-ci-request.json
RUN mkdir -p /work /run/wms-proof /opt/wms/output /opt/wms/app/instance \
    /opt/wms/app/logs /opt/wms/app/backups /opt/wms/app/static/uploads
ENV DATABASE_URL=sqlite:///:memory: WMS_DATABASE_URI=sqlite:///:memory: FLASK_ENV=testing \
    WMS_TEST_RUNTIME_PROOF=/run/wms-proof/proof.json WMS_SKIP_AUTO_UPDATE=1 \
    WMS_SKIP_STARTUP_BACKUP=1 WMS_SKIP_STARTUP_DB_UPGRADE=1 WMS_EXTERNAL_OPERATIONS_PAUSED=0 \
    WMS_LOCAL_PRINT_AGENT=0 AUTO_BACKUP_ENABLED=false WMS_ALLOW_INSECURE_COOKIE=1 \
    SECRET_KEY=synthetic-ci-only-secret WECHAT_HELPER_TOKEN=synthetic-ci-only-token \
    WMS_BOOTSTRAP_PASSWORD=admin PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
    PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONUTF8=1 PYTHONIOENCODING=utf-8 \
    TMPDIR=/work/profile/tmp HOME=/work/profile/home LOG_FILE=/work/profile/logs/app.log \
    UPLOAD_FOLDER=/work/profile/uploads OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
WORKDIR /opt/wms
USER 10001:10001
ENTRYPOINT ["python", "-I", "-B", "/opt/wms/scripts/ci_test_entry.py"]
