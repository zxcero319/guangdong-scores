# -*- coding: utf-8 -*-
"""
重建 guangdong_scores_viewer.html（数据分离架构）

HTML 从 jsDelivr CDN 加载 viewer_data.json，本地只需维护数据文件。

用法:
    python scripts/_rebuild_viewer.py           # 输出到 dist/ 和根目录
    python scripts/_rebuild_viewer.py --check   # 仅校验数据不输出
"""
import json, os, sys, re
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(ROOT, "data", "viewer_data.json")
TEMPLATE_FILE = os.path.join(ROOT, "viewer_template.html")
DIST_DATA = os.path.join(ROOT, "dist", "viewer_data.json")
DIST_VIEWER = os.path.join(ROOT, "dist", "guangdong_scores_viewer.html")
ROOT_VIEWER = os.path.join(ROOT, "index.html")


def load_records(path=None):
    path = path or DATA_FILE
    if not os.path.exists(path):
        raise FileNotFoundError("数据文件不存在: " + path)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_records(records, path=None):
    path = path or DATA_FILE
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, separators=(",", ":"))
    print("Saved {} records to {}".format(len(records), path))


def validate_data(records):
    """快速校验数据完整性。返回 (ok, issues)。"""
    issues = []

    # 必需字段
    required = ["c", "d", "sc", "p", "st", "pr"]
    for i, r in enumerate(records[:5]):
        for f in required:
            if f not in r:
                issues.append("记录 {} 缺少字段 {}".format(i, f))

    # 记录数合理性
    if len(records) < 10000:
        issues.append("记录数异常少: {}".format(len(records)))
    if len(records) > 100000:
        issues.append("记录数异常多: {}".format(len(records)))

    # 城市数
    cities = set(r.get("c", "") for r in records if r.get("c"))
    if len(cities) < 10:
        issues.append("城市数异常少: {}".format(len(cities)))

    # PR>0 的比例
    pr_positive = sum(1 for r in records if r.get("pr") and r["pr"] > 0)
    if pr_positive < len(records) * 0.5:
        issues.append("PR>0 的记录不足一半: {} / {}".format(pr_positive, len(records)))

    return len(issues) == 0, issues


def build_stats(records):
    """生成统计摘要。"""
    total_positions = sum(r.get("pr", 0) or 0 for r in records)
    cities = len(set(r.get("c", "") for r in records if r.get("c")))
    districts = len(set((r.get("c", ""), r.get("d", "")) for r in records if r.get("d")))
    with_ms = sum(1 for r in records if r.get("ms") and r["ms"] > 0)
    with_ts = sum(1 for r in records if r.get("ts") and r["ts"] > 0)
    with_wc = sum(1 for r in records if r.get("wc") and r["wc"] > 0)
    with_ic = sum(1 for r in records if r.get("ic") and r["ic"] > 0)

    return {
        "records": len(records),
        "cities": cities,
        "districts": districts,
        "total_positions": total_positions,
        "ms_positive": with_ms,
        "ts_positive": with_ts,
        "wc_positive": with_wc,
        "ic_positive": with_ic,
    }


def main():
    check_only = "--check" in sys.argv

    print("Loading records...")
    records = load_records(DATA_FILE)
    print("  {} records".format(len(records)))

    print("Validating data...")
    ok, issues = validate_data(records)
    for issue in issues:
        print("  ISSUE: " + issue)
    print("  Data validation: " + ("PASS" if ok else "FAIL"))

    if check_only:
        stats = build_stats(records)
        print("\n=== 数据统计 ===")
        for k, v in stats.items():
            print("  {}: {}".format(k, v))
        return 0 if ok else 1

    # 1. 写入 dist/viewer_data.json
    print("\nWriting dist/viewer_data.json...")
    os.makedirs(os.path.dirname(DIST_DATA), exist_ok=True)
    save_records(records, DIST_DATA)
    data_size = os.path.getsize(DIST_DATA)
    print("  Size: {:,} bytes ({:.0f} MB)".format(data_size, data_size / 1024 / 1024))

    # 2. 从模板生成 HTML（无嵌入数据，仅框架）
    print("Generating HTML from template...")
    with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
        template = f.read()

    # 检查模板没有残留的 placeholders
    for ph in ["__DATA_PLACEHOLDER__", "__CITY_DIST_PLACEHOLDER__", "__CITY_ORDER_PLACEHOLDER__"]:
        if ph in template:
            print("  ERROR: Template contains stale placeholder: " + ph)
            return 1

    # 输出到 dist/
    os.makedirs(os.path.dirname(DIST_VIEWER), exist_ok=True)
    with open(DIST_VIEWER, "w", encoding="utf-8") as f:
        f.write(template)
    print("  dist/guangdong_scores_viewer.html: {:,} bytes".format(os.path.getsize(DIST_VIEWER)))

    # 输出到根目录 index.html
    with open(ROOT_VIEWER, "w", encoding="utf-8") as f:
        f.write(template)
    print("  index.html: {:,} bytes".format(os.path.getsize(ROOT_VIEWER)))

    # 3. 统计摘要
    stats = build_stats(records)
    print("\n=== 构建完成 ===")
    print("记录: {records:,} 条".format(**stats))
    print("城市: {cities} 个 · 辖区: {districts} 个".format(**stats))
    print("拟聘总人数: {total_positions:,}".format(**stats))
    print("MS>0: {ms_positive:,} · TS>0: {ts_positive:,}".format(**stats))
    print("WC>0: {wc_positive:,} · IC>0: {ic_positive:,}".format(**stats))
    print("Done!")

    return 0


if __name__ == "__main__":
    sys.exit(main())
