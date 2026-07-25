"""
全局重排 viewer_data.json:
排序键: city → district → batch → has_data(T/F) → school → position_code
同批次内有成绩(WC/IC/MS/TS>0)的排前面,无成绩的排后面
"""
import json

ROOT = r'D:\claude_code\gaokao\jiaozi\guangdong_scores'

def load_data():
    with open(f'{ROOT}/dist/viewer_data.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def save_data(data):
    with open(f'{ROOT}/dist/viewer_data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)

def has_data(r):
    """True if record has any score/competition data"""
    if r.get('wc', 0) > 0: return True
    if r.get('ic', 0) > 0: return True
    if r.get('ms') is not None and r.get('ms', 0) > 0: return True
    if r.get('ts') is not None and r.get('ts', 0) > 0: return True
    return False

def sort_key(r):
    """Sort by: city, district, batch, has_data(desc), school, position_code"""
    c = r.get('c') or ''
    d = r.get('d') or ''
    b = r.get('b') or ''
    hd = has_data(r)
    sc = r.get('sc') or ''
    pc = r.get('position_code') or ''
    yr = r.get('yr', 0) or 0

    return (c, d, b, not hd, sc, pc, yr)

def main():
    data = load_data()
    print(f'Loaded: {len(data)} records')

    # Count fragmentation before
    from collections import defaultdict
    city_segments_before = defaultdict(int)
    prev_c = ''
    for r in data:
        c = r.get('c', '')
        if c != prev_c:
            city_segments_before[c] += 1
        prev_c = c
    fragmented = sum(1 for v in city_segments_before.values() if v > 1)
    print(f'碎片化城市(>1段): {fragmented}/22')

    # Sort
    data.sort(key=sort_key)

    # Count fragmentation after
    city_segments_after = defaultdict(int)
    prev_c = ''
    for r in data:
        c = r.get('c', '')
        if c != prev_c:
            city_segments_after[c] += 1
        prev_c = c
    fragmented_after = sum(1 for v in city_segments_after.values() if v > 1)
    print(f'排序后碎片化: {fragmented_after}/22 (应为0)')

    # Verify: each city is contiguous
    cities_in_order = []
    prev_c = ''
    for r in data:
        c = r.get('c', '')
        if c != prev_c:
            cities_in_order.append(c)
        prev_c = c
    arrow = ' -> '
    print(f'城市顺序: {arrow.join(cities_in_order)}')

    # Verify广州市直属: all 3 batches contiguous with has_data first
    gz_zhi = [(i, r) for i, r in enumerate(data) if r.get('c') == '广州' and r.get('d') == '市直属']
    print(f'\n广州市直属 after sort: indices {gz_zhi[0][0]} ~ {gz_zhi[-1][0]}')

    # Check batch transitions and has_data grouping
    prev_b = ''
    prev_hd = None
    batch_starts = []
    for i, r in gz_zhi:
        b = r.get('b', '')
        hd = has_data(r)
        if b != prev_b:
            batch_starts.append((i, b))
            prev_b = b
            prev_hd = None
        if hd != prev_hd and prev_hd is not None:
            if hd and not prev_hd:
                pass  # has_data starts after no_data — shouldn't happen
            elif not hd and prev_hd:
                pass  # no_data starts after has_data — expected transition
        prev_hd = hd

    print(f'批次段: {len(batch_starts)}个')
    for idx, b in batch_starts:
        sub = [r for i, r in gz_zhi if r.get('b') == b]
        has = sum(1 for r in sub if has_data(r))
        no = len(sub) - has
        print(f'  [{idx}] {b[:45]}: {len(sub)}条 (有数据={has}, 无={no})')

    # Quick audit: within each batch, has_data should be True first, then False
    prev_b = ''
    seen_no_data = False
    errors = 0
    for i, r in gz_zhi:
        b = r.get('b', '')
        hd = has_data(r)
        if b != prev_b:
            seen_no_data = False
            prev_b = b
        if hd and seen_no_data:
            errors += 1
        if not hd:
            seen_no_data = True

    print(f'有数据→无数据顺序错误: {errors} (应为0)')

    save_data(data)
    print(f'\nSaved: {len(data)} records')

if __name__ == '__main__':
    main()
