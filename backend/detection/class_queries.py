"""Class-keyed SIEM query and log-pattern templates (Sprint D3).

Parallel to CWE Sigma templates — used when no ATT&CK technique is mapped.
"""

from __future__ import annotations


def _web_class_query(
    title: str,
    *,
    elastic_kql: str | None = None,
    splunk_spl: str | None = None,
    sentinel_kql: str | None = None,
    qradar_aql: str | None = None,
    log_patterns: list[str],
) -> dict:
    """Build a class template; caller must supply all four platform queries."""
    query = {
        "title": title,
        "elastic_kql": elastic_kql or "",
        "splunk_spl": splunk_spl or "",
        "sentinel_kql": sentinel_kql or "",
        "qradar_aql": qradar_aql or "",
        "log_patterns": log_patterns,
    }
    return query


def _uri_query_pack(*terms: str) -> dict[str, str]:
    """SIEM queries hunting URL/query-string terms across platforms."""
    elastic = "url.query:(" + " or ".join(f'"{t}"' for t in terms) + ")"
    splunk = (
        "{{INDEX}} {{SOURCETYPE}} "
        + "(" + " OR ".join(f'{{{{URI}}}}="*{t}*"' for t in terms) + ") "
        + "| stats count by {{SRC_IP}}, {{URI}} | sort - count"
    )
    sentinel_terms = ", ".join(f'"{t}"' for t in terms)
    sentinel = (
        "{{TABLE}}\n"
        f"| where csUriStem has_any ({sentinel_terms})\n"
        "| project TimeGenerated, cIP, csMethod, csUriStem, scStatus\n"
        "| order by TimeGenerated desc"
    )
    qradar = (
        "SELECT \"{{SOURCE_IP}}\", \"{{URL}}\", \"{{STATUS}}\" FROM events WHERE "
        + " OR ".join(f"\"{{{{URL}}}}\" LIKE '%{t}%'" for t in terms)
        + " LAST 24 HOURS"
    )
    return {
        "elastic_kql": elastic,
        "splunk_spl": splunk,
        "sentinel_kql": sentinel,
        "qradar_aql": qradar,
    }


def _path_query_pack(*terms: str) -> dict[str, str]:
    """SIEM queries hunting URL path traversal / file-path terms."""
    elastic = "url.path:(" + " or ".join(f'"{t}"' for t in terms) + ")"
    splunk = (
        "{{INDEX}} {{SOURCETYPE}} "
        + "(" + " OR ".join(f'{{{{URI}}}}="*{t}*"' for t in terms) + ") "
        + "| stats count by {{SRC_IP}}, {{URI}} | sort - count"
    )
    sentinel_terms = ", ".join(f'"{t}"' for t in terms)
    sentinel = (
        "{{TABLE}}\n"
        f"| where csUriStem has_any ({sentinel_terms})\n"
        "| project TimeGenerated, cIP, csMethod, csUriStem, scStatus\n"
        "| order by TimeGenerated desc"
    )
    qradar = (
        "SELECT \"{{SOURCE_IP}}\", \"{{URL}}\", \"{{STATUS}}\" FROM events WHERE "
        + " OR ".join(f"\"{{{{URL}}}}\" LIKE '%{t}%'" for t in terms)
        + " LAST 24 HOURS"
    )
    return {
        "elastic_kql": elastic,
        "splunk_spl": splunk,
        "sentinel_kql": sentinel,
        "qradar_aql": qradar,
    }


def _body_query_pack(*terms: str) -> dict[str, str]:
    """SIEM queries hunting HTTP body / payload terms."""
    elastic = "http.request.body:(" + " or ".join(f'"{t}"' for t in terms) + ")"
    splunk = (
        "{{INDEX}} {{SOURCETYPE}} "
        + "(" + " OR ".join(f'_raw="*{t}*"' for t in terms) + ") "
        + "| stats count by {{SRC_IP}}, {{URI}} | sort - count"
    )
    sentinel_terms = ", ".join(f'"{t}"' for t in terms)
    sentinel = (
        "{{TABLE}}\n"
        f"| where RequestBody has_any ({sentinel_terms})\n"
        "| project TimeGenerated, cIP, csMethod, csUriStem, RequestBody\n"
        "| order by TimeGenerated desc"
    )
    qradar = (
        "SELECT \"{{SOURCE_IP}}\", \"{{URL}}\", \"{{STATUS}}\" FROM events WHERE "
        + " OR ".join(f"UTF8(payload) LIKE '%{t}%'" for t in terms)
        + " LAST 24 HOURS"
    )
    return {
        "elastic_kql": elastic,
        "splunk_spl": splunk,
        "sentinel_kql": sentinel,
        "qradar_aql": qradar,
    }


