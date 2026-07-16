document.addEventListener("DOMContentLoaded", () => {
  // Initialize selectors
  tbody = document.getElementById("companies-table-body");
  cardContainer = document.getElementById("companies-cards-container");
  searchInput = document.getElementById("search-input");
  sourceSelect = document.getElementById("source-select");
  remoteCheck = document.getElementById("remote-check");
  emailCheck = document.getElementById("email-check");
  aiCheck = document.getElementById("ai-check");

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

  searchInput.addEventListener("input", applyFilters);
  sourceSelect.addEventListener("change", applyFilters);
  remoteCheck.addEventListener("change", applyFilters);
  emailCheck.addEventListener("change", applyFilters);
  aiCheck.addEventListener("change", applyFilters);

  // Start initial states
  applyFilters();
  initCharts();
});
