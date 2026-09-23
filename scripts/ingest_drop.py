# -*- coding: utf-8 -*-
"""通用 drop 目录入库脚本 — 单遍确定性处理，防兜圈子/反复探针。

用法:
  python scripts/ingest_drop.py <目录路径> [--apply]

设计目标: 一次运行完成「扫描→分类→匹配→入库→汇总」，规则全部写死，
未来把文件丢进目录后直接跑本脚本，不再逐文件手写脚本或反复 probe/查库。

写死规则（来源 CLAUDE.md，不重推）:
  - WC  仅"完整笔试名单/笔试成绩表"可取；综合成绩表/面试/体检/拟聘/签约名单 → WC=0
  - IC  综合成绩表→参加面试人数(排除缺考)；面试名单→入围人数；体检/拟聘名单→不可取(0)
  - MS  进面分 = 入围面试者的笔试最低分 min(笔试)，非"全体考生最低分"
  - TS  min(综合成绩 且 进入/入围体检=是)
  - _final_hired  仅拟聘公示/体检合格名单取; n>pr 异常罗列, n==pr 清None, n<pr max(旧,n)
  - 年份隔离  所有匹配必须校验 yr（同市同年同码）
  - 城市参与匹配（"市直"在 21 市重复）
"""
import os, sys, re, json
from collections import defaultdict, Counter
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, 'scripts')
from _field_normalize import normalize_record

DRY = True  # 干跑时不打印每 code 的 [更新]/[不变]/[清空]（只看汇总+异常+无匹配）

VIEWER = r'D:\claude_code\gaokao\jiaozi\guangdong_scores\dist\guangdong_scores_viewer.html'

# ---------------- 城市/区县 ----------------
CITIES = ['广州', '深圳', '珠海', '汕头', '佛山', '韶关', '湛江', '肇庆', '江门',
          '茂名', '惠州', '梅州', '汕尾', '河源', '阳江', '清远', '东莞', '中山',
          '潮州', '揭阳', '云浮']

DISTRICT_MAP = {
    '三角镇': '中山', '东凤镇': '中山', '南区街道': '中山', '南朗街道': '中山', '大涌镇': '中山',
    '小榄镇': '中山', '横栏镇': '中山', '沙溪镇': '中山', '港口镇': '中山', '火炬开发区': '中山',
    '石岐街道': '中山', '西区街道': '中山', '黄圃镇': '中山',
    '云城区': '云浮', '云安区': '云浮', '新兴县': '云浮', '罗定市': '云浮', '郁南县': '云浮',
    '三水区': '佛山', '南海区': '佛山', '禅城区': '佛山', '顺德区': '佛山', '高明区': '佛山',
    '从化区': '广州', '南沙区': '广州', '增城区': '广州', '天河区': '广州', '海珠区': '广州',
    '番禺区': '广州', '白云区': '广州', '花都区': '广州', '荔湾区': '广州', '越秀区': '广州', '黄埔区': '广州',
    '仲恺高新区': '惠州', '博罗县': '惠州', '大亚湾区': '惠州', '惠东县': '惠州', '惠城区': '惠州',
    '惠阳区': '惠州', '龙门县': '惠州',
    '惠来县': '揭阳', '揭东区': '揭阳', '揭西县': '揭阳', '普宁市': '揭阳', '榕城区': '揭阳',
    '丰顺县': '梅州', '五华县': '梅州', '兴宁市': '梅州', '大埔县': '梅州', '平远县': '梅州',
    '梅县区': '梅州', '梅江区': '梅州', '蕉岭县': '梅州',
    '南澳县': '汕头', '潮南区': '汕头', '潮阳区': '汕头', '澄海区': '汕头', '濠江区': '汕头',
    '金平区': '汕头', '龙湖区': '汕头',
    '海丰县': '汕尾', '陆丰市': '汕尾', '陆河县': '汕尾',
    '台山市': '江门', '开平市': '江门', '恩平市': '江门', '新会区': '江门', '江海区': '江门',
    '蓬江区': '江门', '鹤山市': '江门',
    '东源县': '河源', '和平县': '河源', '江东新区': '河源', '源城区': '河源', '紫金县': '河源',
    '连平县': '河源', '龙川县': '河源',
    '光明区': '深圳', '南山区': '深圳', '坪山区': '深圳', '大鹏新区': '深圳', '宝安区': '深圳',
    '盐田区': '深圳', '福田区': '深圳', '罗湖区': '深圳', '龙华区': '深圳', '龙岗区': '深圳',
    '佛冈县': '清远', '清城区': '清远', '清新区': '清远', '英德市': '清远', '连南瑶族自治县': '清远',
    '连山县': '清远', '连州市': '清远', '阳山县': '清远',
    '吴川市': '湛江', '坡头区': '湛江', '廉江市': '湛江', '徐闻县': '湛江', '经开区': '湛江',
    '赤坎区': '湛江', '遂溪县': '湛江', '雷州市': '湛江', '霞山区': '湛江', '麻章区': '湛江',
    '湘桥区': '潮州', '潮安区': '潮州', '饶平县': '潮州',
    '斗门区': '珠海', '金湾区': '珠海', '高新区': '珠海',
    '四会市': '肇庆', '封开县': '肇庆', '广宁县': '肇庆', '德庆县': '肇庆', '怀集县': '肇庆',
    '端州区': '肇庆', '高要区': '肇庆', '鼎湖区': '肇庆',
    '信宜市': '茂名', '化州市': '茂名', '电白区': '茂名', '茂南区': '茂名', '高州市': '茂名',
    '江城区': '阳江', '阳东区': '阳江', '阳春市': '阳江', '阳西县': '阳江',
    '乐昌市': '韶关', '乳源瑶族自治县': '韶关', '仁化县': '韶关', '南雄市': '韶关', '始兴县': '韶关',
    '新丰县': '韶关', '曲江区': '韶关', '武江区': '韶关', '浈江区': '韶关', '翁源县': '韶关',
}


