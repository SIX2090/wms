"""Build an offline HTML, vector PDF and Mermaid atlas without importing WMS.

Run from any directory: python C:/wms/docs/workflows/build_atlas.py
Requires reportlab; output PDF is under output/pdf as required by the PDF skill.
"""
from __future__ import annotations
import ast
import html
import json
import math
import re
from pathlib import Path

from reportlab.graphics import renderPDF, renderSVG
from reportlab.graphics.shapes import Drawing, Line, Rect, Polygon, String, PolyLine
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph

from flow_content import BASE_SHA, CHAPTERS, DATE, STATUS_ROWS

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
PDF = ROOT / 'output/pdf/wms_flow_atlas_20261014.pdf'
FONT = 'WmsChinese'
PALETTE = {
    'data':('#eaf2ff','#2358a0'), 'human':('#fff1df','#996017'),
    'stock':('#e5f5eb','#206e46'), 'decision':('#fff5cd','#8b671a'),
    'exception':('#fdebec','#a83943'), 'optional':('#f0eefc','#65569a'),
    'read':('#f1f5f9','#475569'),
}


def source(ref):
    name, _, symbol = ref.partition('#')
    path = ROOT / name
    if not path.is_file():
        raise ValueError('Missing source: '+ref)
    line = 1
    if symbol:
        tree = ast.parse(path.read_text(encoding='utf-8-sig'))
        found = []
        for node in ast.walk(tree):
            if isinstance(node,(ast.FunctionDef,ast.ClassDef)) and node.name == symbol:
                found.append(node.lineno)
            if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id == symbol for t in node.targets):
                found.append(node.lineno)
        if not found:
            raise ValueError('Missing source symbol: '+ref)
        line = min(found)
    return {'path':name,'line':line,'symbol':symbol,
            'url':f'https://github.com/SIX2090/wms/blob/{BASE_SHA}/{name}#L{line}'}


def repository_inventory():
    routes, models = [], []
    files = [p for p in (ROOT/'app').rglob('*.py')
             if not any(x in {'.venv','venv','runtime','python','__pycache__'} or x.startswith('_disabled') for x in p.parts)]
    for path in files:
        tree = ast.parse(path.read_text(encoding='utf-8-sig'))
        for node in ast.walk(tree):
            if isinstance(node,ast.FunctionDef):
                for d in node.decorator_list:
                    if isinstance(d,ast.Call) and isinstance(d.func,ast.Attribute) and d.func.attr=='route' and d.args:
                        if isinstance(d.args[0],ast.Constant):
                            methods = ['GET']
                            for kw in d.keywords:
                                if kw.arg == 'methods':
                                    try:methods=ast.literal_eval(kw.value)
                                    except (ValueError,TypeError):methods=['dynamic']
                            roles=[ast.unparse(x) for x in node.decorator_list if 'require_role' in ast.unparse(x)]
                            routes.append({'url':d.args[0].value,'methods':methods,'function':node.name,
                                           'source':str(path.relative_to(ROOT)).replace('\\','/'),'line':node.lineno,'roles':roles})
    for path in files:
        tree=ast.parse(path.read_text(encoding='utf-8-sig'))
        for node in tree.body:
            if isinstance(node,ast.ClassDef) and any(ast.unparse(b)=='db.Model' for b in node.bases):
                models.append({'name':node.name,'source':str(path.relative_to(ROOT)).replace('\\','/'),'line':node.lineno})
    src=(ROOT/'app/templates/base.html').read_text(encoding='utf-8')
    start=src.index('<nav class="sidebar"'); nav=src[start:src.index('</nav>',start)]
    menus=[];seen=set()
    for match in re.finditer(r'<a\b[^>]*href="([^"]*)"[^>]*>(.*?)</a>',nav,re.S):
        label=re.sub(r'<[^>]*>|\{%.*?%\}|\{\{.*?\}\}','',match[2],flags=re.S)
        label=' '.join(label.split())
        if (match[1],label) not in seen:
            menus.append({'label':label,'url':match[1]});seen.add((match[1],label))
    reports=[]
    tree=ast.parse((ROOT/'app/app.py').read_text(encoding='utf-8-sig'))
    for node in tree.body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='REPORT_DEFINITIONS' for t in node.targets):
            for key,val in zip(node.value.keys,node.value.values):
                title=''
                for k,v in zip(val.keys,val.values):
                    if isinstance(k,ast.Constant) and k.value=='title':title=ast.literal_eval(v)
                reports.append({'key':ast.literal_eval(key),'title':title})
    return {'date':DATE,'base_sha':BASE_SHA,'scope':'静态代码清点，不启动业务服务，不读取生产数据',
            'routes':routes,'models':models,'menus':menus,'reports':reports}


