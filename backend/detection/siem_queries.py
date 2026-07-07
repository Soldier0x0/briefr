"""
SIEM quick-search query templates for BRIEFR detection engineering.
Covers Elastic KQL, Splunk SPL, Microsoft Sentinel KQL, and QRadar AQL.

Placeholders use {{FIELD}} notation — analysts replace with actual field names.
Common field name variations documented per platform in each query's `notes`.
"""

from __future__ import annotations

from detection.class_queries import CLASS_QUERIES
from detection.class_router import _resolve_detection_class

# ── Common field name reference ───────────────────────────
# Listed in query `notes` so analysts know what to replace.

FIELD_NOTES = {
    "elastic_kql": (
        "Replace {{SOURCE_IP}} with source.ip or client.ip; "
        "{{URL_PATH}} with url.path or url.full; "
        "{{STATUS_CODE}} with http.response.status_code; "
        "{{PROCESS}} with process.name or process.executable; "
        "{{USER}} with user.name"
    ),
    "splunk_spl": (
        "Replace {{INDEX}} with your index (e.g. index=main); "
        "{{SOURCETYPE}} with your log sourcetype; "
        "{{SRC_IP}} with src_ip or c_ip; "
        "{{URI}} with uri_path, cs_uri_stem, or url; "
        "{{STATUS}} with status, sc_status, or response_code"
    ),
    "sentinel_kql": (
        "Replace {{TABLE}} with the log table (e.g. W3CIISLog, CommonSecurityLog, SecurityEvent); "
        "{{CLIENT_IP}} with cIP, SourceIP, or ClientIP; "
        "{{URL}} with csUriStem, RequestURL, or DestinationURL; "
        "{{STATUS}} with scStatus or ResultCode"
    ),
    "qradar_aql": (
        "Replace {{LOG_SOURCE}} with your log source type; "
        "{{SOURCE_IP}} with sourceip or Source IP; "
        "{{URL}} with URL or Request URL; "
        "{{STATUS}} with Response Code or HTTP Response Code"
    ),
}


