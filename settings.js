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
        
        return isServerReady;
    }
    
    async function loadSettings() {
        try {
            // Tentar conectar ao servidor primeiro
            if (!isServerReady) {
                const connected = await initializeServerConnection();
                if (!connected) {
                    throw new Error('Não foi possível conectar ao servidor. Tente novamente em alguns segundos.');
                }
            }
            
            const response = await fetch(`${BACKEND_URL}/api/config`);
            if (!response.ok) throw new Error('Falha ao carregar configurações.');
            
            currentConfig = await response.json();
            
            headerTitleInput.value = currentConfig.headerTitle || '';
            headerSubtitleInput.value = currentConfig.headerSubtitle || '';
            footerWarningInput.value = currentConfig.footerWarning || '';
            pixKeyInput.value = currentConfig.pixKey || '';
            pixNameInput.value = currentConfig.pixName || '';
            optionsTimTextarea.value = (currentConfig.rechargeOptions?.Tim || []).join('\n');
            optionsVivoTextarea.value = (currentConfig.rechargeOptions?.Vivo || []).join('\n');
            optionsClaroTextarea.value = (currentConfig.rechargeOptions?.Claro || []).join('\n');
            
            // Mostrar mensagem de sucesso
            document.getElementById('save-settings-btn').textContent = 'Configurações Carregadas';
            setTimeout(() => {
                document.getElementById('save-settings-btn').textContent = 'Salvar Alterações';
            }, 2000);
            
        } catch (error) {
            alert(error.message);
            document.body.innerHTML = `<div style="text-align:center;padding:20px;max-width:600px;margin:50px auto;">
                <h2 style="color:#ef4444;">❌ Erro de Conexão</h2>
                <p>${error.message}</p>
                <p>O servidor está em processo de ativação. Isso pode levar até 45 segundos.</p>
                <button onclick="window.location.reload()" style="padding:10px 20px;background:#4f46e5;color:white;border:none;border-radius:5px;cursor:pointer;margin-top:20px;">
                    🔄 Tentar Novamente
                </button>
            </div>`;
        }
    }
    
    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        
        if (!adminPassword) {
            adminPassword = prompt("Para salvar, por favor, insira a senha de administrador:", "");
            if (!adminPassword) return;
        }
        
        if (!isServerReady) {
            alert('Servidor não está pronto. Aguarde alguns segundos e tente novamente.');
            return;
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
        const originalText = saveBtn.textContent;
        saveBtn.textContent = 'Salvando...';
        saveBtn.disabled = true;
        
        try {
            const response = await fetch(`${BACKEND_URL}/api/admin/config`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json', 'Authorization': adminPassword },
                body: JSON.stringify(newConfig)
            });
            
            if (response.status === 401) {
                adminPassword = null;
                throw new Error('Senha incorreta ou expirada.');
            }
            
            const result = await response.json();
            if (!response.ok) throw new Error(result.message);
            
            alert('Configurações salvas com sucesso!');
            currentConfig = newConfig;
            
            // Feedback visual
            saveBtn.textContent = '✅ Salvo!';
            saveBtn.style.background = '#16a34a';
            setTimeout(() => {
                saveBtn.textContent = originalText;
                saveBtn.style.background = '';
            }, 2000);
            
        } catch (error) {
            alert(`Erro ao salvar: ${error.message}`);
            if (String(error.message).includes('Senha incorreta') || String(error.message).includes('Acesso negado')) {
                adminPassword = null;
            }
        } finally {
            saveBtn.textContent = originalText;
            saveBtn.disabled = false;
        }
    });
    
    // Adicionar botão de teste de conexão
    const header = document.querySelector('.header');
    const testButton = document.createElement('button');
    testButton.innerHTML = '🔗 Testar Conexão';
    testButton.style.cssText = 'padding:8px 12px;background:#f59e0b;color:white;border:none;border-radius:5px;cursor:pointer;font-size:14px;margin-left:10px;';
    testButton.onclick = async () => {
        testButton.disabled = true;
        testButton.innerHTML = '🔗 Testando...';
        
        try {
            const connected = await initializeServerConnection();
            if (connected) {
                alert('✅ Conexão com o servidor estabelecida com sucesso!');
                testButton.innerHTML = '✅ Conectado';
                testButton.style.background = '#16a34a';
            } else {
                alert('❌ Não foi possível conectar ao servidor. Tente novamente em alguns segundos.');
                testButton.innerHTML = '❌ Falha';
                testButton.style.background = '#ef4444';
            }
        } catch (error) {
            alert('Erro ao testar conexão: ' + error.message);
            testButton.innerHTML = '🔗 Testar Conexão';
            testButton.style.background = '#f59e0b';
        } finally {
            setTimeout(() => {
                testButton.disabled = false;
                testButton.innerHTML = '🔗 Testar Conexão';
                testButton.style.background = '#f59e0b';
            }, 3000);
        }
    };
    
    header.querySelector('.nav-links').appendChild(testButton);
    
    // Carregar configurações
    loadSettings();
});