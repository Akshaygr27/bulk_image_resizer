import csv
from pathlib import Path
from PIL import Image, ImageOps, UnidentifiedImageError


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}


def format_bytes(num_bytes: int) -> str:
    """Format byte counts cleanly (e.g., 245.5 KB, 1.2 MB)."""
    units = ["B", "KB", "MB", "GB"]
    size = float(num_bytes)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.2f} {unit}".rstrip("0").rstrip(".")
        size /= 1024
    return f"{num_bytes} B"


def parse_dimension(raw_val: str, label: str) -> int | None:
    """Parse a positive integer dimension, or return None if left blank."""
    cleaned = raw_val.strip()
    if not cleaned:
        return None
    try:
        val = int(cleaned)
        if val <= 0:
            print(f"Warning: {label} must be positive. Ignoring '{cleaned}'.")
            return None
        return val
    except ValueError:
        print(f"Warning: Invalid {label} '{cleaned}'. Ignoring.")
        return None


def compute_aspect_fit_size(orig_w: int, orig_h: int, max_w: int | None, max_h: int | None) -> tuple[int, int]:
    """
    Calculate target (width, height) that preserves the original aspect ratio
    while fitting within max_w and/or max_h.
    """
    if max_w is None and max_h is None:
        return orig_w, orig_h

    if max_w is not None and max_h is not None:
        scale = min(max_w / orig_w, max_h / orig_h)
    elif max_w is not None:
        scale = max_w / orig_w
    else:
        scale = max_h / orig_h  # type: ignore[operator]

    new_w = max(1, round(orig_w * scale))
    new_h = max(1, round(orig_h * scale))
    return new_w, new_h


def prepare_image_for_format(img: Image.Image, target_format: str) -> Image.Image:
    """Apply EXIF orientation and convert color mode safely for JPEG or PNG."""
    oriented = ImageOps.exif_transpose(img)

    if target_format == "JPEG":
        if oriented.mode in ("RGBA", "LA", "P"):
            # Flatten transparency onto a clean white background for JPEG
            alpha_img = oriented.convert("RGBA")
            background = Image.new("RGBA", alpha_img.size, (255, 255, 255, 255))
            composited = Image.alpha_composite(background, alpha_img)
            return composited.convert("RGB")
        return oriented.convert("RGB")

    # PNG supports RGB, RGBA, L, LA, P
    if oriented.mode not in ("RGB", "RGBA", "L", "LA", "P"):
        return oriented.convert("RGBA")
    return oriented


def save_resized_image(
    img: Image.Image,
    out_path: Path,
    target_format: str,
    jpeg_quality: int,
) -> None:
    """Save image to disk using appropriate format options."""
    if target_format == "JPEG":
        img.save(
            out_path,
            format="JPEG",
            quality=jpeg_quality,
            optimize=True,
        )
    else:
        img.save(
            out_path,
            format="PNG",
            optimize=True,
        )


