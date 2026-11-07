"""Render an already filled workbook for browser printing without changing its source."""
from bisect import bisect_right
from datetime import date, datetime
import io
import re

from openpyxl import load_workbook

from print_fill import validate_template_file
from services.label_excel_preview import _sheet_layout
from services.report_print_preview import _cell_css, _display_value, _print_bounds

_PAPERS={'1':('Letter',215.9,279.4),'5':('Legal',215.9,355.6),
         '8':('A3',297,420),'9':('A4',210,297),'11':('A5',148,210)}
_PX_PER_MM=96/25.4


def _date_text(cell):
    value = cell.value
    if not isinstance(value, (date, datetime)):
        return _display_value(cell)
    fmt = (cell.number_format or '').lower().replace('"', '')
    year, month, day = value.year, value.month, value.day
    formats = {
        'yyyy-mm-dd': f'{year:04}-{month:02}-{day:02}',
        'yyyy/m/d': f'{year}/{month}/{day}',
        'yyyy/mm/dd': f'{year:04}/{month:02}/{day:02}',
        'yyyy年m月d日': f'{year}年{month}月{day}日',
        'yyyy年mm月dd日': f'{year}年{month:02}月{day:02}日',
        'm/d/yy': f'{month}/{day}/{year % 100:02}',
    }
    if fmt in formats:
        return formats[fmt]
    if isinstance(value, datetime) and fmt in ('yyyy-mm-dd h:mm:ss', 'yyyy-mm-dd hh:mm:ss'):
        return value.strftime('%Y-%m-%d %H:%M:%S')
    raise ValueError('模板日期格式暂不支持浏览器打印，请使用 Excel 文件打印')


def _header_footer(part,number,total,sheet):
    result={}
    for side in ('left','center','right'):
        text=str(getattr(part,side).text or '')
        if '&G' in text or '&[Picture]' in text or '&F' in text or '&Z' in text:
            raise ValueError('模板页眉页脚含图片或文件路径，请使用 Excel 文件打印')
        text=re.sub(r'&"[^\"]*"|&K[0-9A-Fa-f]{6}|&\d+|&[BIUSEXYO]', '',text)
        for token,value in [('&[Page]',number),('&[Pages]',total),('&P',number),('&N',total),
                            ('&A',sheet),('&D',datetime.now().strftime('%Y-%m-%d')),
                            ('&T',datetime.now().strftime('%H:%M'))]:
            text=text.replace(token,str(value))
        result[side]=text.replace('&&','&')
    return result