# ---------------- 基础工具 ----------------
def norm(v):
    if v is None: return ''
    if isinstance(v, float) and v == int(v): return str(int(v))
    return str(v).strip()


def norm_school(s):
    s = (s or '').strip()
    s = re.sub(r'\d+名、?', '', s)
    s = re.sub(r'\s+', '', s)
    return s.rstrip('、，,')


def norm_pos(p):
    p = (p or '').strip()
    p = re.sub(r'\s+', '', p)
    p = re.sub(r'初级教师专业技术[一二三四五六七八九十\d]+级$', '', p)
    return p


def to_float(v):
    try:
        return float(norm(v))
    except (ValueError, TypeError):
        return None


def read_xlsx(path):
    import openpyxl, xlrd
    from io import BytesIO
    with open(path, 'rb') as fh:
        data = fh.read()
    if data[:8].startswith(b'PK'):
        # 用 BytesIO 绕过 openpyxl 按扩展名拒读 .xls（云浮文件实为 xlsx 但后缀 .xls）
        wb = openpyxl.load_workbook(BytesIO(data), data_only=True, read_only=True)
        rows = [[norm(c) for c in r] for ws in wb.worksheets for r in ws.iter_rows(values_only=True)]
        wb.close()
    else:
        wb = xlrd.open_workbook(path)
        rows = [[norm(ws.cell_value(r, c)) for c in range(ws.ncols)] for ws in wb.sheets() for r in range(ws.nrows)]
    return rows


def read_pdf(path):
    import fitz
    doc = fitz.open(path)
    rows = []
    for page in doc:
        for t in page.find_tables().tables:
            rows.extend(t.extract())
    doc.close()
    return [[norm(c) for c in r] for r in rows]


