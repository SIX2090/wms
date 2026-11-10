import io
from pathlib import Path

from PIL import Image
from werkzeug.datastructures import FileStorage

from app import app
from utils import migrate_legacy_material_images, save_upload_image


def make_png_bytes():
    stream = io.BytesIO()
    Image.new("RGB", (1, 1), "white").save(stream, format="PNG")
    return stream.getvalue()


def test_material_upload_uses_flask_static_root_by_default(tmp_path, monkeypatch):
    import importlib

    import config as config_module

    expected_root = Path(app.root_path) / "static" / "uploads"
    # BUG-2026-11-10-009：CI 容器显式导出 UPLOAD_FOLDER=/work/profile/uploads（非 root 可写目录），
    # 导入期常量因此不等于仓库默认值。这里清掉该变量后重新求值 Config，断言的是
    # 「未显式配置时默认落 flask static root」这条规则本身，而非 CI 的覆盖值。
    monkeypatch.delenv("UPLOAD_FOLDER", raising=False)
    try:
        reloaded = importlib.reload(config_module)
        assert Path(reloaded.Config.UPLOAD_FOLDER).resolve() == expected_root.resolve()
    finally:
        importlib.reload(config_module)

    static_root = tmp_path / "static"
    monkeypatch.setattr(app, "static_folder", str(static_root))
    monkeypatch.setitem(app.config, "UPLOAD_FOLDER", str(static_root / "uploads"))

    png_bytes = make_png_bytes()
    with app.app_context():
        file_storage = FileStorage(stream=io.BytesIO(png_bytes), filename="probe.png")
        image_path, error = save_upload_image(file_storage, subfolder="material_images")
        assert error is None
        saved_path = Path(app.config["UPLOAD_FOLDER"]) / "material_images" / image_path.rsplit("/", 1)[-1]
        try:
            with app.test_client().get(f"/static/{image_path}") as response:
                assert response.status_code == 200
                assert response.mimetype == "image/png"
                assert response.data == png_bytes
        finally:
            file_storage.close()
            saved_path.unlink(missing_ok=True)


def test_migrate_legacy_material_images(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    static_root = tmp_path / "static"
    monkeypatch.setattr(app, "static_folder", str(static_root))
    monkeypatch.setitem(app.config, "UPLOAD_FOLDER", str(static_root / "uploads"))
    filename = "legacy-material-image-test.png"
    png_bytes = make_png_bytes()
    legacy_path = Path.cwd() / "uploads" / "material_images" / filename
    static_path = static_root / "uploads" / "material_images" / filename
    legacy_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_path.write_bytes(png_bytes)
    try:
        with app.app_context():
            copied = migrate_legacy_material_images()
            assert copied == 1
            assert migrate_legacy_material_images() == 0
            with app.test_client().get(f"/static/uploads/material_images/{filename}") as response:
                assert response.status_code == 200
                assert response.mimetype == "image/png"
                assert response.data == png_bytes
    finally:
        legacy_path.unlink(missing_ok=True)
        static_path.unlink(missing_ok=True)
