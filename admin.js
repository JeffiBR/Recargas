document.addEventListener('DOMContentLoaded', () => {
    // IMPORTANTE: Substitua pela URL do seu back-end no Render!
    const BACKEND_URL = 'https://thuder-recargas-backend.onrender.com'; // <-- MUDE AQUI!
    
    const tableBody = document.querySelector('#recargas-table tbody');
    let adminPassword = null;

    const addModal = document.getElementById('add-recharge-modal');
    const openModalBtn = document.getElementById('add-recharge-btn');
    const closeModalBtn = document.getElementById('close-modal-btn');
    const addRechargeForm = document.getElementById('add-recharge-form');

    function promptForPassword() {
        adminPassword = prompt("Por favor, insira a senha de administrador:", "");
        if (adminPassword) fetchRecargas();
        else {
            alert("Senha é necessária para acessar o painel.");
            tableBody.innerHTML = '<tr><td colspan="8" style="text-align:center;">Acesso negado.</td></tr>';
        }
    }

    async function fetchRecargas() {
        tableBody.innerHTML = '<tr><td colspan="8" style="text-align:center;">Carregando...</td></tr>';
        try {
            const response = await fetch(`${BACKEND_URL}/api/admin/recargas`, { headers: { 'Authorization': adminPassword } });
            if (response.status === 401) throw new Error('Senha incorreta.');
            if (!response.ok) throw new Error('Falha ao buscar dados.');
            const recargas = await response.json();
            renderTable(recargas);
        } catch (error) {
            alert(error.message);
            tableBody.innerHTML = `<tr><td colspan="8" style="text-align:center;">${error.message}</td></tr>`;
        }
    }

    function renderTable(recargas) {
        tableBody.innerHTML = '';
        if (recargas.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="8" style="text-align:center;">Nenhum pedido encontrado.</td></tr>';
            return;
        }
        recargas.forEach(recarga => {
            const row = document.createElement('tr');
            row.dataset.id = recarga.id;
            const timestamp = new Date(recarga.timestamp).toLocaleString('pt-BR');
            row.innerHTML = `
                <td>${timestamp}</td>
                <td data-field="nome">${recarga.nome}</td>
                <td data-field="telefone">${recarga.telefone}</td>
                <td data-field="recarga_selecionada">${recarga.recarga_selecionada}</td>
                <td data-field="senha_app">${recarga.senha_app || 'N/A'}</td>
                <td><select class="status-select" data-field="status"><option value="Na fila de espera" ${recarga.status === 'Na fila de espera' ? 'selected' : ''}>Na fila</option><option value="Concluída" ${recarga.status === 'Concluída' ? 'selected' : ''}>Concluída</option><option value="Erro" ${recarga.status === 'Erro' ? 'selected' : ''}>Erro</option></select></td>
                <td><textarea class="comment-textarea" data-field="admin_comment" rows="3">${recarga.admin_comment || ''}</textarea></td>
                <td class="action-buttons"><button class="edit-btn">Editar</button><button class="save-btn" style="display:none;">Salvar</button><button class="delete-btn">Excluir</button></td>
            `;
            tableBody.appendChild(row);
        });
    }
    
    openModalBtn.addEventListener('click', () => { addModal.style.display = 'block'; });
    closeModalBtn.addEventListener('click', () => { addModal.style.display = 'none'; });
    window.addEventListener('click', (event) => { if (event.target == addModal) { addModal.style.display = 'none'; } });

    addRechargeForm.addEventListener('submit', async (event) => {
        event.preventDefault();
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
                headers: { 'Content-Type': 'application/json', 'Authorization': adminPassword },
                body: JSON.stringify(newData)
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.message);
            alert('Novo pedido adicionado com sucesso!');
            addModal.style.display = 'none';
            addRechargeForm.reset();
            fetchRecargas();
        } catch (error) {
            alert(`Erro ao adicionar pedido: ${error.message}`);
        }
    });

    tableBody.addEventListener('click', async (event) => {
        const target = event.target;
        const row = target.closest('tr');
        if (!row) return;
        const recargaId = row.dataset.id;
        if (target.classList.contains('edit-btn')) {
            row.classList.add('editing');
            row.querySelectorAll('td[data-field]').forEach(cell => { cell.contentEditable = true; });
            target.style.display = 'none';
            row.querySelector('.save-btn').style.display = 'inline-block';
        }
        if (target.classList.contains('save-btn')) {
            const updatedData = {};
            row.querySelectorAll('[data-field]').forEach(el => { updatedData[el.dataset.field] = el.isContentEditable ? el.textContent : el.value; });
            target.textContent = 'Salvando...';
            target.disabled = true;
            try {
                const response = await fetch(`${BACKEND_URL}/api/admin/recargas/${recargaId}`, { method: 'PUT', headers: { 'Content-Type': 'application/json', 'Authorization': adminPassword }, body: JSON.stringify(updatedData) });
                if (!response.ok) { const res = await response.json(); throw new Error(res.message); }
                row.classList.remove('editing');
                row.querySelectorAll('td[data-field]').forEach(cell => cell.contentEditable = false);
                target.style.display = 'none';
                row.querySelector('.edit-btn').style.display = 'inline-block';
            } catch (error) {
                alert(error.message);
            } finally {
                target.textContent = 'Salvar';
                target.disabled = false;
            }
        }
        if (target.classList.contains('delete-btn')) {
            if (!confirm(`Tem certeza que deseja excluir o pedido de ${row.cells[1].textContent}?`)) return;
            try {
                const response = await fetch(`${BACKEND_URL}/api/admin/recargas/${recargaId}`, { method: 'DELETE', headers: { 'Authorization': adminPassword } });
                if (!response.ok) { const res = await response.json(); throw new Error(res.message); }
                row.remove();
                alert('Pedido excluído com sucesso!');
            } catch (error) {
                alert(error.message);
            }
        }
    });

    promptForPassword();

});
