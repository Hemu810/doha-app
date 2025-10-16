document.addEventListener('DOMContentLoaded', () => {
    // --- STATE MANAGEMENT ---
    let currentQuery = '';
    let currentTableData = [];

    // --- DOM ELEMENTS ---
    const searchInput = document.getElementById('searchInput');
    const dbTabsContainer = document.getElementById('dbTabs');
    const searchIcon = document.querySelector('.search-icon');
    const resultsContainer = document.getElementById('resultsContainer');
    const loadingIndicator = document.getElementById('loadingIndicator');
    const summaryView = document.getElementById('summaryView');
    const detailedView = document.getElementById('detailedView');
    const summaryText = document.getElementById('summaryText');
    const moduleButtonsContainer = document.getElementById('moduleButtonsContainer');
    const backButton = document.getElementById('backButton');
    const detailsTitle = document.getElementById('detailsTitle');
    const aiSummaryText = document.getElementById('aiSummaryText');
    const tableContainer = document.getElementById('tableContainer');
    const exportButton = document.getElementById('exportButton');

    // --- UI VIEW MANAGEMENT ---
    const showView = (viewToShow) => {
        loadingIndicator.classList.add('hidden');
        summaryView.classList.add('hidden');
        detailedView.classList.add('hidden');
        if (viewToShow) {
            resultsContainer.classList.remove('hidden');
            viewToShow.classList.remove('hidden');
        } else {
            resultsContainer.classList.add('hidden');
        }
    };

    // --- CORE LOGIC FUNCTIONS ---
    const performSearch = async () => {
        currentQuery = searchInput.value.trim();
        const selectedDbs = Array.from(dbTabsContainer.querySelectorAll('.db-tab.active')).map(btn => btn.textContent);
        if (!currentQuery || selectedDbs.length === 0) {
            alert('Please type a query and select at least one database.');
            return;
        }
        showView(loadingIndicator);
        try {
            const response = await fetch('http://127.0.0.1:5000/api/query', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: currentQuery, selected_dbs: selectedDbs }),
            });
            if (!response.ok) throw new Error((await response.json()).error || 'API request failed');
            const data = await response.json();
            displaySummaryView(data);
        } catch (error) {
            summaryText.textContent = `An error occurred: ${error.message}`;
            moduleButtonsContainer.innerHTML = '';
            showView(summaryView);
        }
    };

    const displaySummaryView = (data) => {
        summaryText.textContent = data.summary;
        moduleButtonsContainer.innerHTML = '';
        if (Object.keys(data.module_counts).length === 0) {
            moduleButtonsContainer.innerHTML = '<p class="no-results">No relevant records found.</p>';
        } else {
            for (const [module, count] of Object.entries(data.module_counts)) {
                const button = document.createElement('button');
                button.className = 'module-button';
                button.dataset.module = module;
                button.innerHTML = `<span>${module}</span> <span>(${count.toLocaleString()})</span>`;
                moduleButtonsContainer.appendChild(button);
            }
        }
        showView(summaryView);
    };

    const showDetailedView = async (module) => {
        showView(loadingIndicator);
        detailsTitle.textContent = `Detailed Report for "${module}"`;
        try {
            const response = await fetch('http://127.0.0.1:5000/api/details', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: currentQuery, module: module }),
            });
            if (!response.ok) throw new Error((await response.json()).error || 'API request failed');
            const data = await response.json();
            aiSummaryText.textContent = data.aiSummary;
            if (data.tables && data.tables.length > 0) {
                const tableData = data.tables[0].data;
                currentTableData = tableData;
                const tableElement = createDynamicTable(tableData);
                tableContainer.innerHTML = '';
                tableContainer.appendChild(tableElement);
            }
            showView(detailedView);
        } catch (error) {
            alert(`Error fetching details: ${error.message}`);
            showView(summaryView);
        }
    };

    const createDynamicTable = (data) => {
        const container = document.createElement('div');
        container.className = 'table-scroll-wrapper';
        if (!data || data.length === 0) {
            container.innerHTML = '<p>No detailed data available for this query.</p>';
            return container;
        }
        const table = document.createElement('table');
        const thead = document.createElement('thead');
        const headerRow = document.createElement('tr');
        const headers = Object.keys(data[0]);
        headers.forEach(h => { const th = document.createElement('th'); th.textContent = h; headerRow.appendChild(th); });
        thead.appendChild(headerRow);
        table.appendChild(thead);
        const tbody = document.createElement('tbody');
        data.forEach(rowData => {
            const row = document.createElement('tr');
            headers.forEach(header => {
                const td = document.createElement('td');
                td.textContent = rowData[header];
                row.appendChild(td);
            });
            tbody.appendChild(row);
        });
        table.appendChild(tbody);
        container.appendChild(table);
        return container;
    };

    const exportToCSV = () => {
        if (!currentTableData || currentTableData.length === 0) {
            alert("No data to export."); return;
        }
        const headers = Object.keys(currentTableData[0]);
        const csvRows = [headers.join(',')];
        for (const row of currentTableData) {
            const values = headers.map(header => `"${('' + (row[header] || '')).replace(/"/g, '""')}"`);
            csvRows.push(values.join(','));
        }
        const blob = new Blob([csvRows.join('\n')], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.setAttribute('href', url);
        a.setAttribute('download', 'report.csv');
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    };

    // --- EVENT LISTENERS ---
    if (searchInput) searchInput.addEventListener('keyup', (e) => { if (e.key === 'Enter') performSearch(); });
    if (searchIcon) searchIcon.addEventListener('click', performSearch);
    if (dbTabsContainer) {
        dbTabsContainer.addEventListener('click', (e) => {
            if (e.target.tagName === 'BUTTON' && e.target.classList.contains('db-tab')) {
                const button = e.target;
                const isMaster = button.textContent === 'Master DB';
                if (isMaster) {
                    dbTabsContainer.querySelectorAll('.db-tab').forEach(btn => btn.classList.remove('active'));
                    button.classList.add('active');
                } else {
                    const masterButton = dbTabsContainer.querySelector('.db-tab');
                    if (masterButton && masterButton.textContent === 'Master DB') masterButton.classList.remove('active');
                    button.classList.toggle('active');
                }
            }
        });
    }
    if (moduleButtonsContainer) {
        moduleButtonsContainer.addEventListener('click', (e) => {
            const button = e.target.closest('.module-button');
            if (button) {
                const module = button.dataset.module;
                showDetailedView(module);
            }
        });
    }
    if (backButton) {
        backButton.addEventListener('click', () => {
            showView(summaryView);
        });
    }
    if (exportButton) exportButton.addEventListener('click', exportToCSV);
});