def wrap(text, maxwidth, fontsize=17):
    lines=[]
    for raw in text.split('\n'):
        line=''
        for char in re.findall(r'[A-Za-z0-9_./+-]+|.',raw):
            if pdfmetrics.stringWidth(line+char,FONT,fontsize)>maxwidth and line:
                lines.append(line);line=char
            else:line+=char
        lines.append(line)
    if len(lines)>1 and len(lines[-1])==1 and len(lines[-2])>2:
        lines[-1]=lines[-2][-1]+lines[-1];lines[-2]=lines[-2][:-1]
    return lines


def graph(chapter):
    nodes=[];edges=[]
    for i,label in enumerate(chapter['steps']):
        kind='human' if '人工' in label else ('stock' if ('库存增加' in label or '扣库存' in label or '库存减少' in label or '记账' in label) else 'data')
        nodes.append({'id':f'n{i}','label':label,'column':1,'row':i,'kind':kind})
        if i:edges.append({'from':f'n{i-1}','to':f'n{i}','label':'','return':False})
    for j,(row,col,label,kind,target,edge) in enumerate(chapter.get('branches',[])):
        if not (0<=row<len(chapter['steps'])):raise ValueError('Invalid branch row')
        nodes.append({'id':f'b{j}','label':label,'column':col,'row':row,'kind':kind})
        edges.append({'from':f'n{row}','to':f'b{j}','label':edge,'return':False})
        if target is not None:
            if not 0<=target<len(chapter['steps']):raise ValueError('Invalid target row')
            edges.append({'from':f'b{j}','to':f'n{target}','label':'','return':True})
    positions=[(n['column'],n['row']) for n in nodes]
    if len(set(positions))!=len(positions):raise ValueError('Overlapping node positions: '+chapter['id'])
    return nodes,edges


def draw_graph(chapter):
    nodes,edges=graph(chapter)
    width=900;pitch=137;boxw=232;boxh=92
    height=(len(chapter['steps'])-1)*pitch+boxh+80
    drawing=Drawing(width,height)
    by_id={n['id']:n for n in nodes}
    for n in nodes:
        n['x']=36+n['column']*300;n['y']=height-40-n['row']*pitch-boxh
    def arrow(points,ret=False,label=''):
        stroke=colors.HexColor('#8795a5' if not ret else '#9383b5')
        drawing.add(PolyLine([v for point in points for v in point],strokeColor=stroke,strokeWidth=1.65,strokeDashArray=[5,4] if ret else None))
        end=points[-1];prev=points[-2];angle=math.atan2(end[1]-prev[1],end[0]-prev[0]);size=7
        triangle=[end[0],end[1],end[0]-size*math.cos(angle-.5),end[1]-size*math.sin(angle-.5),end[0]-size*math.cos(angle+.5),end[1]-size*math.sin(angle+.5)]
        drawing.add(Polygon(triangle,fillColor=stroke,strokeColor=stroke))
        if label:
            segment=max(zip(points,points[1:]),key=lambda pair:math.dist(*pair))
            mid=((segment[0][0]+segment[1][0])/2,(segment[0][1]+segment[1][1])/2)
            tw=pdfmetrics.stringWidth(label,FONT,13)+12
            drawing.add(Rect(mid[0]-tw/2,mid[1]+4,tw,21,fillColor=colors.white,strokeColor=None))
            drawing.add(String(mid[0],mid[1]+10,label,fontName=FONT,fontSize=13,textAnchor='middle',fillColor=colors.HexColor('#526173')))
    for e in edges:
        a=by_id[e['from']];b=by_id[e['to']]
        if a['column']==b['column']:
            arrow([(a['x']+boxw/2,a['y']),(b['x']+boxw/2,b['y']+boxh)],label=e['label'])
        elif a['row']==b['row']:
            right=b['column']>a['column']
            arrow([(a['x']+(boxw if right else 0),a['y']+boxh/2),
                   (b['x']+(0 if right else boxw),b['y']+boxh/2)],e['return'],e['label'])
        else:
            # Keep return paths in the gap next to the side branch, away from boxes.
            side=a['column']; gutter=315 if side==0 else 615
            start=(a['x']+(boxw if side==0 else 0),a['y']+boxh/2)
            end=(b['x']+(0 if side==0 else boxw),b['y']+boxh/2)
            arrow([start,(gutter,start[1]),(gutter,end[1]),end],True,e['label'])
    for n in nodes:
        fill,stroke=PALETTE[n['kind']]
        drawing.add(Rect(n['x'],n['y'],boxw,boxh,rx=10,ry=10,fillColor=colors.HexColor(fill),strokeColor=colors.HexColor(stroke),strokeWidth=1.4,
                         strokeDashArray=[5,3] if n['kind']=='optional' else None))
        lines=wrap(n['label'],boxw-26,17)
        if len(lines)>4:raise ValueError('Node text too long: '+n['label'])
        first=n['y']+boxh/2+(len(lines)-1)*11-6
        for i,line in enumerate(lines):
            drawing.add(String(n['x']+boxw/2,first-i*22,line,fontName=FONT,fontSize=17,textAnchor='middle',fillColor=colors.HexColor('#182d42')))
        if n['id'].startswith('n'):
            drawing.add(String(n['x']+8,n['y']+boxh-17,str(n['row']+1).zfill(2),fontName=FONT,fontSize=10,fillColor=colors.HexColor(stroke)))
    return drawing,nodes,edges


