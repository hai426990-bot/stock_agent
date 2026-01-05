import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, join_room
from threading import Lock
from stock_agent import StockAgent
from config import Config
from tools.logger import logger
import uuid
import os
import re
from datetime import datetime, date, timedelta
import numpy as np
import pandas as pd
import threading
import time

_data_fetcher_singleton = None
_data_fetcher_lock = Lock()

def _get_data_fetcher():
    global _data_fetcher_singleton
    if _data_fetcher_singleton is not None:
        return _data_fetcher_singleton
    with _data_fetcher_lock:
        if _data_fetcher_singleton is None:
            from tools.data_fetcher import DataFetcher
            _data_fetcher_singleton = DataFetcher()
    return _data_fetcher_singleton

template_dir = os.path.join(os.path.dirname(__file__), 'web', 'templates')
static_dir = os.path.join(os.path.dirname(__file__), 'web', 'static')

app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
app.config['SECRET_KEY'] = Config.FLASK_SECRET_KEY
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    ping_timeout=60,
    ping_interval=25,
    async_mode='eventlet',
    logger=Config.FLASK_DEBUG,
    engineio_logger=Config.FLASK_DEBUG
)

thread = None
thread_lock = Lock()

active_tasks = {}
client_sessions = {}
message_buffers = {}

TASK_TIMEOUT = 3600
BATCH_INTERVAL = 0.5

def cleanup_old_tasks():
    while True:
        try:
            current_time = datetime.now()
            tasks_to_remove = []
            
            with thread_lock:
                active_tasks_items = list(active_tasks.items())
                client_sessions_items = list(client_sessions.items())
                message_buffers_items = list(message_buffers.items())
            
            for task_id, task_info in active_tasks_items:
                task_time = task_info.get('timestamp', current_time)
                if isinstance(task_time, str):
                    task_time = datetime.fromisoformat(task_time)
                
                if current_time - task_time > timedelta(seconds=TASK_TIMEOUT):
                    tasks_to_remove.append(task_id)
            
            if tasks_to_remove:
                with thread_lock:
                    for task_id in tasks_to_remove:
                        if task_id in active_tasks:
                            del active_tasks[task_id]
                            logger.info(f"Cleaned up old task: {task_id}")
            
            sessions_to_remove = []
            for session_id, session_info in client_sessions_items:
                session_time = session_info.get('last_activity', current_time)
                if isinstance(session_time, str):
                    session_time = datetime.fromisoformat(session_time)
                
                if current_time - session_time > timedelta(seconds=TASK_TIMEOUT * 2):
                    sessions_to_remove.append(session_id)
            
            if sessions_to_remove:
                with thread_lock:
                    for session_id in sessions_to_remove:
                        if session_id in client_sessions:
                            del client_sessions[session_id]
                            logger.info(f"Cleaned up old session: {session_id}")
                        if session_id in message_buffers:
                            del message_buffers[session_id]
                            logger.info(f"Cleaned up old message buffer: {session_id}")
            
            buffers_to_remove = []
            now_ts = time.time()
            for session_id, buffer in message_buffers_items:
                last_flush = buffer.get('last_flush', 0)
                if (now_ts - last_flush) > (TASK_TIMEOUT * 2):
                    buffers_to_remove.append(session_id)
            
            if buffers_to_remove:
                with thread_lock:
                    for session_id in buffers_to_remove:
                        if session_id in message_buffers:
                            del message_buffers[session_id]
                            logger.info(f"Cleaned up old message buffer: {session_id}")
            
        except Exception as e:
            logger.exception(f"Error during cleanup: {e}")
        
        time.sleep(300)

cleanup_thread = threading.Thread(target=cleanup_old_tasks, daemon=True)
cleanup_thread.start()

def get_session_id():
    from flask import request
    return request.sid if hasattr(request, 'sid') else None

