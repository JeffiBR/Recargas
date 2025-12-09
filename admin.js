document.addEventListener('DOMContentLoaded', () => {
    // IMPORTANTE: Substitua pela URL do seu back-end no Render!
    const BACKEND_URL = 'https://thuder-recargas-backend.onrender.com'; // <-- MUDE AQUI!
    
    const tableBody = document.querySelector('#recargas-table tbody');
    let adminPassword = null;
    let currentPage = 1;
    let totalPages = 1;
    let currentFilters = {};
    let allData = [];
    
    // Modal elements
    const addModal = document.getElementById('add-recharge-modal');
    const openModalBtn = document.getElementById('add-recharge-btn');
    const closeModalBtn = document.getElementById('close-modal-btn');
    const addRechargeForm = document.getElementById('add-recharge-form');
    
    // Filter elements
    const searchInput = document.getElementById('search-input');
    const statusFilter = document.getElementById('status-filter');
    const operatorFilter = document.getElementById('operator-filter');
    const periodFilter = document.getElementById('period-filter');
    const dateStartInput = document.getElementById('date-start');
    const dateEndInput = document.getElementById('date-end');
    const applyFiltersBtn = document.getElementById('apply-filters');
    const clearFiltersBtn = document.getElementById('clear-filters');
    const dateRangeGroup = document.getElementById('date-range-group');
    const dateRangeGroupEnd = document.getElementById('date-range-group-end');
    
    // Pagination elements
    const prevPageBtn = document.getElementById('prev-page');
    const nextPageBtn = document.getElementById('next-page');
    const paginationInfo = document.getElementById('pagination-info');
    const resultsCount = document.getElementById('results-count');
    const loadingIndicator = document.getElementById('loading-indicator');
    
    // Export elements
    const exportBtn = document.getElementById('export-btn');
    const exportMenu = document.getElementById('export-menu');
    
    // Server status check
    let isServerReady = false;
    
    async function checkServerStatus() {
        try {
            const response = await fetch(`${BACKEND_URL}/health`, {
                method: 'GET',
                headers: {
                    'Cache-Control': 'no-cache'
                },
                timeout: 8000
            });
            
            if (response.ok) {
                isServerReady = true;
                return true;
            }
            return false;
        } catch (error) {
            console.log('Server not ready:', error.message);
            return false;
        }
    }
    
    async function initializeServerConnection() {
        let attempts = 0;
        const maxAttempts = 8;
        
        while (attempts < maxAttempts && !isServerReady) {
            attempts++;
            console.log(`Tentativa ${attempts} de conectar ao servidor...`);
            
            await checkServerStatus();
            
            if (!isServerReady && attempts < maxAttempts) {
                // Aguarda antes da próxima tentativa
                await new Promise(resolve => setTimeout(resolve, 4000));
            }
        }
        
        if (isServerReady) {
            console.log('Servidor conectado com sucesso!');
            return true;
        } else {
            console.log('Não foi possível conectar ao servidor após várias tentativas');
            return false;
        }
    }
    
    function promptForPassword() {
        adminPassword = prompt("Por favor, insira a senha de administrador:", "");
        if (adminPassword) {
            fetchRecargas();
            fetchDashboardData();
        } else {
            alert("Senha é necessária para acessar o painel.");
            tableBody.innerHTML = '<tr><td colspan="9" style="text-align:center;">Acesso negado.</td></tr>';
        }
    }
    
    async function fetchRecargas(page = 1, filters = {}) {
        if (!isServerReady) {
            showLoading(true);
            tableBody.innerHTML = '<tr><td colspan="9" style="text-align:center;padding:20px;">🔄 Conectando ao servidor... Aguarde alguns segundos.</td></tr>';
            
            // Tentar reconectar
            const connected = await initializeServerConnection();
            if (!connected) {
                showLoading(false);
                tableBody.innerHTML = '<tr><td colspan="9" style="text-align:center;padding:20px;">❌ Servidor temporariamente indisponível. Tente novamente em alguns segundos.</td></tr>';
                return;
            }
        }
        
        showLoading(true);
        
        try {
            // Build query string
            const params = new URLSearchParams({
                page: page,
                limit: 10,
                ...filters
            });
            
            const response = await fetch(`${BACKEND_URL}/api/admin/recargas?${params}`, { 
                headers: { 'Authorization': adminPassword } 
            });
            
            if (response.status === 401) {
                adminPassword = null;
                throw new Error('Senha incorreta ou expirada.');
            }
            
            if (!response.ok) {
                if (response.status === 503) {
                    isServerReady = false;
                    throw new Error('Servidor em processo de ativação. Tente novamente em alguns segundos.');
                }
                throw new Error('Falha ao buscar dados.');
            }
            
            const result = await response.json();
            allData = result.data || [];
            totalPages = result.total_pages || 1;
            currentPage = page;
            
            renderTable(result.data);
            updatePagination(result.total || allData.length, result.page || page, result.limit || 10);
            updateResultsCount(result.total || allData.length);
            
        } catch (error) {
            console.error('Erro ao buscar recargas:', error);
            
            if (error.message.includes('Senha incorreta') || error.message.includes('Acesso negado')) {
                adminPassword = null;
                alert('Senha incorreta. Por favor, faça login novamente.');
                window.location.reload();
            } else {
                alert(error.message);
                tableBody.innerHTML = `<tr><td colspan="9" style="text-align:center;padding:20px;">${error.message}</td></tr>`;
            }
        } finally {
            showLoading(false);
        }
    }
    
    async function fetchDashboardData() {
        if (!isServerReady) return;
        
        try {
            const response = await fetch(`${BACKEND_URL}/api/admin/dashboard`, { 
                headers: { 'Authorization': adminPassword } 
            });
            
            if (response.status === 401) {
                adminPassword = null;
                throw new Error('Senha incorreta.');
            }
            
            if (!response.ok) throw new Error('Falha ao buscar dados do dashboard.');
            
            const data = await response.json();
            updateCharts(data);
            updateMetrics(data);
            
        } catch (error) {
            console.error('Erro ao buscar dados do dashboard:', error);
        }
    }
    
    function renderTable(recargas) {
        tableBody.innerHTML = '';
        
        if (!recargas || recargas.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="9" style="text-align:center;padding:20px;">Nenhum pedido encontrado.</td></tr>';
            return;
        }
        
        recargas.forEach(recarga => {
            const row = document.createElement('tr');
            row.dataset.id = recarga.id;
            const timestamp = new Date(recarga.timestamp || recarga.created_at).toLocaleString('pt-BR');
            
            const cells = [
                timestamp,
                recarga.nome || 'N/A',
                recarga.telefone || 'N/A',
                createOperatorBadge(recarga.operadora || 'N/A').outerHTML,
                recarga.recarga_selecionada || 'N/A',
                recarga.senha_app || 'N/A',
                createStatusDropdown(recarga.status || 'na-fila').outerHTML,
                createCommentSection(recarga.admin_comment || '').outerHTML,
                `<div class="action-buttons">
                    <button class="edit-btn"><i class="fas fa-edit"></i> Editar</button>
                    <button class="save-btn" style="display:none;"><i class="fas fa-save"></i> Salvar</button>
                    <button class="delete-btn"><i class="fas fa-trash"></i> Excluir</button>
                </div>`
            ];
            
            cells.forEach(cellContent => {
                const cell = document.createElement('td');
                cell.innerHTML = cellContent;
                row.appendChild(cell);
            });
            
            tableBody.appendChild(row);
        });
    }
    
    function updatePagination(total, page, limit) {
        prevPageBtn.disabled = page <= 1;
        nextPageBtn.disabled = page >= totalPages;
        paginationInfo.textContent = `Página ${page} de ${totalPages}`;
    }
    
    function updateResultsCount(total) {
        const showing = Math.min(total, 10);
        resultsCount.textContent = `Mostrando ${showing} de ${total} resultados`;
    }
    
    function showLoading(show) {
        loadingIndicator.style.display = show ? 'flex' : 'none';
        if (show) {
            loadingIndicator.innerHTML = '<div class="loading-spinner"></div> Conectando ao servidor...';
        }
    }
    
    function createOperatorBadge(operator) {
        const badge = document.createElement('span');
        badge.className = `operator operator-${operator.toLowerCase()}`;
        
        let icon = '';
        switch(operator.toLowerCase()) {
            case 'tim':
                icon = 'fas fa-sim-card';
                break;
            case 'vivo':
                icon = 'fas fa-sim-card';
                break;
            case 'claro':
                icon = 'fas fa-sim-card';
                break;
            default:
                icon = 'fas fa-question-circle';
        }
        
        badge.innerHTML = `<i class="${icon}"></i> ${operator}`;
        return badge;
    }
    
    function createStatusDropdown(currentStatus) {
        const container = document.createElement('div');
        container.className = 'status-dropdown';
        
        const select = document.createElement('select');
        select.className = 'status-select';
        select.dataset.field = 'status';
        
        const statuses = [
            { value: 'recarga-efetuada', text: 'Recarga Efetuada' },
            { value: 'sendo-processada', text: 'Sendo Processada' },
            { value: 'na-fila', text: 'Na Fila' },
            { value: 'erro', text: 'Erro' }
        ];
        
        statuses.forEach(status => {
            const option = document.createElement('option');
            option.value = status.value;
            option.textContent = status.text;
            if (status.value === currentStatus) {
                option.selected = true;
            }
            select.appendChild(option);
        });
        
        select.addEventListener('change', function() {
            const row = this.closest('tr');
            const recargaId = row.dataset.id;
            updateRecargaField(recargaId, 'status', this.value);
        });
        
        container.appendChild(select);
        return container;
    }
    
    function createCommentSection(currentComment) {
        const container = document.createElement('div');
        container.className = 'comment-container';
        
        const textarea = document.createElement('textarea');
        textarea.className = 'comment-input';
        textarea.dataset.field = 'admin_comment';
        textarea.value = currentComment || '';
        textarea.placeholder = 'Adicionar comentário...';
        
        const saveBtn = document.createElement('button');
        saveBtn.className = 'comment-save-btn save-btn';
        saveBtn.innerHTML = '<i class="fas fa-save"></i> Salvar';
        
        saveBtn.addEventListener('click', function() {
            const row = this.closest('tr');
            const recargaId = row.dataset.id;
            updateRecargaField(recargaId, 'admin_comment', textarea.value);
        });
        
        container.appendChild(textarea);
        container.appendChild(saveBtn);
        return container;
    }
    
    async function updateRecargaField(recargaId, field, value) {
        if (!isServerReady) {
            alert('Servidor não está pronto. Aguarde alguns segundos e tente novamente.');
            return;
        }
        
        try {
            const response = await fetch(`${BACKEND_URL}/api/admin/recargas/${recargaId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': adminPassword
                },
                body: JSON.stringify({ [field]: value })
            });
            
            if (response.status === 401) {
                adminPassword = null;
                throw new Error('Senha expirada. Faça login novamente.');
            }
            
            if (!response.ok) {
                const res = await response.json();
                throw new Error(res.message || 'Erro ao atualizar');
            }
            
            showSaveToast();
            
            if (field === 'status') {
                fetchDashboardData();
            }
            
        } catch (error) {
            alert(error.message);
            if (error.message.includes('Senha expirada')) {
                window.location.reload();
            }
        }
    }
    
    function showSaveToast() {
        const toast = document.getElementById('save-toast');
        toast.classList.add('show');
        
        setTimeout(() => {
            toast.classList.remove('show');
        }, 3000);
    }
    
    function buildFilters() {
        const filters = {};
        
        if (searchInput.value.trim()) {
            filters.search = searchInput.value.trim();
        }
        
        if (statusFilter.value) {
            filters.status = statusFilter.value;
        }
        
        if (operatorFilter.value) {
            filters.operadora = operatorFilter.value;
        }
        
        if (periodFilter.value) {
            if (periodFilter.value === 'custom') {
                if (dateStartInput.value && dateEndInput.value) {
                    filters.dateStart = dateStartInput.value;
                    filters.dateEnd = dateEndInput.value;
                }
            } else {
                filters.period = periodFilter.value;
            }
        }
        
        return filters;
    }
    
    applyFiltersBtn.addEventListener('click', () => {
        currentFilters = buildFilters();
        fetchRecargas(1, currentFilters);
    });
    
    clearFiltersBtn.addEventListener('click', () => {
        searchInput.value = '';
        statusFilter.value = '';
        operatorFilter.value = '';
        periodFilter.value = '';
        dateStartInput.value = '';
        dateEndInput.value = '';
        dateRangeGroup.style.display = 'none';
        dateRangeGroupEnd.style.display = 'none';
        
        currentFilters = {};
        fetchRecargas(1, {});
    });
    
    periodFilter.addEventListener('change', () => {
        if (periodFilter.value === 'custom') {
            dateRangeGroup.style.display = 'block';
            dateRangeGroupEnd.style.display = 'block';
        } else {
            dateRangeGroup.style.display = 'none';
            dateRangeGroupEnd.style.display = 'none';
        }
    });
    
    prevPageBtn.addEventListener('click', () => {
        if (currentPage > 1) {
            fetchRecargas(currentPage - 1, currentFilters);
        }
    });
    
    nextPageBtn.addEventListener('click', () => {
        if (currentPage < totalPages) {
            fetchRecargas(currentPage + 1, currentFilters);
        }
    });
    
    exportBtn.addEventListener('click', () => {
        exportMenu.classList.toggle('show');
    });
    
    document.addEventListener('click', (e) => {
        if (!exportBtn.contains(e.target) && !exportMenu.contains(e.target)) {
            exportMenu.classList.remove('show');
        }
    });
    
    document.querySelectorAll('.export-option').forEach(option => {
        option.addEventListener('click', async function() {
            const format = this.dataset.format;
            const filters = buildFilters();
            
            if (!isServerReady) {
                alert('Servidor não está pronto. Aguarde alguns segundos e tente novamente.');
                return;
            }
            
            try {
                showLoading(true);
                
                const params = new URLSearchParams({
                    format: format,
                    ...filters
                });
                
                const response = await fetch(`${BACKEND_URL}/api/admin/export?${params}`, {
                    headers: { 'Authorization': adminPassword }
                });
                
                if (response.status === 401) {
                    adminPassword = null;
                    throw new Error('Senha expirada. Faça login novamente.');
                }
                
                if (!response.ok) throw new Error('Falha ao exportar dados.');
                
                // Handle file download
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `recargas_${new Date().toISOString().split('T')[0]}.${format}`;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
                
                showSaveToast();
                
            } catch (error) {
                alert(error.message);
                if (error.message.includes('Senha expirada')) {
                    window.location.reload();
                }
            } finally {
                showLoading(false);
                exportMenu.classList.remove('show');
            }
        });
    });
    
    openModalBtn.addEventListener('click', () => { 
        addModal.style.display = 'block'; 
    });
    
    closeModalBtn.addEventListener('click', () => { 
        addModal.style.display = 'none'; 
    });
    
    window.addEventListener('click', (event) => { 
        if (event.target == addModal) { 
            addModal.style.display = 'none'; 
        } 
    });
    
    addRechargeForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        
        if (!isServerReady) {
            alert('Servidor não está pronto. Aguarde alguns segundos e tente novamente.');
            return;
        }
        
        const newData = {
            nome: document.getElementById('add-nome').value,
            telefone: document.getElementById('add-telefone').value,
            operadora: document.getElementById('add-operadora').value,
            recarga_selecionada: document.getElementById('add-recarga_selecionada').value,
            senha_app: document.getElementById('add-senha_app').value
        };
        
        try {
            const response = await fetch(`${BACKEND_URL}/api/admin/recargas`, {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json', 
                    'Authorization': adminPassword 
                },
                body: JSON.stringify(newData)
            });
            
            if (response.status === 401) {
                adminPassword = null;
                throw new Error('Senha expirada. Faça login novamente.');
            }
            
            const result = await response.json();
            if (!response.ok) throw new Error(result.message);
            
            alert('Novo pedido adicionado com sucesso!');
            addModal.style.display = 'none';
            addRechargeForm.reset();
            fetchRecargas(currentPage, currentFilters);
            fetchDashboardData();
        } catch (error) {
            alert(`Erro ao adicionar pedido: ${error.message}`);
            if (error.message.includes('Senha expirada')) {
                window.location.reload();
            }
        }
    });
    
    tableBody.addEventListener('click', async (event) => {
        const target = event.target;
        const row = target.closest('tr');
        if (!row) return;
        const recargaId = row.dataset.id;
        
        if (target.classList.contains('edit-btn') || target.closest('.edit-btn')) {
            row.classList.add('editing');
            row.querySelectorAll('td[data-field]').forEach(cell => { 
                cell.contentEditable = true; 
            });
            const editBtn = row.querySelector('.edit-btn');
            const saveBtn = row.querySelector('.save-btn');
            editBtn.style.display = 'none';
            saveBtn.style.display = 'inline-block';
        }
        
        if (target.classList.contains('save-btn') || target.closest('.save-btn')) {
            const updatedData = {};
            row.querySelectorAll('[data-field]').forEach(el => { 
                updatedData[el.dataset.field] = el.isContentEditable ? el.textContent : el.value; 
            });
            
            const saveBtn = row.querySelector('.save-btn');
            saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Salvando...';
            saveBtn.disabled = true;
            
            try {
                const response = await fetch(`${BACKEND_URL}/api/admin/recargas/${recargaId}`, { 
                    method: 'PUT', 
                    headers: { 
                        'Content-Type': 'application/json', 
                        'Authorization': adminPassword 
                    }, 
                    body: JSON.stringify(updatedData) 
                });
                
                if (response.status === 401) {
                    adminPassword = null;
                    throw new Error('Senha expirada. Faça login novamente.');
                }
                
                if (!response.ok) { 
                    const res = await response.json(); 
                    throw new Error(res.message); 
                }
                
                row.classList.remove('editing');
                row.querySelectorAll('td[data-field]').forEach(cell => cell.contentEditable = false);
                const editBtn = row.querySelector('.edit-btn');
                editBtn.style.display = 'inline-block';
                saveBtn.style.display = 'none';
                
                showSaveToast();
                fetchDashboardData();
                
            } catch (error) {
                alert(error.message);
                if (error.message.includes('Senha expirada')) {
                    window.location.reload();
                }
            } finally {
                saveBtn.innerHTML = '<i class="fas fa-save"></i> Salvar';
                saveBtn.disabled = false;
            }
        }
        
        if (target.classList.contains('delete-btn') || target.closest('.delete-btn')) {
            if (!confirm(`Tem certeza que deseja excluir o pedido de ${row.cells[1].textContent}?`)) return;
            
            try {
                const response = await fetch(`${BACKEND_URL}/api/admin/recargas/${recargaId}`, { 
                    method: 'DELETE', 
                    headers: { 
                        'Authorization': adminPassword 
                    } 
                });
                
                if (response.status === 401) {
                    adminPassword = null;
                    throw new Error('Senha expirada. Faça login novamente.');
                }
                
                if (!response.ok) { 
                    const res = await response.json(); 
                    throw new Error(res.message); 
                }
                
                row.remove();
                alert('Pedido excluído com sucesso!');
                
                fetchDashboardData();
                
                if (tableBody.children.length === 1) {
                    fetchRecargas(currentPage, currentFilters);
                }
                
            } catch (error) {
                alert(error.message);
                if (error.message.includes('Senha expirada')) {
                    window.location.reload();
                }
            }
        }
    });
    
    let searchTimeout;
    searchInput.addEventListener('input', () => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            currentFilters = buildFilters();
            fetchRecargas(1, currentFilters);
        }, 500);
    });
    
    function initializeCharts() {
        const isDarkTheme = document.body.getAttribute('data-theme') === 'dark';
        
        const statusCtx = document.getElementById('statusChart').getContext('2d');
        window.statusChart = new Chart(statusCtx, {
            type: 'doughnut',
            data: {
                labels: ['Recarga Efetuada', 'Sendo Processada', 'Na Fila', 'Erro'],
                datasets: [{
                    data: [0, 0, 0, 0],
                    backgroundColor: [
                        '#16a34a',
                        '#f59e0b',
                        '#4f46e5',
                        '#ef4444'
                    ],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            color: isDarkTheme ? '#e6eef7' : '#071028',
                            padding: 20
                        }
                    }
                }
            }
        });
        
        const operatorCtx = document.getElementById('operatorChart').getContext('2d');
        window.operatorChart = new Chart(operatorCtx, {
            type: 'bar',
            data: {
                labels: ['Tim', 'Vivo', 'Claro'],
                datasets: [{
                    label: 'Quantidade de Pedidos',
                    data: [0, 0, 0],
                    backgroundColor: [
                        '#007bff',
                        '#8a2be2',
                        '#ff0000'
                    ],
                    borderRadius: 8
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            color: isDarkTheme ? '#9aa4b2' : '#4b5563',
                            stepSize: 1
                        },
                        grid: {
                            color: isDarkTheme ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)'
                        }
                    },
                    x: {
                        ticks: {
                            color: isDarkTheme ? '#9aa4b2' : '#4b5563'
                        },
                        grid: {
                            display: false
                        }
                    }
                }
            }
        });
    }
    
    function updateCharts(data) {
        if (!window.statusChart || !window.operatorChart) return;
        
        window.statusChart.data.datasets[0].data = [
            data.statusCounts['recarga-efetuada'] || 0,
            data.statusCounts['sendo-processada'] || 0,
            data.statusCounts['na-fila'] || 0,
            data.statusCounts['erro'] || 0
        ];
        window.statusChart.update();
        
        window.operatorChart.data.datasets[0].data = [
            data.operatorCounts['Tim'] || 0,
            data.operatorCounts['Vivo'] || 0,
            data.operatorCounts['Claro'] || 0
        ];
        window.operatorChart.update();
    }
    
    function updateMetrics(data) {
        document.getElementById('total-orders').textContent = data.total || 0;
        document.getElementById('completed-orders').textContent = data.statusCounts['recarga-efetuada'] || 0;
        document.getElementById('pending-orders').textContent = (data.statusCounts['sendo-processada'] || 0) + (data.statusCounts['na-fila'] || 0);
        document.getElementById('error-orders').textContent = data.statusCounts['erro'] || 0;
        
        if (data.variations) {
            updateVariationIndicator('total-orders-change', data.variations.total);
            updateVariationIndicator('completed-orders-change', data.variations.completed);
            updateVariationIndicator('pending-orders-change', data.variations.pending);
            updateVariationIndicator('error-orders-change', data.variations.error);
        }
    }
    
    function updateVariationIndicator(elementId, variation) {
        const element = document.getElementById(elementId);
        if (!element) return;
        
        element.className = 'metric-change ' + (variation >= 0 ? 'positive' : 'negative');
        element.innerHTML = variation >= 0 
            ? `<i class="fas fa-arrow-up"></i> ${Math.abs(variation)}%`
            : `<i class="fas fa-arrow-down"></i> ${Math.abs(variation)}%`;
    }
    
    // Initialize
    async function init() {
        showLoading(true);
        
        // Tentar conectar ao servidor primeiro
        const connected = await initializeServerConnection();
        
        if (connected) {
            initializeCharts();
            promptForPassword();
        } else {
            tableBody.innerHTML = '<tr><td colspan="9" style="text-align:center;padding:20px;">❌ Não foi possível conectar ao servidor. Tente recarregar a página em alguns segundos.</td></tr>';
            showLoading(false);
        }
    }
    
    init();
});