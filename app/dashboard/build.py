"""Dashboard generator for hiring-radar.

Produces a fully static, self-contained single-HTML dashboard representing
the current discovered companies database.
"""

from __future__ import annotations

import json
from pathlib import Path
import orjson

from app.models import Company


_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en" class="h-full bg-slate-950 text-slate-100">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Hiring Radar Dashboard</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Outfit:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    body {
      font-family: 'Inter', sans-serif;
    }
    h1, h2, h3 {
      font-family: 'Outfit', sans-serif;
    }
  </style>
</head>
<body class="h-full flex flex-col">
  <!-- Header -->
  <header class="border-b border-slate-800 bg-slate-900/50 backdrop-blur sticky top-0 z-50">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
      <div class="flex items-center space-x-3">
        <span class="text-2xl">📡</span>
        <h1 class="text-xl font-bold bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent">Hiring Radar Dashboard</h1>
      </div>
      <div class="text-sm text-slate-400" id="last-generated-time">
        Generated: <span class="text-slate-200" id="generated-timestamp"></span>
      </div>
    </div>
  </header>

  <!-- Main Content -->
  <main class="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <!-- Summary Cards -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
      <div class="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-lg">
        <div class="text-sm font-medium text-slate-400 mb-1">Total Companies</div>
        <div class="text-3xl font-bold text-cyan-400" id="stat-total-companies">0</div>
      </div>
      <div class="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-lg">
        <div class="text-sm font-medium text-slate-400 mb-1">Total Active Jobs</div>
        <div class="text-3xl font-bold text-blue-500" id="stat-total-jobs">0</div>
      </div>
      <div class="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-lg">
        <div class="text-sm font-medium text-slate-400 mb-1">Enriched with AI</div>
        <div class="text-3xl font-bold text-indigo-400" id="stat-enriched-ai">0</div>
      </div>
    </div>

    <!-- Table Container -->
    <div class="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-xl">
      <div class="overflow-x-auto">
        <table class="w-full text-left border-collapse">
          <thead>
            <tr class="bg-slate-950 border-b border-slate-800 text-xs font-semibold text-slate-400 uppercase tracking-wider">
              <th class="py-4 px-6">Company</th>
              <th class="py-4 px-6">Platform / Source</th>
              <th class="py-4 px-6 text-center">Jobs Count</th>
              <th class="py-4 px-6 text-center">Email Status</th>
              <th class="py-4 px-6 text-center">AI Summary</th>
              <th class="py-4 px-6">Last Updated</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-800/50" id="companies-table-body">
            <!-- Dynamically populated -->
          </tbody>
        </table>
      </div>
    </div>
  </main>

  <!-- Embed data -->
  <script>
    const COMPANIES = __COMPANIES_JSON_PLACEHOLDER__;
  </script>

  <script>
    document.addEventListener("DOMContentLoaded", () => {
      document.getElementById("generated-timestamp").textContent = new Date().toLocaleString();
      
      if (typeof COMPANIES === 'undefined' || !COMPANIES) {
        console.error("COMPANIES is not defined.");
        return;
      }

      // 1. Stats
      const totalCompanies = COMPANIES.length;
      let totalJobs = 0;
      let enrichedCount = 0;

      COMPANIES.forEach(c => {
        totalJobs += (c.jobs ? c.jobs.length : 0);
        if (c.ai_summary) {
          enrichedCount++;
        }
      });

      document.getElementById("stat-total-companies").textContent = totalCompanies;
      document.getElementById("stat-total-jobs").textContent = totalJobs;
      document.getElementById("stat-enriched-ai").textContent = `${enrichedCount} / ${totalCompanies}`;

      // 2. Populate table
      const tbody = document.getElementById("companies-table-body");
      if (COMPANIES.length === 0) {
        tbody.innerHTML = `
          <tr>
            <td colspan="6" class="py-12 text-center text-slate-400 italic">
              No companies discovered yet. Run discovery and scraper first.
            </td>
          </tr>
        `;
        return;
      }

      COMPANIES.forEach(c => {
        const row = document.createElement("tr");
        row.className = "hover:bg-slate-800/30 transition-colors duration-150";

        // Company info cell
        const nameCell = document.createElement("td");
        nameCell.className = "py-4 px-6";
        const nameDiv = document.createElement("div");
        nameDiv.className = "font-semibold text-slate-100";
        nameDiv.textContent = c.name;
        nameCell.appendChild(nameDiv);
        if (c.website) {
          const webLink = document.createElement("a");
          webLink.href = c.website;
          webLink.target = "_blank";
          webLink.className = "text-xs text-cyan-400 hover:underline block mt-0.5";
          webLink.textContent = c.website;
          nameCell.appendChild(webLink);
        }
        row.appendChild(nameCell);

        // Platform / Source cell
        const sourceCell = document.createElement("td");
        sourceCell.className = "py-4 px-6 text-sm text-slate-300";
        const sourceSpan = document.createElement("span");
        sourceSpan.className = "px-2.5 py-1 rounded-full text-xs font-medium bg-slate-950 border border-slate-800 text-slate-300";
        sourceSpan.textContent = c.ats_platform || (c.jobs && c.jobs[0] ? c.jobs[0].source : "feed");
        sourceCell.appendChild(sourceSpan);
        row.appendChild(sourceCell);

        // Jobs count cell
        const jobsCell = document.createElement("td");
        jobsCell.className = "py-4 px-6 text-center text-sm font-semibold text-slate-100";
        jobsCell.textContent = c.jobs ? c.jobs.length : 0;
        row.appendChild(jobsCell);

        // Email status cell
        const emailCell = document.createElement("td");
        emailCell.className = "py-4 px-6 text-center";
        const hasEmail = c.recruiter_email || (c.generic_emails && c.generic_emails.length > 0);
        const emailBadge = document.createElement("span");
        if (hasEmail) {
          emailBadge.className = "px-2 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20";
          emailBadge.textContent = "Found";
          emailBadge.title = c.recruiter_email || c.generic_emails[0];
        } else {
          emailBadge.className = "px-2 py-0.5 rounded-full text-xs font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20";
          emailBadge.textContent = "None";
        }
        emailCell.appendChild(emailBadge);
        row.appendChild(emailCell);

        // AI summary cell
        const aiCell = document.createElement("td");
        aiCell.className = "py-4 px-6 text-center";
        const aiBadge = document.createElement("span");
        if (c.ai_summary) {
          aiBadge.className = "px-2 py-0.5 rounded-full text-xs font-semibold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20";
          aiBadge.textContent = "Set";
          aiBadge.title = c.ai_summary;
        } else {
          aiBadge.className = "px-2 py-0.5 rounded-full text-xs font-semibold bg-slate-800 text-slate-500 border border-slate-700";
          aiBadge.textContent = "Missing";
        }
        aiCell.appendChild(aiBadge);
        row.appendChild(aiCell);

        // Last updated cell
        const updatedCell = document.createElement("td");
        updatedCell.className = "py-4 px-6 text-sm text-slate-400";
        if (c.last_updated) {
          try {
            const date = new Date(c.last_updated);
            updatedCell.textContent = date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
          } catch(e) {
            updatedCell.textContent = c.last_updated;
          }
        } else {
          updatedCell.textContent = "N/A";
        }
        row.appendChild(updatedCell);

        tbody.appendChild(row);
      });
    });
  </script>
</body>
</html>
"""


def build_dashboard(input_path: Path, output_path: Path) -> None:
    """Build a static self-contained HTML dashboard from the local database.

    Loads the database JSON file, serializes the Company objects, embeds
    the data directly into the template HTML shell, and writes the output.
    """
    if not input_path.exists():
        raise FileNotFoundError(
            f"Input database not found at {input_path}. Please run discovery first."
        )

    try:
        raw_data = orjson.loads(input_path.read_bytes())
        companies = [Company.model_validate(c) for c in raw_data]
    except Exception as exc:
        raise ValueError(f"Failed to load or validate database at {input_path}: {exc}") from exc

    # Serialize companies to JSON safely.
    # Note: Pydantic v2 mode='json' converts datetime objects to strings.
    serialized_list = [c.model_dump(mode="json") for c in companies]
    embedded_json = json.dumps(serialized_list, ensure_ascii=False)

    # Embed inside HTML template
    html_content = _HTML_TEMPLATE.replace("__COMPANIES_JSON_PLACEHOLDER__", embedded_json)

    # Ensure parent directories of output exist
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_content, encoding="utf-8")