def _sheet_pages(sheet):
    if sheet.conditional_formatting:
        raise ValueError('模板含条件格式，浏览器不能可靠计算，请使用 Excel 文件打印')
    if sheet.col_breaks.brk or sheet.HeaderFooter.differentOddEven or sheet.HeaderFooter.differentFirst:
        raise ValueError('模板含分栏分页或不同页眉页脚，请使用 Excel 文件打印')
    try:layout=_sheet_layout(sheet)
    except ValueError as exc:raise ValueError(str(exc).replace('标签','单据')) from exc
    if any(o['top']<0 or o['left']<0 or o['top']+o['height']>layout['content_height']+.01
           or o['left']+o['width']>layout['content_width']+.01 for o in layout['images']):
        raise ValueError('模板图片超出打印区域，请调整打印区域或使用 Excel 文件打印')
    paper=_PAPERS.get(str(sheet.page_setup.paperSize or '9'))
    if paper is None:raise ValueError('模板纸张规格暂不支持浏览器打印，请使用 Excel 文件打印')
    name,width,height=paper
    orientation='landscape' if sheet.page_setup.orientation=='landscape' else 'portrait'
    if orientation=='landscape':width,height=height,width
    margins={key:float(getattr(sheet.page_margins,key) or 0)*25.4 for key in ('top','bottom','left','right')}
    usable_width=width-margins['left']-margins['right']
    usable_height=height-margins['top']-margins['bottom']
    if usable_width<=10 or usable_height<=10:raise ValueError('模板页边距没有留下可打印区域')
    scale=min(1,usable_width*_PX_PER_MM/layout['content_width'])
    if sheet.sheet_properties.pageSetUpPr.fitToPage and sheet.page_setup.fitToHeight == 1:
        scale=min(scale,usable_height*_PX_PER_MM/layout['content_height'])
    capacity=usable_height*_PX_PER_MM/scale
    cells=[]
    for cell,geometry in layout['cells']:
        if cell.alignment.textRotation or cell.alignment.indent or cell.font.vertAlign:
            raise ValueError('模板含旋转、缩进或上下标文字，请使用 Excel 文件打印')
        cells.append(dict(geometry,text=_date_text(cell),css=_cell_css(cell)))
    objects=cells+layout['images']
    boundaries=sorted({0,layout['content_height'],*[c['top'] for c in cells],
                       *[c['top']+c['height'] for c in cells]})
    intervals=[]
    for first,last in sorted((o['top'],o['top']+o['height']) for o in objects):
        if intervals and first<intervals[-1][1]-.01:
            intervals[-1][1]=max(intervals[-1][1],last)
        else:intervals.append([first,last])
    starts=[p[0] for p in intervals]
    cuts=[]
    for y in boundaries:
        index=bisect_right(starts,y-.01)-1
        if index<0 or y>=intervals[index][1]-.01:cuts.append(y)
    header_end=0
    if sheet.print_title_rows:
        first,last=map(int,sheet.print_title_rows.replace('$','').split(':'))
        if first!=1:raise ValueError('重复打印标题需从首行开始，请使用 Excel 文件打印或调整模板')
        header_end=max((g['top']+g['height'] for cell,g in layout['cells'] if cell.row<=last),default=0)
        if header_end not in cuts or header_end>=capacity/2:
            raise ValueError('模板重复标题过大或跨合并区域，请调整后打印')
    bounds=_print_bounds(sheet)
    top=bounds[0][1] if bounds else 1
    if sheet.print_title_rows and top!=1:
        raise ValueError('重复标题在打印区域之外，请使用 Excel 文件打印或调整模板')
    manual=[]
    for marker in sheet.row_breaks.brk:
        y=sum(0 if sheet.row_dimensions[row].hidden else float(sheet.row_dimensions[row].height or 15)*96/72
              for row in range(top,marker.id+1))
        if y in cuts:manual.append(y)
        elif 0<y<layout['content_height']:raise ValueError('手动分页截断合并单元格或图片，请调整模板')
    pages=[];start=0
    while start<layout['content_height']-.01:
        repeat=header_end if pages else 0
        limit=start+capacity-repeat
        choices=[y for y in cuts if start+.01<y<=limit+.01]
        if not choices:raise ValueError('模板合并单元格或图片超过一页，请调整模板或使用 Excel 文件打印')
        stops=[y for y in manual if start+.01<y<=limit+.01]
        end=min(stops) if stops else max(choices)
        def _page_objects(rows):
            result=[]
            if repeat:result.extend(dict(o) for o in rows if o['top']+o['height']<=header_end+.01)
            result.extend(dict(o,top=o['top']-start+repeat) for o in rows
                          if start-.01<=o['top'] and o['top']+o['height']<=end+.01)
            return result
        pages.append(dict(name=sheet.title,paper=name,orientation=orientation,page_width=width,page_height=height,
                          margins=margins,scale=scale,content_width=layout['content_width'],
                          content_height=capacity,cells=_page_objects(cells),images=_page_objects(layout['images']),
                          header_source=sheet.oddHeader,footer_source=sheet.oddFooter))
        start=end
        if len(pages)>500:raise ValueError('单据打印超过500页，请缩小打印内容')
    return pages


def build_document_excel_preview(stream):
    """Keep filled cells, merges, logos, paper sizes and all rows; reject unsupported layouts."""
    stream.seek(0);raw=stream.read()
    error=validate_template_file(raw)
    if error:raise ValueError(error)
    book=load_workbook(io.BytesIO(raw),keep_links=False)
    try:
        visible=[s for s in book.worksheets if s.sheet_state=='visible']
        if not visible:raise ValueError('打印文件没有可见工作表')
        if sum(s.max_row*s.max_column for s in visible)>150000:
            raise ValueError('单据打印内容过大，请使用 Excel 文件打印')
        pages=[p for sheet in visible for p in _sheet_pages(sheet)]
        if len(pages)>500:raise ValueError('单据打印超过500页，请使用 Excel 文件打印')
        for index,page in enumerate(pages,1):
            page['page_number']=index;page['page_name']='documentSheet'+str(index)
            page['header']=_header_footer(page.pop('header_source'),index,len(pages),page['name'])
            page['footer']=_header_footer(page.pop('footer_source'),index,len(pages),page['name'])
        return pages
    finally:book.close()
