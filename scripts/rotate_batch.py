# -*- coding: utf-8 -*-
"""开始更新 = 过期报名归库 + 批次轮换。用法: python scripts/rotate_batch.py

1. 过期报名归库: _batch="active" 且 _reg_end < 今天 → 归库 (_batch="" / _batch_label="")
2. 批次轮换: 上次更新(_batch="previous")→归库空; 本次更新(_batch="current")→上次更新
"""
import sys, json
from datetime import date
sys.stdout.reconfigure(encoding='utf-8')

VIEWER = 'dist/guangdong_scores_viewer.html'
PREV_LABEL = '上次更新'
TODAY = date.today().isoformat()


def main():
    with open(VIEWER, encoding='utf-8') as f:
        html = f.read()
    idx = html.find('var ALL_DATA =')
    b = html.find('[', idx)
    d = 0
    for i in range(b, len(html)):
        if html[i] == '[':
            d += 1
        elif html[i] == ']':
            d -= 1
            if d == 0:
                e = i + 1
                break
    data = json.loads(html[b:e])

    n_expire = 0
    for r in data:
        if r.get('_batch') == 'active' and r.get('_reg_end', '') < TODAY:
            r['_batch'] = ''
            r['_batch_label'] = ''
            n_expire += 1

    n_archive = n_move = 0
    for r in data:
        if r.get('_batch') == 'previous':
            r['_batch'] = ''
            r['_batch_label'] = ''
            n_archive += 1
        elif r.get('_batch') == 'current':
            r['_batch'] = 'previous'
            r['_batch_label'] = PREV_LABEL
            n_move += 1

    with open(VIEWER, 'w', encoding='utf-8') as f:
        f.write(html[:b] + json.dumps(data, ensure_ascii=False, indent=2) + html[e:])
    print(f'过期归库: {n_expire}, 归库(previous→空): {n_archive}, 移到上次更新(current→previous): {n_move}')


if __name__ == '__main__':
    main()
