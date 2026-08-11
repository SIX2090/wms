import io
from pathlib import Path

from PIL import Image
from werkzeug.datastructures import FileStorage

from app import app
from config import Config
from utils import migrate_legacy_material_images, save_upload_image


def make_png_bytes():
    stream = io.BytesIO()
    Image.new("RGB", (1, 1), "white").save(stream, format="PNG")
    return stream.getvalue()


def test_material_upload_uses_flask_static_root_by_default():
    expected_root = Path(app.root_path) / "static" / "uploads"
    assert Path(Config.UPLOAD_FOLDER).resolve() == expected_root.resolve()

    png_bytes = make_png_bytes()
    with app.app_context():
        file_storage = FileStorage(stream=io.BytesIO(png_bytes), filename="probe.png")
        image_path, error = save_upload_image(file_storage, subfolder="material_images")
        assert error is None
        saved_path = Path(app.config["UPLOAD_FOLDER"]) / "material_images" / image_path.rsplit("/", 1)[-1]
        try:
            response = app.test_client().get(f"/static/{image_path}")
            assert response.status_code == 200
            assert response.mimetype == "image/png"
            assert response.data == png_bytes
        finally:
            saved_path.unlink(missing_ok=True)


def test_migrate_legacy_material_images():
    filename = "legacy-material-image-test.png"
    png_bytes = make_png_bytes()
    legacy_path = Path.cwd() / "uploads" / "material_images" / filename
    static_path = Path(app.root_path) / "static" / "uploads" / "material_images" / filename
    legacy_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_path.write_bytes(png_bytes)
    try:
        with app.app_context():
            copied = migrate_legacy_material_images()
            response = app.test_client().get(f"/static/uploads/material_images/{filename}")
            assert copied >= 1
            assert response.status_code == 200
            assert response.mimetype == "image/png"
            assert response.data == png_bytes
    finally:
        legacy_path.unlink(missing_ok=True)
        static_path.unlink(missing_ok=True)
