# Security Policy

We take the security of your private credentials and job application data seriously. Since Hiring Radar is a local-first platform designed to run entirely on your local machine, most security practices rely on protecting your local configuration files.

---

## Supported Versions

Since this is an open-source tool, security updates are applied directly to the main branch. Only the latest version is actively supported:

| Version | Supported |
| --- | --- |
| Latest `main` | ✅ Yes |
| < 0.1.0 | ❌ No |

---

## Reporting a Vulnerability

If you discover a security vulnerability (such as credential exposure risks, parser escapes, or remote code execution bugs), please **do not open a public issue**. Instead, report it privately:

1. Go to the **Security** tab of the GitHub repository.
2. Click on **Advisories** and select **Report a vulnerability** to submit a private security advisory.
3. We will review the report and coordinate a fix promptly.

---

## Sensitive Files & local Safety Guidelines

Please adhere to these security guidelines when operating the platform:

- **Local Configurations**: Your `.env` and `config.yaml` files contain sensitive API credentials (such as your OpenRouter API Key and Telegram Bot Token). These files are explicitly added to `.gitignore` and must **never** be committed to Git.
- **Gmail & SMTP Outreach Credentials**:
  - If you configure the SMTP outreach feature using Gmail, **never use your primary Google Account password**. You must generate and use a secure 16-character **Google App Password**. See Google's security guidance for App Passwords.
  - The SMTP mailer module inside [app/outreach/mailer.py](app/outreach/mailer.py) handles credentials securely and **never** writes or logs credentials to files or loggers.
- **Personal Data Directories**: The `resumes/` folder (holding candidate resumes) and the `output/` directory (holding `companies.json` and `applications.json` databases) contain personal career data. Both directories are added to `.gitignore` to prevent accidental public check-ins.
