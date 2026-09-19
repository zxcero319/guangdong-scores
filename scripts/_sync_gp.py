# -*- coding: utf-8 -*-
"""同步 dist viewer → GitHub Pages 本地部署文件（可复用，日期自动检测）。

用法：python scripts/_sync_gp.py

流程（v138+ 架构，无需 viewer_data.json）:
  1. 读取 dist/guangdong_scores_viewer.html 全量数据
  2. 自动检测旧"数据截止"日期 → 更新为今天
  3. 拆 hot(active/current/previous/historical) / cold(其余)
  4. 写 dist/city/*.json (cold) + index.html (日期 + CITY_META + ALL_DATA hot)
  5. 完整性验证

替换历史: 不再每次建 _sync_gp_sepXX.py 副本，本脚本日期自动取当天。
"""
import sys, os, json, re
from collections import defaultdict
from datetime import date
sys.stdout.reconfigure(encoding='utf-8')

ROOT = r'D:\claude_code\gaokao\jiaozi\guangdong_scores'
VIEWER = os.path.join(ROOT, 'dist', 'guangdong_scores_viewer.html')
INDEX = os.path.join(ROOT, 'index.html')
CITY_DIR = os.path.join(ROOT, 'dist', 'city')

HOT_BATCHES = {'active', 'current', 'previous', 'historical'}
DATE_RE = re.compile(r'数据截止 (\d{4}-\d{2}-\d{2})')


def load_all_data(html):
    idx = html.find('var ALL_DATA =')
    b = html.find('[', idx)
    d = 0; e = b; ins = False; esc = False
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
    return json.loads(html[b:e])


def update_date(html, old, new):
    n = 0
    if old and old in html:
        html = html.replace(old, new)
        n = html.count(new)
    elif new in html:
        n = -1  # 已是新日期
    return html, n


def main():
    today = date.today().isoformat()

    # ── 1. dist viewer: 日期 + 全量数据 ──
    print('=== Step 1: dist viewer ===')
    vhtml = open(VIEWER, encoding='utf-8').read()
    m = DATE_RE.search(vhtml)
    old_date = m.group(1) if m else None
    if old_date and old_date != today:
        vhtml = vhtml.replace(old_date, today)
        open(VIEWER, 'w', encoding='utf-8').write(vhtml)
        print(f'  日期: {old_date} → {today}')
    else:
        print(f'  日期: {old_date or "?"} ({"已是最新" if old_date == today else "未找到标记"})')

    full_data = load_all_data(vhtml)
    print(f'  全量记录: {len(full_data)}')

    # ── 2. hot / cold 拆分 ──
    hot = []
    cold_by_city = defaultdict(list)
    for r in full_data:
        if r.get('_batch') in HOT_BATCHES:
            hot.append(r)
        else:
            cold_by_city[str(r.get('c', '未知'))].append(r)
    n_cold = sum(len(v) for v in cold_by_city.values())
    print(f'  Hot: {len(hot)}  Cold: {n_cold}')

    # ── 3. CITY_META ──
    city_meta = {}
    for r in full_data:
        city = str(r.get('c', ''))
        district = str(r.get('d', ''))
        if not city:
            continue
        if city not in city_meta:
            city_meta[city] = {'total': 0, 'districts': {}}
        city_meta[city]['total'] += 1
        if district:
            city_meta[city]['districts'][district] = city_meta[city]['districts'].get(district, 0) + 1
    city_meta = dict(sorted(city_meta.items(), key=lambda x: x[1]['total'], reverse=True))

    # ── 4. 写 city chunks ──
    os.makedirs(CITY_DIR, exist_ok=True)
    for city, records in cold_by_city.items():
        with open(os.path.join(CITY_DIR, f'{city}.json'), 'w', encoding='utf-8') as f:
            json.dump(records, f, ensure_ascii=False)
    print(f'  城市文件: {len(cold_by_city)}')

    # ── 5. index.html ──
    ihtml = open(INDEX, encoding='utf-8').read()
    if old_date and old_date != today:
        ihtml = ihtml.replace(old_date, today)

    old_meta = re.search(r'var CITY_META = \{.*?\};', ihtml, re.DOTALL)
    if old_meta:
        new_meta = 'var CITY_META = ' + json.dumps(city_meta, ensure_ascii=False, indent=2) + ';'
        ihtml = ihtml[:old_meta.start()] + new_meta + ihtml[old_meta.end():]
    else:
        print('  ERROR: CITY_META 未找到'); sys.exit(1)

    old_data = re.search(r'var ALL_DATA = \[.*?\];', ihtml, re.DOTALL)
    if old_data:
        new_data = 'var ALL_DATA = ' + json.dumps(hot, ensure_ascii=False) + ';'
        ihtml = ihtml[:old_data.start()] + new_data + ihtml[old_data.end():]
    else:
        print('  ERROR: ALL_DATA 未找到'); sys.exit(1)

    # ── 6. 验证 ──
    js = ihtml[ihtml.find('<script>'):ihtml.find('</script>')]
    br_ok = js.count('{') == js.count('}')
    brk_ok = js.count('[') == js.count(']')
    hot_check = json.loads(re.search(r'var ALL_DATA = \[.*?\];', ihtml, re.DOTALL).group(0)[len('var ALL_DATA = '):-1])
    meta_check = json.loads(re.search(r'var CITY_META = \{.*?\};', ihtml, re.DOTALL).group(0)[len('var CITY_META = '):-1])
    ok = br_ok and brk_ok and len(hot_check) == len(hot) and len(meta_check) == len(city_meta)

    if ok:
        open(INDEX, 'w', encoding='utf-8').write(ihtml)
        print(f'  验证 OK: hot={len(hot)} city_meta={len(city_meta)} braces={br_ok}/{brk_ok}')
        print(f'  已保存 index.html')
    else:
        print(f'  FAILED: braces={br_ok}/{brk_ok} hot={len(hot_check)}/{len(hot)} meta={len(meta_check)}/{len(city_meta)}')
        sys.exit(1)

    print('\n=== 完成 ===')
    print(f'  dist viewer: {len(full_data)} 条 | index.html: {len(hot)} hot | city: {len(cold_by_city)}')


if __name__ == '__main__':
    main()
