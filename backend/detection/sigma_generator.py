"""
Template-based Sigma rule generator for BRIEFR.
One template per major ATT&CK tactic family.
Generated rules are marked experimental with a BRIEFR confidence note.
"""

from __future__ import annotations

from datetime import datetime
import re
import yaml

# ── Technique templates ───────────────────────────────────

TECHNIQUE_TEMPLATES: dict[str, dict] = {
    # Initial Access — Exploit Public-Facing Application
    "T1190": {
        "tactic": "initial_access",
        "logsource": {"category": "webserver"},
        "detection": {
            "keywords": ["../", "%2e%2e", "cmd.exe", "/etc/passwd", ";id;", "whoami",
                         "<script", "' OR '1'='1", "UNION SELECT"],
            "condition": "keywords",
        },
        "falsepositives": ["Vulnerability scanners", "Penetration testing", "Security researchers"],
        "level": "high",
    },
    # Initial Access — External Remote Services
    "T1133": {
        "tactic": "initial_access",
        "logsource": {"product": "windows", "category": "network_connection"},
        "detection": {
            "selection": {"DestinationPort": [3389, 22, 5900, 1194, 8443], "Initiated": "true"},
            "filter": {"SourceIp|startswith": ["10.", "192.168.", "172.16."]},
            "condition": "selection and not filter",
        },
        "falsepositives": ["Legitimate remote administration", "VPN connections"],
        "level": "medium",
    },
    # Execution — Command and Scripting Interpreter
    "T1059": {
        "tactic": "execution",
        "logsource": {"product": "windows", "category": "process_creation"},
        "detection": {
            "selection": {
                "Image|endswith": [r"\cmd.exe", r"\powershell.exe", r"\pwsh.exe",
                                   r"\bash.exe", r"\sh.exe", r"\wscript.exe", r"\cscript.exe"],
                "ParentImage|endswith": [r"\svchost.exe", r"\services.exe",
                                          r"\winlogon.exe", r"\lsass.exe"],
            },
            "condition": "selection",
        },
        "falsepositives": ["Administrator activity", "Legitimate scripts run by svchost"],
        "level": "medium",
    },
    # Execution — Exploitation for Client Execution
    "T1203": {
        "tactic": "execution",
        "logsource": {"product": "windows", "category": "process_creation"},
        "detection": {
            "selection": {
                "ParentImage|endswith": [r"\winword.exe", r"\excel.exe", r"\outlook.exe",
                                          r"\firefox.exe", r"\chrome.exe", r"\msedge.exe",
                                          r"\acrobat.exe", r"\acrord32.exe"],
                "Image|endswith": [r"\cmd.exe", r"\powershell.exe", r"\wscript.exe",
                                    r"\mshta.exe", r"\regsvr32.exe", r"\rundll32.exe"],
            },
            "condition": "selection",
        },
        "falsepositives": ["Macros in legitimate documents", "Office automation tools"],
        "level": "high",
    },
    # Privilege Escalation — Exploitation for Privilege Escalation
    "T1068": {
        "tactic": "privilege_escalation",
        "logsource": {"product": "windows", "category": "process_creation"},
        "detection": {
            "selection": {"IntegrityLevel": "System"},
            "filter": {
                "Image|endswith": [r"\services.exe", r"\lsass.exe", r"\smss.exe",
                                    r"\csrss.exe", r"\wininit.exe", r"\svchost.exe"],
            },
            "condition": "selection and not filter",
        },
        "falsepositives": ["Legitimate system processes", "Software installers"],
        "level": "high",
    },
    # Privilege Escalation / Defense Evasion — Process Injection
    "T1055": {
        "tactic": "privilege_escalation",
        "logsource": {"product": "windows", "category": "create_remote_thread"},
        "detection": {
            "selection": {
                "TargetImage|endswith": [r"\explorer.exe", r"\svchost.exe",
                                          r"\lsass.exe", r"\winlogon.exe",
                                          r"\notepad.exe", r"\calc.exe"],
            },
            "filter": {
                "SourceImage|endswith": [r"\svchost.exe", r"\services.exe", r"\csrss.exe"],
            },
            "condition": "selection and not filter",
        },
        "falsepositives": ["Security products", "Legitimate injection frameworks"],
        "level": "high",
    },
    # Defense Evasion — Obfuscated Files or Information
    "T1027": {
        "tactic": "defense_evasion",
        "logsource": {"product": "windows", "category": "process_creation"},
        "detection": {
            "selection": {
                "CommandLine|contains": ["base64", "IEX", "Invoke-Expression",
                                          "FromBase64String", "-enc", "-EncodedCommand",
                                          "char(", "CHAR(", "0x"],
            },
            "condition": "selection",
        },
        "falsepositives": ["Legitimate PowerShell administration", "Software installers using base64"],
        "level": "medium",
    },
    # Defense Evasion — Masquerading
    "T1036": {
        "tactic": "defense_evasion",
        "logsource": {"product": "windows", "category": "process_creation"},
        "detection": {
            "selection": {"Image|endswith": r"\svchost.exe"},
            "filter": {"ParentImage|endswith": [r"\services.exe", r"\MsMpEng.exe"]},
            "condition": "selection and not filter",
        },
        "falsepositives": ["Some security tools that spawn svchost"],
        "level": "high",
    },
    # Credential Access — Brute Force
    "T1110": {
        "tactic": "credential_access",
        "logsource": {"product": "windows", "service": "security"},
        "detection": {
            "selection": {"EventID": 4625},
            "timeframe": "5m",
            "condition": "selection | count() > 10 by TargetUserName",
        },
        "falsepositives": ["Misconfigured services", "Users forgetting passwords"],
        "level": "medium",
    },
    # Credential Access — OS Credential Dumping
    "T1003": {
        "tactic": "credential_access",
        "logsource": {"product": "windows", "category": "process_access"},
        "detection": {
            "selection": {
                "TargetImage|endswith": r"\lsass.exe",
                "GrantedAccess|contains": ["0x1010", "0x1410", "0x147a", "0x143a"],
            },
            "filter": {
                "SourceImage|endswith": [r"\MsMpEng.exe", r"\taskmgr.exe", r"\csrss.exe"],
            },
            "condition": "selection and not filter",
        },
        "falsepositives": ["Security products accessing lsass", "Task Manager"],
        "level": "critical",
    },
    # Lateral Movement — Remote Services
    "T1021": {
        "tactic": "lateral_movement",
        "logsource": {"product": "windows", "service": "security"},
        "detection": {
            "selection": {
                "EventID": [4624, 4648],
                "LogonType": [3, 10],
            },
            "filter": {"SubjectUserName|endswith": "$"},
            "condition": "selection and not filter",
        },
        "falsepositives": ["Legitimate remote administration", "Domain controller logins"],
        "level": "low",
    },
    # Lateral Movement — Lateral Tool Transfer
    "T1570": {
        "tactic": "lateral_movement",
        "logsource": {"product": "windows", "category": "network_connection"},
        "detection": {
            "selection": {"DestinationPort": [445, 139], "Initiated": "true"},
            "filter": {"DestinationIp": ["127.0.0.1", "::1"]},
            "condition": "selection and not filter",
        },
        "falsepositives": ["Legitimate file transfers", "DFS replication", "Print spooler"],
        "level": "low",
    },
    # Command and Control — Application Layer Protocol
    "T1071": {
        "tactic": "command_and_control",
        "logsource": {"category": "proxy"},
        "detection": {
            "keywords": ["CONNECT ", "User-Agent: Mozilla/4.0 (compatible; MSIE 6.0)"],
            "selection": {
                "c-useragent|contains": ["python-requests", "Go-http-client", "curl/", "wget/"],
            },
            "condition": "keywords or selection",
        },
        "falsepositives": ["Legitimate proxy use", "Automated scripts"],
        "level": "medium",
    },
    # Command and Control — Non-Application Layer Protocol
    "T1095": {
        "tactic": "command_and_control",
        "logsource": {"category": "firewall"},
        "detection": {
            "selection": {
                "proto": ["icmp", "icmp6"],
                "data_length|gt": 64,
            },
            "condition": "selection",
        },
        "falsepositives": ["Network monitoring tools", "Ping sweeps"],
        "level": "medium",
    },
}

