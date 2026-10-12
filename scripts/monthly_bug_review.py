#!/usr/bin/env python3
"""
WMS 每月 BUG 复盘脚本

统计 BUG 增减情况，识别高频模块/类型。
用法:
    python3 scripts/monthly_bug_review.py
    python3 scripts/monthly_bug_review.py --month 2026-07
    python3 scripts/monthly_bug_review.py --output reports/2026-07.md
"""
import argparse
import re
import sys
import subprocess
from pathlib import Path
from collections import Counter
from datetime import datetime

REPO_ROOT = Path(__file__).resolve().parent.parent
BASELINE_FILE = REPO_ROOT / 'WMS_BUG_BASELINE.md'
# F4.4 拆分：历史记录按月分片至 docs/ledger/bugs/（fixed-/history-/entries-*.md），
# 复盘需合并主文件 + 全部分片；INDEX.md 为衍生索引不参与。
BUG_SHARD_DIR = REPO_ROOT / 'docs' / 'ledger' / 'bugs'
DEFAULT_OUTPUT = REPO_ROOT / 'WMS_QUALITY_REPORT.md'

# BUG ID 格式: BUG-YYYY-MM-DD-NNN
BUG_ID_PATTERN = re.compile(r'BUG-(\d{4})-(\d{2})-(\d{2})-(\d{3})')

# 类型关键字（用于 BUG 标题分类）
TYPE_KEYWORDS = {
    'CSRF': 'CSRF/安全',
    'LOGIN': '登录/认证',
    'AUTH': '登录/认证',
    'SQL': '数据/SQL',
    'QUERY': '数据/SQL',
    'API': 'API',
    'UI': '界面/UX',
    'UX': '界面/UX',
    'PERF': '性能',
    'IMPORT': '导入/导出',
    'EXPORT': '导入/导出',
    'PRINT': '打印',
    'STOCK': '库存',
    'MATERIAL': '物料',
    'ORDER': '订单',
    'SALES': '销售',
    'PURCHASE': '采购',
}


def next_month_first_day(month_str):
    """根据 'YYYY-MM' 返回下月第一天的 'YYYY-MM-DD'，避免 --until 解析 '2026-07-32' 失败"""
    year, month = map(int, month_str.split('-'))
    if month == 12:
        return f'{year + 1}-01-01'
    return f'{year}-{month + 1:02d}-01'


def classify_type(title):
    """根据 BUG 标题分类"""
    title_upper = title.upper()
    for kw, category in TYPE_KEYWORDS.items():
        if kw in title_upper:
            return category
    return '其他'


