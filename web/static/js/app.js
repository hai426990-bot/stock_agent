// 全局状态管理
const appState = {
    isConnected: false,
    isAnalyzing: false,
    currentStockCode: null,
    socket: null,
    analysisHistory: JSON.parse(localStorage.getItem('analysisHistory')) || [],
    notificationQueue: []
};

// 分析师配置
const agentConfigs = {
    data_downloader: { name: '数据下载', icon: '📥', color: '#95a5a6' },
    technical_analyst: { name: '技术分析师', icon: '📈', color: '#3498db' },
    fundamental_analyst: { name: '基本面分析师', icon: '💰', color: '#2ecc71' },
    risk_manager: { name: '风险控制专家', icon: '⚠️', color: '#e74c3c' },
    sentiment_analyst: { name: '市场情绪分析师', icon: '😊', color: '#9b59b6' },
    investment_strategist: { name: '投资策略师', icon: '🎯', color: '#f39c12' }
};

// DOM元素引用
const elements = {
    statusIndicator: document.getElementById('statusIndicator'),
    statusText: document.getElementById('statusText'),
    stockCode: document.getElementById('stockCode'),
    autocompleteDropdown: document.getElementById('autocompleteDropdown'),
    analyzeBtn: document.getElementById('analyzeBtn'),
    clearBtn: document.getElementById('clearBtn'),
    overallProgressFill: document.getElementById('overallProgressFill'),
    overallProgressPercentage: document.getElementById('overallProgressPercentage'),
    overallProgressStatus: document.getElementById('overallProgressStatus'),
    agentStatusList: document.getElementById('agentStatusList'),
    chartSection: document.getElementById('chartSection'),
    resultsSection: document.getElementById('resultsSection'),
    summarySection: document.getElementById('summarySection'),
    notificationContainer: document.getElementById('notificationContainer'),
    agentsGrid: document.getElementById('agentsGrid'),
    historyList: document.getElementById('historyList')
};

// 初始化应用
function initApp() {
    initSocket();
    initEventListeners();
    renderHistory();
}

// 初始化Socket连接
function initSocket() {
    try {
        const socketUrl = window.location.origin;
        appState.socket = io(socketUrl, {
            transports: ['websocket', 'polling'],
            reconnection: true,
            reconnectionAttempts: Infinity,
            reconnectionDelay: 1000,
            reconnectionDelayMax: 5000,
            timeout: 20000,
            pingTimeout: 60000,
            pingInterval: 25000
        });

        appState.socket.on('connect', handleSocketConnect);
        appState.socket.on('disconnect', handleSocketDisconnect);
        appState.socket.on('connect_error', handleSocketError);
        appState.socket.on('agent_update', handleAgentUpdate);
        appState.socket.on('analysis_complete', handleAnalysisComplete);
        appState.socket.on('analysis_error', handleAnalysisError);
    } catch (error) {
        console.error('Socket初始化失败:', error);
        showNotification('error', '连接失败', '无法初始化实时连接');
    }
}

// 处理Socket连接成功
function handleSocketConnect() {
    appState.isConnected = true;
    updateConnectionStatus();
    showNotification('success', '连接成功', '已连接到服务器');
}

// 处理Socket断开连接
function handleSocketDisconnect() {
    appState.isConnected = false;
    updateConnectionStatus();
    showNotification('warning', '连接断开', '与服务器的连接已断开');
}

// 处理Socket错误
function handleSocketError(error) {
    console.error('Socket错误:', error);
    appState.isConnected = false;
    updateConnectionStatus();
    showNotification('error', '连接错误', '实时连接发生错误');
}

// 更新连接状态
function updateConnectionStatus() {
    if (appState.isConnected) {
        elements.statusIndicator.className = 'status-indicator connected';
        elements.statusText.textContent = '已连接';
    } else {
        elements.statusIndicator.className = 'status-indicator';
        elements.statusText.textContent = '未连接';
    }
}