TECHNIQUE_QUERIES: dict[str, dict] = {
    # ── T1190 — Exploit Public-Facing Application ─────────
    "T1190": {
        "title": "Exploit Public-Facing Application",
        "elastic_kql": (
            '(http.response.status_code:(400 or 403 or 500 or 503) '
            'and http.request.body.bytes > 500) '
            'or url.path:("../" or "%2e%2e" or "cmd.exe" or "/etc/passwd" or "etc%2fpasswd") '
            'or (url.query:("UNION" or "UNION SELECT" or "base64") and http.response.status_code:200)'
        ),
        "splunk_spl": (
            '{{INDEX}} {{SOURCETYPE}} '
            '((status=400 OR status=403 OR status=500 OR status=503) bytes > 500) '
            'OR ({{URI}}="*../*" OR {{URI}}="*%2e%2e*" OR {{URI}}="*cmd.exe*" OR {{URI}}="*/etc/passwd*") '
            '| stats count by {{SRC_IP}}, {{URI}}, status | sort - count'
        ),
        "sentinel_kql": (
            '{{TABLE}}\n'
            '| where scStatus in ("400","403","500","503") and csBytes > 500\n'
            '    or csUriStem has_any ("../", "%2e%2e", "cmd.exe", "/etc/passwd")\n'
            '| project TimeGenerated, cIP, csMethod, csUriStem, scStatus, csBytes\n'
            '| order by TimeGenerated desc'
        ),
        "qradar_aql": (
            'SELECT "{{SOURCE_IP}}", "{{URL}}", "{{STATUS}}", BYTESOUT '
            'FROM events '
            'WHERE "{{STATUS}}" IN (400, 403, 500, 503) AND BYTESOUT > 500 '
            '   OR "{{URL}}" LIKE \'%../%\' OR "{{URL}}" LIKE \'%cmd.exe%\' '
            'LAST 24 HOURS'
        ),
        "log_patterns": [
            "Unusual HTTP 4xx/5xx error spikes from external IPs",
            "Directory traversal sequences (../, %2e%2e) in URL paths",
            "OS command strings (cmd.exe, /etc/passwd, whoami) in request parameters",
            "SQL injection patterns (UNION SELECT, OR 1=1) in query strings",
            "Unexpected large POST bodies to public endpoints",
            "Repeated requests to non-existent paths from a single IP",
        ],
    },

    # ── T1133 — External Remote Services ─────────────────
    "T1133": {
        "title": "External Remote Services",
        "elastic_kql": (
            'network.transport:tcp '
            'and destination.port:(3389 or 22 or 5900 or 1194 or 8443 or 993 or 995) '
            'and not source.ip:(10.0.0.0/8 or 172.16.0.0/12 or 192.168.0.0/16)'
        ),
        "splunk_spl": (
            '{{INDEX}} {{SOURCETYPE}} '
            '(dest_port=3389 OR dest_port=22 OR dest_port=5900 OR dest_port=1194 OR dest_port=8443) '
            'NOT src_ip IN (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16) '
            '| stats count by src_ip, dest_ip, dest_port | sort - count'
        ),
        "sentinel_kql": (
            'NetworkCommunicationEvents\n'
            '| where RemotePort in (3389, 22, 5900, 1194, 8443)\n'
            '    and not ipv4_is_private(RemoteIP)\n'
            '| project Timestamp, LocalIP, RemoteIP, RemotePort, Protocol\n'
            '| order by Timestamp desc'
        ),
        "qradar_aql": (
            'SELECT sourceip, destinationip, destinationport, username '
            'FROM events '
            'WHERE destinationport IN (3389, 22, 5900, 1194, 8443) '
            '  AND NOT INCIDR(\'10.0.0.0/8\', sourceip) '
            '  AND NOT INCIDR(\'192.168.0.0/16\', sourceip) '
            'LAST 24 HOURS'
        ),
        "log_patterns": [
            "Authentication attempts from geographically unusual locations",
            "Connections to remote service ports (RDP/SSH/VNC) from external IPs",
            "VPN logins outside of business hours from new IP ranges",
            "Multiple failed authentication attempts followed by a success",
            "New user accounts or service accounts accessing remote services",
        ],
    },

    # ── T1059 — Command and Scripting Interpreter ─────────
    "T1059": {
        "title": "Command and Scripting Interpreter",
        "elastic_kql": (
            'process.name:(cmd.exe or powershell.exe or pwsh.exe or bash or sh or python or python3) '
            'and process.parent.name:(svchost.exe or services.exe or winlogon.exe or lsass.exe or '
            'w3wp.exe or nginx or apache2 or httpd)'
        ),
        "splunk_spl": (
            '{{INDEX}} {{SOURCETYPE}} '
            '(process="*cmd.exe*" OR process="*powershell.exe*" OR process="*bash*" OR process="*sh*") '
            '(parent_process="*svchost.exe*" OR parent_process="*services.exe*" '
            'OR parent_process="*w3wp.exe*" OR parent_process="*httpd*") '
            '| table _time, host, user, process, parent_process, command_line'
        ),
        "sentinel_kql": (
            'DeviceProcessEvents\n'
            '| where ProcessCommandLine has_any ("cmd.exe", "powershell", "bash", "sh -c")\n'
            '    and InitiatingProcessFileName has_any ("svchost.exe", "w3wp.exe", "httpd", "nginx")\n'
            '| project Timestamp, DeviceName, AccountName, ProcessCommandLine, '
            '          InitiatingProcessFileName\n'
            '| order by Timestamp desc'
        ),
        "qradar_aql": (
            'SELECT "{{SOURCE_IP}}", "Process Name", "Command", username '
            'FROM events '
            'WHERE "Process Name" IN (\'cmd.exe\', \'powershell.exe\', \'bash\', \'sh\') '
            '  AND "Parent Process" IN (\'svchost.exe\', \'w3wp.exe\', \'httpd\') '
            'LAST 24 HOURS'
        ),
        "log_patterns": [
            "Shell or script interpreter spawned by a web server or service process",
            "PowerShell with encoded commands (-enc or -EncodedCommand flags)",
            "Base64-encoded payloads in command line arguments",
            "Unusual parent-child process relationships (web server → cmd.exe)",
            "Script execution from temporary or user-writable directories",
            "Network connections initiated by scripting processes",
        ],
    },

    # ── T1068 — Exploitation for Privilege Escalation ─────
    "T1068": {
        "title": "Exploitation for Privilege Escalation",
        "elastic_kql": (
            'process.token.integrity_level:System '
            'and not process.name:(services.exe or lsass.exe or smss.exe '
            'or csrss.exe or wininit.exe or svchost.exe or winlogon.exe)'
        ),
        "splunk_spl": (
            '{{INDEX}} {{SOURCETYPE}} '
            'integrity_level="System" '
            'NOT process IN ("services.exe", "lsass.exe", "smss.exe", "csrss.exe") '
            '| table _time, host, user, process, parent_process, integrity_level'
        ),
        "sentinel_kql": (
            'DeviceProcessEvents\n'
            '| where ProcessTokenElevationType == "Full"\n'
            '    and not ProcessFileName in~ ("services.exe","lsass.exe","smss.exe","csrss.exe")\n'
            '| project Timestamp, DeviceName, AccountName, ProcessFileName, InitiatingProcessFileName\n'
            '| order by Timestamp desc'
        ),
        "qradar_aql": (
            'SELECT "{{SOURCE_IP}}", username, "Process Name", "Privilege Escalation" '
            'FROM events '
            'WHERE category = \'Privilege Escalation\' '
            '  AND "Severity" >= 7 '
            'LAST 24 HOURS'
        ),
        "log_patterns": [
            "Process running with SYSTEM/root privileges without expected parent",
            "Exploitation of kernel or driver vulnerability (system call anomaly)",
            "Sudden privilege gain for a non-administrative user",
            "Token impersonation events in Windows Security log (Event 4624 with unusual logon type)",
            "SetUID/SetGID file execution on Linux systems",
            "Unexpected changes to /etc/sudoers or Windows privilege assignments",
        ],
    },

    # ── T1055 — Process Injection ─────────────────────────
    "T1055": {
        "title": "Process Injection",
        "elastic_kql": (
            'event.category:process and event.action:"CreateRemoteThread" '
            'and target.process.name:(explorer.exe or svchost.exe or lsass.exe or '
            'notepad.exe or calc.exe or regsvr32.exe)'
        ),
        "splunk_spl": (
            '{{INDEX}} {{SOURCETYPE}} '
            'event_id=10 target_process IN ("explorer.exe", "svchost.exe", "lsass.exe") '
            'NOT source_process IN ("MsMpEng.exe", "csrss.exe", "services.exe") '
            '| table _time, host, source_process, target_process, granted_access'
        ),
        "sentinel_kql": (
            'DeviceEvents\n'
            '| where ActionType == "CreateRemoteThreadApiCall"\n'
            '    and TargetProcessFileName in~ ("explorer.exe","svchost.exe","lsass.exe")\n'
            '    and not InitiatingProcessFileName in~ ("MsMpEng.exe","csrss.exe")\n'
            '| project Timestamp, DeviceName, InitiatingProcessFileName, '
            '          TargetProcessFileName, RemoteUrl\n'
            '| order by Timestamp desc'
        ),
        "qradar_aql": (
            'SELECT "{{SOURCE_IP}}", "Process Name", "Target Process", "Memory Address" '
            'FROM events '
            'WHERE category = \'Process Injection\' OR qid IN '
            '  (SELECT id FROM qroc WHERE name LIKE \'%inject%\') '
            'LAST 24 HOURS'
        ),
        "log_patterns": [
            "CreateRemoteThread calls targeting explorer.exe, svchost.exe, or lsass.exe",
            "WriteProcessMemory followed by CreateRemoteThread or QueueUserAPC",
            "Unexpected DLL loaded by a benign process (DLL injection)",
            "Sysmon Event ID 8 (CreateRemoteThread) from non-security processes",
            "VirtualAllocEx calls with PAGE_EXECUTE_READWRITE permissions",
        ],
    },

    # ── T1027 — Obfuscated Files or Information ────────────
    "T1027": {
        "title": "Obfuscated Files or Information",
        "elastic_kql": (
            'process.command_line:(*base64* or *IEX* or *Invoke-Expression* or '
            '*FromBase64String* or *-enc* or *-EncodedCommand*) '
            'or file.name:*.{jpg,png,gif,txt,doc} and file.path:(*\\Temp\\* or */tmp/*)'
        ),
        "splunk_spl": (
            '{{INDEX}} {{SOURCETYPE}} '
            '(command_line="*base64*" OR command_line="*IEX*" OR command_line="*-enc*" '
            'OR command_line="*Invoke-Expression*" OR command_line="*FromBase64String*") '
            '| table _time, host, user, process, command_line'
        ),
        "sentinel_kql": (
            'DeviceProcessEvents\n'
            '| where ProcessCommandLine has_any ("base64", "IEX", "-enc", '
            '         "Invoke-Expression", "FromBase64String", "-EncodedCommand")\n'
            '| project Timestamp, DeviceName, AccountName, ProcessCommandLine, '
            '          InitiatingProcessFileName\n'
            '| order by Timestamp desc'
        ),
        "qradar_aql": (
            'SELECT "{{SOURCE_IP}}", username, "Command Line", "Process Name" '
            'FROM events '
            'WHERE "Command Line" ILIKE \'%base64%\' OR "Command Line" ILIKE \'%-enc%\' '
            '  OR "Command Line" ILIKE \'%IEX%\' '
            'LAST 24 HOURS'
        ),
        "log_patterns": [
            "PowerShell with -EncodedCommand or -enc flag (Base64 payload)",
            "Invoke-Expression (IEX) in PowerShell command line",
            "Long Base64 strings in process command line arguments",
            "Executable files with misleading extensions (.jpg.exe, .pdf.bat)",
            "Scripts stored in alternate data streams (file.txt:hidden.ps1)",
            "Obfuscated VBScript or JScript in Temp or AppData directories",
        ],
    },

    # ── T1110 — Brute Force ───────────────────────────────
    "T1110": {
        "title": "Brute Force",
        "elastic_kql": (
            'event.action:"failed_logon" and '
            'not source.ip:(10.0.0.0/8 or 172.16.0.0/12 or 192.168.0.0/16)'
        ),
        "splunk_spl": (
            '{{INDEX}} {{SOURCETYPE}} '
            'action=failure OR action=blocked OR EventCode=4625 '
            'NOT src_ip IN (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16) '
            '| bucket span=5m _time | stats count as failures by _time, src_ip, user '
            '| where failures > 10 | sort - failures'
        ),
        "sentinel_kql": (
            'SecurityEvent\n'
            '| where EventID == 4625\n'
            '    and not ipv4_is_private(IpAddress)\n'
            '| summarize failures = count() by bin(TimeGenerated, 5m), IpAddress, TargetAccount\n'
            '| where failures > 10\n'
            '| order by failures desc'
        ),
        "qradar_aql": (
            'SELECT sourceip, username, COUNT(*) AS failures '
            'FROM events '
            'WHERE category = \'Authentication\' AND "Authentication outcome" = \'failure\' '
            '  AND NOT INCIDR(\'10.0.0.0/8\', sourceip) '
            'GROUP BY sourceip, username '
            'HAVING COUNT(*) > 10 '
            'LAST 1 HOURS'
        ),
        "log_patterns": [
            "More than 10 failed authentication attempts from a single IP in 5 minutes",
            "Sequential username enumeration attempts (admin, administrator, user, root…)",
            "Authentication failures followed by a successful login from same IP",
            "Password spray pattern: same password tried against many different accounts",
            "Failed login attempts at unusual hours from external IPs",
        ],
    },

    # ── T1003 — OS Credential Dumping ─────────────────────
    "T1003": {
        "title": "OS Credential Dumping",
        "elastic_kql": (
            '(process.name:lsass.exe and event.action:"process_accessed") '
            'or process.name:(mimikatz.exe or procdump.exe or wce.exe or pwdump*.exe) '
            'or (process.name:ntdsutil.exe and process.command_line:*ntds*)'
        ),
        "splunk_spl": (
            '{{INDEX}} {{SOURCETYPE}} '
            '(target_process="*lsass.exe*" granted_access IN ("0x1010","0x1410","0x147a")) '
            'OR (process IN ("mimikatz.exe","procdump.exe","wce.exe","ntdsutil.exe")) '
            '| table _time, host, user, process, target_process, granted_access'
        ),
        "sentinel_kql": (
            'DeviceEvents\n'
            '| where (ActionType == "OpenProcess" and TargetProcessFileName =~ "lsass.exe"\n'
            '         and ProcessTokenElevationType == "Full")\n'
            '    or InitiatingProcessFileName in~ ("mimikatz.exe","procdump.exe","wce.exe")\n'
            '| project Timestamp, DeviceName, AccountName, InitiatingProcessFileName, '
            '          TargetProcessFileName, GrantedAccess\n'
            '| order by Timestamp desc'
        ),
        "qradar_aql": (
            'SELECT "{{SOURCE_IP}}", username, "Process Name", "Target Process" '
            'FROM events '
            'WHERE "Target Process" LIKE \'%lsass%\' '
            '   OR "Process Name" IN (\'mimikatz.exe\', \'procdump.exe\', \'ntdsutil.exe\') '
            'LAST 24 HOURS'
        ),
        "log_patterns": [
            "Process access to lsass.exe with PROCESS_VM_READ permissions",
            "Known credential dumping tool execution (mimikatz, wce, fgdump)",
            "NTDSUTIL with IFM or ntds keywords in command line",
            "Volume shadow copy creation followed by NTDS.dit access",
            "Unusual registry access to SAM, SECURITY, or SYSTEM hives",
            "Event ID 4688 with procdump.exe or similar in command line",
        ],
    },

    # ── T1021 — Remote Services ───────────────────────────
    "T1021": {
        "title": "Remote Services",
        "elastic_kql": (
            '(event.code:"4624" and winlog.event_data.LogonType:("3" or "10")) '
            'or (network.transport:tcp and destination.port:(445 or 3389 or 22) '
            '    and not source.ip:(10.0.0.0/8 or 172.16.0.0/12 or 192.168.0.0/16))'
        ),
        "splunk_spl": (
            '{{INDEX}} {{SOURCETYPE}} '
            'EventCode=4624 (LogonType=3 OR LogonType=10) '
            'NOT src_ip IN (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16) '
            '| stats count by src_ip, dest_ip, user, LogonType | sort - count'
        ),
        "sentinel_kql": (
            'SecurityEvent\n'
            '| where EventID == 4624 and LogonType in (3, 10)\n'
            '    and not ipv4_is_private(IpAddress)\n'
            '| project TimeGenerated, IpAddress, TargetUserName, LogonType, WorkstationName\n'
            '| order by TimeGenerated desc'
        ),
        "qradar_aql": (
            'SELECT sourceip, username, "Event Category", "Logon Type" '
            'FROM events '
            'WHERE "Event Category" = \'Authentication\' AND "Logon Type" IN (3, 10) '
            '  AND NOT INCIDR(\'10.0.0.0/8\', sourceip) '
            'LAST 24 HOURS'
        ),
        "log_patterns": [
            "Network logons (type 3) from unusual source IPs at off-hours",
            "RDP connections from IPs not in approved list",
            "Service account used for interactive remote login",
            "Pass-the-hash indicator: NTLMv2 logon with anomalous workstation name",
            "Successful SMB connection to ADMIN$ or C$ share from external host",
        ],
    },

    # ── T1071 — Application Layer Protocol (C2) ───────────
    "T1071": {
        "title": "Application Layer Protocol (C2)",
        "elastic_kql": (
            '(http.request.method:POST and url.path.length > 200) '
            'or (dns.question.name:(*duckdns* or *.onion or *.bit) '
            '    and not source.ip:(10.0.0.0/8 or 172.16.0.0/12 or 192.168.0.0/16)) '
            'or user_agent.original:(python-requests* or Go-http-client* or "curl/*")'
        ),
        "splunk_spl": (
            '{{INDEX}} {{SOURCETYPE}} '
            '(method=POST bytes > 5000 '
            'OR (user_agent="*python-requests*" OR user_agent="*Go-http-client*" OR user_agent="*curl*")) '
            'NOT dest IN (known_good_ips) '
            '| stats count, sum(bytes) as total_bytes by src_ip, dest, user_agent | sort - count'
        ),
        "sentinel_kql": (
            'NetworkCommunicationEvents\n'
            '| where RemoteUrl contains_any ("duckdns", "ngrok", "serveo")\n'
            '    or (Protocol == "Tcp" and RemotePort in (4444, 8080, 8443, 1337))\n'
            '| project Timestamp, DeviceName, LocalIP, RemoteIP, RemoteUrl, RemotePort\n'
            '| order by Timestamp desc'
        ),
        "qradar_aql": (
            'SELECT sourceip, destinationip, destinationport, "User Agent", BYTESOUT '
            'FROM events '
            'WHERE "User Agent" ILIKE \'%python%\' OR "User Agent" ILIKE \'%curl%\' '
            '   OR destinationport IN (4444, 8080, 8443, 1337, 31337) '
            'LAST 24 HOURS'
        ),
        "log_patterns": [
            "Beaconing pattern: regular interval connections to a single external IP",
            "Unusual User-Agent strings (python-requests, curl, Go-http-client)",
            "Large outbound data transfers to unusual external IP ranges",
            "HTTP POST requests to newly registered or low-reputation domains",
            "DNS queries to dynamic DNS providers (duckdns.org, no-ip.com, ngrok.io)",
            "Encrypted C2 over uncommon ports (4444, 31337, 1337)",
        ],
    },

    # ── T1095 — Non-Application Layer Protocol ────────────
    "T1095": {
        "title": "Non-Application Layer Protocol (C2)",
        "elastic_kql": (
            '(network.transport:icmp and network.bytes > 64) '
            'or (network.transport:(gre or esp or ah)) '
            'or (destination.port:53 and dns.question.name.length > 50)'
        ),
        "splunk_spl": (
            '{{INDEX}} {{SOURCETYPE}} '
            '(protocol=icmp bytes > 64) OR (protocol=gre) '
            'OR (dest_port=53 uri_length > 50) '
            '| stats sum(bytes) as total_bytes, count by src_ip, dest_ip, protocol '
            '| sort - total_bytes'
        ),
        "sentinel_kql": (
            'NetworkCommunicationEvents\n'
            '| where Protocol in ("ICMP", "GRE", "ESP")\n'
            '    or (RemotePort == 53 and strlen(RemoteUrl) > 50)\n'
            '| project Timestamp, DeviceName, LocalIP, RemoteIP, Protocol, '
            '          BytesSent, BytesReceived\n'
            '| order by BytesSent desc'
        ),
        "qradar_aql": (
            'SELECT sourceip, destinationip, protocolid, BYTESOUT, BYTESIN '
            'FROM events '
            'WHERE protocolid IN (1, 47, 50, 51) '  # ICMP, GRE, ESP, AH
            '   OR (destinationport = 53 AND BYTESOUT > 100) '
            'LAST 24 HOURS'
        ),
        "log_patterns": [
            "ICMP packets with unusually large payloads (> 64 bytes) — ICMP tunneling",
            "GRE or ESP tunnels to external IPs not in VPN infrastructure",
            "Abnormally long DNS query strings (DNS tunneling indicator)",
            "High volume of DNS TXT record requests from a single host",
            "Unusual protocol IDs in firewall logs (not TCP/UDP/ICMP)",
        ],
    },
}