def serialize_data(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    elif isinstance(obj, pd.DataFrame):
        return obj.to_dict('records')
    elif isinstance(obj, pd.Series):
        return obj.to_dict()
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {k: serialize_data(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize_data(item) for item in obj]
    else:
        return obj

def websocket_callback(message, session_id):
    should_flush = False
    with thread_lock:
        if session_id not in message_buffers:
            message_buffers[session_id] = {
                'messages': [],
                'last_flush': time.time()
            }
        
        buffer = message_buffers[session_id]
        buffer['messages'].append(message)
        
        current_time = time.time()
        if current_time - buffer['last_flush'] >= BATCH_INTERVAL:
            should_flush = True
    
    if should_flush:
        flush_messages(session_id)

def flush_messages(session_id):
    with thread_lock:
        buffer = message_buffers.get(session_id)
        if not buffer or not buffer.get('messages'):
            return
        messages = buffer['messages']
        buffer['messages'] = []
        buffer['last_flush'] = time.time()
    
    for message in messages:
        if isinstance(message, dict):
            target_session_id = message.get('session_id', session_id)
            socketio.emit('agent_update', message, room=target_session_id, namespace='/')
        else:
            socketio.emit('agent_update', {
                'agent_type': 'system',
                'agent_name': '系统',
                'agent_title': '系统消息',
                'agent_icon': '🔔',
                'agent_color': '#607d8b',
                'status': 'analyzing',
                'progress': 0,
                'message': message
            }, room=session_id, namespace='/')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/agents', methods=['GET'])
def get_agents():
    agents_info = []
    for agent_type, cfg in Config.AGENT_CONFIGS.items():
        agents_info.append({
            'agent_type': agent_type,
            'name': cfg.get('name', ''),
            'title': cfg.get('title', ''),
            'icon': cfg.get('icon', ''),
            'color': cfg.get('color', '')
        })
    return jsonify({
        'success': True,
        'agents': agents_info
    })

@app.route('/api/analyze', methods=['POST'])
def analyze_stock():
    data = request.json
    if not data:
        return jsonify({
            'success': False,
            'error': '无效的请求数据'
        }), 400
    
    stock_code = data.get('stock_code')
    session_id = data.get('session_id')
    
    # 验证股票代码格式（6位数字）
    if not stock_code or not re.match(r'^\d{6}$', stock_code):
        return jsonify({
            'success': False,
            'error': '请提供有效的6位股票代码'
        }), 400
    
    if not session_id or not isinstance(session_id, str):
        return jsonify({
            'success': False,
            'error': '会话ID无效，请刷新页面重试'
        }), 400
    
    task_id = str(uuid.uuid4())
    
    def create_callback(sid):
        def callback(message):
            websocket_callback(message, sid)
        return callback
    
    def run_analysis():
        import time
        time.sleep(0.1)
        
        try:
            logger.info(f"开始分析股票: {stock_code}, 会话ID: {session_id}")
            stock_agent = StockAgent(callback=create_callback(session_id), session_id=session_id)
            
            # 使用langgraph工作流进行分析
            workflow_result = stock_agent.analysis_workflow.run({
                'analysis_type': 'stock',
                'stock_code': stock_code
            })
            
            # 提取分析结果
            result = {
                'stock_code': stock_code,
                'analyses': workflow_result.get('analyses', {}),
                'stock_data': workflow_result.get('stock_data', {}),
                'status': workflow_result.get('status', 'completed')
            }
            
            flush_messages(session_id)
            
            serialized_result = serialize_data(result)
            
            socketio.emit('analysis_complete', {
                'task_id': task_id,
                'result': serialized_result
            }, room=session_id, namespace='/')
            logger.info(f"analysis_complete 已发送: task_id={task_id}, room={session_id}")
            
            with thread_lock:
                if session_id in message_buffers:
                    del message_buffers[session_id]
                if task_id in active_tasks:
                    del active_tasks[task_id]
        
        except Exception as e:
            logger.exception(f"分析过程出错: {str(e)}")
            
            flush_messages(session_id)
            
            socketio.emit('analysis_error', {
                'task_id': task_id,
                'error': str(e)
            }, room=session_id, namespace='/')
            with thread_lock:
                if session_id in message_buffers:
                    del message_buffers[session_id]
                if task_id in active_tasks:
                    del active_tasks[task_id]
    
    socketio.start_background_task(run_analysis)
    
    with thread_lock:
        active_tasks[task_id] = {
            'stock_code': stock_code,
            'status': 'running',
            'session_id': session_id,
            'timestamp': datetime.now().isoformat()
        }
        
        client_sessions[session_id] = {
            'last_activity': datetime.now().isoformat()
        }
    
    return jsonify({
        'success': True,
        'task_id': task_id,
        'message': '分析任务已启动'
    })

@app.route('/api/kline', methods=['POST'])
def get_kline_data():
    data = request.json
    if not data:
        return jsonify({
            'success': False,
            'error': '无效的请求数据'
        }), 400
    
    stock_code = data.get('stock_code')
    period = data.get('period', 'daily')
    
    # 验证股票代码格式（6位数字）
    if not stock_code or not re.match(r'^\d{6}$', stock_code):
        return jsonify({
            'success': False,
            'error': '请提供有效的6位股票代码'
        }), 400
    
    # 验证周期参数
    valid_periods = ['daily', 'weekly', 'monthly']
    if period not in valid_periods:
        period = 'daily'  # 默认使用日线
    
    try:
        data_fetcher = _get_data_fetcher()
        kline_data = data_fetcher.get_kline_data(stock_code, period=period)
        
        if isinstance(kline_data, pd.DataFrame):
            if not kline_data.empty:
                kline_data = kline_data.to_dict('records')
            else:
                kline_data = []
        else:
            kline_data = []
        
        return jsonify({
            'success': True,
            'kline_data': kline_data
        })
    except Exception as e:
        logger.exception(f"获取K线数据失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': '获取K线数据失败，请稍后重试'
        }), 500

@app.route('/api/search_stock', methods=['GET'])
def search_stock():
    keyword = request.args.get('keyword', '').strip()
    
    if not keyword:
        return jsonify({
            'success': True,
            'results': []
        })
    
    try:
        data_fetcher = _get_data_fetcher()
        results = data_fetcher.search_stock(keyword)
        
        return jsonify({
            'success': True,
            'results': results
        })
    except Exception as e:
        logger.exception(f"搜索股票失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': '搜索股票失败，请稍后重试'
        }), 500

