from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from threading import Lock
from stock_agent import StockAgent
from config import Config
import uuid
import os
from datetime import datetime, date
import numpy as np
import pandas as pd

template_dir = os.path.join(os.path.dirname(__file__), 'web', 'templates')
static_dir = os.path.join(os.path.dirname(__file__), 'web', 'static')

app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
app.config['SECRET_KEY'] = Config.FLASK_SECRET_KEY
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    ping_timeout=60,
    ping_interval=25,
    async_mode='threading',
    logger=True,
    engineio_logger=False
)

thread = None
thread_lock = Lock()

active_tasks = {}
client_sessions = {}

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
    if isinstance(message, dict):
        target_session_id = message.get('session_id', session_id)
        socketio.emit('agent_update', message, room=target_session_id)
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
        }, room=session_id)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/agents', methods=['GET'])
def get_agents():
    stock_agent = StockAgent()
    agents_info = stock_agent.get_agent_info()
    return jsonify({
        'success': True,
        'agents': agents_info
    })

@app.route('/api/analyze', methods=['POST'])
def analyze_stock():
    data = request.json
    print('收到的请求数据:', data)
    stock_code = data.get('stock_code')
    session_id = data.get('session_id')
    
    print('股票代码:', stock_code)
    print('会话ID:', session_id)
    
    if not stock_code:
        return jsonify({
            'success': False,
            'error': '请提供股票代码'
        }), 400
    
    if not session_id:
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
            print(f'开始分析股票: {stock_code}, 会话ID: {session_id}')
            stock_agent = StockAgent(callback=create_callback(session_id), session_id=session_id)
            print('StockAgent创建成功')
            result = stock_agent.analyze_stock(stock_code)
            print('分析完成，准备发送结果')
            
            serialized_result = serialize_data(result)
            
            socketio.emit('analysis_complete', {
                'task_id': task_id,
                'result': serialized_result
            }, room=session_id)
            
            if task_id in active_tasks:
                del active_tasks[task_id]
        
        except Exception as e:
            print(f'分析过程出错: {str(e)}')
            import traceback
            traceback.print_exc()
            socketio.emit('analysis_error', {
                'task_id': task_id,
                'error': str(e)
            }, room=session_id)
            
            if task_id in active_tasks:
                del active_tasks[task_id]
    
    socketio.start_background_task(run_analysis)
    
    active_tasks[task_id] = {
        'stock_code': stock_code,
        'status': 'running',
        'session_id': session_id
    }
    
    return jsonify({
        'success': True,
        'task_id': task_id,
        'message': '分析任务已启动'
    })

@app.route('/api/backtest', methods=['POST'])
def backtest_strategy():
    data = request.json
    print('收到的回测请求数据:', data)
    stock_code = data.get('stock_code')
    session_id = data.get('session_id')
    strategy_content = data.get('strategy_content')
    strategy_signals = data.get('strategy_signals')
    
    print('股票代码:', stock_code)
    print('会话ID:', session_id)
    print('策略内容:', strategy_content)
    print('策略信号:', strategy_signals)
    
    if not stock_code:
        return jsonify({
            'success': False,
            'error': '请提供股票代码'
        }), 400
    
    if not session_id:
        return jsonify({
            'success': False,
            'error': '会话ID无效，请刷新页面重试'
        }), 400
    
    if not strategy_content and not strategy_signals:
        return jsonify({
            'success': False,
            'error': '请提供策略内容或策略信号'
        }), 400
    
    task_id = str(uuid.uuid4())
    
    def create_callback(sid):
        def callback(message):
            websocket_callback(message, sid)
        return callback
    
    def run_backtest():
        import time
        time.sleep(0.1)
        
        try:
            print(f'开始回测股票: {stock_code}, 会话ID: {session_id}')
            stock_agent = StockAgent(callback=create_callback(session_id), session_id=session_id)
            print('StockAgent创建成功')
            result = stock_agent.backtest_strategy(
                stock_code=stock_code,
                strategy_content=strategy_content,
                strategy_signals=strategy_signals
            )
            print('回测完成，准备发送结果')
            
            serialized_result = serialize_data(result)
            
            socketio.emit('backtest_complete', {
                'task_id': task_id,
                'result': serialized_result
            }, room=session_id)
            
            if task_id in active_tasks:
                del active_tasks[task_id]
        
        except Exception as e:
            print(f'回测过程出错: {str(e)}')
            import traceback
            traceback.print_exc()
            socketio.emit('backtest_error', {
                'task_id': task_id,
                'error': str(e)
            }, room=session_id)
            
            if task_id in active_tasks:
                del active_tasks[task_id]
    
    socketio.start_background_task(run_backtest)
    
    active_tasks[task_id] = {
        'stock_code': stock_code,
        'status': 'running',
        'session_id': session_id,
        'type': 'backtest'
    }
    
    return jsonify({
        'success': True,
        'task_id': task_id,
        'message': '回测任务已启动'
    })

@app.route('/api/kline', methods=['POST'])
def get_kline_data():
    from tools.data_fetcher import DataFetcher
    
    data = request.json
    stock_code = data.get('stock_code')
    period = data.get('period', 'daily')
    
    if not stock_code:
        return jsonify({
            'success': False,
            'error': '请提供股票代码'
        }), 400
    
    try:
        data_fetcher = DataFetcher()
        kline_data = data_fetcher.get_kline_data(stock_code, period=period)
        
        if isinstance(kline_data, pd.DataFrame) and not kline_data.empty:
            kline_data = kline_data.to_dict('records')
        
        return jsonify({
            'success': True,
            'kline_data': kline_data
        })
    except Exception as e:
        print(f'获取K线数据失败: {str(e)}')
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@socketio.on('connect')
def handle_connect():
    emit('connected', {'message': '已连接到服务器'})
    print(f'Client connected: {request.sid}')

@socketio.on('disconnect')
def handle_disconnect():
    print(f'Client disconnected: {request.sid}')

@socketio.on('ping')
def handle_ping():
    emit('pong')

@socketio.on('pong')
def handle_pong():
    pass

if __name__ == '__main__':
    socketio.run(app, debug=Config.FLASK_DEBUG, host='127.0.0.1', port=4000)