DEFAULT_TEMPLATE: dict = {
    "tactic": "initial_access",
    "logsource": {"category": "webserver"},
    "detection": {
        "keywords": ["exploit", "attack", "injection", "overflow"],
        "condition": "keywords",
    },
    "falsepositives": ["Security scanners", "Penetration testing"],
    "level": "medium",
}

_DEFAULT_BRIEFR_NOTE = (
    "Validate before deploying to production — adjust field names and "
    "conditions to your environment"
)


def _cwe_template(
    *,
    tactic: str,
    logsource: dict,
    detection: dict,
    falsepositives: list[str],
    level: str,
    briefr_confidence: str = "MEDIUM",
    briefr_note_extra: str = "",
) -> dict:
    return {
        "tactic": tactic,
        "logsource": logsource,
        "detection": detection,
        "falsepositives": falsepositives,
        "level": level,
        "briefr_confidence": briefr_confidence,
        "briefr_note_extra": briefr_note_extra,
    }


_CWE_PATH_TRAVERSAL = _cwe_template(
    tactic="initial_access",
    logsource={"category": "webserver"},
    detection={
        "keywords": [
            "../",
            "..\\",
            "%2e%2e%2f",
            "%252e",
            "/etc/passwd",
            "boot.ini",
            "web.config",
        ],
        "condition": "keywords",
    },
    falsepositives=["URL-encoded path normalization", "Legitimate file paths"],
    level="high",
)