CLASS_QUERIES: dict[str, dict] = {
    "path_traversal": _web_class_query(
        "Path Traversal",
        **_path_query_pack("../", "..\\", "%2e%2e", "/etc/passwd", "web.config"),
        log_patterns=[
            "Directory traversal sequences (../, ..\\, %2e%2e) in URL paths",
            "Sensitive file paths (/etc/passwd, web.config, boot.ini) in requests",
            "URL-encoded dot segments bypassing path normalization",
            "Repeated 404s probing parent directories from one source IP",
        ],
    ),
    "cmd_injection": _web_class_query(
        "OS Command Injection",
        **_uri_query_pack(";id", "|whoami", "cmd.exe /c", "/bin/sh", "&&wget"),
        log_patterns=[
            "Shell metacharacters (;, |, &&, `) in query or form parameters",
            "whoami/id/curl/wget strings in HTTP request bodies",
            "cmd.exe or /bin/sh invoked via web parameters",
            "Unexpected outbound connections after suspicious POST requests",
        ],
    ),
    "sqli": _web_class_query(
        "SQL Injection",
        **_uri_query_pack(
            "UNION SELECT",
            "' OR '1'='1",
            "SLEEP(",
            "information_schema",
        ),
        log_patterns=[
            "UNION SELECT or tautology clauses in query strings",
            "Time-based SQL functions (SLEEP, BENCHMARK) in parameters",
            "information_schema or xp_cmdshell references in HTTP logs",
            "Database error messages in HTTP 500 responses",
        ],
    ),
    "xss": _web_class_query(
        "Cross-Site Scripting",
        **_uri_query_pack("<script", "onerror=", "javascript:", "%3Cscript"),
        log_patterns=[
            "Unescaped <script> tags in reflected request parameters",
            "Event-handler injection (onerror=, onload=) in URLs",
            "javascript: pseudo-protocol in query strings",
            "HTML entity encoding bypass attempts (%3Cscript)",
        ],
    ),
    "deserialization": _web_class_query(
        "Insecure Deserialization",
        **_body_query_pack("rO0AB", "aced0005", "ysoserial", "__VIEWSTATE"),
        log_patterns=[
            "Java serialization magic bytes (rO0AB, aced0005) in POST bodies",
            "ysoserial gadget chain strings in HTTP traffic",
            "Abnormally large __VIEWSTATE or serialized blobs",
            "Unexpected process spawn after deserialization endpoints are hit",
        ],
    ),
    "code_injection": _web_class_query(
        "Code Injection",
        **_uri_query_pack("eval(", "assert(", "{{", "${"),
        log_patterns=[
            "eval/assert calls in user-controlled input",
            "Template delimiter injection ({{ }}, ${ })",
            "base64_decode combined with dynamic execution strings",
            "Server-side template errors after crafted payloads",
        ],
    ),
    "unsafe_upload": _web_class_query(
        "Unrestricted File Upload",
        elastic_kql=(
            'url.path:(".jsp" or ".php" or ".aspx" or ".ashx" or ".war") '
            "and http.request.method:POST"
        ),
        splunk_spl=(
            "{{INDEX}} {{SOURCETYPE}} "
            '({{URI}}="*.jsp*" OR {{URI}}="*.php*" OR {{URI}}="*.aspx*" '
            'OR {{URI}}="*.ashx*" OR {{URI}}="*.war*") method=POST '
            "| stats count by {{SRC_IP}}, {{URI}} | sort - count"
        ),
        sentinel_kql=(
            "{{TABLE}}\n"
            '| where csMethod == "POST" and csUriStem has_any (".jsp", ".php", ".aspx", ".ashx", ".war")\n'
            "| project TimeGenerated, cIP, csMethod, csUriStem, scStatus\n"
            "| order by TimeGenerated desc"
        ),
        qradar_aql=(
            'SELECT "{{SOURCE_IP}}", "{{URL}}", "{{STATUS}}" FROM events WHERE '
            "\"{{URL}}\" LIKE '%.php%' OR \"{{URL}}\" LIKE '%.jsp%' "
            "OR \"{{URL}}\" LIKE '%.aspx%' LAST 24 HOURS"
        ),
        log_patterns=[
            "Executable extensions (.jsp, .php, .aspx) in upload paths",
            "Multipart POSTs with double extensions (file.php.jpg)",
            "New web shells appearing under upload directories",
            "HTTP 200 on upload endpoints followed by execution attempts",
        ],
    ),
    "ssrf": _web_class_query(
        "Server-Side Request Forgery",
        **_uri_query_pack(
            "169.254.169.254",
            "metadata.google",
            "file://",
            "gopher://",
        ),
        log_patterns=[
            "Cloud metadata IP (169.254.169.254) in URL parameters",
            "file:// or gopher:// schemes in server-side fetch parameters",
            "Internal localhost callbacks from application servers",
            "Unusual egress to link-local or RFC1918 from app tier",
        ],
    ),
    "xxe": _web_class_query(
        "XML External Entity",
        **_body_query_pack("<!ENTITY", 'SYSTEM "file://', 'SYSTEM "http://'),
        log_patterns=[
            "DOCTYPE ENTITY declarations in XML request bodies",
            "SYSTEM file:// or http:// references in XML payloads",
            "Large XML posts to legacy SOAP/import endpoints",
            "File read errors or unusual file access after XML uploads",
        ],
    ),
    "auth_bypass": _web_class_query(
        "Authentication Bypass",
        elastic_kql=(
            'url.path:("/admin" or "/api/login" or "/api/auth") '
            "and http.response.status_code:(200 or 302)"
        ),
        splunk_spl=(
            "{{INDEX}} {{SOURCETYPE}} "
            '({{URI}}="*/admin*" OR {{URI}}="*/api/login*" OR {{URI}}="*/api/auth*") '
            "(status=200 OR status=302) "
            "| stats count by {{SRC_IP}}, {{URI}}, status | sort - count"
        ),
        sentinel_kql=(
            "{{TABLE}}\n"
            '| where csUriStem has_any ("/admin", "/api/login", "/api/auth")\n'
            '| where scStatus in ("200", "302")\n'
            "| project TimeGenerated, cIP, csMethod, csUriStem, scStatus\n"
            "| order by TimeGenerated desc"
        ),
        qradar_aql=(
            'SELECT "{{SOURCE_IP}}", "{{URL}}", "{{STATUS}}" FROM events WHERE '
            "\"{{URL}}\" LIKE '%/admin%' OR \"{{URL}}\" LIKE '%/api/login%' "
            "LAST 24 HOURS"
        ),
        log_patterns=[
            "Direct access to /admin or privileged API paths without prior auth",
            "Authentication endpoints returning 200 without failed-login precursors",
            "Privilege or bypass keywords in request parameters",
            "Session cookies issued after anomalous login attempts",
        ],
    ),
    "memory_corruption": {
        "title": "Memory Corruption",
        "elastic_kql": (
            'event.code:(1000 or 1001) or message:("segfault" or "SIGSEGV" or "core dumped")'
        ),
        "splunk_spl": (
            "{{INDEX}} {{SOURCETYPE}} "
            '(EventCode=1000 OR EventCode=1001 OR message="*segfault*" OR message="*SIGSEGV*") '
            "| stats count by {{PROCESS}}, message | sort - count"
        ),
        "sentinel_kql": (
            "Event\n"
            '| where EventID in (1000, 1001) or Message has_any ("segfault", "SIGSEGV")\n'
            "| project TimeGenerated, Computer, EventID, Message\n"
            "| order by TimeGenerated desc"
        ),
        "qradar_aql": (
            'SELECT "Process Name", "Event Category", "Severity" '
            "FROM events "
            "WHERE \"Event Category\" LIKE '%crash%' OR \"Event Name\" LIKE '%fault%' "
            "LAST 24 HOURS"
        ),
        "log_patterns": [
            "Application crash events (Event ID 1000/1001) on exposed services",
            "segfault or SIGSEGV messages in application logs",
            "Core dumps following malformed input to native parsers",
            "Correlate crashes with recent exploit/PoC activity for the CVE",
        ],
    },
    "default_credentials": {
        "title": "Default Credentials",
        "elastic_kql": (
            'event.category:authentication and user.name:(admin or root or guest) '
            "and event.outcome:success"
        ),
        "splunk_spl": (
            "{{INDEX}} {{SOURCETYPE}} "
            "(user=admin OR user=root OR user=guest) action=success "
            "| stats count by user, src_ip | sort - count"
        ),
        "sentinel_kql": (
            "SecurityEvent\n"
            '| where Account in ("admin", "root", "guest") and EventID == 4624\n'
            "| project TimeGenerated, Account, IpAddress, LogonType\n"
            "| order by TimeGenerated desc"
        ),
        "qradar_aql": (
            'SELECT username, sourceip, "Event Category" '
            "FROM events "
            "WHERE username IN ('admin', 'root', 'guest') "
            "LAST 24 HOURS"
        ),
        "log_patterns": [
            "Successful logins with vendor-default account names",
            "admin/root/guest authentications from external IPs",
            "First-time use of factory-default credentials after CVE disclosure",
            "Password reset or onboarding flows abused for default accounts",
        ],
    },
}