# ── Default fallback template ─────────────────────────────
TECHNIQUE_QUERIES["DEFAULT"] = {
    "title": "Suspicious Activity",
    "elastic_kql": (
        'event.action:("process_created" or "network_connection" or "file_created") '
        'and not source.ip:(10.0.0.0/8 or 172.16.0.0/12 or 192.168.0.0/16)'
    ),
    "splunk_spl": (
        '{{INDEX}} {{SOURCETYPE}} '
        '(action=allowed OR action=success) NOT src_ip IN (10.0.0.0/8, 172.16.0.0/12) '
        '| stats count by src_ip, dest_ip, action | sort - count'
    ),
    "sentinel_kql": (
        '{{TABLE}}\n'
        '| where not ipv4_is_private(SourceIP)\n'
        '| project TimeGenerated, SourceIP, DestinationIP, Action, Protocol\n'
        '| order by TimeGenerated desc'
    ),
    "qradar_aql": (
        'SELECT sourceip, destinationip, username, "Event Category" '
        'FROM events '
        'WHERE "Severity" >= 5 AND NOT INCIDR(\'10.0.0.0/8\', sourceip) '
        'LAST 24 HOURS'
    ),
    "log_patterns": [
        "Unexpected process execution or network connections",
        "Authentication events from external IP addresses",
        "Anomalous data volumes leaving the network",
        "Unexpected file creation in system directories",
    ],
}