_CWE_CMD_INJECTION = _cwe_template(
    tactic="initial_access",
    logsource={"category": "webserver"},
    detection={
        "keywords": [
            ";id",
            "; id",
            "|whoami",
            "| whoami",
            "`id`",
            "$(",
            "&&wget",
            "&& wget",
            ";curl",
            "; curl",
            "/bin/sh",
            "cmd.exe /c",
        ],
        "condition": "keywords",
    },
    falsepositives=["Shell tutorials in logs", "Dev tooling"],
    level="high",
)

_CWE_SQLI = _cwe_template(
    tactic="initial_access",
    logsource={"category": "webserver"},
    detection={
        "keywords": [
            "UNION SELECT",
            "' OR '1'='1",
            "SLEEP(",
            "BENCHMARK(",
            "information_schema",
            "xp_cmdshell",
        ],
        "condition": "keywords",
    },
    falsepositives=["ORM debug output", "SQL in documentation requests"],
    level="high",
)

_CWE_XSS = _cwe_template(
    tactic="initial_access",
    logsource={"category": "webserver"},
    detection={
        "keywords": ["<script", "onerror=", "javascript:", "%3Cscript"],
        "condition": "keywords",
    },
    falsepositives=[
        "Rich text editors",
        "Marketing pages with inline scripts",
        "Security scanners",
    ],
    level="low",
    briefr_confidence="LOW",
    briefr_note_extra="High false-positive rate — tune keywords to your apps",
)

_CWE_DESER = _cwe_template(
    tactic="initial_access",
    logsource={"category": "webserver"},
    detection={
        "keywords": [
            "rO0AB",
            "aced0005",
            "TypeObject",
            "ysoserial",
            "__VIEWSTATE",
        ],
        "condition": "keywords",
    },
    falsepositives=["Legitimate serialized session blobs"],
    level="high",
)

