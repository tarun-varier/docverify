import re
import os
from pypdf import PdfReader

class PDFSandboxAnalyzer:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.file_size = os.path.getsize(file_path)
        self.raw_content = b""
        self.sanitized_text = ""
        
        # Read raw content for regex scanning
        try:
            with open(file_path, "rb") as f:
                self.raw_content = f.read()
            self.sanitized_text = self._sanitize_pdf_names(self.raw_content)
        except Exception as e:
            self.sanitized_text = ""

    def _sanitize_pdf_names(self, raw_content: bytes) -> str:
        """
        Decodes PDF hex name escapes (e.g. /Java#53cript -> /JavaScript)
        and converts bytes to a latin-1 string for regex matching.
        """
        try:
            # latin-1 maps bytes 1-to-1 to characters, avoiding encoding crashes
            text = raw_content.decode('latin-1', errors='ignore')
            
            def replace_hex(match):
                hex_val = match.group(1)
                try:
                    return chr(int(hex_val, 16))
                except Exception:
                    return match.group(0)
            
            # Replaces '#53' with 'S' etc.
            return re.sub(r'#([0-9a-fA-F]{2})', replace_hex, text)
        except Exception:
            return ""

    def scan(self) -> dict:
        """
        Runs the full dual-layer local PDF scan.
        """
        report = {
            "file_name": os.path.basename(self.file_path),
            "file_size": self.file_size,
            "pages": 0,
            "metadata": {},
            "threat_score": 0,
            "risk_level": "Safe", # Safe, Suspicious, Dangerous
            "findings": [],
            "keywords_detected": {},
            "extracted_links": [],
            "structure": {
                "has_javascript": False,
                "has_openaction": False,
                "has_launch": False,
                "has_embedded_file": False,
                "has_xfa": False
            }
        }

        # Step 1: Parse Structure with PyPDF
        pypdf_success = False
        try:
            reader = PdfReader(self.file_path)
            report["pages"] = len(reader.pages)
            pypdf_success = True
            
            # Extract metadata
            if reader.metadata:
                for key, val in reader.metadata.items():
                    # Clean up the key prefix (like '/Title' -> 'Title')
                    clean_key = key.lstrip('/')
                    if isinstance(val, bytes):
                        val = val.decode('utf-8', errors='ignore')
                    report["metadata"][clean_key] = str(val)

            # Extract links structuredly
            for page_num, page in enumerate(reader.pages):
                annots = page.get("/Annots")
                if annots:
                    resolved_annots = annots.get_object() if hasattr(annots, "get_object") else annots
                    if isinstance(resolved_annots, list):
                        for annot in resolved_annots:
                            annot_obj = annot.get_object() if hasattr(annot, "get_object") else annot
                            if not isinstance(annot_obj, dict):
                                continue
                            if annot_obj.get("/Subtype") == "/Link":
                                action = annot_obj.get("/A")
                                if action:
                                    action_obj = action.get_object() if hasattr(action, "get_object") else action
                                    if isinstance(action_obj, dict) and action_obj.get("/S") == "/URI":
                                        uri = action_obj.get("/URI")
                                        if uri:
                                            uri_val = uri.get_object() if hasattr(uri, "get_object") else uri
                                            if isinstance(uri_val, bytes):
                                                uri_str = uri_val.decode('utf-8', errors='ignore')
                                            else:
                                                uri_str = str(uri_val)
                                            
                                            report["extracted_links"].append({
                                                "page": page_num + 1,
                                                "url": uri_str
                                            })
        except Exception as e:
            # If pypdf fails to parse (e.g. malformed or obfuscated PDF), we rely entirely on regex
            report["findings"].append({
                "type": "parse_error",
                "severity": "warning",
                "message": f"Structured PDF parser encountered an error ({str(e)}). Relying on raw binary analysis."
            })

        # Step 2: Keyword Scan (Raw Bytes Regex)
        # Define keywords of interest
        keywords = {
            "/JavaScript": r'/JavaScript',
            "/JS": r'/JS',
            "/OpenAction": r'/OpenAction',
            "/AA": r'/AA',
            "/Launch": r'/Launch',
            "/EmbeddedFile": r'/EmbeddedFile',
            "/XFA": r'/XFA',
            "/SubmitForm": r'/SubmitForm',
            "/RichMedia": r'/RichMedia',
            "/ObjStm": r'/ObjStm'
        }

        keyword_counts = {}
        for key, pattern in keywords.items():
            matches = re.findall(pattern, self.sanitized_text, re.IGNORECASE)
            count = len(matches)
            if count > 0:
                keyword_counts[key] = count

        report["keywords_detected"] = keyword_counts

        # Fallback URL extraction using regex in raw content
        try:
            # Matches /URI (http...)
            raw_uris = re.findall(r'/URI\s*\(([^)]+)\)', self.sanitized_text)
            for uri in raw_uris:
                # Deduplicate with already extracted links
                if not any(link["url"] == uri for link in report["extracted_links"]):
                    report["extracted_links"].append({
                        "page": "Unknown (Raw scan)",
                        "url": uri
                    })
        except Exception:
            pass

        # Step 3: Threat Scoring Heuristics
        score = 0
        findings = report["findings"]

        # Track flags for structure
        has_js = ("/JavaScript" in keyword_counts) or ("/JS" in keyword_counts)
        has_openaction = ("/OpenAction" in keyword_counts) or ("/AA" in keyword_counts)
        has_launch = "/Launch" in keyword_counts
        has_embedded = "/EmbeddedFile" in keyword_counts
        has_xfa = "/XFA" in keyword_counts

        report["structure"] = {
            "has_javascript": has_js,
            "has_openaction": has_openaction,
            "has_launch": has_launch,
            "has_embedded_file": has_embedded,
            "has_xfa": has_xfa
        }

        # Evaluate Launch
        if has_launch:
            score += 50
            findings.append({
                "type": "launch_command",
                "severity": "danger",
                "message": f"External program launching (/Launch) detected {keyword_counts.get('/Launch', 1)} times. This is a severe threat as it can execute arbitrary local shell commands."
            })

        # Evaluate JavaScript
        if has_js:
            js_count = keyword_counts.get("/JavaScript", 0) + keyword_counts.get("/JS", 0)
            score += 40
            findings.append({
                "type": "javascript",
                "severity": "warning",
                "message": f"Embedded JavaScript code detected {js_count} times. Scripts can be abused to exploit PDF viewer vulnerabilities or run unauthorized operations."
            })

        # Evaluate OpenAction / AA
        if has_openaction:
            oa_count = keyword_counts.get("/OpenAction", 0) + keyword_counts.get("/AA", 0)
            score += 40
            findings.append({
                "type": "auto_execute",
                "severity": "danger",
                "message": f"Automatic actions on open (/OpenAction or /AA) detected {oa_count} times. This is a high-risk feature that runs commands/scripts automatically when the PDF is opened."
            })

        # Evaluate EmbeddedFile
        if has_embedded:
            emb_count = keyword_counts.get("/EmbeddedFile", 0)
            score += 30
            findings.append({
                "type": "embedded_file",
                "severity": "warning",
                "message": f"Embedded file attachment(s) detected {emb_count} times. Malicious PDFs often embed hidden malware payloads (like .exe or .scr) to drop on the system."
            })

        # Evaluate XFA
        if has_xfa:
            score += 15
            findings.append({
                "type": "xfa_form",
                "severity": "info",
                "message": "XML Forms Architecture (/XFA) detected. Complex dynamic forms can contain scripts and are deprecated in modern secure PDF environments."
            })

        # Evaluate SubmitForm
        if "/SubmitForm" in keyword_counts:
            score += 15
            findings.append({
                "type": "submit_form",
                "severity": "warning",
                "message": "Form data submission hook (/SubmitForm) detected. This action allows the PDF to automatically exfiltrate filled form data to a remote URL."
            })

        # Evaluate RichMedia
        if "/RichMedia" in keyword_counts:
            score += 15
            findings.append({
                "type": "rich_media",
                "severity": "info",
                "message": "Embedded rich media (/RichMedia) detected. This element can execute third-party plugins (like Flash) which are highly prone to security exploits."
            })

        # Check for Obfuscated names in raw scan
        # If we see original names like '#53' but we didn't see standard tags in structure,
        # or if we detect hexadecimal obfuscations:
        hex_esc_pattern = r'/[a-zA-Z]*#[0-9a-fA-F]{2}[a-zA-Z]*'
        hex_escapes = re.findall(hex_esc_pattern, self.raw_content.decode('latin-1', errors='ignore'))
        if len(hex_escapes) > 0:
            score += 20
            findings.append({
                "type": "obfuscation",
                "severity": "warning",
                "message": f"Detected {len(hex_escapes)} obfuscated dictionary keys (using hexadecimal character encoding like '#53'). This is a common evasion technique to bypass security parsers."
            })

        # Cap the max threat score at 100
        report["threat_score"] = min(score, 100)

        # Categorize threat level
        if report["threat_score"] == 0:
            report["risk_level"] = "Safe"
        elif report["threat_score"] <= 20:
            report["risk_level"] = "Low Risk"
        elif report["threat_score"] <= 55:
            report["risk_level"] = "Suspicious"
        else:
            report["risk_level"] = "Dangerous"

        return report
