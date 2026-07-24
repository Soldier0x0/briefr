"""TM-6: standard, published framework reference data.

This is framework *definition* data (which CWEs belong to which OWASP
category, which CAPEC patterns relate to which CWE, which STRIDE class a
weakness falls under) -- not judgment about BRIEFR's own architecture, so it
lives here as versioned code rather than in the curated corpus (which the
loader validates against BRIEFR-record schema). Sources are cited per block.

Coverage is intentionally weighted toward the CWE classes that actually
dominate real CVE data (the CWE Top 25 plus the common web/injection
weaknesses). A CWE that appears in the corpus but is absent from a mapping
here still counts in the CWE workspace (its raw id is shown) and is reported
in an explicit "unmapped" bucket by the OWASP/CAPEC/STRIDE aggregators -- the
totals never silently drop weaknesses we could not classify.

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

# ── CWE human names ───────────────────────────────────────────────────────
# CWE Top 25 (2024) + common web/injection weaknesses. Source: MITRE CWE list
# (cwe.mitre.org). Names not present here fall back to the bare id.
CWE_NAMES: dict[str, str] = {
    "CWE-20": "Improper Input Validation",
    "CWE-22": "Path Traversal",
    "CWE-77": "Command Injection",
    "CWE-78": "OS Command Injection",
    "CWE-79": "Cross-site Scripting (XSS)",
    "CWE-89": "SQL Injection",
    "CWE-94": "Code Injection",
    "CWE-119": "Improper Restriction of Operations within Memory Buffer",
    "CWE-120": "Buffer Copy without Checking Size (Classic Buffer Overflow)",
    "CWE-125": "Out-of-bounds Read",
    "CWE-129": "Improper Validation of Array Index",
    "CWE-190": "Integer Overflow or Wraparound",
    "CWE-200": "Exposure of Sensitive Information",
    "CWE-209": "Generation of Error Message Containing Sensitive Information",
    "CWE-215": "Insertion of Sensitive Information into Debugging Code",
    "CWE-269": "Improper Privilege Management",
    "CWE-276": "Incorrect Default Permissions",
    "CWE-284": "Improper Access Control",
    "CWE-285": "Improper Authorization",
    "CWE-287": "Improper Authentication",
    "CWE-290": "Authentication Bypass by Spoofing",
    "CWE-295": "Improper Certificate Validation",
    "CWE-306": "Missing Authentication for Critical Function",
    "CWE-311": "Missing Encryption of Sensitive Data",
    "CWE-312": "Cleartext Storage of Sensitive Information",
    "CWE-319": "Cleartext Transmission of Sensitive Information",
    "CWE-326": "Inadequate Encryption Strength",
    "CWE-327": "Use of a Broken or Risky Cryptographic Algorithm",
    "CWE-330": "Use of Insufficiently Random Values",
    "CWE-345": "Insufficient Verification of Data Authenticity",
    "CWE-346": "Origin Validation Error",
    "CWE-352": "Cross-Site Request Forgery (CSRF)",
    "CWE-362": "Race Condition",
    "CWE-367": "Time-of-check Time-of-use (TOCTOU) Race Condition",
    "CWE-384": "Session Fixation",
    "CWE-400": "Uncontrolled Resource Consumption",
    "CWE-401": "Missing Release of Memory after Effective Lifetime",
    "CWE-404": "Improper Resource Shutdown or Release",
    "CWE-416": "Use After Free",
    "CWE-425": "Direct Request (Forced Browsing)",
    "CWE-426": "Untrusted Search Path",
    "CWE-434": "Unrestricted Upload of File with Dangerous Type",
    "CWE-476": "NULL Pointer Dereference",
    "CWE-494": "Download of Code Without Integrity Check",
    "CWE-502": "Deserialization of Untrusted Data",
    "CWE-521": "Weak Password Requirements",
    "CWE-522": "Insufficiently Protected Credentials",
    "CWE-532": "Insertion of Sensitive Information into Log File",
    "CWE-538": "Insertion of Sensitive Information into Externally-Accessible File",
    "CWE-552": "Files or Directories Accessible to External Parties",
    "CWE-565": "Reliance on Cookies without Validation and Integrity Checking",
    "CWE-601": "Open Redirect",
    "CWE-611": "Improper Restriction of XML External Entity Reference (XXE)",
    "CWE-613": "Insufficient Session Expiration",
    "CWE-620": "Unverified Password Change",
    "CWE-639": "Authorization Bypass Through User-Controlled Key (IDOR)",
    "CWE-640": "Weak Password Recovery Mechanism",
    "CWE-643": "XPath Injection",
    "CWE-668": "Exposure of Resource to Wrong Sphere",
    "CWE-670": "Always-Incorrect Control Flow Implementation",
    "CWE-674": "Uncontrolled Recursion",
    "CWE-681": "Incorrect Conversion between Numeric Types",
    "CWE-693": "Protection Mechanism Failure",
    "CWE-732": "Incorrect Permission Assignment for Critical Resource",
    "CWE-770": "Allocation of Resources Without Limits or Throttling",
    "CWE-772": "Missing Release of Resource after Effective Lifetime",
    "CWE-776": "Improper Restriction of Recursive Entity References (XEE)",
    "CWE-787": "Out-of-bounds Write",
    "CWE-798": "Use of Hard-coded Credentials",
    "CWE-829": "Inclusion of Functionality from Untrusted Control Sphere",
    "CWE-834": "Excessive Iteration",
    "CWE-835": "Loop with Unreachable Exit Condition (Infinite Loop)",
    "CWE-862": "Missing Authorization",
    "CWE-863": "Incorrect Authorization",
    "CWE-908": "Use of Uninitialized Resource",
    "CWE-913": "Improper Control of Dynamically-Managed Code Resources",
    "CWE-915": "Improperly Controlled Modification of Dynamically-Determined Object Attributes",
    "CWE-918": "Server-Side Request Forgery (SSRF)",
    "CWE-1021": "Improper Restriction of Rendered UI Layers (Clickjacking)",
    "CWE-1188": "Insecure Default Initialization of Resource",
    "CWE-1236": "Improper Neutralization of Formula Elements in a CSV File",
}


def cwe_name(cwe_id: str) -> str:
    return CWE_NAMES.get(cwe_id, cwe_id)


# ── OWASP Top 10 2021 -> CWE ──────────────────────────────────────────────
# Source: OWASP Top 10 2021 (owasp.org/Top10). Each category lists the CWEs
# mapped to it in the official release; a representative subset (weighted to
# the CWEs that appear in real CVE data) is used here. A03 is current (2021);
# the 2025 list is still a release candidate as of this build, so the stable
# 2021 mapping is used and labelled with its year in the UI.
OWASP_TOP10_2021: list[dict] = [
    {
        "id": "A01", "title": "A01:2021 – Broken Access Control",
        "summary": "Restrictions on authenticated users are not properly enforced.",
        "cwes": [
            "CWE-22", "CWE-200", "CWE-201", "CWE-284", "CWE-285", "CWE-352",
            "CWE-359", "CWE-425", "CWE-441", "CWE-497", "CWE-538", "CWE-540",
            "CWE-548", "CWE-552", "CWE-566", "CWE-601", "CWE-639", "CWE-668",
            "CWE-706", "CWE-862", "CWE-863", "CWE-913", "CWE-922", "CWE-1275",
        ],
    },
    {
        "id": "A02", "title": "A02:2021 – Cryptographic Failures",
        "summary": "Failures related to cryptography that expose sensitive data.",
        "cwes": [
            "CWE-261", "CWE-296", "CWE-310", "CWE-311", "CWE-312", "CWE-319",
            "CWE-321", "CWE-322", "CWE-323", "CWE-324", "CWE-325", "CWE-326",
            "CWE-327", "CWE-328", "CWE-329", "CWE-330", "CWE-331", "CWE-335",
            "CWE-336", "CWE-337", "CWE-338", "CWE-340", "CWE-347", "CWE-523",
            "CWE-720", "CWE-757", "CWE-759", "CWE-760", "CWE-780", "CWE-818",
            "CWE-916",
        ],
    },
    {
        "id": "A03", "title": "A03:2021 – Injection",
        "summary": "User-supplied data is not validated, filtered, or sanitized.",
        "cwes": [
            "CWE-20", "CWE-74", "CWE-75", "CWE-77", "CWE-78", "CWE-79",
            "CWE-80", "CWE-83", "CWE-87", "CWE-88", "CWE-89", "CWE-90",
            "CWE-91", "CWE-93", "CWE-94", "CWE-95", "CWE-96", "CWE-97",
            "CWE-98", "CWE-99", "CWE-100", "CWE-113", "CWE-116", "CWE-138",
            "CWE-184", "CWE-470", "CWE-471", "CWE-564", "CWE-610", "CWE-643",
            "CWE-644", "CWE-652", "CWE-917",
        ],
    },
    {
        "id": "A04", "title": "A04:2021 – Insecure Design",
        "summary": "Missing or ineffective control design (threat modeling, secure patterns).",
        "cwes": [
            "CWE-73", "CWE-183", "CWE-209", "CWE-213", "CWE-235", "CWE-256",
            "CWE-257", "CWE-266", "CWE-269", "CWE-280", "CWE-311", "CWE-312",
            "CWE-313", "CWE-316", "CWE-419", "CWE-430", "CWE-434", "CWE-444",
            "CWE-451", "CWE-472", "CWE-501", "CWE-522", "CWE-525", "CWE-539",
            "CWE-579", "CWE-598", "CWE-602", "CWE-642", "CWE-646", "CWE-650",
            "CWE-653", "CWE-656", "CWE-657", "CWE-799", "CWE-807", "CWE-840",
            "CWE-841", "CWE-927", "CWE-1021", "CWE-1173",
        ],
    },
    {
        "id": "A05", "title": "A05:2021 – Security Misconfiguration",
        "summary": "Insecure default configs, verbose errors, unnecessary features.",
        "cwes": [
            "CWE-2", "CWE-11", "CWE-13", "CWE-15", "CWE-16", "CWE-260",
            "CWE-315", "CWE-520", "CWE-526", "CWE-537", "CWE-541", "CWE-547",
            "CWE-611", "CWE-614", "CWE-756", "CWE-776", "CWE-942", "CWE-1004",
            "CWE-1032", "CWE-1174", "CWE-1188",
        ],
    },
    {
        "id": "A06", "title": "A06:2021 – Vulnerable and Outdated Components",
        "summary": "Using components with known vulnerabilities or that are unsupported.",
        "cwes": ["CWE-937", "CWE-1035", "CWE-1104"],
    },
    {
        "id": "A07", "title": "A07:2021 – Identification and Authentication Failures",
        "summary": "Weaknesses in confirming user identity, authentication, and sessions.",
        "cwes": [
            "CWE-255", "CWE-259", "CWE-287", "CWE-288", "CWE-290", "CWE-294",
            "CWE-295", "CWE-297", "CWE-300", "CWE-302", "CWE-304", "CWE-306",
            "CWE-307", "CWE-346", "CWE-384", "CWE-521", "CWE-613", "CWE-620",
            "CWE-640", "CWE-798", "CWE-940", "CWE-1216",
        ],
    },
    {
        "id": "A08", "title": "A08:2021 – Software and Data Integrity Failures",
        "summary": "Code and infrastructure that does not protect against integrity violations.",
        "cwes": [
            "CWE-345", "CWE-353", "CWE-426", "CWE-494", "CWE-502", "CWE-565",
            "CWE-784", "CWE-829", "CWE-830", "CWE-915",
        ],
    },
    {
        "id": "A09", "title": "A09:2021 – Security Logging and Monitoring Failures",
        "summary": "Insufficient logging, detection, monitoring, and active response.",
        "cwes": ["CWE-117", "CWE-223", "CWE-532", "CWE-778"],
    },
    {
        "id": "A10", "title": "A10:2021 – Server-Side Request Forgery (SSRF)",
        "summary": "The app fetches a remote resource without validating the user-supplied URL.",
        "cwes": ["CWE-918"],
    },
]

OWASP_VERSION = "2021"

# CWE -> [owasp category id], reverse-built so only one direction is maintained.
_CWE_TO_OWASP: dict[str, list[str]] = {}
for _cat in OWASP_TOP10_2021:
    for _cwe in _cat["cwes"]:
        _CWE_TO_OWASP.setdefault(_cwe, []).append(_cat["id"])


def owasp_categories_for_cwe(cwe_id: str) -> list[str]:
    return _CWE_TO_OWASP.get(cwe_id, [])


# ── STRIDE threat class -> CWE (documented heuristic) ─────────────────────
# STRIDE has no official 1:1 CWE mapping; this is a documented heuristic that
# assigns each common weakness to the STRIDE class(es) that best describe the
# threat it enables. Surfaced in the UI as a heuristic, with each CWE's raw id
# visible so an analyst can judge the assignment. Based on Microsoft's STRIDE
# definitions and common threat-modeling practice.
STRIDE_CATEGORIES: list[dict] = [
    {"id": "S", "title": "Spoofing", "summary": "Impersonating something or someone else (identity/authentication).",
     "cwes": ["CWE-287", "CWE-290", "CWE-294", "CWE-295", "CWE-297", "CWE-306",
              "CWE-346", "CWE-384", "CWE-521", "CWE-522", "CWE-620", "CWE-640",
              "CWE-798", "CWE-1216"]},
    {"id": "T", "title": "Tampering", "summary": "Modifying data or code (injection, integrity, validation).",
     "cwes": ["CWE-20", "CWE-22", "CWE-74", "CWE-77", "CWE-78", "CWE-79",
              "CWE-89", "CWE-94", "CWE-116", "CWE-345", "CWE-353", "CWE-434",
              "CWE-494", "CWE-502", "CWE-565", "CWE-611", "CWE-643", "CWE-787",
              "CWE-829", "CWE-915", "CWE-917", "CWE-1236"]},
    {"id": "R", "title": "Repudiation", "summary": "Denying an action without the system being able to prove otherwise (logging).",
     "cwes": ["CWE-117", "CWE-223", "CWE-532", "CWE-778"]},
    {"id": "I", "title": "Information Disclosure", "summary": "Exposing information to those not authorized to see it.",
     "cwes": ["CWE-200", "CWE-201", "CWE-209", "CWE-215", "CWE-311", "CWE-312",
              "CWE-319", "CWE-359", "CWE-538", "CWE-540", "CWE-552", "CWE-601",
              "CWE-668", "CWE-918", "CWE-1275"]},
    {"id": "D", "title": "Denial of Service", "summary": "Denying or degrading service to valid users (resource exhaustion).",
     "cwes": ["CWE-400", "CWE-404", "CWE-674", "CWE-770", "CWE-772", "CWE-776",
              "CWE-834", "CWE-835", "CWE-1174"]},
    {"id": "E", "title": "Elevation of Privilege", "summary": "Gaining capabilities without proper authorization.",
     "cwes": ["CWE-250", "CWE-266", "CWE-269", "CWE-276", "CWE-284", "CWE-285",
              "CWE-425", "CWE-639", "CWE-693", "CWE-732", "CWE-862", "CWE-863"]},
]

# CWE -> [stride id], reverse-built.
_CWE_TO_STRIDE: dict[str, list[str]] = {}
for _cat in STRIDE_CATEGORIES:
    for _cwe in _cat["cwes"]:
        _CWE_TO_STRIDE.setdefault(_cwe, []).append(_cat["id"])


def stride_categories_for_cwe(cwe_id: str) -> list[str]:
    return _CWE_TO_STRIDE.get(cwe_id, [])


# ── CWE -> CAPEC (MITRE RelatedAttackPatterns) ────────────────────────────
# Source: MITRE CWE "Related Attack Patterns" (cwe.mitre.org / capec.mitre.org,
# CAPEC v3.9). A representative set of the mechanisms of attack for the common
# CWE classes. CAPEC ids projected here for a CVE inherit its scope filters.
CAPEC_NAMES: dict[str, str] = {
    "CAPEC-1": "Accessing Functionality Not Properly Constrained by ACLs",
    "CAPEC-7": "Blind SQL Injection",
    "CAPEC-12": "Choosing Message Identifier",
    "CAPEC-15": "Command Delimiters",
    "CAPEC-22": "Exploiting Trust in Client",
    "CAPEC-33": "HTTP Request Smuggling",
    "CAPEC-35": "Leverage Executable Code in Non-Executable Files",
    "CAPEC-61": "Session Fixation",
    "CAPEC-62": "Cross Site Request Forgery",
    "CAPEC-63": "Cross-Site Scripting (XSS)",
    "CAPEC-66": "SQL Injection",
    "CAPEC-70": "Try Common or Default Usernames and Passwords",
    "CAPEC-76": "Manipulating Web Input to File System Calls",
    "CAPEC-85": "AJAX Footprinting",
    "CAPEC-88": "OS Command Injection",
    "CAPEC-92": "Forced Integer Overflow",
    "CAPEC-94": "Adversary in the Middle (AiTM)",
    "CAPEC-97": "Cryptanalysis",
    "CAPEC-100": "Overflow Buffers",
    "CAPEC-108": "Command Line Execution through SQL Injection",
    "CAPEC-115": "Authentication Bypass",
    "CAPEC-116": "Excavation",
    "CAPEC-118": "Collect and Analyze Information",
    "CAPEC-122": "Privilege Abuse",
    "CAPEC-125": "Flooding",
    "CAPEC-126": "Path Traversal",
    "CAPEC-137": "Parameter Injection",
    "CAPEC-139": "Relative Path Traversal",
    "CAPEC-151": "Identity Spoofing",
    "CAPEC-157": "Sniffing Attacks",
    "CAPEC-178": "Cross-Site Flashing",
    "CAPEC-191": "Read Sensitive Constants Within an Executable",
    "CAPEC-201": "Serialized Data External Linking",
    "CAPEC-209": "XSS Using MIME Type Mismatch",
    "CAPEC-221": "Data Serialization External Entities Blowup",
    "CAPEC-242": "Code Injection",
    "CAPEC-248": "Command Injection",
    "CAPEC-255": "Manipulate Data Structures",
    "CAPEC-267": "Leverage Alternate Encoding",
    "CAPEC-461": "Web Services API Signature Forgery Leveraging Hash Function Extension Weakness",
    "CAPEC-470": "Expanding Control over the Operating System from the Database",
    "CAPEC-490": "Amplification",
    "CAPEC-500": "WebView Injection",
    "CAPEC-540": "Overread Buffers",
    "CAPEC-586": "Object Injection",
    "CAPEC-588": "DOM-Based XSS",
    "CAPEC-591": "Reflected XSS",
    "CAPEC-592": "Stored XSS",
    "CAPEC-593": "Session Hijacking",
    "CAPEC-597": "Absolute Path Traversal",
    "CAPEC-620": "Drop Encryption Level",
    "CAPEC-664": "Server Side Request Forgery",
}

CWE_TO_CAPEC: dict[str, list[str]] = {
    "CWE-22": ["CAPEC-126", "CAPEC-76", "CAPEC-139", "CAPEC-597"],
    "CWE-77": ["CAPEC-15", "CAPEC-248", "CAPEC-137"],
    "CWE-78": ["CAPEC-88", "CAPEC-108"],
    "CWE-79": ["CAPEC-63", "CAPEC-588", "CAPEC-591", "CAPEC-592", "CAPEC-209", "CAPEC-85"],
    "CWE-89": ["CAPEC-66", "CAPEC-7", "CAPEC-108", "CAPEC-470"],
    "CWE-94": ["CAPEC-242", "CAPEC-35"],
    "CWE-120": ["CAPEC-100"],
    "CWE-125": ["CAPEC-540"],
    "CWE-190": ["CAPEC-92"],
    "CWE-200": ["CAPEC-118", "CAPEC-116"],
    "CWE-287": ["CAPEC-115", "CAPEC-22", "CAPEC-94", "CAPEC-151"],
    "CWE-290": ["CAPEC-151", "CAPEC-94"],
    "CWE-306": ["CAPEC-12"],
    "CWE-319": ["CAPEC-94", "CAPEC-157"],
    "CWE-327": ["CAPEC-620", "CAPEC-97"],
    "CWE-352": ["CAPEC-62"],
    "CWE-384": ["CAPEC-593", "CAPEC-61"],
    "CWE-400": ["CAPEC-490", "CAPEC-125"],
    "CWE-434": ["CAPEC-1"],
    "CWE-502": ["CAPEC-586", "CAPEC-201"],
    "CWE-601": ["CAPEC-178"],
    "CWE-611": ["CAPEC-221"],
    "CWE-787": ["CAPEC-100", "CAPEC-540"],
    "CWE-798": ["CAPEC-70", "CAPEC-191"],
    "CWE-862": ["CAPEC-1", "CAPEC-122"],
    "CWE-863": ["CAPEC-1", "CAPEC-122"],
    "CWE-918": ["CAPEC-664"],
}


def capec_for_cwe(cwe_id: str) -> list[str]:
    return CWE_TO_CAPEC.get(cwe_id, [])


def capec_name(capec_id: str) -> str:
    return CAPEC_NAMES.get(capec_id, capec_id)
