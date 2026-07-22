# Job Outreach, Application Tracking & CRM Engine

This document details the architecture, data models, copy copywriting generators, scheduling, and CLI details for the Outreach and CRM subsystem implemented in Phase 2.4.

---

## 1. CRM Lifecycle Workflow

Hiring Radar automates outreach drafting and scheduling asynchronously after recommendations are generated:

```
  Discovery Completed
            │
            ▼
 Company Intelligence
            │
            ▼
Recommendation Engine
            │
            ▼
Application Prepare Workflow (recommend_outreach)
            │
            ▼
┌──────────────────────────────────────┐
│          OutreachEngine              │
├──────────────────────────────────────┤
│  1. Run resume tailoring signals     │
│  2. Generate cover letter            │
│  3. Generate email copy              │
│  4. Generate LinkedIn message        │
│  5. Generate referral requests       │
│  6. Generate follow-up schedule      │
│  7. Save Application CRM record      │
│  8. Write to timeline history        │
└──────────────────┬───────────────────┘
                   │
                   ▼
       output/applications.json
```

---

## 2. CRM Data Schema

CRM applications are persisted to `output/applications.json` with the following schema:

```json
{
  "company_key": "stripe.com",
  "status": "Prepared",
  "applied_date": null,
  "resume_version": null,
  "notes": ["Tailoring suggestions: ..."],
  "last_contact_date": null,
  "candidate": {
    "skills": ["Python", "Systems"],
    "years_experience": 5.0
  },
  "company": {
    "name": "Stripe",
    "domain": "stripe.com"
  },
  "job": {
    "job_title": "Senior Infrastructure Engineer",
    "job_url": "https://stripe.com/1"
  },
  "cover_letter_version": "...",
  "messages": [
    {
      "channel": "email",
      "subject": "...",
      "content": "...",
      "generated_at": "..."
    },
    {
      "channel": "linkedin",
      "content": "...",
      "generated_at": "..."
    }
  ],
  "timeline": [
    {
      "event": "Application created",
      "description": "Outreach drafts prepared and follow-up schedule initialized.",
      "timestamp": "..."
    }
  ],
  "followup_schedule": [
    {
      "day": 0,
      "action": "Submit application on career portal",
      "template_name": "portal_apply",
      "status": "pending"
    },
    {
      "day": 5,
      "action": "Send first recruiter follow-up email",
      "template_name": "recruiter_followup",
      "status": "pending"
    }
  ],
  "next_followup": "Day 0: Submit application on career portal",
  "last_updated": "..."
}
```

---

## 3. Human-in-the-Loop Copy Generation

Hiring Radar never submits applications or sends messages automatically.

All messaging materials are generated as **drafts** and made viewable or copy-pastable in the console. The user remains in complete control over every external touchpoint.

- **Cover Letters**: Tailored using the `cover_letter.v1` prompt to align candidate skills against company mission.
- **Emails**: Tailored via the `outreach_email.v1` prompt.
- **LinkedIn Recruiter Notes**: Drafted strictly under 300 characters using `linkedin_message.v1`.
- **Referral Requests**: Formulated for networking outreach via `referral_request.v1`.

---

## 4. Background Execution Trigger

A background Completion listener is registered in `ServiceContainer`.

Once the `"recommend_job"` workflow completes:
1. The background runtime automatically enqueues `"recommend_outreach"`.
2. The `"recommend_outreach"` workflow executes the `OutreachPrepareStep` for the top 5 recommendation matches.

---

## 5. CLI Reference

```bash
# List all current CRM applications and stages
hiring-radar apply list

# Manually execute the CRM draft preparation pipeline for a company
hiring-radar apply prepare stripe

# View the generated cold email outreach draft
hiring-radar apply email stripe

# View the LinkedIn recruiter message draft
hiring-radar apply linkedin stripe

# View the generated cover letter draft
hiring-radar apply cover-letter stripe

# View the referral request draft
hiring-radar apply referral stripe

# View the application event timeline
hiring-radar apply timeline stripe

# Force regenerate drafts and schedules for all CRM records
hiring-radar apply refresh
```
