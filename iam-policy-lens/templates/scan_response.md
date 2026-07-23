# IAM Scan Results Response Template

Use this template when summarizing GCP IAM scan results and Terraform updates for the user:

IAM Helper Scan Results — {{ AGENT_OR_APP_NAME }}
The IAM Helper analyzed {{ FILE_COUNT }} {{ LANGUAGE }} files and detected calls to {{ SERVICE_COUNT }} GCP service areas. The following roles were detected:

| Role | Detected API Usages |
| :--- | :--- |
{{ ROLE_TABLE_ROWS }}

If output was written to a Terraform file follow this template:
  - Describe what was written to {{ TERRAFORM_FILE_PATH }}

If no output was writen to a Terraform file, include the TF snippet in the output.

# Hints
- Use iteration in Terraform config whenever possible
- Generate lean Terraform scripts, do not add excessive comments.
- DO NOT RECOMMEND ANY FINER-GRAINED ROLES IN THE OUTPUT
