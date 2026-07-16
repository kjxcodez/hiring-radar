// Global HUD elements references initialized during DOMContentLoaded setup
let tbody;
let cardContainer;
let searchInput;
let sourceSelect;
let remoteCheck;
let emailCheck;
let aiCheck;

// Pagination state variables
let currentPage = 1;
let pageSize = 10;
let filteredCompanies = [];

// Pagination elements references
let pageSizeSelect;
let prevPageBtn;
let nextPageBtn;
let currentPageNum;
let totalPagesNum;
