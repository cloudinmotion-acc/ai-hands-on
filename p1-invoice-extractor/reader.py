import base64
from pathlib import Path
import pymupdf

def file_to_images(file_path: str) -> list[str]:
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return _pdf_to_base64(path)
    elif suffix in [".jpg", ".jpeg", ".png"]:
        return _image_to_base64(path)
    else:
        raise ValueError(f"Unsupported file type: {suffix}")


def _pdf_to_base64(path: Path) -> list[str]:
    doc = pymupdf.open(str(path))
    images = []
    for page in doc:
        pix = page.get_pixmap(dpi=150)  # increase dpi for better quality
        img_bytes = pix.tobytes("jpeg")  # convert to JPEG bytes
        images.append(base64.b64encode(img_bytes).decode("utf-8"))  # encode to base64 and decode to string
    return images

def _image_to_base64(path: Path) -> list[str]:
    with open(path, "rb") as f:
        img_bytes = f.read()
    return [base64.b64encode(img_bytes).decode("utf-8")]  # encode to base64 and decode to string