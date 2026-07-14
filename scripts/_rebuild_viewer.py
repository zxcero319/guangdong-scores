# -*- coding: utf-8 -*-
"""
重建 guangdong_scores_viewer.html

从 data/viewer_data.json 读取记录 → 构建城市/辖区索引 → 填充模板 → 输出 HTML

用法:
    python scripts/_rebuild_viewer.py           # 输出到 dist/
    python scripts/_rebuild_viewer.py --check   # 仅校验数据不输出
"""
import json, os, sys, re
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(ROOT, "data", "viewer_data.json")
TEMPLATE_FILE = os.path.join(ROOT, "viewer_template.html")
OUTPUT_FILE = os.path.join(ROOT, "dist", "guangdong_scores_viewer.html")


def load_records(path=None):
    """加载记录。path 省略则默认从 viewer_data.json 加载。"""
    path = path or DATA_FILE
    if not os.path.exists(path):
        raise FileNotFoundError("数据文件不存在: " + path)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_records(records, path=None):
    """保存记录到 viewer_data.json。"""
    path = path or DATA_FILE
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print("Saved {} records to {}".format(len(records), path))


def build_indices(records):
    """从记录构建城市/辖区索引。返回 (city_order, city_district_list)。"""
    city_districts = defaultdict(set)
    city_counts = Counter()
    for a in records:
        city = a.get("c", "")
        district = a.get("d", "")
        if city:
            city_counts[city] += 1
        if district:
            city_districts[city].add(district)

    city_order = [city for city, _ in city_counts.most_common()]

    city_district_list = {}
    for city in city_order:
        dist_counter = Counter()
        for a in records:
            if a.get("c") == city:
                dist_counter[a.get("d", "")] += 1
        city_district_list[city] = [(d, c) for d, c in dist_counter.most_common()]

    return city_order, city_district_list


def build_html(records, template_path=None):
    """从记录 + 模板构建完整 HTML。返回字符串。"""
    template_path = template_path or TEMPLATE_FILE
    if not os.path.exists(template_path):
        raise FileNotFoundError("模板文件不存在: " + template_path)

    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()

    city_order, city_district_list = build_indices(records)

    data_json = json.dumps(records, ensure_ascii=False, separators=(",", ":"))
    city_dist_json = json.dumps(city_district_list, ensure_ascii=False, separators=(",", ":"))
    city_order_json = json.dumps(city_order, ensure_ascii=False)

    html = template.replace("__DATA_PLACEHOLDER__", data_json)
    html = html.replace("__CITY_DIST_PLACEHOLDER__", city_dist_json)
    html = html.replace("__CITY_ORDER_PLACEHOLDER__", city_order_json)

    return html


def validate_html(html):
    """快速校验 HTML 结构完整性。返回 (ok, issues)。"""
    issues = []

    # 1. 关键 var 声明
    for pat, label in [
        (r"var ALL_DATA = \[", "ALL_DATA"),
        (r"var CITY_DISTRICTS = \{", "CITY_DISTRICTS"),
        (r"var CITY_ORDER = \[", "CITY_ORDER"),
    ]:
        if not re.search(pat, html):
            issues.append("缺少: " + label)

    # 2. 关键函数
    for fn in ["toggleFav", "init", "applyFilters", "renderTable", "exportCSV"]:
        if html.count("function " + fn + "(") != 1:
            issues.append("函数 {} 出现 {} 次".format(fn, html.count("function " + fn + "(")))

    # 3. 闭合标签
    if html.count("</script>") != 1:
        issues.append("</script> 出现 {} 次".format(html.count("</script>")))
    if not html.strip().endswith("</html>"):
        issues.append("未以 </html> 结尾")

    # 4. 结构括号平衡（只检查 {} 和 []，不检查 () 因为数据字段中含半角括号）
    js = html[html.find("<script>") : html.find("</script>")]
    braces_ok = js.count("{") == js.count("}")
    brackets_ok = js.count("[") == js.count("]")
    if not braces_ok:
        issues.append("花括号不平衡 (diff={})".format(js.count("{") - js.count("}")))
    if not brackets_ok:
        issues.append("方括号不平衡 (diff={})".format(js.count("[") - js.count("]")))

    return len(issues) == 0, issues


def main():
    check_only = "--check" in sys.argv

    print("Loading records...")
    records = load_records()
    print("  {} records".format(len(records)))

    print("Building HTML...")
    html = build_html(records)

    print("Validating...")
    ok, issues = validate_html(html)
    if issues:
        for issue in issues:
            print("  ISSUE: " + issue)
    print("  Validation: " + ("PASS" if ok else "FAIL"))

    if check_only:
        print("\nCheck-only mode, no output written.")
        return 0 if ok else 1

    # 提取数据统计
    total_positions = sum(r.get("pr", 0) or 0 for r in records)
    cities = len(set(r.get("c", "") for r in records if r.get("c")))
    districts = len(set((r.get("c", ""), r.get("d", "")) for r in records if r.get("d")))
    with_ms = sum(1 for r in records if r.get("ms") and r["ms"] > 0)
    with_ts = sum(1 for r in records if r.get("ts") and r["ts"] > 0)

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    file_size = os.path.getsize(OUTPUT_FILE)
    print("\n=== 输出 ===")
    print("文件: " + OUTPUT_FILE)
    print("大小: {:,} bytes ({:.0f} KB)".format(file_size, file_size / 1024))
    print("记录: {:,} 条".format(len(records)))
    print("城市: {} 个".format(cities))
    print("辖区: {} 个".format(districts))
    print("拟聘总人数: {:,}".format(total_positions))
    print("MS>0: {:,}".format(with_ms))
    print("TS>0: {:,}".format(with_ts))
    print("Done!")

    return 0


if __name__ == "__main__":
    sys.exit(main())
