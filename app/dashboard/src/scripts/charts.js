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
