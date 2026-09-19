"""
共享字段归一化 — 所有入库脚本必须在写入 Viewer 前调用 normalize_record()
确保下拉菜单不产生格式/同义词重复
"""
import re

# === 标准值（只有这些值能出现在 edu/rs 下拉菜单中）===

# edu 学历 — 7 个标准值（2026-08-12: 硕士研究生及以上 合并到 研究生及以上）
EDU_MAP = {
    # 同义 → 标准
    '本科或以上': '本科及以上',
    '本科以上': '本科及以上',
    '本科及以上学历': '本科及以上',
    '本科 以上': '本科及以上',
    '本科及以上': '本科及以上',  # 不变
    # 本科（无"及以上"）→ 仅限本科
    '本科': '仅限本科',
    '仅限本科': '仅限本科',
    # 研究生 — 所有变体统一为 "研究生及以上"
    '研究生及以上': '研究生及以上',
    '研究生': '研究生及以上',
    '研究生学历': '研究生及以上',
    '硕士研究生及以上': '研究生及以上',
    '硕士研究生以上': '研究生及以上',
    '硕士研究生及\n以上': '研究生及以上',
    '研究生学历硕士或以上学位': '研究生及以上',
    # 博士
    '博士研究生': '博士研究生',
    # 大专
    '大专及以上': '大专及以上',
    '大专以上': '大专及以上',
    # 其他
    '非教师岗位': '非教师岗位',
    '技工院校': '技工院校',
}

# rs 考生类别/招聘范围 — 标准值
RS_MAP = {
    '不限': '不限',
    '应届生': '应届生',
    '应届毕业生': '应届生',
    '社会人员': '社会人员',
    '不限（师范类）': '不限（师范类）',
    '退役军人': '退役军人',
    '基层服务项目人员': '基层服务项目人员',
    '应往届研究生学历毕业生': '应往届研究生学历毕业生',
    '公费师范生': '公费师范生',
}


def normalize(s, mapping):
    """Return (normalized_value, was_changed)"""
    if not s:
        return s, False
    # Strip whitespace and newlines
    cleaned = re.sub(r'\s+', ' ', s).strip()
    if cleaned in mapping:
        normalized = mapping[cleaned]
        return normalized, (normalized != cleaned)
    # Unknown value — print warning but don't change
    if cleaned:
        print(f'  [WARN] Unknown value not in map: "{cleaned}"')
    return cleaned, False


def normalize_record(r):
    """Normalize edu and rs fields on a record dict. Returns count of changes."""
    changes = 0
    edu, changed = normalize(r.get('edu', ''), EDU_MAP)
    if changed:
        r['edu'] = edu
        changes += 1
    rs_raw = re.sub(r'\s+', ' ', str(r.get('rs', '') or '')).strip()
    # 年份前缀应届生变体（如"2026届应届生"）→ 应届生
    if rs_raw and rs_raw not in RS_MAP and '应届' in rs_raw:
        r['rs'] = '应届生'
        changes += 1
    else:
        rs, changed = normalize(rs_raw, RS_MAP)
        if changed:
            r['rs'] = rs
            changes += 1
    return changes


if __name__ == '__main__':
    # Self-test: show all standard values
    print('=== Standard edu values ===')
    seen = set()
    for v in EDU_MAP.values():
        if v not in seen:
            print(f'  {v}')
            seen.add(v)
    print(f'  ({len(seen)} values)')

    print('\n=== Standard rs values ===')
    seen = set()
    for v in RS_MAP.values():
        if v not in seen:
            print(f'  {v}')
            seen.add(v)
    print(f'  ({len(seen)} values)')