def read_file(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == '.pdf':
        return read_pdf(path)
    return read_xlsx(path)


def load_db():
    html = open(VIEWER, encoding='utf-8').read()
    idx = html.find('var ALL_DATA =')
    b = html.find('[', idx)
    d = 0
    for i in range(b, len(html)):
        if html[i] == '[': d += 1
        elif html[i] == ']':
            d -= 1
            if d == 0:
                e = i + 1; break
    return html, b, e, json.loads(html[b:e])


def find_col(hdr, keys):
    for i, c in enumerate(hdr):
        cc = (c or '').replace(' ', '').replace('\n', '').replace('\t', '')
        if any(k in cc for k in keys):
            return i
    return None


def find_ts_col(hdr):
    """TS 列：综合成绩优先；'总成绩'需排除'面试总成绩'等前缀（乐昌：面试总成绩+综合成绩并存）。"""
    norm_hdr = [(c or '').replace(' ', '').replace('\n', '').replace('\t', '') for c in hdr]
    for i, cc in enumerate(norm_hdr):
        if '综合成绩' in cc:
            return i
    for i, cc in enumerate(norm_hdr):
        if '总成绩' in cc and '面试' not in cc:
            return i
    return None


CODE_LIKE = re.compile(r'^[A-Za-z]+\d{4,}$')


def _school_col_is_code(rows, hdr_i, col):
    """化州拟聘名单'报考单位'列实存岗位代码(C202606001)而非校名 → 识别为 code 列。"""
    if col is None:
        return False
    vals = [str(r[col] or '').strip() for r in rows[hdr_i + 1:] if col < len(r)]
    vals = [v for v in vals if v]
    if not vals:
        return False
    n_code = sum(1 for v in vals if CODE_LIKE.match(v))
    return n_code >= len(vals) * 0.8


def has_any(rows, kw):
    return any(kw in (c or '') for r in rows for c in r)


# ---------------- 位置推断（区县优先，区县确定城市） ----------------
# 学校名 → (城市, 区县) 覆盖：标题仅含"佛山市XX中学"而无区县名时（如季华中学在三水区）
SCHOOL_DISTRICT = {
    '季华中学': ('佛山', '三水区'),
}


def infer_loc(title):
    t = title.replace(' ', '').replace('\n', '').replace('\t', '')
    yr_m = re.search(r'(20\d{2})', t)
    yr = int(yr_m.group(1)) if yr_m else None
    if '省直' in t:
        return '省直', '省直', yr
    # 区县优先（最长的区县名），区县映射决定城市（避免校名里的"珠海市第一中学教育集团"误导）
    district = None
    for d in sorted(DISTRICT_MAP, key=len, reverse=True):
        if d in t:
            district = d
            break
    if district is not None:
        return DISTRICT_MAP[district], district, yr
    # 学校名覆盖（标题无区县名、但学校可唯一确定区县）
    for s, (sc, sd) in SCHOOL_DISTRICT.items():
        if s in t:
            return sc, sd, yr
    # 无区县 → 从标题找城市 + 市直
    city = next((c for c in CITIES if c in t), None)
    if '市教育局直属' in t or '市教育局所属' in t or '市直' in t:
        district = '市直'
    elif '市直属' in t:
        district = '市直属'
        city = '深圳'
    # 东莞/中山 直筒子市：无区县名时默认市直（东莞仅有市直；中山无镇街名时也是市直）
    if city in ('东莞', '中山') and district is None:
        district = '市直'
    return city, district, yr


# ---------------- 文件分类 ----------------
CODE_KEYS = ['岗位代码', '职位代码', '岗位编号', '岗位编码']
SCHOOL_KEYS = ['招考单位', '招聘单位', '单位名称', '聘用单位', '拟聘用单位', '报考单位', '工作部门', '主管部门', '学校']
POS_KEYS = ['岗位名称', '报考岗位', '报考岗位名称', '招聘岗位', '招聘岗位名称']

# ---------------- 岗位表（无姓名/成绩列，有岗位代码+计划数） ----------------
PLAN_KEYS = ['招聘人数', '计划数', '拟招聘人数', '招聘计划', '岗位数', '拟聘人数', '招聘数', '计划招聘数', '招聘名额']
JOB_EDU_KEYS = ['学历要求', '学历']
JOB_DEGREE_KEYS = ['学位要求', '学位']
JOB_MAJOR_KEYS = ['专业要求', '专业', '本科专业', '招聘专业']
JOB_GRAD_MAJOR_KEYS = ['研究生专业', '研究生方向']
JOB_UNDER_MAJOR_KEYS = ['本科专业']
JOB_TITLE_KEYS = ['教师资格', '教师资格证', '教资', '教师资格要求']
JOB_AGE_KEYS = ['年龄要求', '年龄']
JOB_POLITICAL_KEYS = ['政治面貌']
JOB_OTHER_KEYS = ['其他要求', '备注', '其他条件']
JOB_RS_KEYS = ['考生类别', '招聘对象', '招聘范围', '报考类别', '招聘对象类别', '人员类别']
JOB_STAGE_KEYS = ['学段', '岗位类别', '招聘学段', '学段要求']
ST_MAP = {'幼儿园': '幼儿', '初中': '初中', '高中': '高中', '小学': '小学', '中职': '中职', '特殊教育': '特殊教育', '高校': '高校'}


def classify(rows, fname):
    """返回 (type, mode)。type: hire/scores/physical/written/interview"""
    hdr = None
    hi = 0
    for i, r in enumerate(rows):
        cc = [(c or '').replace(' ', '').replace('\n', '') for c in r]
        if any('姓名' in c for c in cc) or any(k in c for c in cc for k in CODE_KEYS):
            hdr = r; hi = i; break
    if hdr is None:
        return None
    hdr_s = ''.join(hdr).replace(' ', '').replace('\n', '')
    has_ms = '笔试成绩' in hdr_s
    has_iv = '面试成绩' in hdr_s
    has_ts = '总成绩' in hdr_s or '综合成绩' in hdr_s
    has_phys = any(k in hdr_s for k in ['初检结论', '体检结论', '体检结果', '体检情况'])
    is_hire = ('拟聘' in fname) or ('拟聘用' in fname) or has_any(rows, '拟聘用')

    # 拟聘文件名优先（"拟聘用人员名单"明确是拟聘，即使表内带成绩列）
    if is_hire:
        typ = 'hire'
    elif has_phys:
        typ = 'physical'
    elif has_ts:
        typ = 'scores'  # 有综合/总成绩列 → 综合成绩表 (即使无笔试, 如体育教练员直接考核)
    elif has_ms:
        typ = 'written'
    elif has_iv:
        typ = 'interview'
    elif find_col(hdr, PLAN_KEYS) is not None and find_col(hdr, ['姓名', '准考证号', '身份证号']) is None:
        typ = 'jobtable'  # 岗位表：有岗位代码+计划数，无姓名列、无成绩列
    else:
        return None

    code_col = find_col(hdr, CODE_KEYS)
    school_col = find_col(hdr, SCHOOL_KEYS)
    if code_col is None and _school_col_is_code(rows, hi, school_col):
        code_col = school_col  # 化州拟聘名单'报考单位'列实存岗位代码
        school_col = None
    if code_col is not None:
        mode = 'code'
    elif find_col(hdr, POS_KEYS) is not None and school_col is not None:
        mode = 'school_pos'
    elif school_col is not None:
        mode = 'school_only'
    else:
        mode = 'none'
    return typ, mode


# ---------------- 提取 ----------------
HEADER_CODES = {'岗位编号', '岗位代码', '职位代码', '岗位编码', '岗位名称', '岗位'}
HEADER_SCHOOLS = {'拟聘用单位', '招聘单位', '单位名称', '报考单位', '招考单位'}
HEADER_POS = {'岗位名称', '报考岗位', '岗位', '拟聘用岗位'}


def extract_raw(rows):
    """返回 raw rows: list of dict(code, school, pos, ms, iv, ts, ent)。"""
    hdr = None; hi = 0
    for i, r in enumerate(rows):
        cc = [(c or '').replace(' ', '').replace('\n', '') for c in r]
        if any('姓名' in c for c in cc) or any(k in c for c in cc for k in CODE_KEYS):
            hdr = r; hi = i; break
    if hdr is None:
        return []
    code_col = find_col(hdr, CODE_KEYS)
    # 「择岗后拟聘用单位」优先于「报考单位」：拟聘公示里报考单位是合并校名，择岗后才是实际学校
    school_col = find_col(hdr, ['择岗后拟聘用单位', '择岗后聘用单位'])
    if school_col is None:
        school_col = find_col(hdr, SCHOOL_KEYS)
    pos_col = find_col(hdr, POS_KEYS)
    if code_col is None and _school_col_is_code(rows, hi, school_col):
        code_col = school_col  # 化州拟聘名单'报考单位'列实存岗位代码
        school_col = None
    name_col = find_col(hdr, ['姓名', '准考证号', '身份证号', '身份证号码', '考生姓名'])
    ms_col = find_col(hdr, ['笔试成绩'])
    iv_col = find_col(hdr, ['面试成绩'])
    ts_col = find_ts_col(hdr)
    ent_col = find_col(hdr, ['是否入围体检', '是否进入体检', '进入体检', '是否入闱体检', '是否入围', '是否进入考察', '是否入闱'])
    note_col = find_col(hdr, ['备注', '初检结论', '体检结论', '体检结果'])

    def cell(col, r):
        return norm(r[col]) if (col is not None and col < len(r)) else ''

    raw = []
    prev_code = prev_school = prev_pos = ''
    for r in rows[hi + 1:]:
        name = cell(name_col, r)
        code = cell(code_col, r)
        if not name and not code:
            continue
        school = norm_school(cell(school_col, r))
        pos = norm_pos(cell(pos_col, r))
        if code in HEADER_CODES or school in HEADER_SCHOOLS or pos in HEADER_POS:
            continue
        # 合并单元格前向填充：成绩表常竖排合并代码/校/岗，续行留空，继承上一行
        if not code:
            code = prev_code
        if not school:
            school = prev_school
        if not pos:
            pos = prev_pos
        if code:
            prev_code = code
        if school:
            prev_school = school
        if pos:
            prev_pos = pos
        raw.append(dict(
            code=code, school=school, pos=pos,
            ms=to_float(cell(ms_col, r)), iv=cell(iv_col, r),
            ts=to_float(cell(ts_col, r)),
            ent=cell(ent_col, r) or cell(note_col, r)))
    return raw


# ---------------- 岗位表提取/回填/新增 ----------------
def infer_su(p):
    """从岗位名推断学科；幼儿园/特殊教育无学科 → ''"""
    if not p or '幼儿园' in p or '特殊教育' in p:
        return ''
    m = re.sub(r'^(初中|高中|小学|中职|特殊教育)', '', p)
    m = re.sub(r'教师$', '', m)
    return m


def infer_st(p, stage_col):
    if stage_col:
        return ST_MAP.get(stage_col, stage_col)
    for k in ['高中', '初中', '小学', '幼儿', '中职', '特殊教育', '高校']:
        if k in p:
            return '幼儿' if k == '幼儿' else k
    return ''


def extract_jobtable(rows):
    """从岗位表 rows 提取 code/school/pos/pr + 可展开字段（按表头名找列）。"""
    hdr = None; hi = 0
    for i, r in enumerate(rows):
        cc = [(c or '').replace(' ', '').replace('\n', '') for c in r]
        if any(k in c for c in cc for k in CODE_KEYS):
            hdr = r; hi = i; break
    if hdr is None:
        return []

    def col(keys): return find_col(hdr, keys)
    code_col = col(CODE_KEYS)
    school_col = col(SCHOOL_KEYS)
    pos_col = col(POS_KEYS)
    plan_col = col(PLAN_KEYS)
    edu_col = col(JOB_EDU_KEYS)
    degree_col = col(JOB_DEGREE_KEYS)
    major_col = col(JOB_MAJOR_KEYS)
    grad_col = col(JOB_GRAD_MAJOR_KEYS)
    under_col = col(JOB_UNDER_MAJOR_KEYS)
    # 「专业要求」合并表头跨两列（本科|研究生），第二列表头为空 → 拆为本科/研究生两列
    if grad_col is None and under_col is None and major_col is not None and major_col + 1 < len(hdr):
        if not norm(hdr[major_col + 1]):
            under_col = major_col
            grad_col = major_col + 1
            major_col = None
    title_col = col(JOB_TITLE_KEYS)
    age_col = col(JOB_AGE_KEYS)
    political_col = col(JOB_POLITICAL_KEYS)
    other_col = col(JOB_OTHER_KEYS)
    rs_col = col(JOB_RS_KEYS)
    stage_col = col(JOB_STAGE_KEYS)

    def cell(ci, r):
        return norm(r[ci]) if (ci is not None and ci < len(r)) else ''

    out = []
    prev_code = prev_school = prev_pos = ''
    for r in rows[hi + 1:]:
        code = cell(code_col, r)
        school = norm_school(cell(school_col, r))
        pos = norm_pos(cell(pos_col, r))
        # 多 sheet 拼合时第二个 sheet 的表头 → 重置继承并跳过
        if code in HEADER_CODES or (not code and school in HEADER_SCHOOLS and pos in HEADER_POS):
            prev_code = prev_school = prev_pos = ''
            continue
        if not code:
            code = prev_code
        if not school:
            school = prev_school
        if not pos:
            pos = prev_pos
        if not code:
            continue
        prev_code = code
        prev_school = school
        prev_pos = pos
        plan = cell(plan_col, r)
        try:
            pr = int(float(plan)) if plan else 0
        except ValueError:
            pr = 0
        out.append(dict(
            code=code, school=school, pos=pos, pr=pr,
            edu=cell(edu_col, r), degree=cell(degree_col, r),
            major=cell(major_col, r), grad=cell(grad_col, r), under=cell(under_col, r),
            title=cell(title_col, r), age=cell(age_col, r),
            political=cell(political_col, r), other=cell(other_col, r),
            rs=cell(rs_col, r), stage=cell(stage_col, r)))
    return out


def _clean(v):
    """岗位表空值记号（/ 无 不限 — -）→ ''"""
    v = (v or '').strip()
    return '' if v in ('/', '无', '不限', '—', '-', '\\') else v


def build_job_record(j, c, dist, yr, src_label, rid):
    edu_raw = j['edu']
    rs_raw = j['rs'] or '不限'
    grad = _clean(j['grad']); under = _clean(j['under']); major = _clean(j['major'])
    if grad and under:
        major_req = '研究生：%s\n本科：%s' % (grad, under)
    elif grad:
        major_req = '研究生：%s' % grad
    elif under:
        major_req = '本科：%s' % under
    elif major:
        major_req = major
    else:
        major_req = ''
    rec = dict(
        c=c, d=dist, sc=j['school'], p=j['pos'], yr=yr,
        st=infer_st(j['pos'], j['stage']), su=infer_su(j['pos']),
        edu=edu_raw, rs=rs_raw,
        b=src_label, ssl='',
        wc=0, ic=0, pr=j['pr'], ms=None, ts=None, wr=None, ir=None,
        position_code=j['code'], recruit_plan_source=src_label,
        _edu_req=edu_raw, _degree_req=_clean(j['degree']), _major_req=major_req,
        _title_req=_clean(j['title']), _age_req=_clean(j['age']),
        _political=_clean(j['political']), _other_req=(_clean(j['other']) or '不限'),
        _rid=rid,
        _batch='current', _batch_label='本次更新',
        _wc_ic_same_source=False, _source_url=src_label, _channel='普通招聘',
    )
    normalize_record(rec)  # 归一化 edu/rs 显示字段
    return rec


def _backfill_job(r, j):
    """回填缺失的可展开字段（不覆盖已有值）。返回 changes dict。"""
    changes = {}
    tmp = {'edu': j['edu'] or '', 'rs': j['rs'] or ''}
    normalize_record(tmp)  # 归一化后再回填
    edu_norm, rs_norm = tmp['edu'], tmp['rs']
    if j['pr'] and not r.get('pr'):
        changes['pr'] = j['pr']
    if edu_norm and not r.get('_edu_req'):
        changes['_edu_req'] = edu_norm
        if not r.get('edu'):
            changes['edu'] = edu_norm
    if j['degree'] and not r.get('_degree_req'):
        changes['_degree_req'] = j['degree']
    if not r.get('_major_req'):
        grad = _clean(j['grad']); under = _clean(j['under']); major = _clean(j['major'])
        if grad and under:
            changes['_major_req'] = '研究生：%s\n本科：%s' % (grad, under)
        elif grad:
            changes['_major_req'] = '研究生：%s' % grad
        elif under:
            changes['_major_req'] = '本科：%s' % under
        elif major:
            changes['_major_req'] = major
    if _clean(j['title']) and not r.get('_title_req'):
        changes['_title_req'] = _clean(j['title'])
    if _clean(j['age']) and not r.get('_age_req'):
        changes['_age_req'] = _clean(j['age'])
    if _clean(j['political']) and not r.get('_political'):
        changes['_political'] = _clean(j['political'])
    if not r.get('_other_req'):
        changes['_other_req'] = _clean(j['other']) or '不限'
    if rs_norm and not r.get('rs'):
        changes['rs'] = rs_norm
    if j['stage'] and not r.get('st'):
        changes['st'] = ST_MAP.get(j['stage'], j['stage'])
    if j['pos'] and not r.get('p'):
        changes['p'] = j['pos']
    if j['school'] and not r.get('sc'):
        changes['sc'] = j['school']
    return changes


def match_jobtable(job_code, db, results, idx_code):
    """job_code: (c,dist,yr) -> code -> [job rows]。回填现有 / 新增缺失；校拆、多记录、无计划数罗列不动。"""
    max_rid = max((r.get('_rid') or 0) for r in db)
    new_records = []
    for (c, dist, yr), codes in sorted(job_code.items()):
        print('\n== %s-%s yr=%s (岗位表) %d code' % (c, dist, yr, len(codes)))
        for code, lst in sorted(codes.items()):
            hits = idx_code[(c, dist, yr, code)]
            j = lst[0]
            schools = {x['school'] for x in lst}
            if not hits:
                if not j['pr']:
                    results['nomatch'].append((code, '岗位表无计划数'))
                    print('  [无计划数·罗列不动] %s' % code)
                    continue
                max_rid += 1
                rec = build_job_record(j, c, dist, yr, '%s%s%d岗位表' % (c, dist, yr), max_rid)
                new_records.append(rec)
                if not DRY:
                    print('  [新增] %s %s | %s | pr=%d' % (code, rec['sc'][:14], rec['p'], rec['pr']))
            elif len(hits) == 1:
                changes = _backfill_job(hits[0], j)
                if changes:
                    results['update'].append((hits[0], changes))
                    if not DRY:
                        print('  [回填] %s %s' % (code, ', '.join('%s=%s' % (k, v) for k, v in changes.items())))
                else:
                    results['nochange'].append(code)
            else:
                if len(schools) == 1:
                    results['dup'].append((code, len(lst), len(hits)))
                    print('  [重复%d] %s' % (len(hits), code))
                else:
                    results['nomatch'].append((code, '校拆'))
                    print('  [校拆·罗列不动] %s n=%d' % (code, len(lst)))
    return new_records


# ---------------- 匹配+规则 ----------------
def _apply_hire(r, n, key, results):
    old = r.get('_final_hired')
    pr = r.get('pr') or 0
    if n > pr:
        results['abnormal'].append((key, n, pr))
        print('  [异常] %s n=%d>计划%d (%s)' % (key, n, pr, (r.get('sc') or '')[:14]))
    elif n == pr:
        if old is not None:
            results['clear'].append(r)
            if not DRY:
                print('  [清空] %s n=%d==计划 fh %s→None (%s)' % (key, n, old, (r.get('sc') or '')[:14]))
        else:
            results['nochange'].append(key)
    else:
        new = max(old or 0, n)
        if new != old:
            results['update'].append((r, {'_final_hired': new}))
            if not DRY:
                print('  [更新] %s n=%d fh %s→%s (计划%d %s)' % (key, n, old, new, pr, (r.get('sc') or '')[:14]))
        else:
            results['nochange'].append(key)


def _apply_scores(r, wc, ic, ms, ts, key, results):
    """wc/ic/ms/ts 为 None 表示该类型不取该字段（不动）。"""
    changes = {}
    if wc is not None and wc > 0 and r.get('wc') != wc:
        changes['wc'] = wc
    if ic is not None and ic > 0 and r.get('ic') != ic:
        changes['ic'] = ic
    if ms is not None and (r.get('ms') or 0) != ms:
        changes['ms'] = ms
    if ts is not None and (r.get('ts') or 0) != ts:
        changes['ts'] = ts
    if changes:
        results['update'].append((r, changes))
        if not DRY:
            print('  [更新] %s %s' % (key, ', '.join('%s %s→%s' % (k, r.get(k), v) for k, v in changes.items())))
    else:
        results['nochange'].append(key)
        if not DRY:
            print('  [不变] %s WC=%s IC=%s MS=%s TS=%s' % (key, wc, ic, ms, ts))


def _match_score_group(typ, key, val, hits, results):
    """按文件类型计算 wc/ic/ms/ts，再匹配。
    - scores(综合成绩表): WC=0(不取), IC=参加面试人数(有面试分), MS=min(笔试), TS=min(总 且 进入体检=是)
    - written(笔试成绩表): WC=完整笔试名单(排除缺考), MS=min(笔试), IC/TS 不取
    - interview(面试名单): IC=人数, WC/MS/TS 不取
    """
    if not hits:
        results['nomatch'].append((key, len(val)))
        print('  [无匹配] %s (%d人)' % (key, len(val)))
        return
    if len(hits) > 1:
        results['dup'].append((key, len(val), len(hits)))
        print('  [重复%d] %s' % (len(hits), key))
        return

    if typ == 'scores':
        wc = None  # 综合成绩表永不取 WC
        ic = sum(1 for x in val if to_float(x['iv']) is not None)
        ms_vals = [x['ms'] for x in val if x['ms'] is not None]
        ms = min(ms_vals) if ms_vals else None
        ts_vals = [x['ts'] for x in val if x['ts'] is not None and ('进入体检' in (x['ent'] or '') or '是' in (x['ent'] or ''))]
        ts = min(ts_vals) if ts_vals else None
    elif typ == 'written':
        wc = sum(1 for x in val if x['ms'] is not None)  # 排除缺考
        ms_vals = [x['ms'] for x in val if x['ms'] is not None]
        ms = min(ms_vals) if ms_vals else None
        ic = ts = None
    elif typ == 'interview':
        wc = ms = ts = None
        ic = len(val)
    else:
        wc = ic = ms = ts = None

    _apply_scores(hits[0], wc, ic, ms, ts, key, results)


# ---------------- 主流程 ----------------
def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    dry = '--apply' not in sys.argv
    global DRY
    DRY = dry
    if not args:
        print('用法: python scripts/ingest_drop.py <目录> [--apply]')
        return
    d = args[0]
    if not os.path.isdir(d):
        print('[ERR] 目录不存在: %s' % d)
        return

    html, b, e, db = load_db()
    print('本地库 %d 条 | 目录 %s' % (len(db), d))

    idx_code = defaultdict(list)
    idx_sp = defaultdict(list)
    idx_sch = defaultdict(list)
    for r in db:
        idx_code[(r.get('c'), r.get('d'), r.get('yr'), r.get('position_code') or '')].append(r)
        idx_sp[(r.get('d'), r.get('yr'), norm_school(r.get('sc')), norm_pos(r.get('p')))].append(r)
        idx_sch[(r.get('c'), r.get('d'), r.get('yr'), norm_school(r.get('sc')))].append(r)

    results = {'update': [], 'clear': [], 'abnormal': [], 'nomatch': [], 'dup': [], 'nochange': []}
    files = sorted(f for f in os.listdir(d) if os.path.splitext(f)[1].lower() in ('.xlsx', '.xls', '.pdf'))

    # ---- 阶段1: 跨文件聚合（多批次拟聘公示必须跨文件累加同一 code/校岗）----
    hire_code = defaultdict(lambda: defaultdict(Counter))  # (typ,c,d,yr)[code][school]->count
    hire_sp = defaultdict(Counter)                          # (typ,c,d,yr)[(school,pos)]->count
    hire_sch = defaultdict(Counter)                         # (typ,c,d,yr)[(school,)]->count
    score_code = defaultdict(lambda: defaultdict(list))     # (typ,c,d,yr)[code]->[raw rows]
    score_sp = defaultdict(lambda: defaultdict(list))       # (typ,c,d,yr)[(school,pos)]->[raw rows]
    jobtable_code = defaultdict(lambda: defaultdict(list))  # (c,dist,yr)[code]->[job rows]

    skipped = []
    for f in files:
        path = os.path.join(d, f)
        try:
            rows = read_file(path)
        except Exception as ex:
            print('[ERR] %s: %s' % (f, ex))
            continue
        title = f + '|' + '|'.join('|'.join(r[:4]) for r in rows[:3])
        c, dist, yr = infer_loc(title)
        cls = classify(rows, f)
        if cls is None:
            skipped.append((f, '无法分类'))
            continue
        typ, mode = cls
        raw = extract_raw(rows)
        if not raw:
            skipped.append((f, '无数据'))
            continue
        if c is None or dist is None or yr is None:
            skipped.append((f, '无法定位 c=%s d=%s yr=%s' % (c, dist, yr)))
            continue

        print('%s [%s/%s] c=%s d=%s yr=%s (%d人)' % (f[:40], typ, mode, c, dist, yr, len(raw)))

        if typ == 'jobtable':
            jobs = extract_jobtable(rows)
            if not jobs:
                skipped.append((f, '岗位表无数据'))
                continue
            for x in jobs:
                jobtable_code[(c, dist, yr)][x['code']].append(x)
            continue

        if typ in ('hire', 'physical'):
            for x in raw:
                if typ == 'physical' and '合格' not in (x['ent'] or ''):
                    continue
                if mode == 'code':
                    hire_code[(typ, c, dist, yr)][x['code']][x['school']] += 1
                elif mode == 'school_pos':
                    hire_sp[(typ, c, dist, yr)][(x['school'], x['pos'])] += 1
                elif mode == 'school_only':
                    hire_sch[(typ, c, dist, yr)][(x['school'],)] += 1
        else:
            for x in raw:
                if mode == 'code':
                    score_code[(typ, c, dist, yr)][x['code']].append(x)
                elif mode == 'school_pos':
                    score_sp[(typ, c, dist, yr)][(x['school'], x['pos'])].append(x)

    for f, why in skipped:
        print('[SKIP %s] %s' % (why, f))

    # ---- 阶段2: 匹配 + 规则 ----
    def match_hire_code():
        for (typ, c, dist, yr), codes in sorted(hire_code.items()):
            print('\n== %s-%s yr=%s (%s, 代码匹配) %d code' % (c, dist, yr, typ, len(codes)))
            for code, sc_counter in sorted(codes.items()):
                total = sum(sc_counter.values())
                hits = idx_code[(c, dist, yr, code)]
                if not hits:
                    results['nomatch'].append((code, total))
                    print('  [无匹配] %s n=%d' % (code, total))
                elif len(hits) == 1:
                    _apply_hire(hits[0], total, code, results)
                else:
                    distinct = {norm_school(r.get('sc') or '') for r in hits}
                    if len(distinct) == 1:
                        results['dup'].append((code, total, len(hits)))
                        print('  [重复%d] %s n=%d pr=%s' % (len(hits), code, total, [r.get('pr') for r in hits]))
                    else:
                        matched = False
                        for r in hits:
                            cnt = sc_counter.get(norm_school(r.get('sc') or ''), 0)
                            if cnt > 0:
                                _apply_hire(r, cnt, code, results)
                                matched = True
                        if not matched:
                            results['nomatch'].append((code, total))
                            print('  [无匹配·校拆] %s n=%d' % (code, total))

    def match_hire_sp():
        for (typ, c, dist, yr), sp in sorted(hire_sp.items()):
            print('\n== %s-%s yr=%s (%s, 校岗匹配) %d 组' % (c, dist, yr, typ, len(sp)))
            for (s, p), n in sorted(sp.items()):
                if re.match(r'^(小学|初中|高中|中职)?体育$', p):
                    results['nomatch'].append((s, p, n))
                    print('  [体育专项待核] %s|%s n=%d (无专项, 无法匹配)' % (s[:14], p, n))
                    continue
                hits = idx_sp[(dist, yr, s, p)]
                if not hits:
                    results['nomatch'].append((s, p, n))
                    print('  [无匹配] %s|%s n=%d' % (s[:14], p, n))
                elif len(hits) == 1:
                    _apply_hire(hits[0], n, '%s|%s' % (s[:10], p), results)
                else:
                    results['dup'].append((s, p, n, len(hits)))
                    print('  [重复%d] %s|%s n=%d' % (len(hits), s[:14], p, n))

    def match_hire_sch():
        # 校-only（无代码无岗位名）一律罗列不动：按学校匹配无法精确到岗位，自动写入会猜错
        for (typ, c, dist, yr), sch in sorted(hire_sch.items()):
            print('\n== %s-%s yr=%s (%s, 校匹配·罗列不动) %d 组' % (c, dist, yr, typ, len(sch)))
            for (s,), n in sorted(sch.items()):
                hits = idx_sch[(c, dist, yr, s)]
                results['nomatch'].append((s, n))
                print('  [罗列不动] %s n=%d (命中%d)' % (s[:16], n, len(hits)))

    def match_score():
        for (typ, c, dist, yr), codes in sorted(score_code.items()):
            print('\n== %s-%s yr=%s (%s, 代码匹配) %d code' % (c, dist, yr, typ, len(codes)))
            for code, val in sorted(codes.items()):
                _match_score_group(typ, code, val, idx_code[(c, dist, yr, code)], results)
        for (typ, c, dist, yr), sp in sorted(score_sp.items()):
            print('\n== %s-%s yr=%s (%s, 校岗匹配) %d 组' % (c, dist, yr, typ, len(sp)))
            for (s, p), val in sorted(sp.items()):
                _match_score_group(typ, '%s|%s' % (s[:10], p), val, idx_sp[(dist, yr, s, p)], results)

    match_hire_code()
    match_hire_sp()
    match_hire_sch()
    match_score()
    new_records = match_jobtable(jobtable_code, db, results, idx_code)

    print('\n' + '=' * 60)
    print('汇总: 更新=%d 清空=%d 新增=%d 异常=%d 无匹配=%d 重复=%d 不变=%d' % (
        len(results['update']), len(results['clear']), len(new_records), len(results['abnormal']),
        len(results['nomatch']), len(results['dup']), len(results['nochange'])))

    if dry:
        print('\n[DRY-RUN] 未写入 (加 --apply 写入)')
        return

    for rec in new_records:
        db.append(rec)
    for r, changes in results['update']:
        r.update(changes)
        r['_batch'] = 'current'
        r['_batch_label'] = '本次更新'
    for r in results['clear']:
        r['_final_hired'] = None
        r['_batch'] = 'current'
        r['_batch_label'] = '本次更新'
    new_json = json.dumps(db, ensure_ascii=False, indent=2)
    open(VIEWER, 'w', encoding='utf-8').write(html[:b] + new_json + html[e:])
    print('[APPLY] 更新=%d 清空=%d 新增=%d, 总记录 %d' % (len(results['update']), len(results['clear']), len(new_records), len(db)))


if __name__ == '__main__':
    main()
