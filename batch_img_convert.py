#!/usr/bin/env python3
"""
Batch convert PNG/JPG to WebP and generate responsive sizes.

Usage:
  python batch_img_convert.py --src static/img --sizes 480 800 1200 --quality 80

- Scans --src recursively for .png, .jpg, .jpeg (and .webp if you pass --include-webp).
- For each image, generates WebP variants (e.g., image-480.webp, image-800.webp).
- Preserves aspect ratio; resizes by width.
- Skips generating a size if that output already exists (unless --overwrite).
- By default writes next to the source file; use --out to change destination.

Requirements:
  pip install pillow
"""

import argparse
from pathlib import Path
from PIL import Image

def convert_one(img_path: Path, out_dir: Path, widths, quality=80, overwrite=False):
    try:
        with Image.open(img_path) as im:
            im.load()
            # Ensure RGB for JPEG/PNG with alpha
            if im.mode in ("RGBA", "P"):
                im = im.convert("RGB")
            for w in widths:
                out_name = f"{img_path.stem}-{w}.webp"
                out_path = out_dir / out_name
                if out_path.exists() and not overwrite:
                    print(f"✓ Skip (exists): {out_path}")
                    continue
                ratio = w / im.width
                new_h = max(1, int(im.height * ratio))
                resized = im.resize((w, new_h), Image.LANCZOS)
                resized.save(out_path, "WEBP", quality=quality, method=6)
                print(f"→ Saved: {out_path}")
    except Exception as e:
        print(f"✗ Error with {img_path}: {e}")

def main():
    parser = argparse.ArgumentParser(description="Batch convert images to WebP sized variants.")
    parser.add_argument("--src", type=str, required=True, help="Source directory (e.g., static/img)")
    parser.add_argument("--out", type=str, default=None, help="Output directory (defaults to same as source files)")
    parser.add_argument("--sizes", type=int, nargs="+", default=[480, 800, 1200], help="Widths to generate")
    parser.add_argument("--quality", type=int, default=80, help="WebP quality (0-100)")
    parser.add_argument("--include-webp", action="store_true", help="Also re-encode .webp originals")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing outputs")
    args = parser.parse_args()

    exts = [".png", ".jpg", ".jpeg"]
    if args.include_webp:
        exts.append(".webp")

    src = Path(args.src)
    if not src.exists():
        raise SystemExit(f"Source not found: {src}")

    out_dir = Path(args.out) if args.out else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)

    files = [p for p in src.rglob("*") if p.suffix.lower() in exts]
    if not files:
        print("No images found.")
        return

    print(f"Found {len(files)} images. Converting to sizes: {args.sizes} (quality={args.quality})")
    for img in files:
        target_dir = out_dir if out_dir else img.parent
        convert_one(img, target_dir, args.sizes, quality=args.quality, overwrite=args.overwrite)

if __name__ == "__main__":
    main()
