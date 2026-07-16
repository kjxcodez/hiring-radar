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
<html lang="en" class="h-full">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>📡 Hiring Radar HUD</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
  
  <style>
    :root {
      --color-bg: #0a0e14;
      --color-surface: #101520;
      --color-border: #1e2638;
      --color-primary: #e2e8f0;
      --color-muted: #708090;
      --color-accent: #00e5ff;
      --color-warning: #ff9f0a;
      --color-success: #30d158;
      
      --font-display: 'Space Grotesk', sans-serif;
      --font-body: 'Inter', sans-serif;
      --font-mono: 'JetBrains Mono', monospace;
    }

    body {
      background-color: var(--color-bg);
      color: var(--color-primary);
      font-family: var(--font-body);
    }

    .font-display {
      font-family: var(--font-display);
    }

    .font-mono {
      font-family: var(--font-mono);
    }

    .border-hud {
      border-color: var(--color-border);
    }

    /* Pulse Alert states */
    @keyframes status-pulse {
      0%, 100% { opacity: 0.6; }
      50% { opacity: 1; }
    }
    .pulse-amber {
      animation: status-pulse 2.2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
    }

    #toggle-hud-icon {
      transition: transform 0.2s ease-in-out;
    }

    /* Keyboard focus states */
    input:focus, select:focus, button:focus {
      outline: 2px solid var(--color-accent) !important;
      outline-offset: 1px !important;
    }

    /* prefers-reduced-motion */
    @media (prefers-reduced-motion: reduce) {
      * {
        animation-delay: 0s !important;
        animation-duration: 0s !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0s !important;
        scroll-behavior: auto !important;
      }
      .pulse-amber {
        animation: none !important;
      }
    }
  </style>