_CWE_CODE_INJECTION = _cwe_template(
    tactic="execution",
    logsource={"category": "webserver"},
    detection={
        "keywords": [
            "eval(",
            "assert(",
            "base64_decode(",
            "{{",
            "}}",
            "${",
            "}",
        ],
        "condition": "keywords",
    },
    falsepositives=["Template engines in dev", "Debug endpoints"],
    level="medium",
)

_CWE_UPLOAD = _cwe_template(
    tactic="initial_access",
    logsource={"category": "webserver"},
    detection={
        "keywords": [".jsp", ".jspx", ".php", ".aspx", ".ashx", ".war"],
        "condition": "keywords",
    },
    falsepositives=["Legitimate file uploads", "Static asset paths"],
    level="high",
)

_CWE_SSRF = _cwe_template(
    tactic="initial_access",
    logsource={"category": "webserver"},
    detection={
        "keywords": [
            "169.254.169.254",
            "metadata.google",
            "localhost:",
            "127.0.0.1",
            "file://",
            "gopher://",
        ],
        "condition": "keywords",
    },
    falsepositives=["Health checks", "Internal service callbacks"],
    level="high",
)

_CWE_XXE = _cwe_template(
    tactic="initial_access",
    logsource={"category": "webserver"},
    detection={
        "keywords": [
            "<!ENTITY",
            'SYSTEM "file://',
            'SYSTEM "http://',
            "SYSTEM 'file://",
            "SYSTEM 'http://",
        ],
        "condition": "keywords",
    },
    falsepositives=["XML config parsers", "Document import features"],
    level="high",
)

_CWE_AUTH_BYPASS = _cwe_template(
    tactic="initial_access",
    logsource={"category": "webserver"},
    detection={
        "keywords": [
            "/admin",
            "/api/login",
            "/api/auth",
            "bypass",
            "unauthorized",
            "privilege",
        ],
        "condition": "keywords",
    },
    falsepositives=["Legitimate admin traffic", "Auth integration tests"],
    level="medium",
    briefr_note_extra="Requires environment tuning — map to your admin/API paths",
)

_CWE_MEMORY_CORRUPTION = _cwe_template(
    tactic="execution",
    logsource={"category": "application"},
    detection={
        "selection": {"EventID": [1000, 1001]},
        "keywords": ["segfault", "SIGSEGV", "core dumped"],
        "condition": "selection or keywords",
    },
    falsepositives=[
        "Benign application crashes",
        "Stability issues unrelated to exploitation",
    ],
    level="low",
    briefr_confidence="LOW",
    briefr_note_extra="Crash telemetry is not proof of exploitation — correlate with exploit activity",
)

_CWE_DEFAULT_CREDS = _cwe_template(
    tactic="credential_access",
    logsource={"category": "authentication"},
    detection={
        "keywords": ["admin", "default", "root", "password", "guest"],
        "condition": "keywords",
    },
    falsepositives=["Password reset flows", "Onboarding scripts"],
    level="medium",
    briefr_note_extra="Fill in your product's vendor-default account names",
)

CWE_TEMPLATES: dict[str, dict] = {
    "CWE-22": _CWE_PATH_TRAVERSAL,
    "CWE-23": _CWE_PATH_TRAVERSAL,
    "CWE-35": _CWE_PATH_TRAVERSAL,
    "CWE-78": _CWE_CMD_INJECTION,
    "CWE-89": _CWE_SQLI,
    "CWE-79": _CWE_XSS,
    "CWE-502": _CWE_DESER,
    "CWE-94": _CWE_CODE_INJECTION,
    "CWE-95": _CWE_CODE_INJECTION,
    "CWE-434": _CWE_UPLOAD,
    "CWE-918": _CWE_SSRF,
    "CWE-611": _CWE_XXE,
    "CWE-287": _CWE_AUTH_BYPASS,
    "CWE-288": _CWE_AUTH_BYPASS,
    "CWE-306": _CWE_AUTH_BYPASS,
    "CWE-416": _CWE_MEMORY_CORRUPTION,
    "CWE-787": _CWE_MEMORY_CORRUPTION,
    "CWE-119": _CWE_MEMORY_CORRUPTION,
    "CWE-122": _CWE_MEMORY_CORRUPTION,
    "CWE-798": _CWE_DEFAULT_CREDS,
}


