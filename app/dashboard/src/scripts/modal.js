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
