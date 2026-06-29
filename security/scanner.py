import logging
from typing import List, Tuple, Set, Any
import pypdf

logger = logging.getLogger("security_gateway")

DANGEROUS_KEYS: Set[str] = {
    "/JS",
    "/JavaScript",
    "/OpenAction",
    "/AA",
    "/Launch",
    "/EmbeddedFiles",
}


def resolve_obj(obj: Any) -> Any:
    """Helper to resolve indirect objects in pypdf."""
    if hasattr(obj, "get_object"):
        try:
            return obj.get_object()
        except Exception:
            return obj
    return obj


def inspect_dict(d: Any, path: str, findings: List[str]) -> None:
    """Recursively inspect dictionary objects for dangerous keys."""
    d_resolved = resolve_obj(d)
    if not isinstance(d_resolved, dict):
        return

    for key in d_resolved.keys():
        key_str = str(key)
        if key_str in DANGEROUS_KEYS:
            msg = f"Suspicious element detected in {path}: {key_str}"
            if msg not in findings:
                findings.append(msg)

        val = resolve_obj(d_resolved.get(key))
        if isinstance(val, dict):
            # Recurse into sub-dictionaries like /Names, /AA, /A
            inspect_dict(val, f"{path} -> {key_str}", findings)
        elif isinstance(val, list):
            for idx, item in enumerate(val):
                item_res = resolve_obj(item)
                if isinstance(item_res, dict):
                    inspect_dict(item_res, f"{path} -> {key_str}[{idx}]", findings)


def scan_pdf(file_path: str) -> Tuple[bool, List[str]]:
    """
    Performs static analysis on a PDF file using pypdf to identify dangerous objects,
    actions, embedded files, or corrupted structures.

    Returns:
        (is_clean: bool, findings: List[str])
    """
    findings: List[str] = []

    try:
        reader = pypdf.PdfReader(file_path)
    except Exception as e:
        logger.warning(f"Failed to parse PDF file: {str(e)}")
        return False, [f"Malformed or corrupted PDF structure: {str(e)}"]

    # Check encryption / password protection
    if reader.is_encrypted:
        return False, ["PDF is encrypted or password-protected"]

    try:
        num_pages = len(reader.pages)
        if num_pages == 0:
            return False, ["PDF contains 0 pages or invalid structure"]
    except Exception as e:
        return False, [f"Failed to read PDF pages: {str(e)}"]

    # 1. Inspect Catalog (Root dictionary)
    try:
        catalog = resolve_obj(reader.trailer.get("/Root"))
        if catalog:
            inspect_dict(catalog, "Catalog", findings)
    except Exception as e:
        findings.append(f"Error inspecting PDF Catalog: {str(e)}")

    # 2. Inspect Pages, Page Actions, and Annotations
    try:
        for index, page in enumerate(reader.pages):
            page_obj = resolve_obj(page)
            if page_obj:
                inspect_dict(page_obj, f"Page {index + 1}", findings)
    except Exception as e:
        findings.append(f"Error inspecting PDF Pages: {str(e)}")

    # 3. Inspect Indirect Objects across the entire PDF
    try:
        if hasattr(reader, "objects"):
            for obj_key, obj in reader.objects.items():
                resolved = resolve_obj(obj)
                if isinstance(resolved, dict):
                    for key in resolved.keys():
                        if str(key) in DANGEROUS_KEYS:
                            msg = f"Suspicious element detected in object {obj_key}: {key}"
                            if msg not in findings:
                                findings.append(msg)
    except Exception as e:
        logger.debug(f"Error iterating indirect objects: {e}")

    is_clean = len(findings) == 0
    return is_clean, findings
