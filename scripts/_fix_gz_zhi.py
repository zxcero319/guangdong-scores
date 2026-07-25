"""
Fix广州市直属本次更新 - 主列错位修复:
1. 删除27条表头垃圾行 (sc='单位', p='岗位名称' 等)
2. 修复st=空记录 — 从同校记录继承学段

根因: XLSX岗位表每个学校section之间有表头行,解析时被当数据读入
"""
import json
from collections import defaultdict

ROOT = r'D:\claude_code\gaokao\jiaozi\guangdong_scores'

def load_data():
    with open(f'{ROOT}/dist/viewer_data.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def save_data(data):
    with open(f'{ROOT}/dist/viewer_data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)

def is_garbage(r):
    """Detect header rows parsed as data"""
    sc = r.get('sc', '')
    p = r.get('p', '')
    su = r.get('su', '')
    edu = r.get('edu', '')
    code = r.get('position_code', '')

    if sc in ('单位', '招聘单位', '用人单位') and p in ('岗位名称', '职位名称', '招聘岗位'):
        return True
    if p == '岗位名称' and su == '岗位名称':
        return True
    if edu == '学历要求' and code == '职位代码':
        return True
    return False

def infer_stage(school, position, su, edu):
    """Infer学段 from school name and position name"""
    school = school or ''
    position = position or ''
    su = su or ''

    # School name inference (higher priority)
    if any(kw in school for kw in ['幼儿园', '幼儿']):
        return '幼儿'
    if any(kw in school for kw in ['小学']):
        return '小学'
    if any(kw in school for kw in ['特殊教育', '启智', '启慧', '启明', '聋', '盲']):
        return '特殊教育'
    if any(kw in school for kw in ['职业', '职校', '中专', '技工']):
        return '中职'
    if any(kw in school for kw in ['高等专科', '高职', '职业技术学院']):
        return '高职'
    if any(kw in school for kw in ['大学', '学院']) and '中学' not in school:
        return '高校'

    # Position name inference
    if any(kw in position for kw in ['高中']):
        return '高中'
    if any(kw in position for kw in ['初中']):
        return '初中'
    if '中学' in position:
        return '中学'
    if any(kw in position for kw in ['小学']):
        return '小学'
    if any(kw in position for kw in ['幼儿', '学前']):
        return '幼儿'
    if any(kw in position for kw in ['中职', '职业中专']):
        return '中职'
    if any(kw in position for kw in ['高职']):
        return '高职'
    if any(kw in position for kw in ['特殊教育', '特教']):
        return '特殊教育'

    # School name hints
    if '中学' in school:
        # Check if it's a complete中学 or just contains 中学
        if any(kw in school for kw in ['高级中学', '高中']):
            return '高中'
        if '初级中学' in school:
            return '初中'
        if '完全中学' in school:
            return '中学'
        # 广州中学生劳动技术学校 → 中学
        return '中学'

    if '实验学校' in school or '附属学校' in school or '湾区学校' in school:
        # K-12 type schools — default to中学
        return '中学'

    if '师范' in school:
        return '高职'

    return None

def main():
    data = load_data()
    print(f'Loaded: {len(data)} records')

    # ═══ Step 1: Delete garbage rows ═══
    garbage_indices = []
    for i, r in enumerate(data):
        if r.get('c') == '广州' and r.get('d') == '市直属' and is_garbage(r):
            garbage_indices.append(i)

    print(f'\n垃圾行: {len(garbage_indices)}条')
    for i in garbage_indices:
        r = data[i]
        print(f'  DEL [{i}] sc={r.get("sc")} p={r.get("p")} su={r.get("su")} edu={r.get("edu")} code={r.get("position_code")}')

    # Delete in reverse order to preserve indices
    for i in sorted(garbage_indices, reverse=True):
        del data[i]

    print(f'删除后: {len(data)} records')

    # ═══ Step 2: Fix st=空 for广州市直属 ═══
    gz = [(i, r) for i, r in enumerate(data) if r.get('c') == '广州' and r.get('d') == '市直属']

    # Build per-school st mapping from records that DO have st
    school_st = {}
    for i, r in gz:
        sc = r.get('sc', '')
        st = r.get('st', '')
        if sc and st and st.strip():
            if sc not in school_st:
                school_st[sc] = st

    print(f'\n同校st映射: {len(school_st)}所学校')
    for sc, st in sorted(school_st.items()):
        print(f'  {sc[:50]}: st={st}')

    # Fill empty st
    st_filled = 0
    st_inferred = 0
    for i, r in gz:
        if not r.get('st') or r.get('st', '').strip() == '':
            sc = r.get('sc', '')
            # Try same-school inheritance first
            if sc in school_st:
                r['st'] = school_st[sc]
                st_filled += 1
            else:
                # Try inference
                inferred = infer_stage(r.get('sc', ''), r.get('p', ''), r.get('su', ''), r.get('edu', ''))
                if inferred:
                    r['st'] = inferred
                    st_inferred += 1
                    school_st[sc] = inferred  # propagate to same school
                else:
                    print(f'  WARN: 无法推断st [{i}] sc={sc} p={r.get("p")} su={r.get("su")}')

    print(f'\nst修复:')
    print(f'  同校继承: {st_filled}条')
    print(f'  推断: {st_inferred}条')

    # ═══ Step 3: Check for other column issues ═══
    # Verify no more garbage
    remaining_garbage = sum(1 for r in data if r.get('c') == '广州' and r.get('d') == '市直属' and is_garbage(r))
    print(f'\n剩余垃圾行: {remaining_garbage}')

    # st=空 remaining
    gz_after = [r for r in data if r.get('c') == '广州' and r.get('d') == '市直属']
    st_empty = [r for r in gz_after if not r.get('st') or r.get('st', '').strip() == '']
    print(f'剩余 st=空: {len(st_empty)}条')
    for r in st_empty[:10]:
        print(f'  sc={r.get("sc","")} p={r.get("p","")} su={r.get("su","")}')

    # Update batch tag for repaired records
    fixed_count = 0
    for r in gz_after:
        if r.get('_batch') != 'current' or r.get('_batch_label') != '本次更新':
            r['_batch'] = 'current'
            r['_batch_label'] = '本次更新'
            fixed_count += 1

    print(f'\n广州市直属 post-fix: {len(gz_after)}条')
    print(f'已标记本次更新: +{fixed_count}条')

    # Verify: any record with sc='单位' left?
    sc_danwei = [r for r in data if r.get('sc') == '单位']
    print(f'全库 sc=单位: {len(sc_danwei)}条')

    save_data(data)
    print(f'\nSaved: {len(data)} records')

if __name__ == '__main__':
    main()
