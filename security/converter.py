import os
import logging
from typing import List
from pdf2image import convert_from_path
from pdf2image.exceptions import PDFPageCountError, PDFSyntaxError, PDFInfoNotInstalledError

logger = logging.getLogger("security_gateway")


def convert_pdf_to_pngs(pdf_path: str, output_dir: str, dpi: int = 200, timeout: int = 60) -> List[str]:
    """
    Converts each page of a PDF into a high-quality PNG image inside output_dir (Content Disarm and Reconstruction).
    Deletes the original PDF immediately after successful conversion.

    Returns:
        List of absolute file paths to generated PNG images.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found at {pdf_path}")

    os.makedirs(output_dir, exist_ok=True)
    png_paths: List[str] = []

    # Detect poppler path on macOS if not in default PATH
    poppler_path = None
    if os.path.exists("/opt/homebrew/bin/pdfinfo"):
        poppler_path = "/opt/homebrew/bin"
    elif os.path.exists("/usr/local/bin/pdfinfo"):
        poppler_path = "/usr/local/bin"

    try:
        # Convert PDF pages to PIL images using poppler / pdf2image
        images = convert_from_path(
            pdf_path,
            dpi=dpi,
            fmt="png",
            timeout=timeout,
            poppler_path=poppler_path
        )

        for index, image in enumerate(images):
            png_filename = f"page_{index + 1}.png"
            png_path = os.path.join(output_dir, png_filename)
            image.save(png_path, "PNG")
            png_paths.append(png_path)

        logger.info(f"Successfully converted PDF to {len(png_paths)} PNG page images.")

    except PDFPageCountError as e:
        raise ValueError(f"Unable to determine PDF page count: {str(e)}")
    except PDFSyntaxError as e:
        raise ValueError(f"PDF syntax error during rendering: {str(e)}")
    except PDFInfoNotInstalledError:
        raise RuntimeError("poppler-utils is not installed or poppler binaries are not in PATH.")
    except Exception as e:
        raise RuntimeError(f"Error converting PDF to images: {str(e)}")
    finally:
        # Delete original PDF immediately after conversion or on attempt
        if os.path.exists(pdf_path):
            try:
                os.remove(pdf_path)
                logger.info(f"Original PDF deleted immediately post-conversion: {pdf_path}")
            except Exception as delete_err:
                logger.error(f"Failed to delete original PDF {pdf_path}: {delete_err}")

    return png_paths