def get_commits_for_month(month_str):
    """用 git log 拿当月所有 commit（--until 用下月第一天以包含整个自然月）"""
    try:
        since = f'{month_str}-01'
        until = next_month_first_day(month_str)
        result = subprocess.run(
            ['git', 'log', '--since', since, '--until', until,
             '--pretty=format:%H|%s|%an|%ad', '--date=short', '--no-merges'],
            cwd=str(REPO_ROOT),
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return []
        commits = []
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue
            parts = line.split('|', 3)
            if len(parts) >= 4:
                commits.append({
                    'sha': parts[0],
                    'subject': parts[1],
                    'author': parts[2],
                    'date': parts[3],
                })
        return commits
    except Exception as e:
        print(f'警告：git log 失败：{e}', file=sys.stderr)
        return []


def build_status_index(baseline_content):
    """构建 BUG ID → 状态 的索引，按 BUG ID 出现的最近 section header 判定。
    状态：fixed / open / false_positive / deferred / unknown

    F4.4 拆分兼容：分片文件头为一级标题（``# BUG 基线 · 已修复归档 YYYY-MM``
    等），本函数匹配一二级标题（``^#{1,2}\\s+``），使分片自带状态语义，
    与拆分前「主文件章节标题判定」行为等价、且与拼接顺序无关。
    """
    # 解析 section header
    status_by_id = {}  # 第一次出现的状态
    current_section = 'unknown'

    for line in baseline_content.split('\n'):
        section_m = re.match(r'^#{1,2}\s+(.+)', line)
        if section_m:
            title = section_m.group(1)
            if '已修复' in title or '已修复并纳入回归' in title:
                current_section = 'fixed'
            elif '误报' in title:
                current_section = 'false_positive'
            elif '暂缓' in title or '降级' in title:
                current_section = 'deferred'
            elif '未修复' in title or '开放' in title or '新发现' in title:
                current_section = 'open'
            else:
                current_section = 'unknown'
            continue

        for m in BUG_ID_PATTERN.finditer(line):
            bug_id = f'BUG-{m.group(1)}-{m.group(2)}-{m.group(3)}-{m.group(4)}'
            # 同 ID 多处出现以"第一次"为权威（基线表头）
            if bug_id not in status_by_id:
                status_by_id[bug_id] = current_section
    return status_by_id


def analyze(baseline_content, month_str):
    """分析 BUG 数据"""
    # 1. 找所有 BUG ID + 状态索引
    status_index = build_status_index(baseline_content)
    bug_ids = list(status_index.keys())

    # 2. 找当月 commit
    commits = get_commits_for_month(month_str)
    new_bugs_this_month = []  # 从 commit message 推算

    for c in commits:
        bug_match = BUG_ID_PATTERN.search(c['subject'])
        if bug_match:
            new_bugs_this_month.append({
                'id': f"BUG-{bug_match.group(1)}-{bug_match.group(2)}-{bug_match.group(3)}-{bug_match.group(4)}",
                'commit_sha': c['sha'][:7],
                'subject': c['subject'],
                'date': c['date'],
            })

    # 3. 统计
    type_counter = Counter()
    status_counter = Counter()
    for bug_id, st in status_index.items():
        status_counter[st] += 1

    for nb in new_bugs_this_month:
        # 从 subject 推算类型（去掉 BUG ID 前缀）
        subject = re.sub(BUG_ID_PATTERN, '', nb['subject']).strip()
        bug_type = classify_type(subject)
        type_counter[bug_type] += 1

    return {
        'total': len(bug_ids),
        'status_distribution': status_counter,
        'this_month_commits': len(commits),
        'this_month_bug_commits': new_bugs_this_month,
        'type_distribution': type_counter,
    }


def format_report(month_str, data):
    """生成 Markdown 报告"""
    sd = data['status_distribution']
    lines = []
    lines.append(f'# WMS BUG 复盘报告 - {month_str}')
    lines.append('')
    lines.append(f'**生成时间**：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    lines.append('')
    lines.append('---')
    lines.append('')
    lines.append('## 总体统计')
    lines.append('')
    lines.append(f'- **历史总 BUG 数**：{data["total"]}')
    lines.append(f'- **已修复**：{sd.get("fixed", 0)}')
    lines.append(f'- **待修复/未修复**：{sd.get("open", 0)}')
    lines.append(f'- **已确认误报**：{sd.get("false_positive", 0)}')
    lines.append(f'- **降级/暂缓**：{sd.get("deferred", 0)}')
    lines.append(f'- **未分类**：{sd.get("unknown", 0)}')
    lines.append(f'- **本月 commit 数**：{data["this_month_commits"]}')
    lines.append(f'- **本月 BUG 相关 commit 数**：{len(data["this_month_bug_commits"])}')
    lines.append('')
    lines.append('## 本月 BUG 相关 commit')
    lines.append('')
    if data['this_month_bug_commits']:
        lines.append('| Commit | 日期 | 标题 |')
        lines.append('|---|---|---|')
        for nb in data['this_month_bug_commits']:
            lines.append(f'| {nb["commit_sha"]} | {nb["date"]} | {nb["subject"][:80]} |')
    else:
        lines.append('*本月无 BUG 相关 commit*')
    lines.append('')
    lines.append('## BUG 类型分布（本月）')
    lines.append('')
    if data['type_distribution']:
        lines.append('| 类型 | 数量 |')
        lines.append('|---|---|')
        for t, c in data['type_distribution'].most_common():
            lines.append(f'| {t} | {c} |')
    else:
        lines.append('*本月无 BUG*')
    lines.append('')
    lines.append('## 复盘要点')
    lines.append('')
    lines.append('1. **本月新增 BUG 数量**：' + str(len(data['this_month_bug_commits'])))
    high_type = data['type_distribution'].most_common(1)[0][0] if data['type_distribution'] else '无'
    lines.append('2. **高频类型**：' + high_type)
    lines.append('3. **待修复积压**：' + str(sd.get('open', 0)))
    lines.append('')
    lines.append('---')
    lines.append('')
    lines.append('## 改进建议')
    lines.append('')
    open_n = sd.get('open', 0)
    if open_n > 0:
        lines.append(f'- ⚠️ 有 {open_n} 个 BUG 待修复，建议优先处理')
    if data['this_month_bug_commits'] and len(data['this_month_bug_commits']) > 5:
        lines.append(f'- ⚠️ 本月 BUG 数较多（{len(data["this_month_bug_commits"])} 个），建议回顾根因')
    if not data['this_month_bug_commits']:
        lines.append('- ✅ 本月无 BUG，质量良好')
    if sd.get('unknown', 0) > 0:
        lines.append(f'- ℹ️ {sd.get("unknown", 0)} 个 BUG 状态未标注，建议补"已修复"/"未修复"/"误报"/"暂缓" section')
    lines.append('')
    return '\n'.join(lines)


def _load_baseline_text() -> str:
    """加载基线全文：主文件 + F4.4 分片，按拆分前的章节顺序线性化拼接。

    状态判定（build_status_index）依赖「最近章节标题 + 首次出现」，顺序还原
    保证与拆分前的单文件行为**逐 ID 等价**（fixed 315 / unknown 141 /
    deferred 19 / false_positive 1，2026-10-13 拆分时验证）。
    若主文件缺任一章节标题（未来结构变更），退化为「主文件 + 全部分片」。
    """
    main_lines = BASELINE_FILE.read_text(encoding='utf-8').split('\n')

    def find(needle):
        for i, line in enumerate(main_lines):
            if line.startswith(needle):
                return i
        return None

    def shards(prefix):
        if not BUG_SHARD_DIR.exists():
            return ''
        return '\n'.join(
            p.read_text(encoding='utf-8')
            for p in sorted(BUG_SHARD_DIR.glob(f'{prefix}-*.md'))
        )

    i_fixed = find('## 已修复并纳入回归')
    i_mis = find('## 已确认误报')
    i_hist = find('## 历史登记区')
    i_daily = find('## 每日使用方式')
    if None in (i_fixed, i_mis, i_hist, i_daily):
        # 降级：不保证顺序等价，但统计仍可运行
        text = '\n'.join(main_lines)
        if BUG_SHARD_DIR.exists():
            for shard in sorted(BUG_SHARD_DIR.glob('*.md')):
                if shard.name != 'INDEX.md':
                    text += '\n' + shard.read_text(encoding='utf-8')
        return text

    return (
        '\n'.join(main_lines[:i_fixed]) + '\n'          # 前部（判定规则、技术债等）
        + shards('fixed') + '\n'                         # 原「已修复并纳入回归」
        + '\n'.join(main_lines[i_mis:i_hist]) + '\n'     # 已确认误报 + 降级或暂缓
        + shards('history') + '\n'                       # 原「历史登记区」
        + '\n'.join(main_lines[i_daily:]) + '\n'         # 每日使用方式 + 门禁说明
        + shards('entries')                              # 原门禁段小节 + 尾部详情小节
    )


def main():
    parser = argparse.ArgumentParser(description='WMS 每月 BUG 复盘')
    parser.add_argument('--month', default=datetime.now().strftime('%Y-%m'),
                        help='月份，格式 YYYY-MM（默认当月）')
    parser.add_argument('--output', default=str(DEFAULT_OUTPUT),
                        help='输出文件路径（默认 WMS_QUALITY_REPORT.md）')
    args = parser.parse_args()

    if not BASELINE_FILE.exists():
        print(f'错误：{BASELINE_FILE} 不存在', file=sys.stderr)
        return 1

    baseline_content = _load_baseline_text()
    data = analyze(baseline_content, args.month)
    report = format_report(args.month, data)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding='utf-8')

    sd = data['status_distribution']
    print(f'✓ 报告已生成：{output_path}')
    print(f'  总 BUG: {data["total"]} (已修复 {sd.get("fixed",0)} / 待修复 {sd.get("open",0)} / 误报 {sd.get("false_positive",0)} / 暂缓 {sd.get("deferred",0)} / 未分类 {sd.get("unknown",0)})')
    print(f'  本月 BUG 相关 commit: {len(data["this_month_bug_commits"])}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