</head>
<body class="h-full flex flex-col bg-[#0a0e14]">
  <!-- Header HUD -->
  <header class="border-b border-[#1e2638] bg-[#101520]/80 backdrop-blur sticky top-0 z-50">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
      <div class="flex items-center space-x-3">
        <span class="text-2xl">📡</span>
        <h1 class="text-xl font-bold font-display tracking-wider bg-gradient-to-r from-[#00e5ff] to-blue-400 bg-clip-text text-transparent">HIRING RADAR HUD</h1>
      </div>
      <div class="flex items-center space-x-6">
        <div class="text-xs font-mono text-slate-400 hidden sm:block">
          Generated: <span class="text-[#00e5ff]" id="generated-timestamp"></span>
        </div>
        <button id="toggle-hud-btn" class="flex items-center space-x-1.5 px-3 py-1.5 rounded bg-[#101520] border border-[#1e2638] hover:border-[#00e5ff]/50 text-xs font-semibold font-mono text-slate-300 transition-colors">
          <span>ANALYTICS HUD</span>
          <svg id="toggle-hud-icon" class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
          </svg>
        </button>
      </div>
    </div>
  </header>

  <!-- Main HUD Panel -->
  <main class="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
    <!-- Collapsible Analytics Section -->
    <div id="analytics-hud" class="space-y-6">
      <!-- Summary Cards -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div class="bg-[#101520] border border-[#1e2638] rounded-xl p-5 shadow-lg relative overflow-hidden group">
          <div class="text-xs font-semibold font-mono text-slate-400 uppercase tracking-widest mb-1">TOTAL DETECTED</div>
          <div class="text-3xl font-bold font-display text-[#00e5ff]" id="stat-total-companies">0</div>
          <div class="text-[10px] font-mono text-slate-500 mt-1">Unique company profiles saved</div>
        </div>
        <div class="bg-[#101520] border border-[#1e2638] rounded-xl p-5 shadow-lg relative overflow-hidden group">
          <div class="text-xs font-semibold font-mono text-slate-400 uppercase tracking-widest mb-1">ACTIVE OPENINGS</div>
          <div class="text-3xl font-bold font-display text-blue-400" id="stat-total-jobs">0</div>
          <div class="text-[10px] font-mono text-slate-500 mt-1">Total job listings across targets</div>
        </div>
        <div class="bg-[#101520] border border-[#1e2638] rounded-xl p-5 shadow-lg relative overflow-hidden group">
          <div class="text-xs font-semibold font-mono text-slate-400 uppercase tracking-widest mb-1">AI ENRICHMENT RATIO</div>
          <div class="text-3xl font-bold font-display text-indigo-400" id="stat-enriched-ai">0</div>
          <div class="text-[10px] font-mono text-slate-500 mt-1">Desirability ratings & hooks resolved</div>
        </div>
      </div>

      <!-- Charts HUD -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div class="bg-[#101520] border border-[#1e2638] rounded-xl p-5 shadow-lg flex flex-col justify-between h-[320px]">
          <h4 class="text-xs font-bold font-mono text-slate-400 uppercase tracking-widest mb-3">Jobs by Source / Platform</h4>
          <div class="flex-1 min-h-0 relative">
            <canvas id="chart-source"></canvas>
          </div>
        </div>
        <div class="bg-[#101520] border border-[#1e2638] rounded-xl p-5 shadow-lg flex flex-col justify-between h-[320px]">
          <h4 class="text-xs font-bold font-mono text-slate-400 uppercase tracking-widest mb-3">Jobs by Country (Heuristic)</h4>
          <div class="flex-1 min-h-0 relative flex justify-center items-center">
            <canvas id="chart-country" class="max-h-[220px] max-w-[220px]"></canvas>
          </div>
        </div>
        <div class="bg-[#101520] border border-[#1e2638] rounded-xl p-5 shadow-lg flex flex-col justify-between h-[320px]">
          <h4 class="text-xs font-bold font-mono text-slate-400 uppercase tracking-widest mb-3">Discoveries (Last 14 Days)</h4>
          <div class="flex-1 min-h-0 relative">
            <canvas id="chart-timeline"></canvas>
          </div>
        </div>
      </div>
      <div class="text-[10px] font-mono text-slate-500 italic">
        * Charts reflect total local data state, independent of filters applied below.
      </div>
    </div>

    <!-- Active Scanning controls -->
    <div class="bg-[#101520] border border-[#1e2638] rounded-xl p-5 shadow-md space-y-4">
      <div class="text-xs font-bold font-mono text-[#00e5ff] uppercase tracking-widest flex items-center space-x-2">
        <span class="inline-block h-2 w-2 rounded-full bg-[#00e5ff] animate-ping"></span>
        <span>Detection Filters</span>
      </div>
      
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 items-end">
        <!-- Search Input -->
        <div class="lg:col-span-2">
          <label for="search-input" class="block text-[10px] font-bold font-mono text-slate-400 uppercase tracking-widest mb-2">Search Companies</label>
          <input type="text" id="search-input" placeholder="Type target name..." class="w-full bg-[#070b10] border border-[#1e2638] rounded px-3 py-2 text-sm text-slate-100 placeholder-slate-650 focus:outline-none transition-colors">
        </div>
        <!-- Source select -->
        <div>
          <label for="source-select" class="block text-[10px] font-bold font-mono text-slate-400 uppercase tracking-widest mb-2">Source / ATS</label>
          <select id="source-select" class="w-full bg-[#070b10] border border-[#1e2638] rounded px-3 py-2 text-sm text-slate-100 focus:outline-none transition-colors font-mono">
            <option value="all">All Sources</option>
          </select>
        </div>
        <!-- Checkboxes -->
        <div class="lg:col-span-2 grid grid-cols-1 sm:grid-cols-3 gap-2">
          <label class="flex items-center space-x-2 text-xs font-mono text-slate-350 cursor-pointer select-none py-2 hover:text-[#00e5ff]">
            <input type="checkbox" id="remote-check" class="rounded border-[#1e2638] bg-[#070b10] text-[#00e5ff] focus:ring-0">
            <span>Remote Only</span>
          </label>
          <label class="flex items-center space-x-2 text-xs font-mono text-slate-350 cursor-pointer select-none py-2 hover:text-[#00e5ff]">
            <input type="checkbox" id="email-check" class="rounded border-[#1e2638] bg-[#070b10] text-[#00e5ff] focus:ring-0">
            <span>Has Email</span>
          </label>
          <label class="flex items-center space-x-2 text-xs font-mono text-slate-350 cursor-pointer select-none py-2 hover:text-[#00e5ff]">
            <input type="checkbox" id="ai-check" class="rounded border-[#1e2638] bg-[#070b10] text-[#00e5ff] focus:ring-0">
            <span>Has AI Summary</span>
          </label>
        </div>
      </div>
    </div>

    <!-- Results Counter -->
    <div class="text-xs font-mono text-slate-400 flex items-center justify-between px-1">
      <div>
        Showing <span class="text-[#00e5ff] font-bold" id="count-visible">0</span> of <span class="text-slate-200 font-bold" id="count-total">0</span> target profiles
      </div>
      <div class="flex items-center space-x-3 text-[10px] text-slate-500">
        <span class="flex items-center space-x-1"><span class="h-2 w-2 rounded-full bg-[#30d158]"></span><span>READY</span></span>
        <span class="flex items-center space-x-1"><span class="h-2 w-2 rounded-full bg-[#ff9f0a] pulse-amber"></span><span>ACTION REQUIRED</span></span>
      </div>
    </div>

    <!-- Results HUD (Desktop Table / Mobile Cards) -->
    <div class="bg-[#101520] border border-[#1e2638] rounded-xl overflow-hidden shadow-xl">
      <!-- Desktop Table View -->
      <div class="hidden md:block overflow-x-auto">
        <table class="w-full text-left border-collapse">
          <thead>
            <tr class="bg-[#0c1017] border-b border-[#1e2638] text-[10px] font-bold text-slate-400 uppercase tracking-widest font-mono">
              <th class="py-4 px-6">Company</th>
              <th class="py-4 px-6">Platform / Source</th>
              <th class="py-4 px-6 text-center">Jobs</th>
              <th class="py-4 px-6 text-center">Outreach</th>
              <th class="py-4 px-6 text-center">AI Summary</th>
              <th class="py-4 px-6">Last Updated</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-[#1e2638]/50" id="companies-table-body">
            <!-- Dynamically populated -->
          </tbody>
        </table>
      </div>

      <!-- Mobile Cards View -->
      <div class="md:hidden divide-y divide-[#1e2638]/50" id="companies-cards-container">
        <!-- Dynamically populated -->
      </div>
    </div>
  </main>


  <!-- Detail Modal HUD Overlay -->
  <div id="detail-modal" class="hidden fixed inset-0 bg-[#0a0e14]/90 backdrop-blur flex items-center justify-center p-4 z-50">
    <div class="bg-[#101520] border border-[#1e2638] rounded-xl w-full max-w-4xl max-h-[85vh] flex flex-col shadow-2xl overflow-hidden transition-all duration-350">
      <!-- Modal Header -->
      <div class="border-b border-[#1e2638] p-6 flex justify-between items-start bg-[#0c1017]">
        <div>
          <h2 id="modal-company-name" class="text-2xl font-bold font-display tracking-wide text-slate-100"></h2>
          <div id="modal-company-links" class="flex flex-wrap gap-2 mt-3 font-mono"></div>
        </div>
        <button onclick="closeModal()" class="text-slate-400 hover:text-[#00e5ff] transition-colors p-1.5 rounded border border-[#1e2638] bg-[#101520]" aria-label="Close modal">
          <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <!-- Modal Body -->
      <div class="flex-1 overflow-y-auto p-6 space-y-6">
        <!-- AI Enrichment Section -->
        <div class="space-y-3">
          <h3 class="text-sm font-bold font-mono text-[#00e5ff] uppercase tracking-widest flex items-center space-x-2">
            <span>✨</span> <span>AI Enrichment Profile</span>
          </h3>
          <div id="modal-ai-enrichment"></div>
        </div>

        <!-- Contacts Section -->
        <div class="space-y-3">
          <h3 class="text-sm font-bold font-mono text-[#00e5ff] uppercase tracking-widest flex items-center space-x-2">
            <span>📧</span> <span>Outreach Contacts</span>
          </h3>
          <div id="modal-contacts"></div>
        </div>

        <!-- Jobs List Section -->
        <div class="space-y-3">
          <h3 class="text-sm font-bold font-mono text-[#00e5ff] uppercase tracking-widest flex items-center space-x-2">
            <span>💼</span> <span>Active Openings</span>
          </h3>
          <div class="border border-[#1e2638] rounded overflow-hidden bg-[#0c1017]">
            <div class="overflow-x-auto">
              <table class="w-full text-left border-collapse">
                <thead>
                  <tr class="bg-[#0c1017] border-b border-[#1e2638] text-[10px] font-bold text-slate-400 uppercase tracking-widest font-mono">
                    <th class="py-3 px-4">Title</th>
                    <th class="py-3 px-4">Location</th>
                    <th class="py-3 px-4 text-center">Remote</th>
                    <th class="py-3 px-4 text-right">Post</th>
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
        <div id="modal-notes-section" class="hidden space-y-3">
          <h3 class="text-sm font-bold font-mono text-[#00e5ff] uppercase tracking-widest flex items-center space-x-2">
            <span>📝</span> <span>System Scrape Logs</span>
          </h3>
          <div class="bg-[#0c1017] border border-[#1e2638] rounded p-4">
            <ul id="modal-notes-list" class="list-disc list-inside space-y-1.5 text-sm font-mono text-slate-350">
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

      // Collapsible Analytics HUD implementation
      const toggleBtn = document.getElementById("toggle-hud-btn");
      const hudContainer = document.getElementById("analytics-hud");
      const toggleIcon = document.getElementById("toggle-hud-icon");

      const isCollapsed = localStorage.getItem("analytics-hud-collapsed") === "true";
      if (isCollapsed) {
        hudContainer.classList.add("hidden");
        toggleIcon.style.transform = "rotate(180deg)";
      }

      toggleBtn.addEventListener("click", () => {
        const currentlyHidden = hudContainer.classList.toggle("hidden");
        localStorage.setItem("analytics-hud-collapsed", currentlyHidden);
        if (currentlyHidden) {
          toggleIcon.style.transform = "rotate(180deg)";
        } else {
          toggleIcon.style.transform = "rotate(0deg)";
        }
      });

      // Stats tallies
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

      // Dynamically populate Source drop list
      const sourceSelect = document.getElementById("source-select");
      const sourcesSet = new Set();
      COMPANIES.forEach(c => {
        const src = c.ats_platform || (c.jobs && c.jobs[0] ? c.jobs[0].source : "feed");
        if (src) sourcesSet.add(src);
      });
      sourcesSet.forEach(src => {
        const opt = document.createElement("option");
        opt.value = src;
        opt.textContent = src.toUpperCase();
        sourceSelect.appendChild(opt);
      });

      const tbody = document.getElementById("companies-table-body");
      const cardContainer = document.getElementById("companies-cards-container");
      const searchInput = document.getElementById("search-input");
      const remoteCheck = document.getElementById("remote-check");
      const emailCheck = document.getElementById("email-check");
      const aiCheck = document.getElementById("ai-check");

      searchInput.addEventListener("input", applyFilters);
      sourceSelect.addEventListener("change", applyFilters);
      remoteCheck.addEventListener("change", applyFilters);
      emailCheck.addEventListener("change", applyFilters);
      aiCheck.addEventListener("change", applyFilters);

      function renderTable(visibleCompanies) {
        tbody.innerHTML = "";
        cardContainer.innerHTML = "";
        
        if (visibleCompanies.length === 0) {
          const emptyHtml = `
            <div class="py-12 text-center text-slate-400 italic text-sm">
              No companies match the current detection search.
            </div>
          `;
          tbody.innerHTML = `<tr><td colspan="6" class="text-center">${emptyHtml}</td></tr>`;
          cardContainer.innerHTML = emptyHtml;
          return;
        }

        visibleCompanies.forEach((c) => {
          const originalIndex = COMPANIES.findIndex(comp => comp.name === c.name && comp.domain === c.domain);
          const hasEmail = c.recruiter_email || (c.generic_emails && c.generic_emails.length > 0);
          const hasAi = !!c.ai_summary;
          const isReady = hasEmail && hasAi;

          const borderClasses = isReady 
            ? "border-l-4 border-[#30d158]" 
            : "border-l-4 border-[#ff9f0a] pulse-amber";

          // --- Desktop row design ---
          const row = document.createElement("tr");
          row.className = `${borderClasses} hover:bg-[#161c28]/60 cursor-pointer transition-all duration-150 relative group`;
          row.onclick = () => openModal(originalIndex);

          // Company info cell
          const nameCell = document.createElement("td");
          nameCell.className = "py-4 px-6";
          const nameDiv = document.createElement("div");
          nameDiv.className = "font-bold text-slate-100 font-display text-base tracking-wide flex items-center space-x-2";
          nameDiv.textContent = c.name;
          nameCell.appendChild(nameDiv);
          if (c.website) {
            const webLink = document.createElement("a");
            webLink.href = c.website;
            webLink.target = "_blank";
            webLink.className = "text-xs text-[#00e5ff] hover:underline block mt-0.5 font-mono";
            webLink.textContent = c.website;
            webLink.onclick = (e) => e.stopPropagation();
            nameCell.appendChild(webLink);
          }
          row.appendChild(nameCell);

          // Platform / Source cell
          const sourceCell = document.createElement("td");
          sourceCell.className = "py-4 px-6";
          const sourceSpan = document.createElement("span");
          sourceSpan.className = "px-2.5 py-1 rounded bg-[#0c1017] border border-[#1e2638] text-xs font-semibold font-mono text-[#00e5ff]/80";
          sourceSpan.textContent = c.ats_platform || (c.jobs && c.jobs[0] ? c.jobs[0].source : "feed");
          sourceCell.appendChild(sourceSpan);
          row.appendChild(sourceCell);

          // Jobs count cell
          const jobsCell = document.createElement("td");
          jobsCell.className = "py-4 px-6 text-center text-sm font-semibold font-mono text-slate-100";
          jobsCell.textContent = c.jobs ? c.jobs.length : 0;
          row.appendChild(jobsCell);

          // Email status cell
          const emailCell = document.createElement("td");
          emailCell.className = "py-4 px-6 text-center";
          const emailBadge = document.createElement("span");
          if (hasEmail) {
            emailBadge.className = "px-2.5 py-0.5 rounded text-[10px] font-semibold font-mono bg-[#30d158]/10 text-[#30d158] border border-[#30d158]/20";
            emailBadge.textContent = "READY";
            emailBadge.title = c.recruiter_email || c.generic_emails[0];
          } else {
            emailBadge.className = "px-2.5 py-0.5 rounded text-[10px] font-semibold font-mono bg-[#ff9f0a]/10 text-[#ff9f0a] border border-[#ff9f0a]/20";
            emailBadge.textContent = "NO EMAIL";
          }
          emailCell.appendChild(emailBadge);
          row.appendChild(emailCell);

          // AI summary cell
          const aiCell = document.createElement("td");
          aiCell.className = "py-4 px-6 text-center";
          const aiBadge = document.createElement("span");
          if (hasAi) {
            aiBadge.className = "px-2.5 py-0.5 rounded text-[10px] font-semibold font-mono bg-indigo-500/10 text-indigo-400 border border-indigo-500/20";
            aiBadge.textContent = "ENRICHED";
            aiBadge.title = c.ai_summary;
          } else {
            aiBadge.className = "px-2.5 py-0.5 rounded text-[10px] font-semibold font-mono bg-[#ff9f0a]/10 text-[#ff9f0a] border border-[#ff9f0a]/20";
            aiBadge.textContent = "MISSING";
          }
          aiCell.appendChild(aiBadge);
          row.appendChild(aiCell);

          // Last updated cell
          const updatedCell = document.createElement("td");
          updatedCell.className = "py-4 px-6 text-sm font-mono text-slate-400";
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

          // --- Mobile Card design ---
          const card = document.createElement("div");
          card.className = `${borderClasses} p-4 bg-[#101520] hover:bg-[#161c28]/60 cursor-pointer transition-all duration-150 space-y-3`;
          card.onclick = () => openModal(originalIndex);

          const cardHeader = document.createElement("div");
          cardHeader.className = "flex justify-between items-start";
          const cardName = document.createElement("div");
          cardName.className = "font-bold text-slate-100 font-display text-base";
          cardName.textContent = c.name;
          cardHeader.appendChild(cardName);

          const cardSource = document.createElement("span");
          cardSource.className = "px-2 py-0.5 rounded bg-[#0c1017] border border-[#1e2638] text-[10px] font-semibold font-mono text-[#00e5ff]/80";
          cardSource.textContent = c.ats_platform || (c.jobs && c.jobs[0] ? c.jobs[0].source : "feed");
          cardHeader.appendChild(cardSource);
          card.appendChild(cardHeader);

          if (c.website) {
            const cardLink = document.createElement("a");
            cardLink.href = c.website;
            cardLink.target = "_blank";
            cardLink.className = "text-xs text-[#00e5ff] hover:underline block font-mono truncate";
            cardLink.textContent = c.website;
            cardLink.onclick = (e) => e.stopPropagation();
            card.appendChild(cardLink);
          }

          const cardDetails = document.createElement("div");
          cardDetails.className = "flex flex-wrap items-center gap-2 text-xs pt-1";
          
          const cardJobs = document.createElement("span");
          cardJobs.className = "font-mono text-slate-300 bg-[#0c1017] px-2 py-0.5 rounded border border-[#1e2638]";
          cardJobs.textContent = `${c.jobs ? c.jobs.length : 0} jobs`;
          cardDetails.appendChild(cardJobs);

          const cardEmailBadge = document.createElement("span");
          if (hasEmail) {
            cardEmailBadge.className = "px-2 py-0.5 rounded text-[10px] font-semibold font-mono bg-[#30d158]/10 text-[#30d158] border border-[#30d158]/20";
            cardEmailBadge.textContent = "READY";
          } else {
            cardEmailBadge.className = "px-2 py-0.5 rounded text-[10px] font-semibold font-mono bg-[#ff9f0a]/10 text-[#ff9f0a] border border-[#ff9f0a]/20";
            cardEmailBadge.textContent = "NO EMAIL";
          }
          cardDetails.appendChild(cardEmailBadge);

          const cardAiBadge = document.createElement("span");
          if (hasAi) {
            cardAiBadge.className = "px-2 py-0.5 rounded text-[10px] font-semibold font-mono bg-indigo-500/10 text-indigo-400 border border-indigo-500/20";
            cardAiBadge.textContent = "ENRICHED";
          } else {
            cardAiBadge.className = "px-2 py-0.5 rounded text-[10px] font-semibold font-mono bg-[#ff9f0a]/10 text-[#ff9f0a] border border-[#ff9f0a]/20";
            cardAiBadge.textContent = "MISSING";
          }
          cardDetails.appendChild(cardAiBadge);
          card.appendChild(cardDetails);

          cardContainer.appendChild(card);
        });
      }

      function applyFilters() {
        const query = searchInput.value.toLowerCase().trim();
        const selectedSource = sourceSelect.value;
        const remoteOnly = remoteCheck.checked;
        const hasEmailOnly = emailCheck.checked;
        const hasAiOnly = aiCheck.checked;

        const filtered = COMPANIES.filter(c => {
          if (query && !c.name.toLowerCase().includes(query)) {
            return false;
          }
          if (selectedSource !== "all") {
            const src = c.ats_platform || (c.jobs && c.jobs[0] ? c.jobs[0].source : "feed");
            if (src !== selectedSource) return false;
          }
          if (remoteOnly) {
            const hasRemoteJob = c.jobs && c.jobs.some(j => j.remote_type === "remote");
            if (!hasRemoteJob) return false;
          }
          if (hasEmailOnly) {
            const hasEmail = c.recruiter_email || (c.generic_emails && c.generic_emails.length > 0);
            if (!hasEmail) return false;
          }
          if (hasAiOnly && !c.ai_summary) {
            return false;
          }
          return true;
        });

        document.getElementById("count-visible").textContent = filtered.length;
        document.getElementById("count-total").textContent = COMPANIES.length;

        renderTable(filtered);
      }

      // Start initial states
      applyFilters();
      initCharts();
    });

    function initCharts() {
      const sourceJobs = {};
      COMPANIES.forEach(c => {
        const src = c.ats_platform || (c.jobs && c.jobs[0] ? c.jobs[0].source : "feed");
        const jobCount = c.jobs ? c.jobs.length : 0;
        sourceJobs[src.toUpperCase()] = (sourceJobs[src.toUpperCase()] || 0) + jobCount;
      });

      const countryJobs = {
        "USA": 0,
        "CANADA": 0,
        "UK": 0,
        "REMOTE": 0,
        "OTHER": 0
      };

      COMPANIES.forEach(c => {
        if (c.jobs) {
          c.jobs.forEach(j => {
            const loc = (j.location || "").toLowerCase();
            const remoteType = (j.remote_type || "").toLowerCase();

            if (remoteType === "remote" || loc === "remote") {
              countryJobs["REMOTE"]++;
            } else if (loc.includes("usa") || loc.includes("united states") || loc.includes("u.s.")) {
              countryJobs["USA"]++;
            } else if (loc.includes("canada") || loc.includes("can")) {
              countryJobs["CANADA"]++;
            } else if (loc.includes("uk") || loc.includes("united kingdom") || loc.includes("london") || loc.includes("great britain")) {
              countryJobs["UK"]++;
            } else {
              countryJobs["OTHER"]++;
            }
          });
        }
      });

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

      // --- Chart 1: Source Bar chart ---
      new Chart(document.getElementById("chart-source"), {
        type: 'bar',
        data: {
          labels: Object.keys(sourceJobs),
          datasets: [{
            label: 'Jobs Count',
            data: Object.values(sourceJobs),
            backgroundColor: 'rgba(0, 229, 255, 0.65)',
            borderColor: 'rgba(0, 229, 255, 1)',
            borderWidth: 1.5,
            barThickness: 20
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
              ticks: { color: '#708090', font: { family: 'JetBrains Mono', size: 9 }, precision: 0 }
            },
            x: {
              grid: { display: false },
              ticks: { color: '#708090', font: { family: 'JetBrains Mono', size: 9 } }
            }
          }
        }
      });

      // --- Chart 2: Country Doughnut chart ---
      new Chart(document.getElementById("chart-country"), {
        type: 'doughnut',
        data: {
          labels: Object.keys(countryJobs),
          datasets: [{
            data: Object.values(countryJobs),
            backgroundColor: [
              'rgba(0, 229, 255, 0.65)',
              'rgba(255, 159, 10, 0.65)',
              'rgba(142, 84, 233, 0.65)',
              'rgba(48, 209, 88, 0.65)',
              'rgba(112, 128, 144, 0.65)'
            ],
            borderColor: '#101520',
            borderWidth: 2
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              position: 'right',
              labels: { color: '#708090', font: { family: 'JetBrains Mono', size: 9 } }
            }
          }
        }
      });

      // --- Chart 3: Discoveries Timeline line chart ---
      new Chart(document.getElementById("chart-timeline"), {
        type: 'line',
        data: {
          labels: dateLabels.map(dl => dl.label),
          datasets: [{
            label: 'Companies Discovered',
            data: timelineValues,
            fill: true,
            backgroundColor: 'rgba(0, 229, 255, 0.08)',
            borderColor: 'rgba(0, 229, 255, 1)',
            tension: 0.35,
            borderWidth: 2.5,
            pointBackgroundColor: 'rgba(0, 229, 255, 1)',
            pointRadius: 3
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
              ticks: { color: '#708090', font: { family: 'JetBrains Mono', size: 9 }, precision: 0 }
            },
            x: {
              grid: { display: false },
              ticks: { color: '#708090', font: { family: 'JetBrains Mono', size: 9 } }
            }
          }
        }
      });
    }

    function openModal(companyIndex) {
      const c = COMPANIES[companyIndex];
      if (!c) return;

      document.getElementById("modal-company-name").textContent = c.name;
      
      const webContainer = document.getElementById("modal-company-links");
      webContainer.innerHTML = "";
      
      const linkFields = [
        { label: "Website", url: c.website, icon: "🌐" },
        { label: "Careers", url: c.career_page_url, icon: "📄" },
        { label: "LinkedIn", url: c.linkedin_url, icon: "🔗" },
        { label: "GitHub", url: c.github_url, icon: "💻" }
      ];

      linkFields.forEach(f => {
        if (f.url) {
          const a = document.createElement("a");
          a.href = f.url;
          a.target = "_blank";
          a.className = "px-3 py-1.5 rounded bg-[#101520] hover:bg-[#161c28] text-[#00e5ff] border border-[#1e2638] hover:border-[#00e5ff]/50 transition-colors flex items-center space-x-1.5";
          a.innerHTML = `<span>${f.icon}</span> <span>${f.label}</span>`;
          webContainer.appendChild(a);
        }
      });

      // AI Enrichment Notes
      const aiContainer = document.getElementById("modal-ai-enrichment");
      if (c.ai_summary || (c.ai_talking_points && c.ai_talking_points.length > 0) || c.ai_fit_rationale) {
        let talkingPointsHtml = "";
        if (c.ai_talking_points && c.ai_talking_points.length > 0) {
          talkingPointsHtml = `
            <div class="mt-3">
              <div class="text-[10px] font-bold font-mono text-[#00e5ff] uppercase tracking-widest mb-2">Outreach Hooks / Talking Points</div>
              <ul class="list-disc list-inside space-y-1.5 text-sm text-slate-300 pl-1">
                ${c.ai_talking_points.map(pt => `<li>${pt}</li>`).join("")}
              </ul>
            </div>
          `;
        }

        aiContainer.innerHTML = `
          <div class="bg-[#0c1017] border border-[#1e2638] rounded-lg p-5 space-y-4">
            <div>
              <div class="text-[10px] font-bold font-mono text-[#00e5ff] uppercase tracking-widest mb-1.5">AI Summary Summary</div>
              <p class="text-sm text-slate-200 leading-relaxed">${c.ai_summary || "—"}</p>
            </div>
            <div>
              <div class="text-[10px] font-bold font-mono text-[#00e5ff] uppercase tracking-widest mb-1.5">Compatibility Fit Rationale</div>
              <p class="text-sm text-slate-200 leading-relaxed">${c.ai_fit_rationale || "—"}</p>
            </div>
            ${talkingPointsHtml}
          </div>
        `;
      } else {
        aiContainer.innerHTML = `
          <div class="bg-[#0c1017] border border-dashed border-[#1e2638] rounded-lg p-6 text-center text-slate-400 text-sm font-mono">
            ✨ No local AI enrichment — run <code class="bg-[#070b10] px-2 py-1 rounded text-[#00e5ff] border border-[#1e2638]">hiring-radar enrich</code> or <code class="bg-[#070b10] px-2 py-1 rounded text-[#00e5ff] border border-[#1e2638]">hiring-radar research "${c.name}"</code> to gather intelligence.
          </div>
        `;
      }

      // Contacts Section
      const contactsContainer = document.getElementById("modal-contacts");
      const recruiterName = c.recruiter_name || "—";
      const recruiterEmail = c.recruiter_email ? `<a href="mailto:${c.recruiter_email}" class="text-[#00e5ff] hover:underline">${c.recruiter_email}</a>` : "—";
      
      let genericEmailsHtml = "—";
      if (c.generic_emails && c.generic_emails.length > 0) {
        genericEmailsHtml = c.generic_emails.map(email => `<a href="mailto:${email}" class="text-[#00e5ff] hover:underline block">${email}</a>`).join("");
      }

      contactsContainer.innerHTML = `
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div class="bg-[#0c1017] border border-[#1e2638] rounded p-4 font-mono">
            <div class="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-3">Target Representative Contact</div>
            <div class="space-y-1.5 text-sm">
              <div><span class="text-slate-500">Name:</span> <span class="text-slate-200">${recruiterName}</span></div>
              <div><span class="text-slate-500">Email:</span> <span class="text-slate-200">${recruiterEmail}</span></div>
            </div>
          </div>
          <div class="bg-[#0c1017] border border-[#1e2638] rounded p-4 font-mono">
            <div class="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-3">Scraped Generic Emails</div>
            <div class="space-y-1.5 text-sm text-slate-200">
              ${genericEmailsHtml}
            </div>
          </div>
        </div>
      `;

      // Openings List Section
      const jobsContainer = document.getElementById("modal-jobs-body");
      jobsContainer.innerHTML = "";
      if (c.jobs && c.jobs.length > 0) {
        c.jobs.forEach(j => {
          const row = document.createElement("tr");
          row.className = "border-b border-[#1e2638]/50 hover:bg-[#161c28]/40";
          
          const titleCell = document.createElement("td");
          titleCell.className = "py-3 px-4 text-sm font-semibold text-slate-200 font-display";
          titleCell.textContent = j.job_title;
          row.appendChild(titleCell);

          const locCell = document.createElement("td");
          locCell.className = "py-3 px-4 text-sm text-slate-350 font-mono";
          locCell.textContent = j.location || "—";
          row.appendChild(locCell);

          const typeCell = document.createElement("td");
          typeCell.className = "py-3 px-4 text-center";
          const typeSpan = document.createElement("span");
          typeSpan.className = `px-2 py-0.5 rounded text-[10px] font-bold font-mono ${
            j.remote_type === 'remote' ? 'bg-[#30d158]/10 text-[#30d158] border border-[#30d158]/20' :
            j.remote_type === 'hybrid' ? 'bg-[#ff9f0a]/10 text-[#ff9f0a] border border-[#ff9f0a]/20' :
            'bg-slate-800 text-slate-400 border border-slate-700'
          }`;
          typeSpan.textContent = (j.remote_type || "unknown").toUpperCase();
          typeCell.appendChild(typeSpan);
          row.appendChild(typeCell);

          const actionCell = document.createElement("td");
          actionCell.className = "py-3 px-4 text-right font-mono";
          const a = document.createElement("a");
          a.href = j.job_url;
          a.target = "_blank";
          a.className = "text-xs text-[#00e5ff] hover:underline";
          a.textContent = "LINK ↗";
          actionCell.appendChild(a);
          row.appendChild(actionCell);

          jobsContainer.appendChild(row);
        });
      } else {
        jobsContainer.innerHTML = `
          <tr>
            <td colspan="4" class="py-6 text-center text-slate-500 italic text-sm font-mono">No active job postings recorded.</td>
          </tr>
        `;
      }

      // Notes logs
      const notesContainer = document.getElementById("modal-notes-section");
      if (c.notes && c.notes.length > 0) {
        notesContainer.classList.remove("hidden");
        const list = document.getElementById("modal-notes-list");
        list.innerHTML = c.notes.map(n => `<li class="text-slate-300">${n}</li>`).join("");
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

    // click outside close
    document.getElementById("detail-modal").addEventListener("click", (e) => {
      if (e.target === document.getElementById("detail-modal")) {
        closeModal();
      }
    });

    // escape key close
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