@socketio.on('connect')
def handle_connect(auth):
    emit('connected', {'message': '已连接到服务器'})
    logger.info(f"Client connected: {request.sid}")
    with thread_lock:
        client_sessions[request.sid] = {
            'last_activity': datetime.now().isoformat()
        }
    join_room(request.sid)

@socketio.on('disconnect')
def handle_disconnect():
    logger.info(f"Client disconnected: {request.sid}")
    with thread_lock:
        if request.sid in client_sessions:
            del client_sessions[request.sid]
        if request.sid in message_buffers:
            del message_buffers[request.sid]

@socketio.on('ping')
def handle_ping(*args):
    with thread_lock:
        if request.sid in client_sessions:
            client_sessions[request.sid]['last_activity'] = datetime.now().isoformat()
    emit('pong')

@socketio.on('pong')
def handle_pong(*args):
    with thread_lock:
        if request.sid in client_sessions:
            client_sessions[request.sid]['last_activity'] = datetime.now().isoformat()

@app.route('/api/analyze_sector', methods=['POST'])
def analyze_sector():
    data = request.json
    if not data:
        return jsonify({
            'success': False,
            'error': '无效的请求数据'
        }), 400
    
    sector_name = data.get('sector_name')
    session_id = data.get('session_id')
    
    if not sector_name:
        return jsonify({
            'success': False,
            'error': '请提供板块名称'
        }), 400
    
    if not session_id or not isinstance(session_id, str):
        return jsonify({
            'success': False,
            'error': '会话ID无效，请刷新页面重试'
        }), 400
    
    # 验证板块是否存在
    try:
        data_fetcher = _get_data_fetcher()
        validation_result = data_fetcher.validate_sector(sector_name)
        
        if not validation_result.get('exists', False):
            return jsonify({
                'success': False,
                'error': f'板块 "{sector_name}" 不存在',
                'supported_sectors': validation_result.get('supported_sectors', [])
            }), 400
    except Exception as e:
        logger.exception(f"验证板块失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': '验证板块失败，请稍后重试'
        }), 500
    
    task_id = str(uuid.uuid4())
    
    def create_callback(sid):
        def callback(message):
            websocket_callback(message, sid)
        return callback
    
    def run_analysis():
        import time
        time.sleep(0.1)
        
        try:
            logger.info(f"开始分析板块: {sector_name}, 会话ID: {session_id}")
            stock_agent = StockAgent(callback=create_callback(session_id), session_id=session_id)
            
            # 使用langgraph工作流进行分析
            workflow_result = stock_agent.analysis_workflow.run({
                'analysis_type': 'sector',
                'sector_name': sector_name
            })
            
            # 提取分析结果
            result = {
                'sector_name': sector_name,
                'analyses': workflow_result.get('analyses', {}),
                'sector_data': workflow_result.get('sector_data', {}),
                'status': workflow_result.get('status', 'completed')
            }
            
            flush_messages(session_id)
            
            serialized_result = serialize_data(result)
            
            socketio.emit('sector_analysis_complete', {
                'task_id': task_id,
                'result': serialized_result
            }, room=session_id, namespace='/')
            logger.info(f"sector_analysis_complete 已发送: task_id={task_id}, room={session_id}")
            
            with thread_lock:
                if session_id in message_buffers:
                    del message_buffers[session_id]
                if task_id in active_tasks:
                    del active_tasks[task_id]
        
        except Exception as e:
            logger.exception(f"板块分析过程出错: {str(e)}")
            
            flush_messages(session_id)
            
            socketio.emit('sector_analysis_error', {
                'task_id': task_id,
                'error': str(e)
            }, room=session_id, namespace='/')
            with thread_lock:
                if session_id in message_buffers:
                    del message_buffers[session_id]
                if task_id in active_tasks:
                    del active_tasks[task_id]
    
    socketio.start_background_task(run_analysis)
    
    with thread_lock:
        active_tasks[task_id] = {
            'sector_name': sector_name,
            'status': 'running',
            'session_id': session_id,
            'timestamp': datetime.now().isoformat()
        }
        
        client_sessions[session_id] = {
            'last_activity': datetime.now().isoformat()
        }
    
    return jsonify({
        'success': True,
        'task_id': task_id,
        'message': '板块分析请求已提交'
    })