def paragraph(canvas,text,x,y,width,size=10,leading=None,color='#23364b'):
    style=ParagraphStyle('text',fontName=FONT,fontSize=size,leading=leading or size*1.65,textColor=colors.HexColor(color),wordWrap='CJK',spaceAfter=0)
    p=Paragraph(text,style);w,h=p.wrap(width,1000);p.drawOn(canvas,x,y-h)
    return y-h


def build_pdf(chapters,inventory):
    from reportlab.pdfgen import canvas
    PDF.parent.mkdir(parents=True,exist_ok=True)
    c=canvas.Canvas(str(PDF),pagesize=A4,invariant=1,pageCompression=1)
    c.setTitle('WMS全系统详细流程图册');c.setAuthor('WMS项目 · 基于当前源码')
    pw,ph=A4;page=0
    def header(title):
        nonlocal page
        page+=1;c.setFillColor(colors.HexColor('#162f4d'));c.rect(0,ph-10,pw,10,fill=1,stroke=0)
        c.setFont(FONT,8);c.setFillColor(colors.HexColor('#597086'));c.drawString(30,ph-31,'WMS FLOW ATLAS | '+DATE+' | 源码 '+BASE_SHA[:8])
        paragraph(c,html.escape(title),30,ph-51,pw-60,17,23)
        c.setFont(FONT,8);c.setFillColor(colors.HexColor('#738399'));c.drawString(30,20,'基于代码核对 / 图中“完成”必须结合对应对象理解');c.drawRightString(pw-30,20,f'{page:02d}')
    header('WMS全系统详细流程图册')
    y=ph-118
    y=paragraph(c,'业务总览 · 采购销售 · 仓库库存 · BOM领料 · 委外 · 手机扫码 · AI · 报表 · 打印 · 运维',30,y,pw-60,18,30)
    y-=28;y=paragraph(c,'30个流程专题 / 每专题含流程图及操作与口径说明 / 可缩放矢量PDF / 离线网页 / Mermaid图源',30,y,pw-60,12,22)
    y-=24
    for text in ['核对基线：'+BASE_SHA,'本册描述代码已实现流程及可选开关，不表示所有能力在当前部署已配置或已启用。','重要口径：草稿、订单执行、库存记账、识别任务和打印任务分别管理。','使用建议：先读总览和普通单据流程，再按菜单查对应专题；反提交、退货、盘点与期初请结合口径说明。','图例：蓝=数据与普通步骤；橙=人工动作；绿=库存动作；红=失败/限制；紫虚框=可选分支；灰=只读；虚线=回到前一步或分支汇合。']:
        y-=14;y=paragraph(c,html.escape(text),30,y,pw-60,11,19)
    y-=22;y=paragraph(c,f'静态清点：{len(inventory["routes"])}条路由声明、{len(inventory["models"])}个模型类、{len(inventory["menus"])}个去重菜单链接、{len(inventory["reports"])}类通用报表。数量是扫描范围统计，不等同生产启用数量。',30,y,pw-60,10,17)
    c.showPage();header('阅读导航与专题目录');y=ph-96
    for index,ch in enumerate(chapters):
        target=f'flow-{ch["id"]}';label=ch['title'];y=paragraph(c,html.escape(label),32,y,pw-64,10,17)
        c.linkRect('',target,(30,y,pw-30,y+17),relative=0,thickness=0);y-=5
        if y<60 and index<len(chapters)-1:c.showPage();header('阅读导航与专题目录（续）');y=ph-96
    c.showPage()
    for ch in chapters:
        header(ch['title']+' / 流程图');c.bookmarkPage('flow-'+ch['id']);c.addOutlineEntry(ch['title'],'flow-'+ch['id'],level=0)
        y=paragraph(c,'入口：'+html.escape(ch['entry']),30,ph-88,pw-60,9,15)
        drawing=ch['drawing'];avail=(pw-46, y-62);scale=min(avail[0]/drawing.width,avail[1]/drawing.height)
        c.saveState();c.translate((pw-drawing.width*scale)/2,y-12-drawing.height*scale);c.scale(scale,scale);renderPDF.draw(drawing,c,0,0);c.restoreState();c.showPage()
        header(ch['title']+' / 操作与口径');y=ph-98
        y=paragraph(c,'<b>库存影响</b>　'+html.escape(ch['effect']),30,y,pw-60,11,19);y-=18
        for i,note in enumerate(ch['notes'],1):
            y=paragraph(c,f'<b>{i:02d}</b>　'+html.escape(note),30,y,pw-60,10.5,18);y-=15
        y-=3;y=paragraph(c,'<b>代码核对来源</b>（链接固定到制图源码基线）',30,y,pw-60,10,17);y-=8
        for ref in ch['sources']:
            label=ref['path']+(('#'+ref['symbol']) if ref['symbol'] else '')+f':{ref["line"]}'
            y=paragraph(c,'<link href="'+html.escape(ref['url'],quote=True)+'" color="#2358a0">'+html.escape(label)+'</link>',30,y,pw-60,8.5,14);y-=7
        if y<42:raise ValueError('Detail page overflow: '+ch['id'])
        c.showPage()
    header('附录A / 单据状态与库存影响');y=ph-98
    for row in STATUS_ROWS:
        block=f'<b>{html.escape(row[0])}</b><br/>状态：{html.escape(row[1])}<br/>回退：{html.escape(row[2])}<br/>库存：{html.escape(row[3])}'
        if y<130:c.showPage();header('附录A / 状态与库存影响（续）');y=ph-98
        y=paragraph(c,block,30,y,pw-60,9.5,15);y-=15
    c.showPage();header('附录B / 通用报表与其他专题');y=ph-98
    for report in inventory['reports']:
        y=paragraph(c,html.escape(report['title']+'　/report/view/'+report['key']),30,y,pw-60,10,17);y-=8
    y-=18;paragraph(c,'另有采购专题、销售执行/价格/对账、仪表盘与异常工作台，不能把14类通用报表当成全部报表。完整菜单与路由清点见离线网页附录和source_inventory.json。',30,y,pw-60,10,18)
    c.showPage();header('附录C / 范围、维护与使用边界');y=ph-98
    for text in ['资料来源：当前源码、模型、页面菜单、库存真相、业务口径与AI权限矩阵；没有使用生产写入测试来编造流程。','旧文档状态表与当前路由有时间差。工单领料、调拨已存在反提交；采购订单有关闭/重开，销售订单有有条件取消。本册按实际代码列出，不把过时注释当作唯一操作依据。','某模型保留状态不代表当前页面一定提供对应按钮；某路由存在不代表所有角色、开关或当前配置都能使用。','当前批次/有效期为明细事实记录，客供没有独立所有权余额账；BOM领料不是完整生产ERP，销售对账不是财务总账。','本册不提供线上恢复数据库、修改密码或直接改库存的授权。任何实际动作必须遵守单据状态、来源关联、角色和人工确认边界。','更新方式：维护docs/workflows/flow_content.py后运行build_atlas.py，再核对图文、来源与PDF页面。业务代码变化时重新审查流转，不能只更新图上标题。']:
        y=paragraph(c,html.escape(text),30,y,pw-60,11,19);y-=20
    c.save();return page


