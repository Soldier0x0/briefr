/** Curated autocomplete data — no user profile content. */

export const OS_SUGGESTIONS = [
  'Windows Server 2022',
  'Ubuntu 22.04',
  'RHEL 9',
  'Debian 13',
  'macOS Sonoma',
]

export const APP_CATEGORIES = [
  'Web Server',
  'Database',
  'Network Device',
  'Cloud Platform',
  'Security Tool',
  'Container',
  'Other',
]

/** 50 common enterprise products with optional vendor hint for CPE matching. */
export const ENTERPRISE_PRODUCTS = [
  { name: 'Apache httpd', vendor: 'apache', product: 'http_server' },
  { name: 'nginx', vendor: 'nginx', product: 'nginx' },
  { name: 'Microsoft IIS', vendor: 'microsoft', product: 'internet_information_services' },
  { name: 'Tomcat', vendor: 'apache', product: 'tomcat' },
  { name: 'PostgreSQL', vendor: 'postgresql', product: 'postgresql' },
  { name: 'MySQL', vendor: 'oracle', product: 'mysql' },
  { name: 'Microsoft SQL Server', vendor: 'microsoft', product: 'sql_server' },
  { name: 'MongoDB', vendor: 'mongodb', product: 'mongodb' },
  { name: 'Redis', vendor: 'redis', product: 'redis' },
  { name: 'Elasticsearch', vendor: 'elastic', product: 'elasticsearch' },
  { name: 'OpenSSL', vendor: 'openssl', product: 'openssl' },
  { name: 'OpenSSH', vendor: 'openssh', product: 'openssh' },
  { name: 'BIND', vendor: 'isc', product: 'bind' },
  { name: 'Cisco IOS', vendor: 'cisco', product: 'ios' },
  { name: 'Cisco ASA', vendor: 'cisco', product: 'adaptive_security_appliance_software' },
  { name: 'Fortinet FortiOS', vendor: 'fortinet', product: 'fortios' },
  { name: 'Palo Alto PAN-OS', vendor: 'paloaltonetworks', product: 'pan-os' },
  { name: 'VMware vCenter', vendor: 'vmware', product: 'vcenter_server' },
  { name: 'VMware ESXi', vendor: 'vmware', product: 'esxi' },
  { name: 'Docker', vendor: 'docker', product: 'docker' },
  { name: 'Kubernetes', vendor: 'kubernetes', product: 'kubernetes' },
  { name: 'Jenkins', vendor: 'jenkins', product: 'jenkins' },
  { name: 'GitLab', vendor: 'gitlab', product: 'gitlab' },
  { name: 'Atlassian Jira', vendor: 'atlassian', product: 'jira' },
  { name: 'Confluence', vendor: 'atlassian', product: 'confluence' },
  { name: 'Splunk', vendor: 'splunk', product: 'splunk' },
  { name: 'CrowdStrike Falcon', vendor: 'crowdstrike', product: 'falcon' },
  { name: 'Microsoft Exchange', vendor: 'microsoft', product: 'exchange_server' },
  { name: 'Active Directory', vendor: 'microsoft', product: 'active_directory' },
  { name: 'Windows 11', vendor: 'microsoft', product: 'windows_11' },
  { name: 'Windows Server 2019', vendor: 'microsoft', product: 'windows_server_2019' },
  { name: 'Ubuntu Linux', vendor: 'canonical', product: 'ubuntu_linux' },
  { name: 'RHEL', vendor: 'redhat', product: 'enterprise_linux' },
  { name: 'Debian Linux', vendor: 'debian', product: 'debian_linux' },
  { name: 'macOS', vendor: 'apple', product: 'macos' },
  { name: 'PHP', vendor: 'php', product: 'php' },
  { name: 'Python', vendor: 'python', product: 'python' },
  { name: 'Node.js', vendor: 'nodejs', product: 'node.js' },
  { name: 'Java', vendor: 'oracle', product: 'jdk' },
  { name: 'Spring Framework', vendor: 'vmware', product: 'spring_framework' },
  { name: 'WordPress', vendor: 'wordpress', product: 'wordpress' },
  { name: 'Drupal', vendor: 'drupal', product: 'drupal' },
  { name: 'Citrix ADC', vendor: 'citrix', product: 'application_delivery_controller' },
  { name: 'F5 BIG-IP', vendor: 'f5', product: 'big-ip' },
  { name: 'Zabbix', vendor: 'zabbix', product: 'zabbix' },
  { name: 'Nagios', vendor: 'nagios', product: 'nagios' },
  { name: 'SAP NetWeaver', vendor: 'sap', product: 'netweaver' },
  { name: 'Oracle Database', vendor: 'oracle', product: 'database_server' },
  { name: 'IBM WebSphere', vendor: 'ibm', product: 'websphere_application_server' },
  { name: 'TeamCity', vendor: 'jetbrains', product: 'teamcity' },
]

export const AI_PRODUCTS = [
  'TensorFlow',
  'PyTorch',
  'LangChain',
  'OpenAI API',
  'Hugging Face Transformers',
  'ONNX',
  'scikit-learn',
  'Keras',
  'JAX',
  'Anthropic Claude API',
  'Ollama',
  'Stable Diffusion',
  'Other',
]

export const INDUSTRY_SECTORS = [
  'Financial Services',
  'Healthcare',
  'Government',
  'Technology',
  'Energy and OT',
  'Education',
  'Retail',
  'Telecommunications',
  'Defence',
  'Other',
]

export const CRITICALITY_LEVELS = ['Low', 'Medium', 'High', 'Critical']

export const INTERNET_FACING_OPTIONS = ['All', 'Some', 'None']

/** W5 scoring criticality (OP/SSVC) — distinct from environment.criticality labels. */
export const SCORING_CRITICALITY_OPTIONS = [
  { value: '', label: 'Not set (default)' },
  { value: 'MISSION_CRITICAL', label: 'Mission critical' },
  { value: 'IMPORTANT', label: 'Important' },
  { value: 'SUPPORTING', label: 'Supporting' },
]
