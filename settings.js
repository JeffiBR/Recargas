document.addEventListener('DOMContentLoaded', () => {
    // IMPORTANTE: Substitua pela URL do seu back-end no Render!
    const BACKEND_URL = 'https://thuder-recargas-backend.onrender.com'; // <-- MUDE AQUI!
    
    let adminPassword = null;
    let currentConfig = {};

    const form = document.getElementById('settings-form');
    const headerTitleInput = document.getElementById('headerTitle');
    const headerSubtitleInput = document.getElementById('headerSubtitle');
    const footerWarningInput = document.getElementById('footerWarning');
    const pixKeyInput = document.getElementById('pixKey');
    const pixNameInput = document.getElementById('pixName');
    const optionsTimTextarea = document.getElementById('options-tim');
    const optionsVivoTextarea = document.getElementById('options-vivo');
    const optionsClaroTextarea = document.getElementById('options-claro');

    async function loadSettings() {
        try {
            const response = await fetch(`${BACKEND_URL}/api/config`);
            if (!response.ok) throw new Error('Falha ao carregar configurações.');
            currentConfig = await response.json();
            
            headerTitleInput.value = currentConfig.headerTitle;
            headerSubtitleInput.value = currentConfig.headerSubtitle;
            footerWarningInput.value = currentConfig.footerWarning;
            pixKeyInput.value = currentConfig.pixKey;
            pixNameInput.value = currentConfig.pixName;
            optionsTimTextarea.value = (currentConfig.rechargeOptions.Tim || []).join('\n');
            optionsVivoTextarea.value = (currentConfig.rechargeOptions.Vivo || []).join('\n');
            optionsClaroTextarea.value = (currentConfig.rechargeOptions.Claro || []).join('\n');

        } catch (error) {
            alert(error.message);
            document.body.innerHTML = `<p style="text-align:center;padding:20px;">${error.message}</p>`;
        }
    }

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        
        if (!adminPassword) {
            adminPassword = prompt("Para salvar, por favor, insira a senha de administrador:", "");
            if (!adminPassword) return;
        }

        const newConfig = {
            ...currentConfig,
            headerTitle: headerTitleInput.value,
            headerSubtitle: headerSubtitleInput.value,
            footerWarning: footerWarningInput.value,
            pixKey: pixKeyInput.value,
            pixName: pixNameInput.value,
            rechargeOptions: {
                Tim: optionsTimTextarea.value.split('\n').filter(line => line.trim() !== ''),
                Vivo: optionsVivoTextarea.value.split('\n').filter(line => line.trim() !== ''),
                Claro: optionsClaroTextarea.value.split('\n').filter(line => line.trim() !== '')
            }
        };

        const saveBtn = document.getElementById('save-settings-btn');
        saveBtn.textContent = 'Salvando...';
        saveBtn.disabled = true;

        try {
            const response = await fetch(`${BACKEND_URL}/api/admin/config`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json', 'Authorization': adminPassword },
                body: JSON.stringify(newConfig)
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.message);
            
            alert('Configurações salvas com sucesso!');
            currentConfig = newConfig;

        } catch (error) {
            alert(`Erro ao salvar: ${error.message}`);
            if (String(error.message).includes('Acesso negado')) adminPassword = null;
        } finally {
            saveBtn.textContent = 'Salvar Alterações';
            saveBtn.disabled = false;
        }
    });

    loadSettings();

});