def table(headers,rows):
    return '<table><thead><tr>'+''.join('<th>'+html.escape(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+html.escape(str(x))+'</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table>'


def main():
    fonts=[Path('C:/Windows/Fonts/msyh.ttc'),Path('C:/Windows/Fonts/simhei.ttf')]
    font=next((p for p in fonts if p.exists()),None)
    if not font:raise RuntimeError('A Chinese font is required')
    pdfmetrics.registerFont(TTFont(FONT,str(font)))
    inventory=repository_inventory();chapters=[];md=[];html_sections=[]
    OUT.mkdir(exist_ok=True);(OUT/'svg').mkdir(exist_ok=True)
    md.extend(['# WMS 全系统详细流程图册',f'制图日期：{DATE}；代码基线：`{BASE_SHA}`。','本册按当前代码描述30个专题。蓝框为数据、橙框为人工、绿框为库存动作、红框为限制、紫虚框为可选分支；虚线表示回退或汇合。','当前代码支持的操作可能比旧状态表更多，详见附录。'])
    ids=set()
    for ch in CHAPTERS:
        if ch['id'] in ids:raise ValueError('Duplicate chapter')
        ids.add(ch['id']);ch=dict(ch);ch['sources']=[source(r) for r in ch['refs']]
        d,nodes,edges=draw_graph(ch);ch['drawing']=d;chapters.append(ch)
        svg=renderSVG.drawToString(d).replace('font-family="'+FONT+'"','font-family="Microsoft YaHei, SimHei, sans-serif"').replace('font-family: '+FONT,'font-family: Microsoft YaHei, SimHei, sans-serif')
        svg=svg[svg.index('<svg'):]
        svg=svg.replace('<svg ','<svg role="img" aria-label="'+html.escape(ch['title'],quote=True)+'" ',1)
        (OUT/'svg'/f'{ch["id"]}.svg').write_text(svg,encoding='utf-8')
        lines=['flowchart TD']
        for n in nodes:
            label=html.escape(n['label'].replace('\n','<br/>'),quote=True).replace('&lt;br/&gt;','<br/>')
            lines.append(f'  {n["id"]}["{label}"]')
        for e in edges:
            line='-.->' if e['return'] else '-->'
            lines.append(f'  {e["from"]} {line}'+ ('|'+e['label']+'|' if e['label'] else '')+' '+e['to'])
        for kind,(fill,stroke) in PALETTE.items():
            lines.append(f'  classDef {kind} fill:{fill},stroke:{stroke},color:#182d42')
            matching=[n['id'] for n in nodes if n['kind']==kind]
            if matching:lines.append('  class '+','.join(matching)+' '+kind)
        md.extend(['',f'## {ch["title"]}','',f'入口：{ch["entry"]}。',f'库存影响：{ch["effect"]}。','','```mermaid',*lines,'```','','### 操作与口径',''])
        md.extend(f'{i}. {note}' for i,note in enumerate(ch['notes'],1));md.extend(['','### 核对来源',''])
        md.extend(f'- [{r["path"]}'+ ('#'+r['symbol'] if r['symbol'] else '')+f':{r["line"]}]({r["url"]})' for r in ch['sources'])
        notes=''.join('<li>'+html.escape(n)+'</li>' for n in ch['notes'])
        sources=''.join('<li><a href="'+html.escape(r['url'],quote=True)+'">'+html.escape(r['path']+(' #'+r['symbol'] if r['symbol'] else '')+f':{r["line"]}')+'</a></li>' for r in ch['sources'])
        html_sections.append('<section id="'+ch['id']+'" class="chapter"><header><h2>'+html.escape(ch['title'])+'</h2><p>入口：'+html.escape(ch['entry'])+'</p><p class="effect">库存影响：'+html.escape(ch['effect'])+'</p></header><div class="diagram">'+svg+'</div><h3>操作与口径</h3><ol>'+notes+'</ol><details><summary>代码核对来源</summary><ul>'+sources+'</ul></details><p class="download"><a href="svg/'+ch['id']+'.svg" download>保存本张矢量流程图</a> · <a href="#top">回到顶部</a></p></section>')
    inventory['chapters']=[{'id':ch['id'],'title':ch['title'],'sources':ch['sources'],'nodes':graph(ch)[0],'edges':graph(ch)[1]} for ch in chapters]
    (OUT/'source_inventory.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    md.extend(['','## 附录A：单据状态与库存影响','','| 对象 | 状态 | 回退 | 库存 |','|---|---|---|---|'])
    md.extend('| '+' | '.join(row)+' |' for row in STATUS_ROWS)
    md.extend(['','## 附录B：通用报表类型','']);md.extend('- '+r['title']+'：`/report/view/'+r['key']+'`' for r in inventory['reports'])
    md.extend(['','## 附录C：完整菜单清点','']);md.extend('- '+m['label']+'：`'+m['url']+'`' for m in inventory['menus'])
    md.extend(['','## 附录D：制图范围','',f'静态扫描{len(inventory["routes"])}条路由声明、{len(inventory["models"])}个模型类；不是生产启用数量。完整路由清单、方法、函数、角色声明及源代码行号见source_inventory.json。','本册未执行生产业务写入、单据完成、库存调整、密码修改或备份恢复。'])
    (OUT/'WMS_FLOW_ATLAS.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
    nav=''.join('<a href="#'+ch['id']+'">'+html.escape(ch['title'])+'</a>' for ch in chapters)
    appendix='<section id="appendix" class="chapter"><h2>附录：状态与库存影响</h2>'+table(['对象','状态','回退规则','库存影响'],STATUS_ROWS)+'<h2>通用报表（14类）</h2>'+table(['报表','入口'],[(r['title'],'/report/view/'+r['key']) for r in inventory['reports']])+'<details><summary>完整菜单清点（含角色菜单去重链接）</summary>'+table(['菜单','入口'],[(m['label'],m['url']) for m in inventory['menus']])+'</details><details><summary>技术路由清点（静态声明，不等同已启用数量）</summary>'+table(['方法','路径','源码定位'],[('/'.join(r['methods']),r['url'],r['source']+':'+str(r['line'])+' #'+r['function']) for r in inventory['routes']])+'</details></section>'
    css='''*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#f4f7fb;color:#24364b;font:15px/1.75 "Microsoft YaHei",sans-serif}a{color:#2358a0}header.hero{padding:40px 5vw 28px;background:#18314d;color:white}h1{margin:0 0 12px;font-size:32px}h2{color:#193b5d;margin:0 0 10px}h3{color:#294d70}p{margin:8px 0}.meta{opacity:.85}.tools{display:flex;flex-wrap:wrap;gap:12px;padding:16px 5vw;background:white;position:sticky;top:0;z-index:5;border-bottom:1px solid #dbe4ef}input,button,.pdf-link{font:inherit;padding:8px 13px;border:1px solid #bac8d9;border-radius:6px;background:white;color:#23405e}input{min-width:220px;flex:1}button{cursor:pointer}.pdf-link{background:#eaf2ff;text-decoration:none}.layout{display:grid;grid-template-columns:265px minmax(0,1fr);gap:25px;padding:25px 3vw}.nav{align-self:start;position:sticky;top:84px;max-height:calc(100vh - 110px);overflow:auto}.nav a{display:block;padding:7px 10px;text-decoration:none;font-size:13px}.nav a:hover{background:#e0eafa}.chapter{background:white;margin:0 0 28px;padding:26px;border:1px solid #dde5ef;border-radius:10px;scroll-margin-top:100px}.effect{padding:10px 14px;background:#edf7f1;border-left:4px solid #398267}.diagram{overflow:auto;margin:20px 0;border-top:1px solid #edf1f6;border-bottom:1px solid #edf1f6}.diagram svg{display:block;width:100%;height:auto;min-width:550px}li{margin:10px 0}summary{cursor:pointer;font-weight:600;padding:10px 0}table{width:100%;border-collapse:collapse;margin:12px 0;font-size:12px;overflow-wrap:anywhere}th,td{border:1px solid #dce4ed;padding:9px;vertical-align:top;text-align:left}th{background:#eff4fa}.download{font-size:13px}.legend{display:flex;gap:12px;flex-wrap:wrap;margin:18px 0 0}.legend span{border-radius:4px;padding:3px 8px}.disclaimer{background:#fff8de;padding:12px 16px}.empty{display:none;padding:25px;font-weight:600}body.focus-diagrams .chapter ol,body.focus-diagrams .chapter details,body.focus-diagrams .chapter h3{display:none}@media(max-width:850px){.layout{display:block;padding:15px}.nav{position:static;max-height:220px;background:white;margin-bottom:18px}.chapter{padding:16px}h1{font-size:25px}.tools{position:static}.chapter{scroll-margin-top:15px}}@media print{body{background:white}.tools,.nav,.download,.meta,.empty{display:none}.layout{display:block;padding:0}.chapter{border:0;margin:0;padding:0;break-before:page}.diagram svg{min-width:0;max-height:210mm}.diagram{overflow:visible;border:0}header.hero{background:white;color:#18314d;padding:20px 0}details{display:none}table{font-size:10px}}'''
    script='''const search=document.getElementById('search');search.addEventListener('input',()=>{const term=search.value.trim().toLowerCase();let count=0;document.querySelectorAll('main .chapter').forEach(s=>{s.hidden=!!term&&!s.textContent.toLowerCase().includes(term);if(!s.hidden)count++;});document.querySelectorAll('.nav a').forEach(a=>{const s=document.querySelector(a.getAttribute('href'));a.hidden=s&&s.hidden;});document.getElementById('count').textContent=term?`匹配 ${count} 个专题/附录`:'30个专题 + 附录';document.getElementById('empty').style.display=count?'none':'block';});document.getElementById('print').addEventListener('click',()=>window.print());document.getElementById('mode').addEventListener('click',e=>{const active=document.body.classList.toggle('focus-diagrams');e.target.textContent=active?'显示操作说明':'只看流程图';e.target.setAttribute('aria-pressed',String(active));});'''
    doc='<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>WMS全系统详细流程图册</title><style>'+css+'</style></head><body id="top"><header class="hero"><h1>WMS 全系统详细流程图册</h1><p>30个流程专题，从基础资料到业务记账、AI辅助与生产运维。</p><p class="meta">核对日期 '+DATE+' · 源码 '+BASE_SHA[:8]+' · 离线可用 · 矢量可放大</p><div class="legend">'+''.join('<span style="background:'+fill+';color:'+stroke+'">'+label+'</span>' for label,(fill,stroke) in zip(['数据/步骤','人工动作','库存动作','条件','失败/限制','可选分支','只读'],PALETTE.values()))+'</div></header><div class="tools"><input id="search" aria-label="搜索流程专题" placeholder="搜索：BOM、采购、盘点、备份……"><button id="mode" aria-pressed="false">只看流程图</button><button id="print">打印当前内容</button><a class="pdf-link" href="../../output/pdf/wms_flow_atlas_20261014.pdf">查看完整PDF</a><span id="count" aria-live="polite">30个专题 + 附录</span></div><div class="layout"><nav class="nav" aria-label="流程目录">'+nav+'<a href="#appendix">附录：状态、报表、菜单与路由</a></nav><main><p class="disclaimer">草稿、单据完成、订单执行、AI任务和打印任务各有状态；可选能力是否可用，还需看实际角色、开关和配置。本册不执行生产业务操作。</p><div id="empty" class="empty">没有匹配专题，请更换关键词。</div>'+''.join(html_sections)+appendix+'</main></div><script>'+script+'</script></body></html>'
    (OUT/'index.html').write_text(doc,encoding='utf-8')
    pages=build_pdf(chapters,inventory)
    manifest={'date':DATE,'base_sha':BASE_SHA,'chapters':len(chapters),'pdf_pages':pages,'routes':len(inventory['routes']),'models':len(inventory['models']),'menus':len(inventory['menus']),'reports':len(inventory['reports']),'validated_source_references':sum(len(c['sources']) for c in chapters),'pdf':str(PDF.relative_to(ROOT)).replace('\\','/')}
    (OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(manifest,ensure_ascii=False))


if __name__=='__main__':
    main()
