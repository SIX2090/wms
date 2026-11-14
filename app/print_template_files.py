"""打印模板文件回收；只处理当前静态目录中已失去所有模板引用的文件。"""
from pathlib import Path

from flask import current_app


def _discard_unreferenced_template_file(template_path, static_folder):
    from models.print import ExcelPrintTemplate, InOrderPrintTemplate, OutOrderPrintTemplate
    from print_fill import template_file_abspath

    try:
        if not template_path:
            return
        directory = (Path(static_folder) / 'uploads' / 'print_templates').resolve()
        raw = Path(template_file_abspath(template_path, static_folder))
        target = raw.resolve()
        if (raw.is_symlink() or target.parent != directory
                or target.name.lower().startswith('builtin_')
                or target.suffix.lower() not in ('.xlsx', '.xls')
                or not target.is_file() or target.stat().st_nlink != 1):
            return
        for model in (InOrderPrintTemplate, OutOrderPrintTemplate, ExcelPrintTemplate):
            for (reference,) in model.query.with_entities(model.excel_template_path).all():
                if reference and Path(template_file_abspath(reference, static_folder)).resolve() == target:
                    return
        target.unlink()
    except Exception:
        # 数据库已提交的结果不因文件占用/查询失败变成失败；保留文件供后续核查。
        current_app.logger.warning('打印模板文件暂未回收：%s', template_path, exc_info=True)
