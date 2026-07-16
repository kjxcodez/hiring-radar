function updatePaginationControls() {
  const totalPages = Math.max(1, Math.ceil(filteredCompanies.length / pageSize));
  
  // Clamping page size range
  if (currentPage > totalPages) {
    currentPage = totalPages;
  }
  if (currentPage < 1) {
    currentPage = 1;
  }

  // Update button states
  prevPageBtn.disabled = currentPage <= 1;
  nextPageBtn.disabled = currentPage >= totalPages;

  // Update text values
  currentPageNum.textContent = currentPage;
  totalPagesNum.textContent = totalPages;

  // Update range counters
  const rangeSpan = document.getElementById("count-visible-range");
  if (filteredCompanies.length === 0) {
    rangeSpan.textContent = "0";
  } else {
    const start = (currentPage - 1) * pageSize + 1;
    const end = Math.min(currentPage * pageSize, filteredCompanies.length);
    rangeSpan.textContent = `${start}–${end}`;
  }
}

function getCurrentPageSlice() {
  if (pageSize === -1) {
    return filteredCompanies;
  }
  const start = (currentPage - 1) * pageSize;
  const end = start + pageSize;
  return filteredCompanies.slice(start, end);
}

function changePageSize(size) {
  if (size === "all") {
    pageSize = -1;
  } else {
    pageSize = parseInt(size, 10);
  }
  currentPage = 1;
  renderTable(getCurrentPageSlice());
  updatePaginationControls();
}

function prevPage() {
  if (currentPage > 1) {
    currentPage--;
    renderTable(getCurrentPageSlice());
    updatePaginationControls();
  }
}

function nextPage() {
  const totalPages = Math.max(1, Math.ceil(filteredCompanies.length / pageSize));
  if (currentPage < totalPages) {
    currentPage++;
    renderTable(getCurrentPageSlice());
    updatePaginationControls();
  }
}
