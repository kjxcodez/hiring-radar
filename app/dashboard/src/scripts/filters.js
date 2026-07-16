function renderTable(visibleCompanies) {
  tbody.innerHTML = "";
  cardContainer.innerHTML = "";
  
  if (visibleCompanies.length === 0) {
    const emptyHtml = `
      <div class="py-12 text-center text-slate-400 italic text-sm">
        No companies match the current search filters.
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
      ? "border-l-4 border-[#10b981]" 
      : "border-l-4 border-[#f59e0b] pulse-amber";

    // --- Desktop row design ---
    const row = document.createElement("tr");
    row.className = `${borderClasses} hover:bg-slate-50 cursor-pointer transition-all duration-150 relative group`;
    row.onclick = () => openModal(originalIndex);

    // Company info cell
    const nameCell = document.createElement("td");
    nameCell.className = "py-4 px-6";
    const nameDiv = document.createElement("div");
    nameDiv.className = "font-bold text-slate-900 font-display text-sm tracking-tight flex items-center space-x-2";
    nameDiv.textContent = c.name;
    nameCell.appendChild(nameDiv);
    if (c.website) {
      const webLink = document.createElement("a");
      webLink.href = c.website;
      webLink.target = "_blank";
      webLink.className = "text-xs text-indigo-650 hover:text-indigo-800 hover:underline block mt-0.5 font-mono";
      webLink.textContent = c.website;
      webLink.onclick = (e) => e.stopPropagation();
      nameCell.appendChild(webLink);
    }
    row.appendChild(nameCell);

    // Platform / Source cell
    const sourceCell = document.createElement("td");
    sourceCell.className = "py-4 px-6";
    const sourceSpan = document.createElement("span");
    sourceSpan.className = "px-2 py-0.5 rounded bg-slate-50 border border-slate-200 text-xs font-semibold font-mono text-slate-700";
    sourceSpan.textContent = c.ats_platform || (c.jobs && c.jobs[0] ? c.jobs[0].source : "feed");
    sourceCell.appendChild(sourceSpan);
    row.appendChild(sourceCell);

    // Jobs count cell
    const jobsCell = document.createElement("td");
    jobsCell.className = "py-4 px-6 text-center text-sm font-semibold font-mono text-slate-900";
    jobsCell.textContent = c.jobs ? c.jobs.length : 0;
    row.appendChild(jobsCell);

    // Email status cell
    const emailCell = document.createElement("td");
    emailCell.className = "py-4 px-6 text-center";
    const emailBadge = document.createElement("span");
    if (hasEmail) {
      emailBadge.className = "px-2 py-0.5 rounded text-[10px] font-semibold font-mono bg-[#10b981]/10 text-[#10b981] border border-[#10b981]/20";
      emailBadge.textContent = "READY";
      emailBadge.title = c.recruiter_email || c.generic_emails[0];
    } else {
      emailBadge.className = "px-2 py-0.5 rounded text-[10px] font-semibold font-mono bg-[#f59e0b]/10 text-[#f59e0b] border border-[#f59e0b]/20";
      emailBadge.textContent = "NO EMAIL";
    }
    emailCell.appendChild(emailBadge);
    row.appendChild(emailCell);

    // AI summary cell
    const aiCell = document.createElement("td");
    aiCell.className = "py-4 px-6 text-center";
    const aiBadge = document.createElement("span");
    if (hasAi) {
      aiBadge.className = "px-2 py-0.5 rounded text-[10px] font-semibold font-mono bg-indigo-50 text-indigo-750 border border-indigo-150";
      aiBadge.textContent = "ENRICHED";
      aiBadge.title = c.ai_summary;
    } else {
      aiBadge.className = "px-2 py-0.5 rounded text-[10px] font-semibold font-mono bg-[#f59e0b]/10 text-[#f59e0b] border border-[#f59e0b]/20";
      aiBadge.textContent = "MISSING";
    }
    aiCell.appendChild(aiBadge);
    row.appendChild(aiCell);

    // Last updated cell
    const updatedCell = document.createElement("td");
    updatedCell.className = "py-4 px-6 text-sm font-mono text-slate-500";
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
    card.className = `${borderClasses} p-4 bg-white hover:bg-slate-50 cursor-pointer transition-all duration-150 space-y-3`;
    card.onclick = () => openModal(originalIndex);

    const cardHeader = document.createElement("div");
    cardHeader.className = "flex justify-between items-start";
    const cardName = document.createElement("div");
    cardName.className = "font-bold text-slate-900 font-display text-sm";
    cardName.textContent = c.name;
    cardHeader.appendChild(cardName);

    const cardSource = document.createElement("span");
    cardSource.className = "px-2 py-0.5 rounded bg-slate-50 border border-slate-200 text-[10px] font-semibold font-mono text-slate-700";
    cardSource.textContent = c.ats_platform || (c.jobs && c.jobs[0] ? c.jobs[0].source : "feed");
    cardHeader.appendChild(cardSource);
    card.appendChild(cardHeader);

    if (c.website) {
      const cardLink = document.createElement("a");
      cardLink.href = c.website;
      cardLink.target = "_blank";
      cardLink.className = "text-xs text-indigo-650 hover:underline block font-mono truncate";
      cardLink.textContent = c.website;
      cardLink.onclick = (e) => e.stopPropagation();
      card.appendChild(cardLink);
    }

    const cardDetails = document.createElement("div");
    cardDetails.className = "flex flex-wrap items-center gap-2 text-xs pt-1";
    
    const cardJobs = document.createElement("span");
    cardJobs.className = "font-mono text-slate-500 bg-slate-50 px-2 py-0.5 rounded border border-slate-200";
    cardJobs.textContent = `${c.jobs ? c.jobs.length : 0} jobs`;
    cardDetails.appendChild(cardJobs);

    const cardEmailBadge = document.createElement("span");
    if (hasEmail) {
      cardEmailBadge.className = "px-2 py-0.5 rounded text-[10px] font-semibold font-mono bg-[#10b981]/10 text-[#10b981] border border-[#10b981]/20";
      cardEmailBadge.textContent = "READY";
    } else {
      cardEmailBadge.className = "px-2 py-0.5 rounded text-[10px] font-semibold font-mono bg-[#f59e0b]/10 text-[#f59e0b] border border-[#f59e0b]/20";
      cardEmailBadge.textContent = "NO EMAIL";
    }
    cardDetails.appendChild(cardEmailBadge);

    const cardAiBadge = document.createElement("span");
    if (hasAi) {
      cardAiBadge.className = "px-2 py-0.5 rounded text-[10px] font-semibold font-mono bg-indigo-50 text-indigo-750 border border-indigo-150";
      cardAiBadge.textContent = "ENRICHED";
    } else {
      cardAiBadge.className = "px-2 py-0.5 rounded text-[10px] font-semibold font-mono bg-[#f59e0b]/10 text-[#f59e0b] border border-[#f59e0b]/20";
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

  filteredCompanies = COMPANIES.filter(c => {
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

  document.getElementById("count-total").textContent = COMPANIES.length;
  document.getElementById("count-visible").textContent = filteredCompanies.length;

  // Reset to page 1 upon filtering change
  currentPage = 1;
  renderTable(getCurrentPageSlice());
  updatePaginationControls();
}
