#!/bin/bash
# 一键启用 WMS 仓库的 pre-commit 钩子
# 作用：把 git 的 core.hooksPath 指向本仓库自带的 .githooks/ 目录，
#      这样 git commit / git push 时会自动跑 pre-commit / pre-push 钩子。
# 为什么必须启用：
#   - 仓库 7 条防 BUG 规则 + 86 项静态回归 + 90 项单元测试 都依赖 .githooks/pre-commit
#   - 不启用等于裸调，CI 跑过的规则本地漏过，等于"只在 CI 拦截"，开发者体验差
#   - 主动 unset 是绕过检查；本脚本一键恢复，忘记/绕过都不必要
# 跳过方法（紧急情况）：git commit --no-verify（不推荐，会绕过所有检查）

set -e

REPO_ROOT="$(git rev-parse --show-toplevel)"
HOOKS_DIR="$REPO_ROOT/.githooks"

if [ ! -d "$HOOKS_DIR" ]; then
    echo "✗ 找不到 $HOOKS_DIR，请确认你在 WMS 仓库根目录执行"
    exit 1
fi

git config core.hooksPath "$HOOKS_DIR"

echo "✓ pre-commit 钩子已启用"
echo "  hooksPath = $(git config core.hooksPath)"
echo "  钩子文件: pre-commit (防 BUG 7 条规则) / pre-push (禁删 main)"
echo ""
echo "验证：尝试提交一次会跑以下检查："
echo "  1. scripts/lint_wms_rules.py  (A1-A7 7 条规则)"
echo "  2. scripts/lint_no_raw_post_fetch.py  (裸调 fetch 检查)"
echo ""
echo "跳过钩子: git commit --no-verify (不推荐)"
echo "恢复钩子: bash .githooks/install-hooks.sh (就是本脚本)"
