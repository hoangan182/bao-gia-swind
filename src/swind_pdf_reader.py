# -*- coding: utf-8 -*-
"""
SWIND PDF READER: Chuyển đổi file PDF thành ảnh PNG để chạy qua luồng OCR (Agent 01B).

Khi nhận diện file đầu vào là PDF:
1. Chuyển từng trang PDF thành ảnh PNG (DPI cao, đảm bảo chất lượng OCR)
2. Lưu ảnh vào thư mục tạm trong 'input picture/'
3. Trả về danh sách đường dẫn ảnh để Agent 01B xử lý tiếp

Yêu cầu: pypdfium2 (đã cài sẵn cùng pdfplumber)
"""

import os
import sys
import shutil
import tempfile
from datetime import datetime


def is_pdf_file(filepath):
    """Kiểm tra file có phải PDF không (theo extension và magic bytes)."""
    if not filepath or not os.path.isfile(filepath):
        return False
    if filepath.lower().endswith('.pdf'):
        return True
    try:
        with open(filepath, 'rb') as f:
            header = f.read(5)
            return header == b'%PDF-'
    except (IOError, OSError):
        return False


def pdf_to_images(pdf_path, output_dir=None, scale=3, prefix=None):
    """
    Chuyển đổi file PDF thành danh sách ảnh PNG.
    """
    result = {
        "status": "ERROR",
        "image_paths": [],
        "output_dir": None,
        "page_count": 0,
        "error": None
    }

    if not os.path.isfile(pdf_path):
        result["error"] = f"Không tìm thấy file PDF: {pdf_path}"
        return result

    if not is_pdf_file(pdf_path):
        result["error"] = f"File không phải định dạng PDF: {pdf_path}"
        return result

    try:
        import pypdfium2 as pdfium
    except ImportError:
        result["error"] = (
            "Thiếu thư viện pypdfium2. Cài đặt bằng lệnh:\n"
            "  ./venv/bin/pip install pypdfium2"
        )
        return result

    if output_dir is None:
        ws_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        output_dir = os.path.join(ws_root, "input picture")

    os.makedirs(output_dir, exist_ok=True)
    result["output_dir"] = output_dir

    if prefix is None:
        prefix = os.path.splitext(os.path.basename(pdf_path))[0]
    prefix = prefix.replace("/", "_").replace("\\", "_")

    try:
        pdf = pdfium.PdfDocument(pdf_path)
        n_pages = len(pdf)
        result["page_count"] = n_pages

        print(f"\n[PDF Reader] Đang chuyển đổi PDF → ảnh PNG...")
        print(f"  • File PDF: {os.path.basename(pdf_path)}")
        print(f"  • Số trang: {n_pages}")
        print(f"  • Scale: {scale}x (~{int(72 * scale)} DPI)")
        print(f"  • Thư mục ảnh: {output_dir}")

        image_paths = []
        for i in range(n_pages):
            page = pdf[i]
            bitmap = page.render(scale=scale)
            img = bitmap.to_pil()

            if n_pages == 1:
                img_filename = f"{prefix}.png"
            else:
                img_filename = f"{prefix}_page_{i + 1:02d}.png"

            img_path = os.path.join(output_dir, img_filename)
            img.save(img_path, "PNG")
            image_paths.append(img_path)

            w, h = img.size
            print(f"  ✓ Trang {i + 1}/{n_pages}: {img_filename} ({w}x{h}px)")

        pdf.close()

        result["status"] = "OK"
        result["image_paths"] = image_paths
        print(f"[PDF Reader] Hoàn tất! {n_pages} trang → {n_pages} ảnh PNG.\n")

    except Exception as e:
        result["error"] = f"Lỗi khi render PDF: {e}"
        print(f"[PDF Reader] LỖI: {e}")

    return result


def pdf_to_excel_via_ocr(pdf_path, workspace_dir=None, scale=3, split_per_image=True):
    """
    Pipeline đầy đủ: PDF → Ảnh PNG → OCR (Agent 01B) → Excel BOQ.
    """
    if workspace_dir is None:
        workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    img_dir = os.path.join(workspace_dir, "input picture")
    pdf_result = pdf_to_images(pdf_path, output_dir=img_dir, scale=scale)

    if pdf_result["status"] != "OK":
        return {
            "status": "ERROR",
            "excel_paths": [],
            "image_paths": [],
            "error": pdf_result["error"]
        }

    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from agent_01b_image_boq_reader import Agent01B_ImageBOQReader

        reader = Agent01B_ImageBOQReader(workspace_dir)

        tmp_img_dir = os.path.join(img_dir, f"_pdf_tmp_{os.getpid()}")
        os.makedirs(tmp_img_dir, exist_ok=True)

        try:
            for img_path in pdf_result["image_paths"]:
                dst = os.path.join(tmp_img_dir, os.path.basename(img_path))
                shutil.copy2(img_path, dst)

            ocr_result = reader.process_image_folder(
                image_dir=tmp_img_dir,
                split_per_image=split_per_image
            )

            return {
                "status": ocr_result.get("status", "OK"),
                "excel_paths": ocr_result.get("excel_paths", []),
                "image_paths": pdf_result["image_paths"],
                "error": None
            }
        finally:
            shutil.rmtree(tmp_img_dir, ignore_errors=True)

    except Exception as e:
        return {
            "status": "ERROR",
            "excel_paths": [],
            "image_paths": pdf_result["image_paths"],
            "error": f"Lỗi OCR Agent 01B: {e}"
        }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Swind PDF Reader - Chuyển PDF thành ảnh/Excel BOQ")
    parser.add_argument("pdf_file", help="Đường dẫn file PDF đầu vào")
    parser.add_argument("--scale", type=int, default=3, help="Hệ số phóng đại render (mặc định: 3)")
    parser.add_argument("--images-only", action="store_true",
                        help="Chỉ chuyển PDF → ảnh PNG (không chạy OCR)")
    parser.add_argument("--output-dir", default=None,
                        help="Thư mục lưu ảnh (mặc định: 'input picture/')")

    args = parser.parse_args()

    pdf_path = args.pdf_file
    if not os.path.isabs(pdf_path):
        ws_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        pdf_path = os.path.join(ws_root, pdf_path)

    if args.images_only:
        result = pdf_to_images(pdf_path, output_dir=args.output_dir, scale=args.scale)
    else:
        result = pdf_to_excel_via_ocr(pdf_path, scale=args.scale)

    if result["status"] == "OK":
        if "excel_paths" in result and result["excel_paths"]:
            print("\n📦 File Excel BOQ đã tạo:")
            for p in result["excel_paths"]:
                print(f"  • {p}")
        if "image_paths" in result:
            print(f"\n🖼️  Ảnh PNG: {len(result['image_paths'])} file")
    else:
        print(f"\n❌ Lỗi: {result.get('error', 'Unknown')}")
        sys.exit(1)
