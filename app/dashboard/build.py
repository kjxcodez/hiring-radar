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
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
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

    <!-- Charts Section -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-4">
      <!-- Chart 1: Jobs by Source -->
      <div class="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg flex flex-col justify-between h-[320px]">
        <h4 class="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-3">Jobs by Source / Platform</h4>
        <div class="flex-1 min-h-0 relative">
          <canvas id="chart-source"></canvas>
        </div>
      </div>
      <!-- Chart 2: Jobs by Country -->
      <div class="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg flex flex-col justify-between h-[320px]">
        <h4 class="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-3">Jobs by Country (Heuristic)</h4>
        <div class="flex-1 min-h-0 relative flex justify-center items-center">
          <canvas id="chart-country" class="max-h-[220px] max-w-[220px]"></canvas>
        </div>
      </div>
      <!-- Chart 3: Discoveries Over Time -->
      <div class="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg flex flex-col justify-between h-[320px]">
        <h4 class="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-3">Discoveries (Last 14 Days)</h4>
        <div class="flex-1 min-h-0 relative">
          <canvas id="chart-timeline"></canvas>
        </div>
      </div>
    </div>
    <div class="text-xs text-slate-500 italic mb-8">
      💡 Charts reflect all companies, independent of filters below.
    </div>


    <!-- Filter Bar -->
    <div class="bg-slate-900 border border-slate-800 rounded-xl p-5 mb-6 shadow-md">
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 items-end">
        <!-- Search Input -->
        <div class="lg:col-span-2">
          <label for="search-input" class="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Search Companies</label>
          <input type="text" id="search-input" placeholder="Type company name..." class="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-500 transition-colors">
        </div>
        <!-- Source/Platform Dropdown -->
        <div>
          <label for="source-select" class="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Source / ATS</label>
          <select id="source-select" class="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-cyan-500 transition-colors">
            <option value="all">All Sources</option>
          </select>
        </div>
        <!-- Checkboxes -->
        <div class="lg:col-span-2 grid grid-cols-1 sm:grid-cols-3 gap-2">
          <!-- Remote Only -->
          <label class="flex items-center space-x-2 text-sm text-slate-300 cursor-pointer select-none py-2">
            <input type="checkbox" id="remote-check" class="rounded border-slate-850 bg-slate-950 text-cyan-500 focus:ring-0">
            <span>Remote Only</span>
          </label>
          <!-- Has Email -->
          <label class="flex items-center space-x-2 text-sm text-slate-300 cursor-pointer select-none py-2">
            <input type="checkbox" id="email-check" class="rounded border-slate-850 bg-slate-950 text-cyan-500 focus:ring-0">
            <span>Has Email</span>
          </label>
          <!-- Has AI Summary -->
          <label class="flex items-center space-x-2 text-sm text-slate-300 cursor-pointer select-none py-2">
            <input type="checkbox" id="ai-check" class="rounded border-slate-850 bg-slate-950 text-cyan-500 focus:ring-0">
            <span>Has AI Summary</span>
          </label>
        </div>
      </div>
    </div>

    <!-- Results Counter -->
    <div class="text-sm text-slate-400 mb-4" id="results-counter">
      Showing <span class="text-slate-200 font-semibold" id="count-visible">0</span> of <span class="text-slate-200 font-semibold" id="count-total">0</span> companies
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


  <!-- Detail Modal Overlay -->
  <div id="detail-modal" class="hidden fixed inset-0 bg-slate-950/80 backdrop-blur flex items-center justify-center p-4 z-50">
    <div class="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-4xl max-h-[85vh] flex flex-col shadow-2xl overflow-hidden transition-all duration-350">
      <!-- Modal Header -->
      <div class="border-b border-slate-800 p-6 flex justify-between items-start bg-slate-950/30">
        <div>
          <h2 id="modal-company-name" class="text-2xl font-bold text-slate-100"></h2>
          <div id="modal-company-links" class="flex flex-wrap gap-2 mt-3"></div>
        </div>
        <button onclick="closeModal()" class="text-slate-400 hover:text-slate-200 transition-colors p-1 rounded-lg hover:bg-slate-800">
          <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <!-- Modal Body -->
      <div class="flex-1 overflow-y-auto p-6 space-y-6">
        <!-- AI Enrichment Section -->
        <div>
          <h3 class="text-lg font-bold text-slate-200 mb-3 flex items-center space-x-2">
            <span>✨</span> <span>AI Enrichment Notes</span>
          </h3>
          <div id="modal-ai-enrichment"></div>
        </div>

        <!-- Contacts Section -->
        <div>
          <h3 class="text-lg font-bold text-slate-200 mb-3 flex items-center space-x-2">
            <span>📧</span> <span>Outreach Contacts</span>
          </h3>
          <div id="modal-contacts"></div>
        </div>

        <!-- Jobs List Section -->
        <div>
          <h3 class="text-lg font-bold text-slate-200 mb-3 flex items-center space-x-2">
            <span>💼</span> <span>Active Job Openings</span>
          </h3>
          <div class="border border-slate-800 rounded-xl overflow-hidden bg-slate-950/20">
            <div class="overflow-x-auto">
              <table class="w-full text-left border-collapse">
                <thead>
                  <tr class="bg-slate-950/60 border-b border-slate-800 text-xs font-semibold text-slate-400 uppercase tracking-wider">
                    <th class="py-3 px-4">Title</th>
                    <th class="py-3 px-4">Location</th>
                    <th class="py-3 px-4 text-center">Remote</th>
                    <th class="py-3 px-4 text-right">Link</th>
                  </tr>
                </thead>
                <tbody id="modal-jobs-body">
                  <!-- Dynamically populated -->
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <!-- Operational Notes Section -->
        <div id="modal-notes-section" class="hidden">
          <h3 class="text-lg font-bold text-slate-200 mb-3 flex items-center space-x-2">
            <span>📝</span> <span>Scrape & Scrying Notes</span>
          </h3>
          <div class="bg-slate-950/40 border border-slate-800 rounded-xl p-4">
            <ul id="modal-notes-list" class="list-disc list-inside space-y-1.5 text-sm text-slate-300">
              <!-- Dynamically populated -->
            </ul>
          </div>
        </div>
      </div>
    </div>
  </div>

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

      // 2. Populate Source select dropdown options dynamically
      const sourceSelect = document.getElementById("source-select");
      const sourcesSet = new Set();
      COMPANIES.forEach(c => {
        const src = c.ats_platform || (c.jobs && c.jobs[0] ? c.jobs[0].source : "feed");
        if (src) sourcesSet.add(src);
      });
      sourcesSet.forEach(src => {
        const opt = document.createElement("option");
        opt.value = src;
        opt.textContent = src;
        sourceSelect.appendChild(opt);
      });

      const tbody = document.getElementById("companies-table-body");
      const searchInput = document.getElementById("search-input");
      const remoteCheck = document.getElementById("remote-check");
      const emailCheck = document.getElementById("email-check");
      const aiCheck = document.getElementById("ai-check");

      // Bind event listeners
      searchInput.addEventListener("input", applyFilters);
      sourceSelect.addEventListener("change", applyFilters);
      remoteCheck.addEventListener("change", applyFilters);
      emailCheck.addEventListener("change", applyFilters);
      aiCheck.addEventListener("change", applyFilters);

      function renderTable(visibleCompanies) {
        tbody.innerHTML = "";
        
        if (visibleCompanies.length === 0) {
          tbody.innerHTML = `
            <tr>
              <td colspan="6" class="py-12 text-center text-slate-400 italic">
                No companies match the current filter criteria.
              </td>
            </tr>
          `;
          return;
        }

        visibleCompanies.forEach((c) => {
          // Find original index to pass to openModal
          const originalIndex = COMPANIES.findIndex(comp => comp.name === c.name && comp.domain === c.domain);
          
          const row = document.createElement("tr");
          row.className = "hover:bg-slate-850 cursor-pointer transition-colors duration-150";
          row.onclick = () => openModal(originalIndex);

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
            webLink.onclick = (e) => e.stopPropagation();
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
      }

      function applyFilters() {
        const query = searchInput.value.toLowerCase().trim();
        const selectedSource = sourceSelect.value;
        const remoteOnly = remoteCheck.checked;
        const hasEmailOnly = emailCheck.checked;
        const hasAiOnly = aiCheck.checked;

        const filtered = COMPANIES.filter(c => {
          // 1. Text search
          if (query && !c.name.toLowerCase().includes(query)) {
            return false;
          }

          // 2. Source dropdown
          if (selectedSource !== "all") {
            const src = c.ats_platform || (c.jobs && c.jobs[0] ? c.jobs[0].source : "feed");
            if (src !== selectedSource) return false;
          }

          // 3. Remote check
          if (remoteOnly) {
            const hasRemoteJob = c.jobs && c.jobs.some(j => j.remote_type === "remote");
            if (!hasRemoteJob) return false;
          }

          // 4. Has email check
          if (hasEmailOnly) {
            const hasEmail = c.recruiter_email || (c.generic_emails && c.generic_emails.length > 0);
            if (!hasEmail) return false;
          }

          // 5. Has AI check
          // Note: "Has AI summary" doubles as a rough proxy for "enriched" vs "not yet enriched".
          // This should later be replaced/supplemented once company scoring lands in Phase 10.
          if (hasAiOnly && !c.ai_summary) {
            return false;
          }

          return true;
        });

        // Update counter
        document.getElementById("count-visible").textContent = filtered.length;
        document.getElementById("count-total").textContent = COMPANIES.length;

        // Render
        renderTable(filtered);
      }

      // Initial run
      applyFilters();
      initCharts();
    });

    function initCharts() {
      // 1. Jobs by Source
      const sourceJobs = {};
      COMPANIES.forEach(c => {
        const src = c.ats_platform || (c.jobs && c.jobs[0] ? c.jobs[0].source : "feed");
        const jobCount = c.jobs ? c.jobs.length : 0;
        sourceJobs[src] = (sourceJobs[src] || 0) + jobCount;
      });

      // 2. Jobs by Country (approximate heuristic matching)
      const countryJobs = {
        "USA": 0,
        "Canada": 0,
        "UK": 0,
        "Remote": 0,
        "Other": 0
      };

      COMPANIES.forEach(c => {
        if (c.jobs) {
          c.jobs.forEach(j => {
            const loc = (j.location || "").toLowerCase();
            const remoteType = (j.remote_type || "").toLowerCase();

            if (remoteType === "remote" || loc === "remote") {
              countryJobs["Remote"]++;
            } else if (loc.includes("usa") || loc.includes("united states") || loc.includes("u.s.")) {
              countryJobs["USA"]++;
            } else if (loc.includes("canada") || loc.includes("can")) {
              countryJobs["Canada"]++;
            } else if (loc.includes("uk") || loc.includes("united kingdom") || loc.includes("london") || loc.includes("great britain")) {
              countryJobs["UK"]++;
            } else {
              countryJobs["Other"]++;
            }
          });
        }
      });

      // 3. Discoveries per day over the last 14 days
      const timelineData = {};
      const dateLabels = [];
      
      for (let i = 13; i >= 0; i--) {
        const d = new Date();
        d.setDate(d.getDate() - i);
        const dateStr = d.toISOString().split('T')[0];
        timelineData[dateStr] = 0;
        
        const label = d.toLocaleDateString([], { month: 'short', day: 'numeric' });
        dateLabels.push({ dateStr, label });
      }

      COMPANIES.forEach(c => {
        if (c.discovered_at) {
          const datePart = c.discovered_at.split('T')[0];
          if (timelineData[datePart] !== undefined) {
            timelineData[datePart]++;
          }
        }
      });

      const timelineValues = dateLabels.map(dl => timelineData[dl.dateStr]);

      // --- Chart 1: Jobs by Source ---
      new Chart(document.getElementById("chart-source"), {
        type: 'bar',
        data: {
          labels: Object.keys(sourceJobs),
          datasets: [{
            label: 'Jobs Count',
            data: Object.values(sourceJobs),
            backgroundColor: 'rgba(34, 211, 238, 0.6)',
            borderColor: 'rgb(34, 211, 238)',
            borderWidth: 1
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false }
          },
          scales: {
            y: {
              grid: { color: 'rgba(255, 255, 255, 0.05)' },
              ticks: { color: '#94a3b8', precision: 0 }
            },
            x: {
              grid: { display: false },
              ticks: { color: '#94a3b8' }
            }
          }
        }
      });

      // --- Chart 2: Jobs by Country (Doughnut) ---
      new Chart(document.getElementById("chart-country"), {
        type: 'doughnut',
        data: {
          labels: Object.keys(countryJobs),
          datasets: [{
            data: Object.values(countryJobs),
            backgroundColor: [
              'rgba(59, 130, 246, 0.6)',
              'rgba(168, 85, 247, 0.6)',
              'rgba(236, 72, 153, 0.6)',
              'rgba(16, 185, 129, 0.6)',
              'rgba(100, 116, 139, 0.6)'
            ],
            borderColor: '#0f172a',
            borderWidth: 2
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              position: 'right',
              labels: { color: '#94a3b8', font: { size: 10 } }
            }
          }
        }
      });

      // --- Chart 3: Timeline ---
      new Chart(document.getElementById("chart-timeline"), {
        type: 'line',
        data: {
          labels: dateLabels.map(dl => dl.label),
          datasets: [{
            label: 'Companies Discovered',
            data: timelineValues,
            fill: true,
            backgroundColor: 'rgba(99, 102, 241, 0.1)',
            borderColor: 'rgb(99, 102, 241)',
            tension: 0.3,
            borderWidth: 2,
            pointBackgroundColor: 'rgb(99, 102, 241)'
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false }
          },
          scales: {
            y: {
              grid: { color: 'rgba(255, 255, 255, 0.05)' },
              ticks: { color: '#94a3b8', precision: 0 }
            },
            x: {
              grid: { display: false },
              ticks: { color: '#94a3b8' }
            }
          }
        }
      });
    }

    function openModal(companyIndex) {
      const c = COMPANIES[companyIndex];
      if (!c) return;

      // Set Title
      document.getElementById("modal-company-name").textContent = c.name;
      
      // Set Website Link
      const webContainer = document.getElementById("modal-company-links");
      webContainer.innerHTML = "";
      
      const linkFields = [
        { label: "Website", url: c.website, icon: "🌐" },
        { label: "Careers Page", url: c.career_page_url, icon: "📄" },
        { label: "LinkedIn", url: c.linkedin_url, icon: "🔗" },
        { label: "GitHub", url: c.github_url, icon: "💻" }
      ];

      linkFields.forEach(f => {
        if (f.url) {
          const a = document.createElement("a");
          a.href = f.url;
          a.target = "_blank";
          a.className = "px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-cyan-400 border border-slate-700 transition-colors flex items-center space-x-1";
          a.innerHTML = `<span>${f.icon}</span> <span>${f.label}</span>`;
          webContainer.appendChild(a);
        }
      });

      // Populate AI Enrichment
      const aiContainer = document.getElementById("modal-ai-enrichment");
      if (c.ai_summary || (c.ai_talking_points && c.ai_talking_points.length > 0) || c.ai_fit_rationale) {
        let talkingPointsHtml = "";
        if (c.ai_talking_points && c.ai_talking_points.length > 0) {
          talkingPointsHtml = `
            <div class="mt-3">
              <div class="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Outreach Hooks / Talking Points</div>
              <ul class="list-disc list-inside space-y-1 text-sm text-slate-300 pl-2">
                ${c.ai_talking_points.map(pt => `<li>${pt}</li>`).join("")}
              </ul>
            </div>
          `;
        }

        aiContainer.innerHTML = `
          <div class="bg-slate-950/40 border border-slate-800 rounded-xl p-5 space-y-4">
            <div>
              <div class="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">AI Summary</div>
              <p class="text-sm text-slate-200">${c.ai_summary || "—"}</p>
            </div>
            <div>
              <div class="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">Outreach Fit Rationale</div>
              <p class="text-sm text-slate-200">${c.ai_fit_rationale || "—"}</p>
            </div>
            ${talkingPointsHtml}
          </div>
        `;
      } else {
        aiContainer.innerHTML = `
          <div class="bg-slate-950/20 border border-dashed border-slate-800 rounded-xl p-6 text-center text-slate-400 text-sm">
            ✨ Not yet enriched — run <code class="bg-slate-950 px-1.5 py-0.5 rounded text-xs text-indigo-400">jobs enrich</code> to populate AI summaries and hooks.
          </div>
        `;
      }

      // Populate Contacts
      const contactsContainer = document.getElementById("modal-contacts");
      const recruiterName = c.recruiter_name || "—";
      const recruiterEmail = c.recruiter_email ? `<a href="mailto:${c.recruiter_email}" class="text-cyan-400 hover:underline">${c.recruiter_email}</a>` : "—";
      
      let genericEmailsHtml = "—";
      if (c.generic_emails && c.generic_emails.length > 0) {
        genericEmailsHtml = c.generic_emails.map(email => `<a href="mailto:${email}" class="text-cyan-400 hover:underline block">${email}</a>`).join("");
      }

      contactsContainer.innerHTML = `
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div class="bg-slate-950/40 border border-slate-800 rounded-xl p-4">
            <div class="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Recruiter / Contact Person</div>
            <div class="space-y-1.5 text-sm">
              <div><span class="text-slate-400">Name:</span> <span class="text-slate-200">${recruiterName}</span></div>
              <div><span class="text-slate-400">Email:</span> <span class="text-slate-200">${recruiterEmail}</span></div>
            </div>
          </div>
          <div class="bg-slate-950/40 border border-slate-800 rounded-xl p-4">
            <div class="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Generic Company Emails</div>
            <div class="space-y-1.5 text-sm text-slate-200">
              ${genericEmailsHtml}
            </div>
          </div>
        </div>
      `;

      // Populate Jobs List
      const jobsContainer = document.getElementById("modal-jobs-body");
      jobsContainer.innerHTML = "";
      if (c.jobs && c.jobs.length > 0) {
        c.jobs.forEach(j => {
          const row = document.createElement("tr");
          row.className = "border-b border-slate-800/50 hover:bg-slate-800/20";
          
          const titleCell = document.createElement("td");
          titleCell.className = "py-3 px-4 text-sm font-semibold text-slate-200";
          titleCell.textContent = j.job_title;
          row.appendChild(titleCell);

          const locCell = document.createElement("td");
          locCell.className = "py-3 px-4 text-sm text-slate-300";
          locCell.textContent = j.location || "—";
          row.appendChild(locCell);

          const typeCell = document.createElement("td");
          typeCell.className = "py-3 px-4 text-center";
          const typeSpan = document.createElement("span");
          typeSpan.className = `px-2 py-0.5 rounded-full text-xs font-semibold ${
            j.remote_type === 'remote' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' :
            j.remote_type === 'hybrid' ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' :
            'bg-slate-800 text-slate-400 border border-slate-700'
          }`;
          typeSpan.textContent = j.remote_type || "unknown";
          typeCell.appendChild(typeSpan);
          row.appendChild(typeCell);

          const actionCell = document.createElement("td");
          actionCell.className = "py-3 px-4 text-right";
          const a = document.createElement("a");
          a.href = j.job_url;
          a.target = "_blank";
          a.className = "text-xs text-cyan-400 hover:underline";
          a.textContent = "View Post ↗";
          actionCell.appendChild(a);
          row.appendChild(actionCell);

          jobsContainer.appendChild(row);
        });
      } else {
        jobsContainer.innerHTML = `
          <tr>
            <td colspan="4" class="py-6 text-center text-slate-500 italic text-sm">No job postings available.</td>
          </tr>
        `;
      }

      // Populate Notes
      const notesContainer = document.getElementById("modal-notes-section");
      if (c.notes && c.notes.length > 0) {
        notesContainer.classList.remove("hidden");
        const list = document.getElementById("modal-notes-list");
        list.innerHTML = c.notes.map(n => `<li class="text-slate-350">${n}</li>`).join("");
      } else {
        notesContainer.classList.add("hidden");
      }

      // Show Modal
      const modal = document.getElementById("detail-modal");
      modal.classList.remove("hidden");
      modal.classList.add("flex");
    }

    function closeModal() {
      const modal = document.getElementById("detail-modal");
      modal.classList.add("hidden");
      modal.classList.remove("flex");
    }

    // Close on click outside card
    document.getElementById("detail-modal").addEventListener("click", (e) => {
      if (e.target === document.getElementById("detail-modal")) {
        closeModal();
      }
    });

    // Close on escape key
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        closeModal();
      }
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