def _normalize_cwe_id(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    compact = re.sub(r"\s+", "", text.upper())
    if compact.isdigit():
        return f"CWE-{compact}"
    match = re.match(r"^CWE-?(\d+)$", compact)
    if match:
        return f"CWE-{match.group(1)}"
    return compact


def _resolve_template(
    technique_id: str,
    cwe_ids: list[str] | None,
) -> tuple[dict, str, str]:
    """Return (template, briefr_basis, matched_cwe_id)."""
    prefix = technique_id.strip().upper()[:5] if technique_id else ""
    if prefix in TECHNIQUE_TEMPLATES:
        return TECHNIQUE_TEMPLATES[prefix], "attack_technique", ""

    for raw in cwe_ids or []:
        cwe_id = _normalize_cwe_id(str(raw))
        template = CWE_TEMPLATES.get(cwe_id)
        if template is not None:
            return template, "cwe", cwe_id

    return DEFAULT_TEMPLATE, "generic", ""


# ── Generator ─────────────────────────────────────────────

def generate_sigma_rule(
    cve_id: str,
    technique_id: str,
    product: str = "",
    description: str = "",
    cwe_ids: list[str] | None = None,
) -> str:
    """
    Generate a Sigma rule YAML string for a CVE/technique pair.
    Selection order: ATT&CK technique template → CWE class template → generic default.
    """
    template, briefr_basis, matched_cwe = _resolve_template(technique_id, cwe_ids)

    title_product = product.strip() if product else "Affected Product"
    briefr_note = _DEFAULT_BRIEFR_NOTE
    extra_note = (template.get("briefr_note_extra") or "").strip()
    if extra_note:
        briefr_note = f"{briefr_note} — {extra_note}"

    rule: dict = {
        "title": f"{title_product} - {cve_id} Exploitation Attempt",
        "id": _generate_rule_id(cve_id, technique_id, matched_cwe),
        "status": "experimental",
        "description": description.strip() or f"Detects exploitation attempt targeting {cve_id}.",
        "references": [
            f"https://nvd.nist.gov/vuln/detail/{cve_id}",
        ],
        "author": "BRIEFR (generated)",
        "date": datetime.now().strftime("%Y/%m/%d"),
        "tags": [
            f"attack.{template['tactic']}",
        ],
        "logsource": template["logsource"],
        "detection": template["detection"],
        "falsepositives": template["falsepositives"],
        "level": template["level"],
        "briefr_basis": briefr_basis,
        "briefr_confidence": template.get("briefr_confidence", "MEDIUM"),
        "briefr_note": briefr_note,
    }

    # Add technique and CVE tags
    if technique_id:
        rule["tags"].append(f"attack.{technique_id.lower()}")
    if matched_cwe:
        rule["tags"].append(matched_cwe.lower().replace("-", "."))
    rule["tags"].append(f"cve.{cve_id.lower().replace('-', '.')}")

    return yaml.dump(rule, default_flow_style=False, sort_keys=False, allow_unicode=True)


def _generate_rule_id(cve_id: str, technique_id: str, cwe_id: str = "") -> str:
    """Deterministic UUID-like ID from CVE + technique/CWE (stable, not a real UUID)."""
    import hashlib

    digest = hashlib.md5(f"{cve_id}:{technique_id}:{cwe_id}".encode()).hexdigest()
    return f"{digest[:8]}-{digest[8:12]}-{digest[12:16]}-{digest[16:20]}-{digest[20:32]}"
