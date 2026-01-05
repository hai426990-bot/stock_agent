// WebSocket连接管理模块
const DEBUG_SOCKET = false;
const debugSocketLog = (...args) => {
    if (DEBUG_SOCKET) console.log(...args);
};

class SocketManager {
    constructor() {
        this.socket = null;
        this.isConnected = false;
        this.callbacks = {};
    }

    connect(url = (typeof window !== 'undefined' && window.location ? window.location.origin : 'http://localhost:5000')) {
        if (this.socket) {
            this.socket.disconnect();
        }

        this.socket = io(url, {
            transports: ['websocket', 'polling'],
            reconnection: true,
            reconnectionAttempts: Infinity,
            reconnectionDelay: 1000,
            reconnectionDelayMax: 5000,
            timeout: 30000,
            pingTimeout: 300000,
            pingInterval: 25000
        });

        this.setupEventListeners();
    }

    setupEventListeners() {
        this.socket.on('connect_error', (error) => {
            console.error('Socket连接错误:', error);
            this.isConnected = false;
            this.emit('connect_error', error);
        });

        this.socket.on('connect_timeout', (timeout) => {
            console.error('Socket连接超时:', timeout);
            this.isConnected = false;
            this.emit('connect_timeout', timeout);
        });

        this.socket.on('error', (error) => {
            console.error('Socket错误:', error);
            this.emit('error', error);
        });

        this.socket.on('connect', () => {
            this.isConnected = true;
            debugSocketLog('已连接到服务器, Socket ID:', this.socket.id);
            this.emit('connect', this.socket.id);
        });

        this.socket.on('disconnect', (reason) => {
            this.isConnected = false;
            debugSocketLog('与服务器断开连接:', reason);
            this.emit('disconnect', reason);
        });

        this.socket.on('reconnect', (attemptNumber) => {
            this.isConnected = true;
            debugSocketLog('重新连接成功，尝试次数:', attemptNumber);
            this.emit('reconnect', attemptNumber);
        });

        this.socket.on('reconnect_attempt', (attemptNumber) => {
            debugSocketLog('尝试重新连接...', attemptNumber);
            this.emit('reconnect_attempt', attemptNumber);
        });

        this.socket.on('reconnect_error', (error) => {
            console.error('重新连接失败:', error);
            this.emit('reconnect_error', error);
        });

        this.socket.on('reconnect_failed', () => {
            console.error('重新连接失败，已达到最大尝试次数');
            this.emit('reconnect_failed');
        });

        this.socket.on('pong', () => {
            debugSocketLog('收到服务器pong响应');
            this.emit('pong');
        });

        this.socket.on('connected', (data) => {
            debugSocketLog(data.message);
            this.emit('connected', data);
        });

        this.socket.on('agent_update', (data) => {
            debugSocketLog('Agent更新:', data);
            this.emit('agent_update', data);
        });

        this.socket.on('analysis_complete', (data) => {
            debugSocketLog('收到 analysis_complete 事件:', data);
            this.emit('analysis_complete', data);
        });

        this.socket.on('analysis_error', (data) => {
            console.error('分析错误:', data);
            this.emit('analysis_error', data);
        });
    }

    on(event, callback) {
        if (!this.callbacks[event]) {
            this.callbacks[event] = [];
        }
        this.callbacks[event].push(callback);
    }

    off(event, callback) {
        if (this.callbacks[event]) {
            this.callbacks[event] = this.callbacks[event].filter(cb => cb !== callback);
        }
    }

    emit(event, data) {
        if (this.callbacks[event]) {
            this.callbacks[event].forEach(callback => {
                callback(data);
            });
        }
    }

    send(event, data) {
        if (this.socket && this.isConnected) {
            this.socket.emit(event, data);
        }
    }

    disconnect() {
        if (this.socket) {
            this.socket.disconnect();
            this.socket = null;
            this.isConnected = false;
        }
    }

    isSocketReady() {
        return this.socket && this.isConnected;
    }

    getSocketId() {
        return this.socket ? this.socket.id : null;
    }
}

// 导出单例实例
const socketManager = new SocketManager();
export default socketManager;