def write_report_csv(records: list[dict], report_path: Path) -> None:
    """Write a CSV comparing original and processed image dimensions and file sizes."""
    fieldnames = [
        "Source File",
        "Output File",
        "Thumbnail File",
        "Format",
        "Original Dimensions",
        "Resized Dimensions",
        "Thumbnail Dimensions",
        "Original Size (Bytes)",
        "Original Size",
        "Processed Size (Bytes)",
        "Processed Size",
        "Size Change (%)",
        "Thumbnail Size",
    ]
    with report_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def process_images(
    input_dir: Path,
    output_dir: Path,
    max_width: int | None,
    max_height: int | None,
    output_format: str,
    jpeg_quality: int,
    make_thumbnails: bool,
    thumb_max_size: int = 200,
) -> None:
    """Batch-process supported images in input_dir and write results + CSV report."""
    output_dir.mkdir(parents=True, exist_ok=True)
    thumb_dir = output_dir / "thumbnails"
    if make_thumbnails:
        thumb_dir.mkdir(parents=True, exist_ok=True)

    ext_map = {"JPEG": ".jpg", "PNG": ".png"}
    target_ext = ext_map[output_format]

    image_files = sorted(
        [
            p
            for p in input_dir.iterdir()
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
        ]
    )

    if not image_files:
        print(f"No supported image files found in '{input_dir}'.")
        return

    report_rows: list[dict] = []
    processed_count = 0
    failed_count = 0

    for src_path in image_files:
        dest_name = (
            f"{src_path.stem}_resized{target_ext}"
            if src_path.parent.resolve() == output_dir.resolve()
            else f"{src_path.stem}{target_ext}"
        )
        dest_path = output_dir / dest_name

        try:
            orig_size_bytes = src_path.stat().st_size
            with Image.open(src_path) as raw_img:
                raw_img.load()
                orig_w, orig_h = raw_img.size

                # Fixed: use parameter name `max_height` instead of `max_h`
                target_w, target_h = compute_aspect_fit_size(orig_w, orig_h, max_width, max_height)
                prepared = prepare_image_for_format(raw_img, output_format)
                resized_img = prepared.resize((target_w, target_h), Image.Resampling.LANCZOS)
                save_resized_image(resized_img, dest_path, output_format, jpeg_quality)

                thumb_name = ""
                thumb_dims_str = "N/A"
                thumb_size_str = "N/A"

                if make_thumbnails:
                    thumb_img = resized_img.copy()
                    thumb_img.thumbnail((thumb_max_size, thumb_max_size), Image.Resampling.LANCZOS)
                    thumb_path = thumb_dir / f"{src_path.stem}_thumb{target_ext}"
                    save_resized_image(thumb_img, thumb_path, output_format, jpeg_quality)
                    thumb_name = thumb_path.name
                    thumb_dims_str = f"{thumb_img.width}x{thumb_img.height}"
                    thumb_size_str = format_bytes(thumb_path.stat().st_size)

            new_size_bytes = dest_path.stat().st_size
            pct_change = (
                ((new_size_bytes - orig_size_bytes) / orig_size_bytes * 100)
                if orig_size_bytes > 0
                else 0.0
            )

            report_rows.append(
                {
                    "Source File": src_path.name,
                    "Output File": dest_path.name,
                    "Thumbnail File": thumb_name,
                    "Format": output_format,
                    "Original Dimensions": f"{orig_w}x{orig_h}",
                    "Resized Dimensions": f"{target_w}x{target_h}",
                    "Thumbnail Dimensions": thumb_dims_str,
                    "Original Size (Bytes)": orig_size_bytes,
                    "Original Size": format_bytes(orig_size_bytes),
                    "Processed Size (Bytes)": new_size_bytes,
                    "Processed Size": format_bytes(new_size_bytes),
                    "Size Change (%)": f"{pct_change:+.1f}%",
                    "Thumbnail Size": thumb_size_str,
                }
            )
            processed_count += 1
            print(
                f"Processed {src_path.name}: {orig_w}x{orig_h} ({format_bytes(orig_size_bytes)}) "
                f"-> {target_w}x{target_h} ({format_bytes(new_size_bytes)}) [{pct_change:+.1f}%]"
            )

        except (UnidentifiedImageError, OSError, ValueError) as exc:
            failed_count += 1
            print(f"Error processing '{src_path.name}': {exc}")

    report_path = output_dir / "image_resize_report.csv"
    if report_rows:
        write_report_csv(report_rows, report_path)

    print("\n--- Batch Resize Summary ---")
    print(f"Images processed : {processed_count}")
    print(f"Images failed    : {failed_count}")
    if report_rows:
        print(f"Report saved to  : {report_path}")


def main() -> None:
    in_str = input("Enter input folder path (e.g. ./product_photos): ").strip().strip('"').strip("'")
    out_str = input("Enter output folder path (e.g. ./resized_photos): ").strip().strip('"').strip("'")

    input_dir = Path(in_str).expanduser()
    output_dir = Path(out_str).expanduser()

    if not input_dir.exists() or not input_dir.is_dir():
        print(f"Error: Input folder '{input_dir}' does not exist.")
        return

    max_w = parse_dimension(input("Max target width in px (press Enter for no width cap): "), "width")
    max_h = parse_dimension(input("Max target height in px (press Enter for no height cap): "), "height")

    fmt_choice = input("Output format (JPEG / PNG, default JPEG): ").strip().upper()
    output_format = "PNG" if fmt_choice == "PNG" else "JPEG"

    jpeg_quality = 85
    if output_format == "JPEG":
        q_raw = input("JPEG quality (1-95, default 85): ").strip()
        if q_raw:
            try:
                q_val = int(q_raw)
                if 1 <= q_val <= 95:
                    jpeg_quality = q_val
                else:
                    print("Quality out of range (1-95). Using default 85.")
            except ValueError:
                print("Invalid quality value. Using default 85.")

    thumb_choice = input("Generate thumbnails too? (y/n, default n): ").strip().lower()
    make_thumbnails = thumb_choice == "y"
    thumb_max = 200
    if make_thumbnails:
        t_raw = input("Max thumbnail dimension in px (default 200): ").strip()
        parsed_thumb = parse_dimension(t_raw, "thumbnail size")
        if parsed_thumb is not None:
            thumb_max = parsed_thumb

    process_images(
        input_dir=input_dir,
        output_dir=output_dir,
        max_width=max_w,
        max_height=max_h,
        output_format=output_format,
        jpeg_quality=jpeg_quality,
        make_thumbnails=make_thumbnails,
        thumb_max_size=thumb_max,
    )


if __name__ == "__main__":
    main()