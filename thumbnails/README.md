# Bulk Image Resizer

A Python batch-processing utility built with Pillow that resizes images while preserving aspect ratios, converts formats (`JPEG` or `PNG`) with configurable JPEG quality, optionally generates thumbnails, and outputs a CSV comparison report without modifying source files.

## Features

- **Aspect-Ratio-Safe Resizing:** Scales images to fit user-specified maximum width and/or height bounds while maintaining original proportions and EXIF orientation.
- **Format Conversion & JPEG Quality:** Converts supported images (`.jpg`, `.jpeg`, `.png`, `.webp`, `.bmp`, `.tiff`, `.tif`) to `JPEG` (with customizable quality `1–95` and transparency flattening) or `PNG`.
- **Optional Thumbnails:** Generates scaled thumbnail copies in a `thumbnails/` subfolder when enabled.
- **Non-Destructive Batching & CSV Report:** Leaves original files intact and exports `image_resize_report.csv` comparing original and processed dimensions and file sizes.

## Tech Stack

- **Python 3** (`pathlib`, `csv`)
- **Pillow** (`PIL`)

## Getting Started

### Prerequisites

- Python 3.9 or higher with `Pillow` installed.

### Installation & Usage

1. Clone or download the repository and install dependencies:

   ```bash
   git clone <your-repo-url>
   cd <your-repo-folder>
   pip install Pillow

2. Run:

    python bulk_image_resizer.py