"""One read-only template selection and preview flow for existing document print files."""
from pathlib import Path
import io

from flask import g,render_template,request,url_for
from flask_login import login_required
from werkzeug.exceptions import HTTPException

from routes.doc_print_excel import _DOC_ROUTE_MODELS

_DOCUMENTS={code:(prefix,model,f'doc_print_excel_{code}')
            for code,(prefix,model) in _DOC_ROUTE_MODELS.items()}
_DOCUMENTS.update(in_order=('in_order','InOrder','print_in_order_excel'),
                  out_order=('out_order','OutOrder','print_out_order_excel'))


def _base_context(code,oid):
    prefix,_,download=_DOCUMENTS[code]
    query={'template_id':request.args['template_id']} if request.args.get('template_id') else {}
    web_query={'format':'html'} if code in ('purchase_request','in_order','out_order') else {}
    return dict(title='单据打印',number='',templates=[],selected_id=request.args.get('template_id',''),
                error=None,preview_url=f'/{prefix}/{oid}/print_preview',
                selection_url=f'/{prefix}/{oid}/print_options',
                download_url=url_for(f'document_{code}_print_file',id=oid,**query),
                fallback_download_url=url_for(download,id=oid,**query),
                web_url=url_for('print_purchase_request',id=oid,**web_query) if code=='purchase_request'
                         else f'/{prefix}/{oid}/print'+('?format=html' if web_query else ''),
                settings_url='/in_order_print_template' if code=='in_order' else '/out_order_print_template'
                             if code=='out_order' else url_for('print_templates',target_type='document',target_code=code))


def _print_context(code,oid):
    import app as w
    from doc_print_excel import DOC_EXCEL_PRINT_TYPES
    from print_fill import template_file_abspath
    _,model,_=_DOCUMENTS[code];order=w.db.session.get(getattr(w,model),oid)
    if order is None:
        from flask import abort
        abort(404)
    result=_base_context(code,oid)
    result.update(title=DOC_EXCEL_PRINT_TYPES[code]['label'] if code in DOC_EXCEL_PRINT_TYPES
                  else (order.business_type or ('入库单' if code=='in_order' else '出库单')),
                  number=next((str(getattr(order,n)) for n in ('order_no','request_no','check_no','transfer_no',
                              'adjustment_no','req_no','bom_no','doc_no','issue_no','receive_no') if getattr(order,n,None)),str(oid)))
    if code in ('in_order','out_order'):
        model=w.InOrderPrintTemplate if code=='in_order' else w.OutOrderPrintTemplate
        query=model.query.filter_by(template_type='excel')
    else:query=w.ExcelPrintTemplate.query.filter_by(target_type='document',target_code=code,template_type='excel')
    records=query.order_by(model.is_default.desc(),model.updated_at.desc()).all() if code in ('in_order','out_order') else query.order_by(w.ExcelPrintTemplate.is_default.desc(),w.ExcelPrintTemplate.updated_at.desc()).all()
    for record in records:
        path=template_file_abspath(record.excel_template_path,w.app.static_folder)
        result['templates'].append(dict(id=record.id,name=record.name,is_default=bool(record.is_default),
                                        available=bool(path and Path(path).is_file())))
    raw=request.args.get('template_id','').strip()
    if raw:
        if not raw.isdigit() or int(raw)<=0:raise ValueError('打印模板参数不正确，请重新选择')
        chosen=next((t for t in result['templates'] if t['id']==int(raw)),None)
        if chosen is None:raise ValueError('所选模板不属于当前单据类型，请重新选择')
        if not chosen['available']:raise ValueError('所选模板文件不可用，请在模板设置中修复后重试')
        result['template_name']=chosen['name']
        selected=next(t for t in records if t.id==int(raw))
        result['selected_path']=template_file_abspath(selected.excel_template_path,w.app.static_folder)
    else:result['template_name']='默认版式'
    return result


def _make_document_print_view(app,code,preview,download=False):
    def _view(id):
        context=_base_context(code,id)
        try:
            context=_print_context(code,id)
            if preview or download:
                from services.document_excel_preview import build_document_excel_preview
                from print_fill import validate_template_file
                if context.get('selected_path'):
                    selected=Path(context['selected_path'])
                    if selected.stat().st_size>20*1024*1024:raise ValueError('模板文件过大，请精简后打印')
                    error=validate_template_file(selected.read_bytes())
                    if error:raise ValueError(error)
                previous=getattr(g,'document_excel_layout',False)
                g.document_excel_layout=True
                try:response=app.make_response(app.view_functions[_DOCUMENTS[code][2]](id))
                finally:g.document_excel_layout=previous
                if download:
                    response.headers['Cache-Control']='no-store'
                    return response
                try:
                    if response.status_code!=200 or 'spreadsheetml' not in response.mimetype:
                        raise ValueError('Excel打印文件生成失败，请检查所选模板后重试')
                    response.direct_passthrough=False
                    context['pages']=build_document_excel_preview(io.BytesIO(response.get_data()))
                finally:response.close()
        except ValueError as exc:
            context['error']=str(exc);status=400
        except HTTPException:
            raise
        except Exception:
            app.logger.exception('单据Excel打印预览失败：%s/%s',code,id)
            context['error']='打印预览生成失败，请检查模板后重试';status=500
        else:status=200
        result=app.make_response((render_template('document_excel_preview.html' if preview else 'document_print_options.html',**context),status))
        result.headers['Cache-Control']='no-store'
        return result
    return _view


def register_document_print_routes(app):
    """Register selection and filled-workbook preview for every existing Excel print type."""
    for code,(prefix,_,_) in _DOCUMENTS.items():
        for preview,download,suffix in ((False,False,'print_options'),(True,False,'print_preview'),(True,True,'print_file')):
            app.add_url_rule(f'/{prefix}/<int:id>/{suffix}',endpoint=f'document_{code}_{suffix}',
                             view_func=login_required(_make_document_print_view(app,code,preview,download)),methods=['GET'])
