"""
Template-based Sigma rule generator for BRIEFR.
One template per major ATT&CK tactic family.
Generated rules are marked experimental with a BRIEFR confidence note.
"""

from __future__ import annotations

from datetime import datetime
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


# ── Generator ─────────────────────────────────────────────

def generate_sigma_rule(
    cve_id: str,
    technique_id: str,
    product: str = "",
    description: str = "",
) -> str:
    """
    Generate a Sigma rule YAML string for a CVE/technique pair.
    Uses technique-specific templates; falls back to DEFAULT_TEMPLATE.
    """
    prefix = technique_id.strip().upper()[:5] if technique_id else ""
    template = TECHNIQUE_TEMPLATES.get(prefix, DEFAULT_TEMPLATE)

    title_product = product.strip() if product else "Affected Product"
    rule: dict = {
        "title": f"{title_product} - {cve_id} Exploitation Attempt",
        "id": _generate_rule_id(cve_id, technique_id),
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
        "briefr_confidence": "MEDIUM",
        "briefr_note": "Validate before deploying to production — adjust field names and conditions to your environment",
    }

    # Add technique and CVE tags
    if technique_id:
        rule["tags"].append(f"attack.{technique_id.lower()}")
    rule["tags"].append(f"cve.{cve_id.lower().replace('-', '.')}")

    return yaml.dump(rule, default_flow_style=False, sort_keys=False, allow_unicode=True)


def _generate_rule_id(cve_id: str, technique_id: str) -> str:
    """Deterministic UUID-like ID from CVE + technique (not a real UUID, just stable)."""
    import hashlib
    digest = hashlib.md5(f"{cve_id}:{technique_id}".encode()).hexdigest()
    return f"{digest[:8]}-{digest[8:12]}-{digest[12:16]}-{digest[16:20]}-{digest[20:32]}"