// 初始化事件监听器
function initEventListeners() {
    // 股票代码输入事件
    elements.stockCode.addEventListener('input', debounce(handleStockInput, 300));
    elements.stockCode.addEventListener('keypress', handleStockKeyPress);
    
    // 按钮事件
    elements.analyzeBtn.addEventListener('click', handleAnalyzeClick);
    elements.clearBtn.addEventListener('click', handleClearClick);
    
    // 自动补全点击事件（通过事件委托）
    elements.autocompleteDropdown.addEventListener('click', handleAutocompleteClick);
    
    // 点击页面其他区域关闭自动补全
    document.addEventListener('click', handleDocumentClick);
}

// 防抖函数
function debounce(func, delay) {
    let timeoutId;
    return function(...args) {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => func.apply(this, args), delay);
    };
}

// 处理股票代码输入
async function handleStockInput() {
    const keyword = elements.stockCode.value.trim();
    if (keyword.length >= 2) {
        const results = await searchStock(keyword);
        showAutocomplete(results);
    } else {
        hideAutocomplete();
    }
}

// 处理股票代码按键
function handleStockKeyPress(e) {
    if (e.key === 'Enter') {
        e.preventDefault();
        handleAnalyzeClick();
    }
}

// 处理分析按钮点击
async function handleAnalyzeClick() {
    const stockCode = elements.stockCode.value.trim();
    
    if (!stockCode || stockCode.length !== 6) {
        showNotification('warning', '参数错误', '请输入有效的6位股票代码');
        elements.stockCode.focus();
        return;
    }
    
    if (!appState.isConnected) {
        showNotification('error', '连接错误', '请先确保已连接到服务器');
        return;
    }
    
    if (appState.isAnalyzing) {
        showNotification('warning', '分析中', '当前正在分析中，请等待完成');
        return;
    }
    
    appState.isAnalyzing = true;
    appState.currentStockCode = stockCode;
    
    // 更新UI状态
    elements.analyzeBtn.classList.add('loading');
    elements.analyzeBtn.innerHTML = '<span class="spinner"></span> <span class="btn-text">分析中...</span>';
    elements.analyzeBtn.disabled = true;
    
    // 显示进度区域
    initializeProgress();
    
    try {
        // 先获取K线数据
        const klineData = await fetchKlineData(stockCode);
        if (klineData) {
            // 更新K线图表
            updateChartInfo(klineData);
            elements.chartSection.style.display = 'block';
        }
        
        // 发送分析请求
        const response = await fetch('/api/analyze', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                stock_code: stockCode,
                session_id: appState.socket.id
            })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP错误: ${response.status}`);
        }
        
        const data = await response.json();
        if (data.success) {
            showNotification('success', '分析请求已提交', `正在分析股票 ${stockCode}`);
        } else {
            throw new Error(data.error || '分析请求失败');
        }
        
    } catch (error) {
        console.error('分析请求失败:', error);
        showNotification('error', '分析失败', error.message || '无法开始分析');
        resetAnalysisState();
    }
}

// 处理清除按钮点击
function handleClearClick() {
    if (confirm('确定要清除所有历史记录吗？')) {
        appState.analysisHistory = [];
        localStorage.removeItem('analysisHistory');
        renderHistory();
        showNotification('success', '清除成功', '历史记录已清除');
    }
}

// 处理自动补全点击
function handleAutocompleteClick(e) {
    const item = e.target.closest('.autocomplete-item');
    if (item) {
        const code = item.dataset.code;
        elements.stockCode.value = code;
        hideAutocomplete();
    }
}

// 处理文档点击
function handleDocumentClick(e) {
    if (!elements.autocompleteDropdown.contains(e.target) && e.target !== elements.stockCode) {
        hideAutocomplete();
    }
}

// 股票搜索函数
async function searchStock(keyword) {
    try {
        const response = await fetch(`/api/search_stock?keyword=${encodeURIComponent(keyword)}`);
        const data = await response.json();
        return data.success ? data.results : [];
    } catch (error) {
        console.error('搜索股票失败:', error);
        return [];
    }
}

// 显示自动补全
function showAutocomplete(results) {
    if (results.length === 0) {
        hideAutocomplete();
        return;
    }
    
    let html = '<div class="autocomplete-items">';
    results.forEach(stock => {
        const changeClass = stock.change_percent.startsWith('+') ? 'positive' : 'negative';
        html += `
            <div class="autocomplete-item" data-code="${stock.stock_code}" data-name="${stock.stock_name}">
                <div class="autocomplete-item-header">
                    <span class="stock-code">${stock.stock_code}</span>
                    <span class="stock-name">${stock.stock_name}</span>
                </div>
                <div class="autocomplete-item-details">
                    <span class="current-price">${stock.current_price}元</span>
                    <span class="change-percent ${changeClass}">${stock.change_percent}</span>
                </div>
            </div>
        `;
    });
    html += '</div>';
    
    elements.autocompleteDropdown.innerHTML = html;
    elements.autocompleteDropdown.classList.add('show');
}

// 隐藏自动补全
function hideAutocomplete() {
    elements.autocompleteDropdown.classList.remove('show');
}

// 获取K线数据
async function fetchKlineData(stockCode, period = 'daily') {
    try {
        const response = await fetch('/api/kline', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                stock_code: stockCode,
                period: period
            })
        });
        
        const data = await response.json();
        if (data.success && data.kline_data && data.kline_data.length > 0) {
            return data.kline_data;
        }
        return null;
    } catch (error) {
        console.error('获取K线数据失败:', error);
        return null;
    }
}

// 更新图表信息
function updateChartInfo(klineData) {
    if (!klineData || klineData.length === 0) return;
    
    const last = klineData[klineData.length - 1];
    const prev = klineData.length > 1 ? klineData[klineData.length - 2] : last;
    
    const change = last['收盘'] - prev['收盘'];
    const changePercent = (change / prev['收盘'] * 100).toFixed(2);
    const changeClass = change >= 0 ? 'positive' : 'negative';
    const changeSign = change >= 0 ? '+' : '';
    
    // 股票名称应该从API获取，这里先使用代码+名称的格式
    document.getElementById('stockName').textContent = `股票 ${appState.currentStockCode}`;
    document.getElementById('stockCodeDisplay').textContent = appState.currentStockCode;
    document.getElementById('currentPrice').textContent = last['收盘'] + ' 元';
    document.getElementById('priceChange').className = `price-change ${changeClass}`;
    document.getElementById('priceChange').textContent = `${changeSign}${change.toFixed(2)} (${changeSign}${changePercent}%)`;
}

// 初始化进度显示
function initializeProgress() {
    // 重置整体进度
    elements.overallProgressFill.style.width = '0%';
    elements.overallProgressPercentage.textContent = '0%';
    elements.overallProgressStatus.textContent = '准备分析...';
    
    // 生成分析师状态列表
    let agentStatusHtml = '';
    Object.keys(agentConfigs).forEach(agentType => {
        const config = agentConfigs[agentType];
        agentStatusHtml += `
            <div class="agent-status-item" id="agent-${agentType}">
                <span class="agent-status-icon">${config.icon}</span>
                <span class="agent-status-name">${config.name}</span>
                <span class="agent-status-text">等待中</span>
            </div>
        `;
    });
    elements.agentStatusList.innerHTML = agentStatusHtml;
    
    // 清空之前的结果
    elements.agentsGrid.innerHTML = '';
    elements.resultsSection.style.display = 'none';
    elements.summarySection.style.display = 'none';
}

// 处理分析师更新
function handleAgentUpdate(data) {
    console.log('Agent更新:', data);
    
    // 更新单个分析师状态
    const agentItem = document.getElementById(`agent-${data.agent_type}`);
    if (agentItem) {
        const statusIcon = agentItem.querySelector('.agent-status-icon');
        const statusText = agentItem.querySelector('.agent-status-text');
        
        if (statusIcon && statusText) {
            if (data.status === 'analyzing' || data.status === 'streaming') {
                statusIcon.textContent = '🔵';
                statusText.className = 'agent-status-text analyzing';
                statusText.textContent = '分析中';
            } else if (data.status === 'completed') {
                statusIcon.textContent = '✅';
                statusText.className = 'agent-status-text completed';
                statusText.textContent = '已完成';
            } else if (data.status === 'error') {
                statusIcon.textContent = '❌';
                statusText.className = 'agent-status-text error';
                statusText.textContent = '失败';
            }
        }
    }
    
    // 更新整体进度
    updateOverallProgress();
    
    // 更新分析师卡片内容
    updateAgentCard(data);
}

// 更新整体进度
function updateOverallProgress() {
    const agentItems = document.querySelectorAll('.agent-status-item');
    const completedAgents = document.querySelectorAll('.agent-status-text.completed').length;
    const totalAgents = agentItems.length;
    const progress = Math.round((completedAgents / totalAgents) * 100);
    
    elements.overallProgressFill.style.width = `${progress}%`;
    elements.overallProgressPercentage.textContent = `${progress}%`;
    
    if (progress === 0) {
        elements.overallProgressStatus.textContent = '准备分析...';
    } else if (progress < 100) {
        elements.overallProgressStatus.textContent = `分析进行中 (${completedAgents}/${totalAgents})`;
    } else {
        elements.overallProgressStatus.textContent = '分析完成';
    }
}

// 更新分析师卡片
function updateAgentCard(data) {
    const config = agentConfigs[data.agent_type];
    if (!config) return;
    
    let card = document.getElementById(`card-${data.agent_type}`);
    if (!card) {
        // 创建新卡片
        card = document.createElement('div');
        card.className = 'agent-card';
        card.id = `card-${data.agent_type}`;
        card.innerHTML = `
            <div class="agent-header">
                <span class="agent-icon">${config.icon}</span>
                <div class="agent-info">
                    <h3 class="agent-name">${config.name}</h3>
                    <p class="agent-title">分析报告</p>
                </div>
                <span class="agent-status-badge analyzing">分析中</span>
            </div>
            <div class="agent-progress">
                <div class="agent-progress-bar">
                    <div class="agent-progress-fill" id="progress-${data.agent_type}"></div>
                </div>
                <span class="agent-progress-text" id="progress-text-${data.agent_type}">0%</span>
            </div>
            <div class="agent-content" id="content-${data.agent_type}">
                <p class="placeholder">等待分析结果...</p>
            </div>
        `;
        elements.agentsGrid.appendChild(card);
        elements.resultsSection.style.display = 'block';
    }
    
    // 更新进度
    const progressFill = document.getElementById(`progress-${data.agent_type}`);
    const progressText = document.getElementById(`progress-text-${data.agent_type}`);
    const contentDiv = document.getElementById(`content-${data.agent_type}`);
    const statusBadge = card.querySelector('.agent-status-badge');
    
    if (progressFill && progressText) {
        progressFill.style.width = `${data.progress}%`;
        progressText.textContent = `${data.progress}%`;
    }
    
    if (statusBadge) {
        statusBadge.className = `agent-status-badge ${data.status}`;
        if (data.status === 'analyzing' || data.status === 'streaming') {
            statusBadge.textContent = '分析中';
        } else if (data.status === 'completed') {
            statusBadge.textContent = '已完成';
        } else if (data.status === 'error') {
            statusBadge.textContent = '失败';
        }
    }
    
    if (contentDiv) {
        if (data.is_stream && data.message) {
            const currentContent = contentDiv.innerHTML;
            if (currentContent.includes('placeholder')) {
                // 处理**格式并转换为加粗标签
                let processedMessage = data.message.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
                contentDiv.innerHTML = `<div class="content-wrapper">${processedMessage}</div>`;
            } else {
                const contentWrapper = contentDiv.querySelector('.content-wrapper');
                if (contentWrapper) {
                    // 处理**格式并转换为加粗标签
                    let processedMessage = data.message.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
                    contentWrapper.innerHTML += processedMessage;
                } else {
                    // 处理**格式并转换为加粗标签
                    let processedMessage = data.message.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
                    contentDiv.innerHTML = `<div class="content-wrapper">${processedMessage}</div>`;
                }
            }
            contentDiv.scrollTop = contentDiv.scrollHeight;
        } else if (data.message && data.status === 'analyzing') {
            // 处理**格式并转换为加粗标签
            let processedMessage = data.message.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
            contentDiv.innerHTML = `<p style="color: #667eea;">${processedMessage}</p>`;
        }
    }
}

// 处理分析完成
function handleAnalysisComplete(data) {
    console.log('分析完成:', data);
    
    appState.isAnalyzing = false;
    
    // 恢复按钮状态
    elements.analyzeBtn.classList.remove('loading');
    elements.analyzeBtn.innerHTML = '<span class="btn-icon">🚀</span> <span class="btn-text">开始分析</span>';
    elements.analyzeBtn.disabled = false;
    
    if (!data.result || !data.result.analyses) {
        showNotification('error', '分析失败', '未收到完整的分析结果');
        return;
    }
    
    // 更新所有分析师卡片的最终状态
    Object.entries(data.result.analyses).forEach(([agentType, analysis]) => {
        const card = document.getElementById(`card-${agentType}`);
        if (card) {
            const statusBadge = card.querySelector('.agent-status-badge');
            const contentDiv = document.getElementById(`content-${agentType}`);
            const progressFill = document.getElementById(`progress-${agentType}`);
            const progressText = document.getElementById(`progress-text-${agentType}`);
            
            if (statusBadge) {
                statusBadge.className = 'agent-status-badge completed';
                statusBadge.textContent = '已完成';
            }
            
            if (progressFill) {
                progressFill.style.width = '100%';
            }
            
            if (progressText) {
                progressText.textContent = '100%';
            }
            
            if (contentDiv) {
                if (analysis.error) {
                    contentDiv.innerHTML = `<div class="content-wrapper" style="color: var(--danger-color);">❌ 分析失败: ${analysis.error}</div>`;
                } else if (analysis.result && analysis.result.content) {
                    // 处理**格式并转换为加粗标签
                    let processedContent = analysis.result.content.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
                    // 替换换行符为<br>标签
                    processedContent = processedContent.replace(/\n/g, '<br>');
                    contentDiv.innerHTML = `<div class="content-wrapper">${processedContent}</div>`;
                } else if (analysis.raw_response) {
                    // 处理**格式并转换为加粗标签
                    let processedContent = analysis.raw_response.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
                    // 替换换行符为<br>标签
                    processedContent = processedContent.replace(/\n/g, '<br>');
                    contentDiv.innerHTML = `<div class="content-wrapper">${processedContent}</div>`;
                } else {
                    contentDiv.innerHTML = `<div class="content-wrapper" style="color: var(--warning-color);">⚠️ 暂无分析结果</div>`;
                }
            }
        }
    });
    
    // 显示最终建议
    showFinalRecommendation(data.result);
    
    // 添加到历史记录
    addToHistory(data.result);
    
    // 显示成功通知
    showNotification('success', '分析完成', `股票 ${appState.currentStockCode} 分析已完成`);
}

// 处理分析错误
function handleAnalysisError(data) {
    console.error('分析错误:', data);
    
    appState.isAnalyzing = false;
    
    // 恢复按钮状态
    elements.analyzeBtn.classList.remove('loading');
    elements.analyzeBtn.innerHTML = '<span class="btn-icon">🚀</span> <span class="btn-text">开始分析</span>';
    elements.analyzeBtn.disabled = false;
    
    showNotification('error', '分析失败', data.error || '分析过程中发生未知错误');
}

// 显示最终建议
function showFinalRecommendation(result) {
    let strategyAnalysis;
    
    // 尝试获取投资策略师的分析结果，如果不存在则尝试获取其他分析师的结果
    if (result.analyses && result.analyses.investment_strategist) {
        strategyAnalysis = result.analyses.investment_strategist;
    } else {
        // 获取第一个有结果的分析师
        strategyAnalysis = Object.values(result.analyses).find(analysis => analysis && analysis.result && analysis.result.content);
    }
    
    // 定义默认内容
    let content = '暂无完整的分析结果，请稍后重试。';
    let score = '--';
    let risk = '--';
    let position = '--';
    let target = '--';
    let recommendation = '分析中';
    let recommendationClass = 'analyzing';
    
    if (strategyAnalysis && strategyAnalysis.result && strategyAnalysis.result.content) {
        content = strategyAnalysis.result.content;
        
        // 增强的关键指标提取逻辑
        const scoreMatch = content.match(/(?:综合评分|评分|综合得分)[：:]*\s*(\d+(?:\.\d+)?)/i);
        const riskMatch = content.match(/(?:风险等级|风险评级|风险)[：:]\s*([^。\n]+)/i);
        const positionMatch = content.match(/(?:建议仓位|仓位建议|仓位)[：:]\s*([^。\n]+)/i);
        const targetMatch = content.match(/(?:目标价位|目标价格|目标价)[：:]\s*([^。\n]+)/i);
        
        // 提取推荐建议
        const recommendationMatch = content.match(/(?:投资建议|建议|推荐)[：:]\s*([^。\n]+)/i);
        
        score = scoreMatch ? scoreMatch[1] : '--';
        risk = riskMatch ? riskMatch[1].trim() : '--';
        position = positionMatch ? positionMatch[1].trim() : '--';
        target = targetMatch ? targetMatch[1].trim() : '--';
        
        // 设置推荐建议
        if (recommendationMatch) {
            const recommendationText = recommendationMatch[1].trim();
            recommendation = recommendationText;
            
            // 根据推荐内容设置徽章样式
            if (recommendationText.includes('买入') || recommendationText.includes('增持') || recommendationText.includes('持有')) {
                recommendationClass = 'buy';
            } else if (recommendationText.includes('卖出') || recommendationText.includes('减持') || recommendationText.includes('空仓')) {
                recommendationClass = 'sell';
            } else {
                recommendationClass = 'hold';
            }
        }
    }
    
    // 更新推荐徽章
    const recommendationBadge = document.getElementById('recommendationBadge');
    recommendationBadge.className = `recommendation-badge ${recommendationClass}`;
    recommendationBadge.innerHTML = `<span class="badge-text">${recommendation}</span>`;
    
    // 更新摘要卡片
    document.getElementById('scoreValue').textContent = score;
    document.getElementById('riskValue').textContent = risk;
    document.getElementById('positionValue').textContent = position;
    document.getElementById('targetValue').textContent = target;
    
    // 优化内容显示，确保换行和格式正确
    let formattedContent = content;
    // 替换**文本**为HTML加粗标签
    formattedContent = formattedContent.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    // 替换换行符为<br>标签
    formattedContent = formattedContent.replace(/\n/g, '<br>');
    
    // 更新建议内容
    const summaryContent = document.getElementById('summaryContent');
    summaryContent.innerHTML = `<div class="content-wrapper">${formattedContent}</div>`;
    
    // 添加平滑过渡效果
    elements.summarySection.style.display = 'block';
    elements.summarySection.style.opacity = '0';
    elements.summarySection.style.transform = 'translateY(20px)';
    elements.summarySection.style.transition = 'all 0.5s cubic-bezier(0.25, 0.46, 0.45, 0.94)';
    
    // 触发重排后应用过渡效果
    setTimeout(() => {
        elements.summarySection.style.opacity = '1';
        elements.summarySection.style.transform = 'translateY(0)';
    }, 10);
}

// 添加到历史记录
function addToHistory(result) {
    const historyItem = {
        id: Date.now(),
        stockCode: appState.currentStockCode,
        timestamp: new Date().toISOString(),
        result: result
    };
    
    appState.analysisHistory.unshift(historyItem);
    
    // 限制历史记录数量
    if (appState.analysisHistory.length > 10) {
        appState.analysisHistory.pop();
    }
    
    // 保存到本地存储
    localStorage.setItem('analysisHistory', JSON.stringify(appState.analysisHistory));
    
    // 更新历史记录显示
    renderHistory();
}

// 渲染历史记录
function renderHistory() {
    if (appState.analysisHistory.length === 0) {
        elements.historyList.innerHTML = '<p class="no-history">暂无历史记录</p>';
        return;
    }
    
    let historyHtml = '';
    appState.analysisHistory.forEach(item => {
        const date = new Date(item.timestamp);
        const dateStr = date.toLocaleString('zh-CN');
        
        historyHtml += `
            <div class="history-item">
                <div class="history-info">
                    <div class="history-stock">股票代码: ${item.stockCode}</div>
                    <div class="history-date">分析时间: ${dateStr}</div>
                </div>
                <div class="history-actions">
                    <button class="history-btn view" onclick="viewHistoryItem(${item.id})">查看</button>
                    <button class="history-btn delete" onclick="deleteHistoryItem(${item.id})">删除</button>
                </div>
            </div>
        `;
    });
    
    elements.historyList.innerHTML = historyHtml;
}

// 查看历史记录项
function viewHistoryItem(id) {
    const item = appState.analysisHistory.find(h => h.id === id);
    if (item) {
        appState.currentStockCode = item.stockCode;
        elements.stockCode.value = item.stockCode;
        
        // 直接显示结果
        initializeProgress();
        showFinalRecommendation(item.result);
        
        // 模拟分析师结果更新
        Object.entries(item.result.analyses).forEach(([agentType, analysis]) => {
            handleAgentUpdate({
                agent_type: agentType,
                status: 'completed',
                progress: 100,
                message: analysis.result.content
            });
        });
        
        updateOverallProgress();
        showNotification('info', '历史记录', `已加载股票 ${item.stockCode} 的分析结果`);
    }
}

// 删除历史记录项
function deleteHistoryItem(id) {
    appState.analysisHistory = appState.analysisHistory.filter(h => h.id !== id);
    localStorage.setItem('analysisHistory', JSON.stringify(appState.analysisHistory));
    renderHistory();
    showNotification('success', '删除成功', '历史记录已删除');
}

// 显示通知
function showNotification(type, title, message, duration = 4000) {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.innerHTML = `
        <div class="notification-icon">${getNotificationIcon(type)}</div>
        <div class="notification-content">
            <div class="notification-title">${title}</div>
            <div class="notification-message">${message}</div>
        </div>
        <button class="notification-close" onclick="this.parentElement.remove()">×</button>
    `;
    
    elements.notificationContainer.appendChild(notification);
    
    // 自动关闭
    setTimeout(() => {
        if (notification.parentElement) {
            notification.classList.add('hiding');
            setTimeout(() => {
                if (notification.parentElement) {
                    notification.remove();
                }
            }, 300);
        }
    }, duration);
}

// 获取通知图标
function getNotificationIcon(type) {
    const icons = {
        success: '✓',
        error: '✕',
        warning: '⚠',
        info: 'ℹ'
    };
    return icons[type] || icons.info;
}

// 页面加载完成后初始化应用
document.addEventListener('DOMContentLoaded', initApp);

// 导出全局函数（供HTML调用）
window.viewHistoryItem = viewHistoryItem;
window.deleteHistoryItem = deleteHistoryItem;