@app.route('/api/search_sector', methods=['GET'])
def search_sector():
    """搜索板块"""
    keyword = request.args.get('keyword', '').strip()
    if not keyword:
        return jsonify({
            'success': True,
            'results': []
        })
    
    try:
        data_fetcher = _get_data_fetcher()
        sector_list = data_fetcher.get_sector_list()
        sectors = sector_list.get('sectors', [])
        
        # 简单的模糊匹配
        filtered_sectors = []
        for sector in sectors:
            if keyword in sector.get('sector_name', ''):
                filtered_sectors.append(sector)
        
        return jsonify({
            'success': True,
            'results': filtered_sectors[:10]  # 最多返回10个结果
        })
    except Exception as e:
        logger.exception(f"搜索板块失败: {e}")
        return jsonify({
            'success': False,
            'error': f"搜索板块失败: {str(e)}"
        })

@app.route('/api/sectors_by_category', methods=['GET'])
def sectors_by_category():
    """获取分类的板块列表"""
    try:
        data_fetcher = _get_data_fetcher()
        sectors_data = data_fetcher.get_sectors_by_category()
        
        return jsonify({
            'success': True,
            'data': sectors_data
        })
    except Exception as e:
        logger.exception(f"获取分类板块列表失败: {e}")
        return jsonify({
            'success': False,
            'error': f"获取分类板块列表失败: {str(e)}"
        }), 500

if __name__ == '__main__':
    socketio.run(app, debug=Config.FLASK_DEBUG, host='0.0.0.0', port=5000, use_reloader=False)
