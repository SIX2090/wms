# WMS Makefile
# 一键封装 lint / test / smoke，提交前默认跑 `make check`。
# 用法：在仓库根目录执行 `make <target>` 或 `make help`。
#
# 适用环境：
#   - Linux / macOS：直接用 GNU make
#   - Windows：建议在 Git Bash / WSL 内执行（项目本身以 Python 为主，PowerShell 入口见各 .bat 脚本）
#
# 依赖：Python 3.11+；pytest 在 app/requirements.txt 或 `pip install pytest` 即可

PYTHON ?= python3
PIP ?= $(PYTHON) -m pip

# 默认端口 8080；如需换端口：make smoke BASE_URL=http://127.0.0.1:18080
BASE_URL ?= http://127.0.0.1:8080

.DEFAULT_GOAL := help

.PHONY: help
help: ## 显示本 Makefile 所有可执行 target
	@echo "WMS Makefile - 提交前必跑 \`make check\`"
	@echo ""
	@echo "常用 target:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "示例："
	@echo "  make check    # 提交前：lint + 86 BUG 回归 + pytest"
	@echo "  make smoke    # 改完模板/路由后：121 冒烟（需先启动 WMS 服务）"

.PHONY: lint
lint: ## 跑 7 条防 BUG 规则 + 禁止裸调非 GET fetch
	@echo ">> lint_wms_rules.py (A1-A7)"
	@$(PYTHON) scripts/lint_wms_rules.py
	@echo ">> lint_no_raw_post_fetch.py (防 CSRF 漏写)"
	@$(PYTHON) scripts/lint_no_raw_post_fetch.py
	@echo "OK: lint 通过"

.PHONY: bugs
bugs: ## 跑 86 项 BUG 静态回归（无需启动服务）
	@echo ">> verify_wms_bugs.py"
	@$(PYTHON) scripts/verify_wms_bugs.py

.PHONY: unit
unit: ## 跑 pytest 单元测试（tests/）
	@echo ">> pytest tests/ -q"
	@$(PYTHON) -m pytest tests/ -q

.PHONY: check
check: lint bugs unit ## 提交前必跑：lint + 86 BUG 回归 + pytest
	@echo ""
	@echo "✓ make check 全部通过，可以 commit"

.PHONY: smoke
smoke: ## 跑 121 项冒烟测试（需先在另一个终端启动 WMS 服务）
	@echo ">> full_smoke_test.py (BASE_URL=$(BASE_URL))"
	@echo "   提示：另起一个终端执行 \`$(PYTHON) app/run_server.py\`"
	@$(PYTHON) scripts/full_smoke_test.py --base-url $(BASE_URL)

.PHONY: ci
ci: check smoke ## 本地模拟 GitHub Actions：check + smoke

.PHONY: install
install: ## 安装开发依赖（app/requirements.txt + pytest）
	@echo ">> pip install -r app/requirements.txt"
	@$(PIP) install -r app/requirements.txt
	@echo ">> pip install pytest"
	@$(PIP) install pytest
	@echo "OK: 依赖安装完成"

.PHONY: hooks
hooks: ## 启用本地 git 钩子（每个 clone 必做一次）
	@bash .githooks/install-hooks.sh

.PHONY: audit
audit: ## 跑完整静态审计（lint + 86 回归 + 月度 BUG 复盘）
	@$(MAKE) check
	@echo ">> monthly_bug_review.py (月度 BUG 复盘)"
	@$(PYTHON) scripts/monthly_bug_review.py

.PHONY: clean
clean: ## 清理 pytest / pyc 缓存
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name '*.pyc' -delete 2>/dev/null || true
	@echo "OK: 缓存清理完成"
