"""
V130 PDF ingestion: 乳源综合成绩 + 陆河笔试 + 新会体检 + 江海区综合成绩
Fill WC/IC/MS/TS/PR where currently 0/None.
"""
import json, os
from collections import defaultdict
import pdfplumber

ROOT = r'D:\claude_code\gaokao\jiaozi\guangdong_scores'
VIEWER_PATH = os.path.join(ROOT, 'dist', 'viewer_data.json')
DL_BASE = os.path.join(ROOT, 'data', 'raw', 'tmp', '_gov_downloads_july22')

stats = {'wc':0, 'ms':0, 'ts':0, 'ic':0, 'pr':0, 'tagged':0}

def load_data():
    with open(VIEWER_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_data(data):
    with open(VIEWER_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)

def find_file(fname):
    for root, dirs, files in os.walk(DL_BASE):
        if fname in files:
            return os.path.join(root, fname)
    return None

def safe_float(v):
    if v is None: return None
    if isinstance(v, (int, float)): return float(v)
    s = str(v).strip().replace('\n', '')
    if s in ('', '-', '缺考', '违纪', 'None', 'N/A'): return None
    try: return float(s)
    except: return None

def tag_current(r):
    r['_batch'] = 'current'
    r['_batch_label'] = '本次更新'
    stats['tagged'] += 1

def build_indexes(data):
    by_code = defaultdict(list)
    for i, r in enumerate(data):
        pc = str(r.get('position_code', '')).strip()
        if pc: by_code[pc].append(i)
    return by_code

def apply_updates(data, by_code, updates, label):
    applied = 0
    for code, upd in updates.items():
        code = str(code).strip()
        if code not in by_code: continue
        for idx in by_code[code]:
            r = data[idx]
            changed = False
            for fld in ['wc','ic']:
                if upd.get(fld,0)>0 and r.get(fld,0)==0:
                    r[fld] = upd[fld]; stats[fld] += 1; changed = True
            for fld in ['ms','ts']:
                if upd.get(fld) is not None and (r.get(fld) is None or r.get(fld, 0) == 0):
                    r[fld] = upd[fld]; stats[fld] += 1; changed = True
            if upd.get('pr',0)>0 and r.get('pr',0)==0:
                r['pr'] = upd['pr']; stats['pr'] += 1; changed = True
            elif upd.get('pr',0)>0 and upd.get('pr_override') and upd['pr']>r.get('pr',0):
                r['pr'] = upd['pr']; stats['pr'] += 1; changed = True
            if changed:
                tag_current(r); applied += 1
                if r.get('wc',0)>0 and r.get('pr',0)>0:
                    r['wr'] = round(r['wc']/r['pr'],2)
                if r.get('ic',0)>0 and r.get('pr',0)>0:
                    r['ir'] = round(r['ic']/r['pr'],2)
    print(f'  [{label}] {applied} updates from {len(updates)} codes')

# ═══════════════════════════════════════════════════════════
# 乳源综合成绩 (2864692_1.pdf) — WC+MS+TS+IC+PR
# ═══════════════════════════════════════════════════════════
def parse_ruyuan(data, by_code):
    fpath = find_file('2864692_1.pdf')
    if not fpath: print('乳源: PDF not found'); return
    print('\n===== 乳源县 综合成绩 =====')

    # Per-code aggregation
    code_data = defaultdict(lambda: {'wc':0, 'written':[], 'composite':[], 'pass_composite':[], 'plan':0})
    with pdfplumber.open(fpath) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                if not table or not table[0]: continue
                for row in table[1:]:
                    if not row or not row[3]: continue
                    code = str(row[3]).strip().replace('\n', '') if row[3] else ''
                    if not code or code == 'None': continue
                    d = code_data[code]
                    d['wc'] += 1
                    plan = int(row[4]) if row[4] and str(row[4]).strip().replace('.','').isdigit() else 0
                    d['plan'] = max(d['plan'], plan)
                    written = safe_float(row[6])
                    composite = safe_float(row[8])
                    passed = str(row[10]).strip() if row[10] else ''
                    if written is not None: d['written'].append(written)
                    if composite is not None:
                        d['composite'].append(composite)
                        if passed == '是': d['pass_composite'].append(composite)

    updates = {}
    for code, d in code_data.items():
        updates[code] = {
            'wc': d['wc'], 'ic': d['wc'],
            'pr': len(d['pass_composite']) if d['pass_composite'] else 0,
            'ms': min(d['written']) if d['written'] else None,
            'ts': min(d['pass_composite']) if d['pass_composite'] else None,
        }
    print(f'  Parsed: {len(updates)} codes, {sum(d["wc"] for d in code_data.values())} candidates')
    apply_updates(data, by_code, updates, '乳源')
    for code in sorted(updates.keys())[:5]:
        u = updates[code]
        print(f'    {code}: WC={u["wc"]} MS={u["ms"]} TS={u["ts"]} PR={u["pr"]}')

# ═══════════════════════════════════════════════════════════
# 陆河笔试名单 (1262756.pdf) — WC+IC (no scores)
# ═══════════════════════════════════════════════════════════
def parse_luhe(data, by_code):
    fpath = find_file('1262756.pdf')
    if not fpath: print('陆河: PDF not found'); return
    print('\n===== 陆河县 笔试名单 =====')

    code_counts = defaultdict(int)
    with pdfplumber.open(fpath) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                if not table or not table[0]: continue
                for row in table[1:]:
                    if not row or not row[1]: continue
                    code = str(row[1]).strip().replace('\n', '') if row[1] else ''
                    if code and code != 'None': code_counts[code] += 1

    updates = {code: {'wc': count, 'ic': count} for code, count in code_counts.items()}
    print(f'  Parsed: {len(updates)} codes, {sum(code_counts.values())} candidates')
    apply_updates(data, by_code, updates, '陆河')
    for code, count in sorted(code_counts.items(), key=lambda x: -x[1])[:5]:
        print(f'    {code}: WC=IC={count}')

# ═══════════════════════════════════════════════════════════
# 新会区体检名单 (3523235.pdf) — IC+TS+PR
# ═══════════════════════════════════════════════════════════
def parse_xinhui(data, by_code):
    fpath = find_file('3523235.pdf')
    if not fpath: print('新会: PDF not found'); return
    print('\n===== 新会区 体检名单 =====')

    code_data = defaultdict(lambda: {'ic':0, 'ts_list':[], 'plan':0})
    with pdfplumber.open(fpath) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                if not table or not table[0]: continue
                for row in table[1:]:
                    if not row or not row[2]: continue
                    code = str(row[2]).strip().replace('\n', '') if row[2] else ''
                    if not code or code == 'None': continue
                    d = code_data[code]
                    d['ic'] += 1
                    plan = int(row[3]) if row[3] and str(row[3]).strip().replace('.','').isdigit() else 0
                    d['plan'] = max(d['plan'], plan)
                    ts_val = safe_float(row[5])
                    if ts_val is not None: d['ts_list'].append(ts_val)

    updates = {}
    for code, d in code_data.items():
        updates[code] = {
            'ic': d['ic'], 'pr': d['plan'], 'pr_override': True,
            'ts': min(d['ts_list']) if d['ts_list'] else None,
        }
    print(f'  Parsed: {len(updates)} codes, {sum(d["ic"] for d in code_data.values())} candidates')
    apply_updates(data, by_code, updates, '新会')
    for code in sorted(updates.keys()):
        u = updates[code]
        print(f'    {code}: IC={u["ic"]} TS={u["ts"]} PR={u["pr"]}')

# ═══════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════
def main():
    print('=' * 70)
    print('V130 PDF INGESTION')
    print('=' * 70)

    data = load_data()
    print(f'Loaded: {len(data)} records')
    by_code = build_indexes(data)
    print(f'Index: {len(by_code)} unique codes')

    cur_before = sum(1 for r in data if r.get('_batch') == 'current')

    parse_ruyuan(data, by_code)
    parse_luhe(data, by_code)
    parse_xinhui(data, by_code)

    print(f'\nSUMMARY: WC={stats["wc"]} MS={stats["ms"]} TS={stats["ts"]} IC={stats["ic"]} PR={stats["pr"]}')
    cur_after = sum(1 for r in data if r.get('_batch') == 'current')
    print(f'Current: {cur_before} -> {cur_after} (+{cur_after-cur_before})')

    # Quick audit
    for city, dist in [('韶关','乳源瑶族自治县'),('韶关','乳源县'),('汕尾','陆河县'),('江门','新会区')]:
        recs = [r for r in data if r.get('c')==city and r.get('d')==dist]
        wc = sum(1 for r in recs if r.get('wc',0)>0)
        ic = sum(1 for r in recs if r.get('ic',0)>0)
        ms = sum(1 for r in recs if r.get('ms') is not None and r.get('ms',0)>0)
        ts = sum(1 for r in recs if r.get('ts') is not None and r.get('ts',0)>0)
        print(f'{city}/{dist}: {len(recs)} recs, WC>0={wc}, IC>0={ic}, MS>0={ms}, TS>0={ts}')

    save_data(data)

if __name__ == '__main__':
    main()