# ── Public API ────────────────────────────────────────────

def get_siem_queries(
    technique_id: str,
    cve_id: str = "",
    product: str = "",
    cwe_ids: list[str] | None = None,
    detection_context: dict | None = None,
) -> dict:
    """
    Return SIEM queries for a CVE/technique pair.
    Selection order: ATT&CK technique template → class template (from unified
    router) → DEFAULT. Substitutes {CVE_ID} and {PRODUCT} placeholders.
    """
    prefix = (technique_id or "").strip().upper()[:5]
    detection_class = _resolve_detection_class(
        {
            "technique_id": technique_id,
            "cwe_ids": cwe_ids,
            "detection_context": detection_context,
        }
    )
    if prefix in TECHNIQUE_QUERIES:
        template = dict(TECHNIQUE_QUERIES[prefix])
    else:
        template = dict(
            CLASS_QUERIES.get(detection_class, TECHNIQUE_QUERIES["DEFAULT"])
        )

    subs = {
        "{CVE_ID}": cve_id or "CVE-XXXX-XXXXX",
        "{PRODUCT}": product or "affected_product",
    }

    result: dict = {
        "title": template.get("title", "Suspicious Activity"),
        "detection_class": detection_class,
    }
    for platform in ("elastic_kql", "splunk_spl", "sentinel_kql", "qradar_aql"):
        q = template.get(platform, "")
        for k, v in subs.items():
            q = q.replace(k, v)
        result[platform] = {
            "query": q,
            "notes": FIELD_NOTES.get(platform, ""),
        }
    result["log_patterns"] = template.get("log_patterns", [])
    return result
