# -*- coding: utf-8 -*-
"""过期正在报名归库（可复用，TODAY 自动取当天）。

用法：python scripts/expire_active.py
动作：将所有 _batch="active" 且 _reg_end < 今天 的记录归库（_batch=""，_batch_label=""）。
     无过期时为空操作。
"""
import sys, os, json
from datetime import datetime, date
sys.stdout.reconfigure(encoding='utf-8')

ROOT = r'D:\claude_code\gaokao\jiaozi\guangdong_scores'
VIEWER = os.path.join(ROOT, 'dist', 'guangdong_scores_viewer.html')
BACKUP_DIR = os.path.join(ROOT, 'data', 'raw', 'tmp', '_viewer_backups')
os.makedirs(BACKUP_DIR, exist_ok=True)

TODAY = date.today().isoformat()  # 自动取当天，如 2026-09-13


def load_viewer():
    html = open(VIEWER, 'r', encoding='utf-8').read()
    idx = html.find('var ALL_DATA =')
    b = html.find('[', idx)
    d = 0
    e = b
    ins = False
    esc = False
    for i in range(b, len(html)):
        c = html[i]
        if ins:
            if esc:
                esc = False
            elif c == '\\':
                esc = True
            elif c == '"':
                ins = False
            continue
        if c == '"':
            ins = True
        elif c == '[':
            d += 1
        elif c == ']':
            d -= 1
            if d == 0:
                e = i + 1
                break
    return html, json.loads(html[b:e]), b, e


def save_viewer(html, data, b, e, label):
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    bp = os.path.join(BACKUP_DIR, 'viewer_backup_%s_%s.html' % (label, ts))
    open(bp, 'w', encoding='utf-8').write(html)
    print('Backup:', bp)
    new_json = json.dumps(data, ensure_ascii=False, indent=2)
    new_html = html[:b] + new_json + html[e:]
    idx2 = new_html.find('var ALL_DATA =')
    b2 = new_html.find('[', idx2)
    d2 = 0
    e2 = b2
    ins = False
    esc = False
    for i in range(b2, len(new_html)):
        c = new_html[i]
        if ins:
            if esc:
                esc = False
            elif c == '\\':
                esc = True
            elif c == '"':
                ins = False
            continue
        if c == '"':
            ins = True
        elif c == '[':
            d2 += 1
        elif c == ']':
            d2 -= 1
            if d2 == 0:
                e2 = i + 1
                break
    test_data = json.loads(new_html[b2:e2])
    assert len(test_data) == len(data), 'Mismatch: %d vs %d' % (len(test_data), len(data))
    open(VIEWER, 'w', encoding='utf-8').write(new_html)
    print('Saved: %d records' % len(data))


def main():
    html, data, b, e = load_viewer()
    print('Loaded: %d records | TODAY=%s' % (len(data), TODAY))

    from collections import Counter
    active = [r for r in data if r.get('_batch') == 'active']
    before = Counter(str(r.get('_reg_end', '?')) for r in active)
    print('归库前正在报名: %d 条' % len(active))
    for dt in sorted(before):
        print('  reg_end=%s: %d' % (dt, before[dt]))

    expire_count = 0
    for r in data:
        if r.get('_batch') == 'active' and r.get('_reg_end', '') < TODAY:
            old_end = r.get('_reg_end', '')
            r['_batch'] = ''
            r['_batch_label'] = ''
            print('[EXP] %s %s | %s | %s | reg_end=%s → 归库' % (
                r.get('c', ''), r.get('d', ''), str(r.get('sc', ''))[:25], str(r.get('p', ''))[:20], old_end))
            expire_count += 1

    print('\n=== 汇总 ===')
    print('过期归库: %d' % expire_count)

    if expire_count > 0:
        save_viewer(html, data, b, e, 'expire_%s' % TODAY.replace('-', ''))

    active2 = [r for r in data if r.get('_batch') == 'active']
    after = Counter(str(r.get('_reg_end', '?')) for r in active2)
    print('\n归库后正在报名: %d 条' % len(active2))
    for dt in sorted(after):
        print('  reg_end=%s: %d' % (dt, after[dt]))

    expired_remain = [r for r in data if r.get('_batch') == 'active' and r.get('_reg_end', '') < TODAY]
    print('\n过期残留: %d 条%s' % (len(expired_remain), '' if not expired_remain else ' !!!'))


if __name__ == '__main__':
    main()
