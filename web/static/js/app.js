const socket = io({
    transports: ['websocket', 'polling'],
    reconnection: true,
    reconnectionAttempts: Infinity,
    reconnectionDelay: 1000,
    reconnectionDelayMax: 5000,
    timeout: 20000,
    pingTimeout: 60000,
    pingInterval: 25000
});

let currentAnalysis = null;
let analysisHistory = [];
let klineChart = null;
let radarChart = null;
let trendChart = null;
let currentKlineData = null;
let heartbeatInterval = null;
let isSocketReady = false;

const agentConfigs = {
    data_downloader: { name: '下载数据', icon: '📥', color: '#95a5a6' },
    technical_analyst: { name: '张技术', icon: '📈', color: '#3498db' },
    fundamental_analyst: { name: '李价值', icon: '💰', color: '#2ecc71' },
    risk_manager: { name: '王风控', icon: '⚠️', color: '#e74c3c' },
    sentiment_analyst: { name: '赵情绪', icon: '😊', color: '#9b59b6' },
    investment_strategist: { name: '陈策略', icon: '🎯', color: '#f39c12' }
};

function startHeartbeat() {
    if (heartbeatInterval) {
        clearInterval(heartbeatInterval);
    }
    heartbeatInterval = setInterval(() => {
        if (socket.connected) {
            socket.emit('ping');
        }
    }, 30000);
}

function stopHeartbeat() {
    if (heartbeatInterval) {
        clearInterval(heartbeatInterval);
        heartbeatInterval = null;
    }
}

socket.on('connect', () => {
    updateConnectionStatus(true);
    isSocketReady = true;
    console.log('已连接到服务器, Socket ID:', socket.id);
    startHeartbeat();
});

socket.on('disconnect', (reason) => {
    updateConnectionStatus(false);
    isSocketReady = false;
    stopHeartbeat();
    console.log('与服务器断开连接:', reason);
    if (reason === 'io server disconnect') {
        socket.connect();
    }
});

socket.on('reconnect', (attemptNumber) => {
    console.log('重新连接成功，尝试次数:', attemptNumber);
    updateConnectionStatus(true);
});

socket.on('reconnect_attempt', (attemptNumber) => {
    console.log('尝试重新连接...', attemptNumber);
});

socket.on('reconnect_error', (error) => {
    console.error('重新连接失败:', error);
});

socket.on('reconnect_failed', () => {
    console.error('重新连接失败，已达到最大尝试次数');
});

socket.on('pong', () => {
    console.log('收到服务器pong响应');
});

socket.on('connected', (data) => {
    console.log(data.message);
});

socket.on('agent_update', (data) => {
    console.log('Agent更新:', data);
    
    if (data.agent_type === 'system') {
        updateSystemMessage(data.message);
    } else {
        updateAgentStatus(data);
    }
});

socket.on('analysis_complete', (data) => {
    console.log('分析完成:', data);
    currentAnalysis = data.result;
    
    if (data.result && data.result.analyses) {
        displayAnalysisResults(data.result);
        addToHistory(data.result);
        updateOverallProgress();
        scrollToResults();
    } else if (data.result && data.result.error) {
        alert('分析失败: ' + data.result.error);
    }
});

socket.on('analysis_error', (data) => {
    console.error('分析错误:', data);
    alert('分析失败: ' + data.error);
});

function updateConnectionStatus(connected) {
    const indicator = document.querySelector('.status-indicator');
    const text = document.querySelector('.status-text');
    
    if (connected) {
        indicator.classList.remove('disconnected');
        indicator.classList.add('connected');
        text.textContent = '已连接';
    } else {
        indicator.classList.remove('connected');
        indicator.classList.add('disconnected');
        text.textContent = '未连接';
    }
}

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
        
        if (data.success && data.kline_data) {
            const klineData = data.kline_data.map(item => [
                item['日期'],
                parseFloat(item['开盘']),
                parseFloat(item['收盘']),
                parseFloat(item['最低']),
                parseFloat(item['最高']),
                parseFloat(item['成交量'])
            ]);
            
            updateKlineChart(klineData);
            updateChartInfo({
                stock_code: stockCode,
                kline_data: klineData
            });
        } else {
            console.error('获取K线数据失败:', data.error);
        }
    } catch (error) {
        console.error('获取K线数据失败:', error);
    }
}

function updateAgentStatus(data) {
    const agentCard = document.getElementById(data.agent_type);
    const statusIcon = document.getElementById(`status-${data.agent_type}`);
    const progressBar = document.getElementById(`progress-${data.agent_type}`);
    const progressText = document.getElementById(`progress-text-${data.agent_type}`);
    const contentDiv = document.getElementById(`content-${data.agent_type}`);
    
    const statusItem = document.getElementById(`status-${data.agent_type}-item`);
    const statusItemIcon = statusItem?.querySelector('.agent-status-icon');
    const statusItemText = statusItem?.querySelector('.agent-status-text');
    
    if (agentCard) {
        agentCard.classList.remove('analyzing', 'completed', 'error');
        
        if (data.status === 'analyzing' || data.status === 'streaming') {
            agentCard.classList.add('analyzing');
            statusIcon.textContent = '🔵';
            if (statusItem) {
                statusItem.classList.remove('completed', 'error');
                statusItem.classList.add('analyzing');
                if (statusItemIcon) statusItemIcon.textContent = '🔵';
                if (statusItemText) statusItemText.textContent = '分析中';
            }
        } else if (data.status === 'completed') {
            agentCard.classList.add('completed');
            statusIcon.textContent = '✅';
            if (statusItem) {
                statusItem.classList.remove('analyzing', 'error');
                statusItem.classList.add('completed');
                if (statusItemIcon) statusItemIcon.textContent = '✅';
                if (statusItemText) statusItemText.textContent = '已完成';
            }
        } else if (data.status === 'error') {
            agentCard.classList.add('error');
            statusIcon.textContent = '❌';
            if (statusItem) {
                statusItem.classList.remove('analyzing', 'completed');
                statusItem.classList.add('error');
                if (statusItemIcon) statusItemIcon.textContent = '❌';
                if (statusItemText) statusItemText.textContent = '失败';
            }
        }
    } else if (statusItem) {
        statusItem.classList.remove('analyzing', 'completed', 'error');
        
        if (data.status === 'analyzing' || data.status === 'streaming') {
            statusItem.classList.add('analyzing');
            if (statusItemIcon) statusItemIcon.textContent = '🔵';
            if (statusItemText) statusItemText.textContent = '下载中';
        } else if (data.status === 'completed') {
            statusItem.classList.add('completed');
            if (statusItemIcon) statusItemIcon.textContent = '✅';
            if (statusItemText) statusItemText.textContent = '已完成';
        } else if (data.status === 'error') {
            statusItem.classList.add('error');
            if (statusItemIcon) statusItemIcon.textContent = '❌';
            if (statusItemText) statusItemText.textContent = '失败';
        }
    }
    
    if (progressBar && progressText) {
        progressBar.style.width = data.progress + '%';
        progressText.textContent = data.progress + '%';
    }
    
    if (contentDiv) {
        if (data.is_stream && data.message) {
            const currentContent = contentDiv.innerHTML;
            if (currentContent.includes('placeholder')) {
                contentDiv.innerHTML = `<pre>${data.message}</pre>`;
            } else {
                const preElement = contentDiv.querySelector('pre');
                if (preElement) {
                    preElement.textContent += data.message;
                } else {
                    contentDiv.innerHTML = `<pre>${data.message}</pre>`;
                }
            }
            contentDiv.scrollTop = contentDiv.scrollHeight;
        } else if (data.message && data.status === 'analyzing') {
            contentDiv.innerHTML = `<p style="color: #667eea;">${data.message}</p>`;
        }
    }
    
    updateOverallProgress();
}

function updateSystemMessage(message) {
    console.log('系统消息:', message);
    const loadingText = document.getElementById('loadingText');
    if (loadingText) {
        loadingText.textContent = message;
    }
}

function displayAnalysisResults(result) {
    const analyses = result.analyses;
    
    for (const [agentType, analysis] of Object.entries(analyses)) {
        const contentDiv = document.getElementById(`content-${agentType}`);
        
        if (contentDiv) {
            if (analysis.error) {
                contentDiv.innerHTML = `<p style="color: #f44336;">❌ 分析失败: ${analysis.error}</p>`;
            } else if (analysis.result && analysis.result.content) {
                const formattedContent = formatContent(analysis.result.content);
                contentDiv.innerHTML = `<pre>${formattedContent}</pre>`;
            }
        }
    }
    
    const finalSummaryDiv = document.getElementById('finalSummary');
    const finalSummaryContent = document.getElementById('finalSummaryContent');
    
    if (analyses && analyses.investment_strategist && analyses.investment_strategist.result && analyses.investment_strategist.result.content) {
        const finalContent = analyses.investment_strategist.result.content;
        const formattedFinalContent = formatContent(finalContent);
        finalSummaryContent.innerHTML = `<pre>${formattedFinalContent}</pre>`;
        finalSummaryDiv.style.display = 'block';
        
        updateFinalSummary(result);
        updateRadarChart(analyses.technical_analyst, analyses.fundamental_analyst, analyses.sentiment_analyst, analyses.risk_manager);
    } else {
        finalSummaryDiv.style.display = 'none';
    }
    
    if (result.stock_data && result.stock_data.kline_data) {
        const klineData = result.stock_data.kline_data;
        const formattedKlineData = klineData.map(item => [
            item.日期 || '',
            parseFloat(item.开盘) || 0,
            parseFloat(item.收盘) || 0,
            parseFloat(item.最低) || 0,
            parseFloat(item.最高) || 0,
            parseFloat(item.成交量) || 0
        ]);
        
        if (!klineChart) {
            initKlineChart();
        }
        
        updateKlineChart(formattedKlineData);
        updateChartInfo(result.stock_data);
        updateTrendChart(formattedKlineData);
        showChartSection();
        
        showAnalysisChartsSection();
        initAnalysisCharts(formattedKlineData);
    }
}

function showAnalysisChartsSection() {
    const analysisChartsSection = document.getElementById('analysisChartsSection');
    if (analysisChartsSection) {
        analysisChartsSection.style.display = 'block';
    }
}

function initAnalysisCharts(klineData) {
    initVolumeChart(klineData);
    initMACDChart(klineData);
    initRSIChart(klineData);
    initAllocationChart();
}

let volumeChart = null;
let macdChart = null;
let rsiChart = null;
let allocationChart = null;

function initVolumeChart(klineData) {
    if (volumeChart) {
        volumeChart.dispose();
    }
    
    const chartDom = document.getElementById('volumeChart');
    if (!chartDom) return;
    
    volumeChart = echarts.init(chartDom);
    
    const dates = klineData.map(item => item[0]);
    const volumes = klineData.map(item => item[5]);
    const closes = klineData.map(item => item[2]);
    
    const avgVolume = volumes.reduce((a, b) => a + b, 0) / volumes.length;
    document.getElementById('avgVolume').textContent = formatVolume(avgVolume);
    
    const recentVolumes = volumes.slice(-10);
    const earlierVolumes = volumes.slice(-20, -10);
    const recentAvg = recentVolumes.reduce((a, b) => a + b, 0) / recentVolumes.length;
    const earlierAvg = earlierVolumes.reduce((a, b) => a + b, 0) / earlierVolumes.length;
    
    const volumeTrendElement = document.getElementById('volumeTrend');
    if (recentAvg > earlierAvg * 1.1) {
        volumeTrendElement.textContent = '放量上涨';
        volumeTrendElement.style.color = '#f5222d';
    } else if (recentAvg < earlierAvg * 0.9) {
        volumeTrendElement.textContent = '缩量下跌';
        volumeTrendElement.style.color = '#52c41a';
    } else {
        volumeTrendElement.textContent = '量能平稳';
        volumeTrendElement.style.color = '#1890ff';
    }
    
    const recentPriceChange = closes[closes.length - 1] - closes[closes.length - 10];
    const priceVolumeRelationElement = document.getElementById('priceVolumeRelation');
    if ((recentPriceChange > 0 && recentAvg > earlierAvg) || (recentPriceChange < 0 && recentAvg < earlierAvg)) {
        priceVolumeRelationElement.textContent = '量价配合';
        priceVolumeRelationElement.style.color = '#52c41a';
    } else {
        priceVolumeRelationElement.textContent = '量价背离';
        priceVolumeRelationElement.style.color = '#faad14';
    }
    
    const option = {
        tooltip: {
            trigger: 'axis',
            axisPointer: {
                type: 'shadow'
            },
            backgroundColor: 'rgba(255, 255, 255, 0.95)',
            borderColor: '#d9d9d9',
            borderWidth: 1,
            textStyle: {
                color: '#262626',
                fontSize: 12
            },
            padding: [10, 15],
            formatter: function(params) {
                return `<div style="font-weight:600;margin-bottom:5px;">${params[0].axisValue}</div>` +
                       `<div style="margin:3px 0;"><span style="color:${params[0].color};">●</span><span style="margin-left:8px;color:#262626;">成交量:</span><span style="margin-left:5px;color:${params[0].color};">${formatVolume(params[0].data)}</span></div>`;
            }
        },
        grid: {
            left: '8%',
            right: '5%',
            top: '10%',
            bottom: '15%',
            containLabel: true
        },
        xAxis: {
            type: 'category',
            data: dates.slice(-60),
            axisLine: {
                lineStyle: {
                    color: '#d9d9d9'
                }
            },
            axisTick: {
                show: false
            },
            axisLabel: {
                color: '#8c8c8c',
                fontSize: 10,
                rotate: 45
            },
            splitLine: {
                show: false
            }
        },
        yAxis: {
            type: 'value',
            axisLine: {
                show: false
            },
            axisTick: {
                show: false
            },
            axisLabel: {
                color: '#8c8c8c',
                fontSize: 10,
                formatter: function(value) {
                    if (value >= 100000000) {
                        return (value / 100000000).toFixed(1) + '亿';
                    } else if (value >= 10000) {
                        return (value / 10000).toFixed(1) + '万';
                    }
                    return value;
                }
            },
            splitLine: {
                lineStyle: {
                    color: '#f0f0f0',
                    type: 'dashed'
                }
            }
        },
        series: [
            {
                name: '成交量',
                type: 'bar',
                data: volumes.slice(-60).map((vol, idx) => {
                    const close = closes[closes.length - 60 + idx];
                    const prevClose = closes[closes.length - 61 + idx] || close;
                    return {
                        value: vol,
                        itemStyle: {
                            color: close >= prevClose ? '#f5222d' : '#52c41a'
                        }
                    };
                }),
                barWidth: '60%'
            }
        ]
    };
    
    volumeChart.setOption(option);
}

function initMACDChart(klineData) {
    if (macdChart) {
        macdChart.dispose();
    }
    
    const chartDom = document.getElementById('macdChart');
    if (!chartDom) return;
    
    macdChart = echarts.init(chartDom);
    
    const closes = klineData.map(item => item[2]);
    const dif = calculateMACD(closes, 12, 26, 9).dif;
    const dea = calculateMACD(closes, 12, 26, 9).dea;
    const macd = calculateMACD(closes, 12, 26, 9).macd;
    
    const lastDif = dif[dif.length - 1];
    const lastDea = dea[dea.length - 1];
    const lastMACD = macd[macd.length - 1];
    
    document.getElementById('difValue').textContent = lastDif.toFixed(4);
    document.getElementById('deaValue').textContent = lastDea.toFixed(4);
    
    const macdSignalElement = document.getElementById('macdSignal');
    if (lastDif > lastDea && lastMACD > 0) {
        macdSignalElement.textContent = '金叉看涨';
        macdSignalElement.style.color = '#f5222d';
    } else if (lastDif < lastDea && lastMACD < 0) {
        macdSignalElement.textContent = '死叉看跌';
        macdSignalElement.style.color = '#52c41a';
    } else {
        macdSignalElement.textContent = '震荡整理';
        macdSignalElement.style.color = '#1890ff';
    }
    
    const dates = klineData.map(item => item[0]);
    
    const option = {
        tooltip: {
            trigger: 'axis',
            axisPointer: {
                type: 'cross'
            },
            backgroundColor: 'rgba(255, 255, 255, 0.95)',
            borderColor: '#d9d9d9',
            borderWidth: 1,
            textStyle: {
                color: '#262626',
                fontSize: 12
            },
            padding: [10, 15]
        },
        legend: {
            data: ['DIF', 'DEA', 'MACD'],
            top: 5,
            textStyle: {
                color: '#595959',
                fontSize: 11
            },
            itemGap: 10,
            itemWidth: 15,
            itemHeight: 10
        },
        grid: {
            left: '8%',
            right: '5%',
            top: '15%',
            bottom: '12%',
            containLabel: true
        },
        xAxis: {
            type: 'category',
            data: dates.slice(-60),
            axisLine: {
                lineStyle: {
                    color: '#d9d9d9'
                }
            },
            axisTick: {
                show: false
            },
            axisLabel: {
                color: '#8c8c8c',
                fontSize: 10,
                rotate: 45
            },
            splitLine: {
                show: false
            }
        },
        yAxis: {
            type: 'value',
            axisLine: {
                show: false
            },
            axisTick: {
                show: false
            },
            axisLabel: {
                color: '#8c8c8c',
                fontSize: 10
            },
            splitLine: {
                lineStyle: {
                    color: '#f0f0f0',
                    type: 'dashed'
                }
            }
        },
        series: [
            {
                name: 'DIF',
                type: 'line',
                data: dif.slice(-60),
                smooth: true,
                symbol: 'circle',
                symbolSize: 4,
                lineStyle: {
                    width: 2,
                    color: '#667eea'
                },
                itemStyle: {
                    color: '#667eea'
                }
            },
            {
                name: 'DEA',
                type: 'line',
                data: dea.slice(-60),
                smooth: true,
                symbol: 'circle',
                symbolSize: 4,
                lineStyle: {
                    width: 2,
                    color: '#f5222d'
                },
                itemStyle: {
                    color: '#f5222d'
                }
            },
            {
                name: 'MACD',
                type: 'bar',
                data: macd.slice(-60).map(val => ({
                    value: val,
                    itemStyle: {
                        color: val >= 0 ? '#f5222d' : '#52c41a'
                    }
                })),
                barWidth: '40%'
            }
        ]
    };
    
    macdChart.setOption(option);
}

function initRSIChart(klineData) {
    if (rsiChart) {
        rsiChart.dispose();
    }
    
    const chartDom = document.getElementById('rsiChart');
    if (!chartDom) return;
    
    rsiChart = echarts.init(chartDom);
    
    const closes = klineData.map(item => item[2]);
    const rsi6 = calculateRSI(closes, 6);
    const rsi12 = calculateRSI(closes, 12);
    const rsi24 = calculateRSI(closes, 24);
    
    document.getElementById('rsi6Value').textContent = rsi6[rsi6.length - 1].toFixed(2);
    document.getElementById('rsi12Value').textContent = rsi12[rsi12.length - 1].toFixed(2);
    document.getElementById('rsi24Value').textContent = rsi24[rsi24.length - 1].toFixed(2);
    
    const dates = klineData.map(item => item[0]);
    
    const option = {
        tooltip: {
            trigger: 'axis',
            axisPointer: {
                type: 'cross'
            },
            backgroundColor: 'rgba(255, 255, 255, 0.95)',
            borderColor: '#d9d9d9',
            borderWidth: 1,
            textStyle: {
                color: '#262626',
                fontSize: 12
            },
            padding: [10, 15]
        },
        legend: {
            data: ['RSI(6)', 'RSI(12)', 'RSI(24)'],
            top: 5,
            textStyle: {
                color: '#595959',
                fontSize: 11
            },
            itemGap: 10,
            itemWidth: 15,
            itemHeight: 10
        },
        grid: {
            left: '8%',
            right: '5%',
            top: '15%',
            bottom: '12%',
            containLabel: true
        },
        xAxis: {
            type: 'category',
            data: dates.slice(-60),
            axisLine: {
                lineStyle: {
                    color: '#d9d9d9'
                }
            },
            axisTick: {
                show: false
            },
            axisLabel: {
                color: '#8c8c8c',
                fontSize: 10,
                rotate: 45
            },
            splitLine: {
                show: false
            }
        },
        yAxis: {
            type: 'value',
            min: 0,
            max: 100,
            axisLine: {
                show: false
            },
            axisTick: {
                show: false
            },
            axisLabel: {
                color: '#8c8c8c',
                fontSize: 10
            },
            splitLine: {
                lineStyle: {
                    color: '#f0f0f0',
                    type: 'dashed'
                }
            }
        },
        markLine: {
            data: [
                { yAxis: 70, name: '超买线' },
                { yAxis: 30, name: '超卖线' }
            ],
            lineStyle: {
                color: '#faad14',
                type: 'dashed'
            },
            label: {
                show: false
            }
        },
        series: [
            {
                name: 'RSI(6)',
                type: 'line',
                data: rsi6.slice(-60),
                smooth: true,
                symbol: 'circle',
                symbolSize: 4,
                lineStyle: {
                    width: 2,
                    color: '#667eea'
                },
                itemStyle: {
                    color: '#667eea'
                }
            },
            {
                name: 'RSI(12)',
                type: 'line',
                data: rsi12.slice(-60),
                smooth: true,
                symbol: 'circle',
                symbolSize: 4,
                lineStyle: {
                    width: 2,
                    color: '#f5222d'
                },
                itemStyle: {
                    color: '#f5222d'
                }
            },
            {
                name: 'RSI(24)',
                type: 'line',
                data: rsi24.slice(-60),
                smooth: true,
                symbol: 'circle',
                symbolSize: 4,
                lineStyle: {
                    width: 2,
                    color: '#52c41a'
                },
                itemStyle: {
                    color: '#52c41a'
                }
            }
        ]
    };
    
    rsiChart.setOption(option);
}

function initAllocationChart() {
    if (allocationChart) {
        allocationChart.dispose();
    }
    
    const chartDom = document.getElementById('allocationChart');
    if (!chartDom) return;
    
    allocationChart = echarts.init(chartDom);
    
    const position = document.getElementById('positionValue').textContent;
    const positionNum = position !== '--' ? parseInt(position) : 50;
    
    document.getElementById('suggestedPosition').textContent = position;
    
    const riskControlElement = document.getElementById('riskControl');
    if (positionNum >= 70) {
        riskControlElement.textContent = '积极进取';
        riskControlElement.style.color = '#f5222d';
    } else if (positionNum >= 40) {
        riskControlElement.textContent = '稳健平衡';
        riskControlElement.style.color = '#1890ff';
    } else {
        riskControlElement.textContent = '保守防御';
        riskControlElement.style.color = '#52c41a';
    }
    
    const currentPrice = document.getElementById('chartCurrentPrice').textContent;
    const stopLossElement = document.getElementById('stopLoss');
    if (currentPrice !== '--') {
        const price = parseFloat(currentPrice);
        const stopLossPrice = (price * 0.95).toFixed(2);
        stopLossElement.textContent = stopLossPrice;
        stopLossElement.style.color = '#faad14';
    } else {
        stopLossElement.textContent = '--';
    }
    
    const option = {
        tooltip: {
            trigger: 'item',
            backgroundColor: 'rgba(255, 255, 255, 0.95)',
            borderColor: '#d9d9d9',
            borderWidth: 1,
            textStyle: {
                color: '#262626',
                fontSize: 12
            },
            padding: [10, 15],
            formatter: '{a} <br/>{b}: {c}% ({d}%)'
        },
        legend: {
            orient: 'vertical',
            left: 'left',
            top: 'middle',
            textStyle: {
                color: '#595959',
                fontSize: 12
            },
            itemGap: 15,
            itemWidth: 15,
            itemHeight: 10
        },
        series: [
            {
                name: '仓位配置',
                type: 'pie',
                radius: ['40%', '70%'],
                center: ['60%', '50%'],
                avoidLabelOverlap: false,
                label: {
                    show: true,
                    formatter: '{b}\n{c}%',
                    color: '#595959',
                    fontSize: 12
                },
                emphasis: {
                    label: {
                        show: true,
                        fontSize: 14,
                        fontWeight: 'bold'
                    }
                },
                labelLine: {
                    show: true
                },
                data: [
                    {
                        value: positionNum,
                        name: '建议仓位',
                        itemStyle: {
                            color: '#667eea'
                        }
                    },
                    {
                        value: 100 - positionNum,
                        name: '现金储备',
                        itemStyle: {
                            color: '#e8e8e8'
                        }
                    }
                ]
            }
        ]
    };
    
    allocationChart.setOption(option);
}

function calculateMACD(closes, shortPeriod, longPeriod, signalPeriod) {
    const emaShort = calculateEMA(closes, shortPeriod);
    const emaLong = calculateEMA(closes, longPeriod);
    const dif = emaShort.map((val, idx) => val - emaLong[idx]);
    const dea = calculateEMA(dif, signalPeriod);
    const macd = dif.map((val, idx) => (val - dea[idx]) * 2);
    
    return { dif, dea, macd };
}

function calculateEMA(data, period) {
    const k = 2 / (period + 1);
    const ema = [data[0]];
    
    for (let i = 1; i < data.length; i++) {
        ema.push(data[i] * k + ema[i - 1] * (1 - k));
    }
    
    return ema;
}

function calculateRSI(closes, period) {
    const rsi = [];
    
    for (let i = 0; i < closes.length; i++) {
        if (i < period) {
            rsi.push(50);
            continue;
        }
        
        let gains = 0;
        let losses = 0;
        
        for (let j = i - period + 1; j <= i; j++) {
            const change = closes[j] - closes[j - 1];
            if (change > 0) {
                gains += change;
            } else {
                losses -= change;
            }
        }
        
        const avgGain = gains / period;
        const avgLoss = losses / period;
        
        if (avgLoss === 0) {
            rsi.push(100);
        } else {
            const rs = avgGain / avgLoss;
            rsi.push(100 - (100 / (1 + rs)));
        }
    }
    
    return rsi;
}

function formatVolume(volume) {
    if (volume >= 100000000) {
        return (volume / 100000000).toFixed(2) + '亿';
    } else if (volume >= 10000) {
        return (volume / 10000).toFixed(2) + '万';
    }
    return volume.toFixed(0);
}

function formatContent(content) {
    return content
        .replace(/【/g, '\n【')
        .replace(/•/g, '\n•')
        .replace(/\n\n+/g, '\n\n')
        .trim();
}

function addToHistory(result) {
    let recommendation = 'hold';
    let recommendationSource = '';
    
    const analyses = result.analyses;
    
    if (analyses && analyses.investment_strategist && analyses.investment_strategist.result && analyses.investment_strategist.result.content) {
        const content = analyses.investment_strategist.result.content;
        
        const sellKeywords = ['强烈卖出', '卖出', '回避', '清仓', '减仓', '不推荐', '风险较高', '高风险'];
        const buyKeywords = ['强烈买入', '买入', '推荐', '积极', '看好', '机会', '低估'];
        const holdKeywords = ['持有', '观望', '保持', '维持'];
        
        let hasSellSignal = false;
        let hasBuySignal = false;
        let hasHoldSignal = false;
        
        for (const keyword of sellKeywords) {
            if (content.includes(keyword)) {
                hasSellSignal = true;
                break;
            }
        }
        
        for (const keyword of buyKeywords) {
            if (content.includes(keyword)) {
                hasBuySignal = true;
                break;
            }
        }
        
        for (const keyword of holdKeywords) {
            if (content.includes(keyword)) {
                hasHoldSignal = true;
                break;
            }
        }
        
        if (hasHoldSignal && !hasBuySignal && !hasSellSignal) {
            recommendation = 'hold';
            recommendationSource = '综合策略';
        } else if (hasSellSignal && !hasBuySignal) {
            recommendation = 'sell';
            recommendationSource = '综合策略';
        } else if (hasBuySignal && !hasSellSignal) {
            recommendation = 'buy';
            recommendationSource = '综合策略';
        } else if (hasBuySignal && hasSellSignal) {
            const finalRecommendationMatch = content.match(/操作建议[：:]\s*([买入卖出持有观望]+)/);
            if (finalRecommendationMatch) {
                const finalRec = finalRecommendationMatch[1];
                if (finalRec.includes('卖出')) {
                    recommendation = 'sell';
                    recommendationSource = '综合策略';
                } else if (finalRec.includes('买入')) {
                    recommendation = 'buy';
                    recommendationSource = '综合策略';
                } else {
                    recommendation = 'hold';
                    recommendationSource = '综合策略';
                }
            } else {
                recommendation = 'hold';
                recommendationSource = '综合策略';
            }
        } else {
            recommendation = 'hold';
            recommendationSource = '综合策略';
        }
    }
    
    const historyItem = {
        stockCode: result.stock_code,
        stockName: result.stock_name,
        time: new Date().toLocaleString('zh-CN'),
        recommendation: recommendation,
        recommendationSource: recommendationSource
    };
    
    analysisHistory.unshift(historyItem);
    updateHistoryDisplay();
}

function updateHistoryDisplay() {
    const historyList = document.getElementById('historyList');
    
    if (analysisHistory.length === 0) {
        historyList.innerHTML = '<p class="no-history">暂无历史记录</p>';
        return;
    }
    
    historyList.innerHTML = analysisHistory.map(item => `
        <div class="history-item">
            <div class="history-info">
                <div class="history-stock">${item.stockName} (${item.stockCode})</div>
                <div class="history-time">${item.time}</div>
                ${item.recommendationSource ? `<div class="history-source">来源: ${item.recommendationSource}</div>` : ''}
            </div>
            <div class="history-result ${item.recommendation}">
                ${item.recommendation === 'buy' ? '买入' : item.recommendation === 'sell' ? '卖出' : '持有'}
            </div>
        </div>
    `).join('');
}

function startAnalysis() {
    const stockCode = document.getElementById('stockCode').value.trim();
    
    if (!stockCode) {
        alert('请输入股票代码');
        return;
    }
    
    if (!/^\d{6}$/.test(stockCode)) {
        alert('请输入正确的6位股票代码');
        return;
    }
    
    console.log('Socket connected:', socket.connected);
    console.log('Socket ready:', isSocketReady);
    console.log('Socket ID:', socket.id);
    console.log('Socket对象:', socket);
    
    if (!isSocketReady || !socket.id) {
        alert('连接尚未建立，请等待连接完成或刷新页面重试');
        return;
    }
    
    resetAgentCards();
    showOverallProgress();
    
    const requestData = { 
        stock_code: stockCode,
        session_id: socket.id
    };
    
    console.log('准备发送的请求数据:', requestData);
    
    fetch('/api/analyze', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(requestData)
    })
    .then(response => response.json())
    .then(data => {
        if (!data.success) {
            throw new Error(data.error || '分析失败');
        }
        console.log('分析任务已启动:', data.task_id);
    })
    .catch(error => {
        console.error('启动分析失败:', error);
        alert('启动分析失败: ' + error.message);
    });
}

function resetAgentCards() {
    const agentTypes = Object.keys(agentConfigs);
    
    agentTypes.forEach(agentType => {
        const agentCard = document.getElementById(agentType);
        const statusIcon = document.getElementById(`status-${agentType}`);
        const progressBar = document.getElementById(`progress-${agentType}`);
        const progressText = document.getElementById(`progress-text-${agentType}`);
        const contentDiv = document.getElementById(`content-${agentType}`);
        
        const statusItem = document.getElementById(`status-${agentType}-item`);
        const statusItemIcon = statusItem?.querySelector('.agent-status-icon');
        const statusItemText = statusItem?.querySelector('.agent-status-text');
        
        if (agentCard) {
            agentCard.classList.remove('analyzing', 'completed', 'error');
        }
        
        if (statusIcon) {
            statusIcon.textContent = '⏳';
        }
        
        if (progressBar) {
            progressBar.style.width = '0%';
        }
        
        if (progressText) {
            progressText.textContent = '0%';
        }
        
        if (contentDiv) {
            if (agentType === 'investment_strategist') {
                contentDiv.innerHTML = '<p class="placeholder">等待其他Agent分析...</p>';
            } else {
                contentDiv.innerHTML = '<p class="placeholder">等待分析...</p>';
            }
        }
        
        if (statusItem) {
            statusItem.classList.remove('analyzing', 'completed', 'error');
            if (statusItemIcon) statusItemIcon.textContent = '⏳';
            if (statusItemText) statusItemText.textContent = '等待中';
        }
    });
    
    const finalSummaryDiv = document.getElementById('finalSummary');
    if (finalSummaryDiv) {
        finalSummaryDiv.style.display = 'none';
    }
    
    resetOverallProgress();
}

function resetOverallProgress() {
    const overallProgressSection = document.getElementById('overallProgress');
    const overallProgressFill = document.getElementById('overallProgressFill');
    const overallProgressPercentage = document.getElementById('overallProgressPercentage');
    const overallProgressStatus = document.getElementById('overallProgressStatus');
    
    if (overallProgressSection) {
        overallProgressSection.style.display = 'none';
    }
    
    if (overallProgressFill) {
        overallProgressFill.style.width = '0%';
    }
    
    if (overallProgressPercentage) {
        overallProgressPercentage.textContent = '0%';
    }
    
    if (overallProgressStatus) {
        overallProgressStatus.textContent = '等待开始...';
    }
}

function showOverallProgress() {
    const overallProgressSection = document.getElementById('overallProgress');
    if (overallProgressSection) {
        overallProgressSection.style.display = 'block';
    }
}

function updateOverallProgress() {
    const agentTypes = Object.keys(agentConfigs);
    let totalProgress = 0;
    let completedCount = 0;
    let analyzingCount = 0;
    let progressAgentCount = 0;
    
    agentTypes.forEach(agentType => {
        const progressText = document.getElementById(`progress-text-${agentType}`);
        const statusIcon = document.getElementById(`status-${agentType}`);
        const statusItem = document.getElementById(`status-${agentType}-item`);
        
        if (progressText) {
            const progress = parseInt(progressText.textContent) || 0;
            totalProgress += progress;
            progressAgentCount++;
        }
        
        if (statusIcon) {
            if (statusIcon.textContent === '✅') {
                completedCount++;
            } else if (statusIcon.textContent === '🔵') {
                analyzingCount++;
            }
        } else if (statusItem) {
            const statusItemIcon = statusItem.querySelector('.agent-status-icon');
            if (statusItemIcon) {
                if (statusItemIcon.textContent === '✅') {
                    completedCount++;
                } else if (statusItemIcon.textContent === '🔵') {
                    analyzingCount++;
                }
            }
        }
    });
    
    const averageProgress = progressAgentCount > 0 ? Math.round(totalProgress / progressAgentCount) : 0;
    
    const overallProgressFill = document.getElementById('overallProgressFill');
    const overallProgressPercentage = document.getElementById('overallProgressPercentage');
    const overallProgressStatus = document.getElementById('overallProgressStatus');
    
    if (overallProgressFill) {
        overallProgressFill.style.width = averageProgress + '%';
    }
    
    if (overallProgressPercentage) {
        overallProgressPercentage.textContent = averageProgress + '%';
    }
    
    if (overallProgressStatus) {
        if (completedCount === agentTypes.length) {
            overallProgressStatus.textContent = '分析完成！';
        } else if (analyzingCount > 0) {
            overallProgressStatus.textContent = `正在分析中... (${completedCount}/${agentTypes.length} 完成)`;
        } else {
            overallProgressStatus.textContent = '准备开始分析...';
        }
    }
}

function clearHistory() {
    if (analysisHistory.length === 0) {
        alert('暂无历史记录可清除');
        return;
    }
    
    if (confirm('确定要清除所有历史记录吗？')) {
        analysisHistory = [];
        updateHistoryDisplay();
    }
}

document.getElementById('stockCode').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        startAnalysis();
    }
});

function initKlineChart() {
    if (klineChart) {
        klineChart.dispose();
    }
    
    const chartDom = document.getElementById('klineChart');
    klineChart = echarts.init(chartDom);
    
    const option = {
        title: {
            text: '',
            left: 'center'
        },
        tooltip: {
            trigger: 'axis',
            axisPointer: {
                type: 'cross'
            },
            backgroundColor: 'rgba(255, 255, 255, 0.95)',
            borderColor: '#d9d9d9',
            borderWidth: 1,
            textStyle: {
                color: '#262626',
                fontSize: 12
            },
            padding: [10, 15],
            formatter: function(params) {
                let result = `<div style="font-weight:600;margin-bottom:5px;">${params[0].axisValue}</div>`;
                params.forEach(param => {
                    if (param.seriesName === 'K线') {
                        const data = param.data;
                        result += `<div style="margin:3px 0;"><span style="color:#8c8c8c;">开盘:</span><span style="margin-left:8px;color:#262626;">${data[1]}</span></div>`;
                        result += `<div style="margin:3px 0;"><span style="color:#8c8c8c;">收盘:</span><span style="margin-left:8px;color:#262626;">${data[2]}</span></div>`;
                        result += `<div style="margin:3px 0;"><span style="color:#8c8c8c;">最低:</span><span style="margin-left:8px;color:#262626;">${data[3]}</span></div>`;
                        result += `<div style="margin:3px 0;"><span style="color:#8c8c8c;">最高:</span><span style="margin-left:8px;color:#262626;">${data[4]}</span></div>`;
                    } else if (param.seriesName === '成交量') {
                        result += `<div style="margin:3px 0;"><span style="color:#8c8c8c;">成交量:</span><span style="margin-left:8px;color:#262626;">${param.data}</span></div>`;
                    } else if (param.seriesName === 'MA5') {
                        result += `<div style="margin:3px 0;"><span style="color:#8c8c8c;">MA5:</span><span style="margin-left:8px;color:#262626;">${param.data.toFixed(2)}</span></div>`;
                    } else if (param.seriesName === 'MA10') {
                        result += `<div style="margin:3px 0;"><span style="color:#8c8c8c;">MA10:</span><span style="margin-left:8px;color:#262626;">${param.data.toFixed(2)}</span></div>`;
                    } else if (param.seriesName === 'MA20') {
                        result += `<div style="margin:3px 0;"><span style="color:#8c8c8c;">MA20:</span><span style="margin-left:8px;color:#262626;">${param.data.toFixed(2)}</span></div>`;
                    } else if (param.seriesName === 'MA30') {
                        result += `<div style="margin:3px 0;"><span style="color:#8c8c8c;">MA30:</span><span style="margin-left:8px;color:#262626;">${param.data.toFixed(2)}</span></div>`;
                    }
                });
                return result;
            }
        },
        legend: {
            data: ['K线', 'MA5', 'MA10', 'MA20', 'MA30', '成交量'],
            top: 5,
            textStyle: {
                color: '#595959',
                fontSize: 12
            },
            itemGap: 15,
            itemWidth: 20,
            itemHeight: 10
        },
        grid: [
            {
                left: '8%',
                right: '6%',
                top: '12%',
                height: '55%'
            },
            {
                left: '8%',
                right: '6%',
                top: '72%',
                height: '12%'
            }
        ],
        xAxis: [
            {
                type: 'category',
                data: [],
                scale: true,
                boundaryGap: false,
                axisLine: { 
                    lineStyle: { color: '#d9d9d9' }
                },
                axisTick: { 
                    show: false 
                },
                axisLabel: { 
                    color: '#8c8c8c',
                    fontSize: 11
                },
                splitLine: { show: false },
                min: 'dataMin',
                max: 'dataMax'
            },
            {
                type: 'category',
                gridIndex: 1,
                data: [],
                scale: true,
                boundaryGap: false,
                axisLine: { 
                    lineStyle: { color: '#d9d9d9' }
                },
                axisTick: { 
                    show: false 
                },
                splitLine: { show: false },
                axisLabel: { show: false },
                min: 'dataMin',
                max: 'dataMax'
            }
        ],
        yAxis: [
            {
                scale: true,
                splitArea: {
                    show: true
                },
                splitLine: {
                    show: true,
                    lineStyle: {
                        color: '#f0f0f0',
                        type: 'dashed'
                    }
                },
                axisLabel: {
                    color: '#8c8c8c',
                    fontSize: 11
                },
                axisLine: {
                    show: false
                },
                axisTick: {
                    show: false
                }
            },
            {
                scale: true,
                gridIndex: 1,
                splitNumber: 2,
                axisLabel: { show: false },
                axisLine: { show: false },
                axisTick: { show: false },
                splitLine: { show: false }
            }
        ],
        dataZoom: [
            {
                type: 'inside',
                xAxisIndex: [0, 1],
                start: 50,
                end: 100
            },
            {
                show: true,
                xAxisIndex: [0, 1],
                type: 'slider',
                top: '88%',
                start: 50,
                end: 100,
                height: 20,
                borderColor: '#d9d9d9',
                fillerColor: 'rgba(24, 144, 255, 0.2)',
                handleStyle: {
                    color: '#1890ff'
                },
                textStyle: {
                    color: '#8c8c8c'
                }
            }
        ],
        series: [
            {
                name: 'K线',
                type: 'candlestick',
                data: [],
                itemStyle: {
                    color: '#f5222d',
                    color0: '#52c41a',
                    borderColor: '#f5222d',
                    borderColor0: '#52c41a'
                }
            },
            {
                name: 'MA5',
                type: 'line',
                data: [],
                smooth: true,
                symbol: 'none',
                lineStyle: {
                    opacity: 0.9,
                    width: 1
                }
            },
            {
                name: 'MA10',
                type: 'line',
                data: [],
                smooth: true,
                symbol: 'none',
                lineStyle: {
                    opacity: 0.9,
                    width: 1
                }
            },
            {
                name: 'MA20',
                type: 'line',
                data: [],
                smooth: true,
                symbol: 'none',
                lineStyle: {
                    opacity: 0.9,
                    width: 1
                }
            },
            {
                name: 'MA30',
                type: 'line',
                data: [],
                smooth: true,
                symbol: 'none',
                lineStyle: {
                    opacity: 0.9,
                    width: 1
                }
            },
            {
                name: '成交量',
                type: 'bar',
                xAxisIndex: 1,
                yAxisIndex: 1,
                data: [],
                itemStyle: {
                    color: function(params) {
                        const dataIndex = params.dataIndex;
                        const klineData = currentKlineData && currentKlineData[dataIndex];
                        if (klineData) {
                            return klineData[1] > klineData[2] ? '#f5222d' : '#52c41a';
                        }
                        return '#52c41a';
                    }
                }
            }
        ]
    };
    
    klineChart.setOption(option);
    
    window.addEventListener('resize', function() {
        klineChart.resize();
        if (radarChart) radarChart.resize();
        if (trendChart) trendChart.resize();
    });
}

function initRadarChart() {
    if (radarChart) {
        radarChart.dispose();
    }
    
    const chartDom = document.getElementById('radarChart');
    if (!chartDom) return;
    
    radarChart = echarts.init(chartDom);
    
    const option = {
        tooltip: {
            trigger: 'item',
            backgroundColor: 'rgba(255, 255, 255, 0.95)',
            borderColor: '#d9d9d9',
            borderWidth: 1,
            textStyle: {
                color: '#262626',
                fontSize: 12
            },
            padding: [10, 15]
        },
        radar: {
            indicator: [
                { name: '技术面', max: 100 },
                { name: '基本面', max: 100 },
                { name: '资金面', max: 100 },
                { name: '情绪面', max: 100 },
                { name: '消息面', max: 100 },
                { name: '趋势面', max: 100 }
            ],
            radius: '65%',
            center: ['50%', '50%'],
            splitNumber: 5,
            splitArea: {
                areaStyle: {
                    color: ['rgba(102, 126, 234, 0.05)', 'rgba(102, 126, 234, 0.1)', 'rgba(102, 126, 234, 0.15)', 'rgba(102, 126, 234, 0.2)', 'rgba(102, 126, 234, 0.25)']
                }
            },
            axisLine: {
                lineStyle: {
                    color: '#d9d9d9'
                }
            },
            splitLine: {
                lineStyle: {
                    color: '#e8e8e8'
                }
            },
            name: {
                textStyle: {
                    color: '#595959',
                    fontSize: 12
                }
            }
        },
        series: [
            {
                name: '技术指标',
                type: 'radar',
                data: [
                    {
                        value: [0, 0, 0, 0, 0, 0],
                        name: '当前指标',
                        symbol: 'circle',
                        symbolSize: 6,
                        lineStyle: {
                            width: 2,
                            color: '#667eea'
                        },
                        areaStyle: {
                            color: 'rgba(102, 126, 234, 0.3)'
                        },
                        itemStyle: {
                            color: '#667eea'
                        }
                    }
                ]
            }
        ]
    };
    
    radarChart.setOption(option);
}

function initTrendChart() {
    if (trendChart) {
        trendChart.dispose();
    }
    
    const chartDom = document.getElementById('trendChart');
    if (!chartDom) return;
    
    trendChart = echarts.init(chartDom);
    
    const option = {
        tooltip: {
            trigger: 'axis',
            axisPointer: {
                type: 'cross'
            },
            backgroundColor: 'rgba(255, 255, 255, 0.95)',
            borderColor: '#d9d9d9',
            borderWidth: 1,
            textStyle: {
                color: '#262626',
                fontSize: 12
            },
            padding: [10, 15],
            formatter: function(params) {
                let result = `<div style="font-weight:600;margin-bottom:5px;">${params[0].axisValue}</div>`;
                params.forEach(param => {
                    result += `<div style="margin:3px 0;"><span style="color:${param.color};">●</span><span style="margin-left:8px;color:#262626;">${param.seriesName}:</span><span style="margin-left:5px;color:${param.color};">${param.data.toFixed(2)}</span></div>`;
                });
                return result;
            }
        },
        legend: {
            data: ['预测价格', '当前价格'],
            top: 5,
            textStyle: {
                color: '#595959',
                fontSize: 11
            },
            itemGap: 10,
            itemWidth: 15,
            itemHeight: 10
        },
        grid: {
            left: '8%',
            right: '5%',
            top: '20%',
            bottom: '12%',
            containLabel: true
        },
        xAxis: {
            type: 'category',
            boundaryGap: false,
            data: [],
            axisLine: {
                lineStyle: {
                    color: '#d9d9d9'
                }
            },
            axisTick: {
                show: false
            },
            axisLabel: {
                color: '#8c8c8c',
                fontSize: 10
            },
            splitLine: {
                show: false
            }
        },
        yAxis: {
            type: 'value',
            axisLine: {
                show: false
            },
            axisTick: {
                show: false
            },
            axisLabel: {
                color: '#8c8c8c',
                fontSize: 10
            },
            splitLine: {
                lineStyle: {
                    color: '#f0f0f0',
                    type: 'dashed'
                }
            }
        },
        series: [
            {
                name: '预测价格',
                type: 'line',
                data: [],
                smooth: true,
                symbol: 'circle',
                symbolSize: 4,
                lineStyle: {
                    width: 2,
                    color: '#667eea'
                },
                itemStyle: {
                    color: '#667eea'
                },
                areaStyle: {
                    color: {
                        type: 'linear',
                        x: 0,
                        y: 0,
                        x2: 0,
                        y2: 1,
                        colorStops: [
                            { offset: 0, color: 'rgba(102, 126, 234, 0.3)' },
                            { offset: 1, color: 'rgba(102, 126, 234, 0.05)' }
                        ]
                    }
                }
            },
            {
                name: '当前价格',
                type: 'line',
                data: [],
                lineStyle: {
                    width: 2,
                    type: 'dashed',
                    color: '#f5222d'
                },
                itemStyle: {
                    color: '#f5222d'
                },
                symbol: 'none'
            }
        ]
    };
    
    trendChart.setOption(option);
}

function calculateMA(dayCount, data) {
    const result = [];
    for (let i = 0, len = data.length; i < len; i++) {
        if (i < dayCount) {
            result.push('-');
            continue;
        }
        let sum = 0;
        for (let j = 0; j < dayCount; j++) {
            sum += data[i - j][2];
        }
        result.push((sum / dayCount).toFixed(2));
    }
    return result;
}

function updateKlineChart(klineData) {
    if (!klineData || klineData.length === 0) {
        return;
    }
    
    currentKlineData = klineData;
    
    const dates = klineData.map(item => item[0]);
    const values = klineData.map(item => [item[1], item[2], item[3], item[4]]);
    const volumes = klineData.map(item => item[5]);
    
    const ma5 = calculateMA(5, values);
    const ma10 = calculateMA(10, values);
    const ma20 = calculateMA(20, values);
    const ma30 = calculateMA(30, values);
    
    klineChart.setOption({
        xAxis: [
            {
                data: dates
            },
            {
                data: dates
            }
        ],
        series: [
            {
                data: values
            },
            {
                data: ma5
            },
            {
                data: ma10
            },
            {
                data: ma20
            },
            {
                data: ma30
            },
            {
                data: volumes
            }
        ]
    });
}

function updateChartInfo(stockData) {
    if (!stockData) {
        return;
    }
    
    document.getElementById('chartStockName').textContent = stockData.stock_name || '--';
    document.getElementById('chartStockCode').textContent = stockData.stock_code || '--';
    document.getElementById('chartCurrentPrice').textContent = stockData.current_price || '--';
    
    const klineData = stockData.kline_data;
    if (klineData && klineData.length > 1) {
        const latest = klineData[klineData.length - 1];
        const previous = klineData[klineData.length - 2];
        
        let latestClose, previousClose, latestVolume;
        
        if (Array.isArray(latest)) {
            latestClose = latest[2];
            latestVolume = latest[5];
            previousClose = previous[2];
        } else {
            latestClose = parseFloat(latest.收盘) || 0;
            latestVolume = parseFloat(latest.成交量) || 0;
            previousClose = parseFloat(previous.收盘) || 0;
        }
        
        const change = latestClose - previousClose;
        const changePercent = previousClose > 0 ? ((change / previousClose) * 100).toFixed(2) : '0.00';
        
        const changeElement = document.getElementById('chartChange');
        const changePercentElement = document.getElementById('chartChangePercent');
        
        changeElement.textContent = change > 0 ? `+${change.toFixed(2)}` : change.toFixed(2);
        changePercentElement.textContent = change > 0 ? `+${changePercent}%` : `${changePercent}%`;
        
        if (change > 0) {
            changeElement.classList.add('rise');
            changeElement.classList.remove('fall');
            changePercentElement.classList.add('rise');
            changePercentElement.classList.remove('fall');
        } else if (change < 0) {
            changeElement.classList.add('fall');
            changeElement.classList.remove('rise');
            changePercentElement.classList.add('fall');
            changePercentElement.classList.remove('rise');
        } else {
            changeElement.classList.remove('rise', 'fall');
            changePercentElement.classList.remove('rise', 'fall');
        }
        
        const volume = latestVolume;
        const amount = volume * latestClose;
        
        document.getElementById('chartVolume').textContent = formatVolume(volume);
        document.getElementById('chartAmount').textContent = formatAmount(amount);
    }
}

function formatVolume(volume) {
    if (volume >= 100000000) {
        return (volume / 100000000).toFixed(2) + '亿';
    } else if (volume >= 10000) {
        return (volume / 10000).toFixed(2) + '万';
    }
    return volume.toFixed(0);
}

function formatAmount(amount) {
    if (amount >= 100000000) {
        return (amount / 100000000).toFixed(2) + '亿';
    } else if (amount >= 10000) {
        return (amount / 10000).toFixed(2) + '万';
    }
    return amount.toFixed(2);
}

function updateRadarChart(technical, fundamental, sentiment, risk) {
    if (!radarChart) {
        initRadarChart();
    }
    
    let techScore = 50;
    let fundScore = 50;
    let sentScore = 50;
    let riskScore = 50;
    let trendScore = 50;
    let newsScore = 50;
    
    if (technical && technical.result && technical.result.content) {
        const content = technical.result.content;
        if (content.includes('强势') || content.includes('看涨') || content.includes('买入')) {
            techScore = 80;
        } else if (content.includes('弱势') || content.includes('看跌') || content.includes('卖出')) {
            techScore = 30;
        } else if (content.includes('中性') || content.includes('震荡')) {
            techScore = 50;
        }
    }
    
    if (fundamental && fundamental.result && fundamental.result.content) {
        const content = fundamental.result.content;
        if (content.includes('优质') || content.includes('低估') || content.includes('价值')) {
            fundScore = 80;
        } else if (content.includes('高估') || content.includes('风险') || content.includes('谨慎')) {
            fundScore = 30;
        }
    }
    
    if (sentiment && sentiment.result && sentiment.result.content) {
        const content = sentiment.result.content;
        if (content.includes('积极') || content.includes('乐观') || content.includes('看好')) {
            sentScore = 80;
        } else if (content.includes('消极') || content.includes('悲观') || content.includes('担忧')) {
            sentScore = 30;
        }
    }
    
    if (risk && risk.result && risk.result.content) {
        const content = risk.result.content;
        if (content.includes('低风险') || content.includes('安全') || content.includes('可控')) {
            riskScore = 80;
        } else if (content.includes('高风险') || content.includes('警惕') || content.includes('危险')) {
            riskScore = 30;
        }
    }
    
    const avgScore = (techScore + fundScore + sentScore + riskScore) / 4;
    trendScore = avgScore;
    newsScore = avgScore;
    
    radarChart.setOption({
        series: [
            {
                data: [
                    {
                        value: [techScore, fundScore, avgScore, sentScore, newsScore, trendScore]
                    }
                ]
            }
        ]
    });
}

function updateTrendChart(klineData) {
    if (!trendChart) {
        initTrendChart();
    }
    
    if (!klineData || klineData.length < 10) {
        return;
    }
    
    const recentData = klineData.slice(-20);
    const dates = recentData.map(item => item[0]);
    const closePrices = recentData.map(item => item[2]);
    const currentPrice = closePrices[closePrices.length - 1];
    
    const predictedPrices = [...closePrices];
    const lastPrice = currentPrice;
    const trend = closePrices[closePrices.length - 1] - closePrices[closePrices.length - 5];
    
    for (let i = 0; i < 5; i++) {
        const prediction = lastPrice + (trend / 5) * (i + 1) * (Math.random() * 0.2 + 0.9);
        predictedPrices.push(prediction);
        dates.push(`预测${i + 1}天`);
    }
    
    const currentPriceLine = new Array(dates.length).fill(currentPrice);
    
    trendChart.setOption({
        xAxis: {
            data: dates
        },
        series: [
            {
                data: predictedPrices
            },
            {
                data: currentPriceLine
            }
        ]
    });
}

function updateFinalSummary(result) {
    const analyses = result.analyses;
    
    let score = '--';
    let risk = '--';
    let riskDesc = '--';
    let position = '--';
    let positionDesc = '--';
    let target = '--';
    let targetDesc = '--';
    let recommendation = '分析中';
    let recommendationIcon = '🎯';
    
    if (analyses && analyses.investment_strategist && analyses.investment_strategist.result && analyses.investment_strategist.result.content) {
        const content = analyses.investment_strategist.result.content;
        
        const scoreMatch = content.match(/综合评分[：:]\s*(\d+)/);
        if (scoreMatch) {
            score = scoreMatch[1];
        } else {
            score = '75';
        }
        
        const riskMatch = content.match(/风险等级[：:]\s*([低中高]+(?:风险)?)/);
        if (riskMatch) {
            risk = riskMatch[1];
            if (risk.includes('低')) {
                riskDesc = '风险可控';
            } else if (risk.includes('高')) {
                riskDesc = '需谨慎';
            } else {
                riskDesc = '中等风险';
            }
        } else {
            risk = '中';
            riskDesc = '中等风险';
        }
        
        const positionMatch = content.match(/建议仓位[：:]\s*(\d+%)/);
        if (positionMatch) {
            position = positionMatch[1];
            const posNum = parseInt(position);
            if (posNum >= 70) {
                positionDesc = '积极布局';
            } else if (posNum >= 40) {
                positionDesc = '适度参与';
            } else {
                positionDesc = '轻仓观望';
            }
        } else {
            position = '50%';
            positionDesc = '适度参与';
        }
        
        const targetMatch = content.match(/目标价位[：:]\s*([\d.]+)/);
        if (targetMatch) {
            target = targetMatch[1];
            const currentPrice = result.stock_data && result.stock_data.current_price ? result.stock_data.current_price : 0;
            if (currentPrice > 0) {
                const potential = ((parseFloat(target) - currentPrice) / currentPrice * 100).toFixed(1);
                targetDesc = `潜在涨幅 ${potential}%`;
            } else {
                targetDesc = '参考目标';
            }
        } else {
            target = '--';
            targetDesc = '待评估';
        }
        
        const buyKeywords = ['强烈买入', '买入', '推荐', '积极', '看好'];
        const sellKeywords = ['强烈卖出', '卖出', '回避', '清仓', '减仓'];
        const holdKeywords = ['持有', '观望', '保持', '维持'];
        
        let hasBuy = false;
        let hasSell = false;
        let hasHold = false;
        
        for (const keyword of buyKeywords) {
            if (content.includes(keyword)) {
                hasBuy = true;
                break;
            }
        }
        
        for (const keyword of sellKeywords) {
            if (content.includes(keyword)) {
                hasSell = true;
                break;
            }
        }
        
        for (const keyword of holdKeywords) {
            if (content.includes(keyword)) {
                hasHold = true;
                break;
            }
        }
        
        if (hasBuy && !hasSell) {
            recommendation = '买入';
            recommendationIcon = '📈';
        } else if (hasSell && !hasBuy) {
            recommendation = '卖出';
            recommendationIcon = '📉';
        } else if (hasHold) {
            recommendation = '持有';
            recommendationIcon = '⏸️';
        } else {
            recommendation = '观望';
            recommendationIcon = '👀';
        }
    }
    
    document.getElementById('scoreValue').textContent = score;
    const scoreTrend = document.getElementById('scoreTrend');
    if (score !== '--') {
        const scoreNum = parseInt(score);
        if (scoreNum >= 80) {
            scoreTrend.textContent = '优秀';
            scoreTrend.style.color = '#52c41a';
        } else if (scoreNum >= 60) {
            scoreTrend.textContent = '良好';
            scoreTrend.style.color = '#1890ff';
        } else {
            scoreTrend.textContent = '一般';
            scoreTrend.style.color = '#faad14';
        }
    } else {
        scoreTrend.textContent = '--';
    }
    
    document.getElementById('riskValue').textContent = risk;
    document.getElementById('riskDesc').textContent = riskDesc;
    
    document.getElementById('positionValue').textContent = position;
    document.getElementById('positionDesc').textContent = positionDesc;
    
    document.getElementById('targetValue').textContent = target;
    document.getElementById('targetDesc').textContent = targetDesc;
    
    const badgeText = document.querySelector('.recommendation-text');
    const badgeIcon = document.querySelector('.recommendation-icon');
    const badge = document.querySelector('.recommendation-badge');
    
    if (badgeText) badgeText.textContent = recommendation;
    if (badgeIcon) badgeIcon.textContent = recommendationIcon;
    
    if (recommendation === '买入') {
        badge.style.background = 'linear-gradient(135deg, #52c41a 0%, #73d13d 100%)';
    } else if (recommendation === '卖出') {
        badge.style.background = 'linear-gradient(135deg, #ff4d4f 0%, #ff7875 100%)';
    } else if (recommendation === '持有') {
        badge.style.background = 'linear-gradient(135deg, #faad14 0%, #ffc53d 100%)';
    } else {
        badge.style.background = 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)';
    }
    
    updateKeyPoints(analyses);
}

function updateKeyPoints(analyses) {
    const keyPointsList = document.getElementById('keyPointsList');
    if (!keyPointsList) return;
    
    const keyPoints = [];
    
    if (analyses && analyses.technical_analyst && analyses.technical_analyst.result && analyses.technical_analyst.result.content) {
        const content = analyses.technical_analyst.result.content;
        if (content.includes('突破')) keyPoints.push('技术面突破关键位');
        if (content.includes('支撑')) keyPoints.push('下方支撑较强');
        if (content.includes('压力')) keyPoints.push('上方存在压力');
        if (content.includes('趋势向上')) keyPoints.push('趋势向上');
        if (content.includes('趋势向下')) keyPoints.push('趋势向下');
    }
    
    if (analyses && analyses.fundamental_analyst && analyses.fundamental_analyst.result && analyses.fundamental_analyst.result.content) {
        const content = analyses.fundamental_analyst.result.content;
        if (content.includes('低估')) keyPoints.push('估值处于低位');
        if (content.includes('高估')) keyPoints.push('估值偏高');
        if (content.includes('盈利')) keyPoints.push('盈利能力良好');
        if (content.includes('成长')) keyPoints.push('成长性较好');
    }
    
    if (analyses && analyses.risk_manager && analyses.risk_manager.result && analyses.risk_manager.result.content) {
        const content = analyses.risk_manager.result.content;
        if (content.includes('低风险')) keyPoints.push('风险可控');
        if (content.includes('高风险')) keyPoints.push('需注意风险');
        if (content.includes('波动')) keyPoints.push('波动较大');
    }
    
    if (analyses && analyses.sentiment_analyst && analyses.sentiment_analyst.result && analyses.sentiment_analyst.result.content) {
        const content = analyses.sentiment_analyst.result.content;
        if (content.includes('积极') || content.includes('乐观')) keyPoints.push('市场情绪积极');
        if (content.includes('消极') || content.includes('悲观')) keyPoints.push('市场情绪谨慎');
    }
    
    if (keyPoints.length === 0) {
        keyPoints.push('分析完成，请查看详细报告');
    }
    
    keyPointsList.innerHTML = keyPoints.slice(0, 6).map(point => `
        <li>
            <span class="key-point-icon">✓</span>
            <span class="key-point-text">${point}</span>
        </li>
    `).join('');
}

function showChartSection() {
    document.getElementById('chartSection').style.display = 'block';
}

function hideChartSection() {
    document.getElementById('chartSection').style.display = 'none';
}

function scrollToResults() {
    const chartSection = document.getElementById('chartSection');
    const agentsGrid = document.getElementById('agentsGrid');
    
    if (chartSection && chartSection.style.display !== 'none') {
        chartSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } else if (agentsGrid) {
        agentsGrid.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

document.addEventListener('DOMContentLoaded', function() {
    const periodButtons = document.querySelectorAll('.chart-period-btn');
    periodButtons.forEach(button => {
        button.addEventListener('click', async function() {
            periodButtons.forEach(btn => btn.classList.remove('active'));
            this.classList.add('active');
            
            const period = this.getAttribute('data-period');
            console.log('切换K线周期:', period);
            
            if (currentAnalysis && currentAnalysis.stock_code) {
                await fetchKlineData(currentAnalysis.stock_code, period);
            }
        });
    });
    
    const chartTabButtons = document.querySelectorAll('.chart-tab-btn');
    chartTabButtons.forEach(button => {
        button.addEventListener('click', function() {
            chartTabButtons.forEach(btn => btn.classList.remove('active'));
            this.classList.add('active');
            
            const tab = this.getAttribute('data-tab');
            document.querySelectorAll('.chart-panel').forEach(panel => {
                panel.classList.remove('active');
            });
            document.getElementById(tab + 'Panel').classList.add('active');
        });
    });
    
    const runBacktestBtn = document.getElementById('runBacktestBtn');
    if (runBacktestBtn) {
        runBacktestBtn.addEventListener('click', runBacktest);
    }
    
    const downloadReportBtn = document.getElementById('downloadReportBtn');
    if (downloadReportBtn) {
        downloadReportBtn.addEventListener('click', downloadBacktestReport);
    }
    
    const tradesFilter = document.getElementById('tradesFilter');
    if (tradesFilter) {
        tradesFilter.addEventListener('change', filterTradesTable);
    }
});

let equityCurveChart = null;
let drawdownChart = null;
let tradeDistributionChart = null;
let metricsRadarChart = null;

let comparisonStocks = [];
let priceComparisonChart = null;
let performanceComparisonChart = null;
let metricsComparisonChart = null;
let currentBacktestResult = null;

async function runBacktest() {
    if (!currentAnalysis) {
        alert('请先进行股票分析');
        return;
    }
    
    const stockCode = document.getElementById('stockCode').value;
    if (!stockCode) {
        alert('请输入股票代码');
        return;
    }
    
    const runBacktestBtn = document.getElementById('runBacktestBtn');
    runBacktestBtn.disabled = true;
    runBacktestBtn.textContent = '运行中...';
    
    try {
        const response = await fetch('/api/backtest', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                stock_code: stockCode,
                session_id: socket.id
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            currentBacktestResult = result.data;
            displayBacktestResults(result.data);
            showBacktestSection();
        } else {
            alert('回测失败: ' + result.message);
        }
    } catch (error) {
        console.error('回测错误:', error);
        alert('回测失败，请稍后重试');
    } finally {
        runBacktestBtn.disabled = false;
        runBacktestBtn.textContent = '运行回测';
    }
}

function showBacktestSection() {
    document.getElementById('backtestSection').style.display = 'block';
    document.getElementById('backtestSection').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function displayBacktestResults(backtestResult) {
    updateBacktestSummaryCards(backtestResult);
    initBacktestCharts(backtestResult);
    populateTradesTable(backtestResult);
}

function updateBacktestSummaryCards(backtestResult) {
    const metrics = backtestResult.metrics || {};
    
    const totalReturn = metrics.total_return || 0;
    document.getElementById('totalReturn').textContent = totalReturn.toFixed(2) + '%';
    
    const totalReturnChange = document.getElementById('totalReturnChange');
    if (totalReturn >= 0) {
        totalReturnChange.textContent = '+' + totalReturn.toFixed(2) + '%';
        totalReturnChange.className = 'backtest-card-change positive';
    } else {
        totalReturnChange.textContent = totalReturn.toFixed(2) + '%';
        totalReturnChange.className = 'backtest-card-change negative';
    }
    
    document.getElementById('annualReturn').textContent = (metrics.annual_return || 0).toFixed(2) + '%';
    document.getElementById('maxDrawdown').textContent = (metrics.max_drawdown || 0).toFixed(2) + '%';
    document.getElementById('sharpeRatio').textContent = (metrics.sharpe_ratio || 0).toFixed(2);
    document.getElementById('winRate').textContent = (metrics.trade_win_rate || 0).toFixed(1) + '%';
    document.getElementById('profitLossRatio').textContent = (metrics.profit_loss_ratio || 0).toFixed(2);
}

function initBacktestCharts(backtestResult) {
    initEquityCurveChart(backtestResult);
    initDrawdownChart(backtestResult);
    initTradeDistributionChart(backtestResult);
    initMetricsRadarChart(backtestResult);
}

function initEquityCurveChart(backtestResult) {
    if (equityCurveChart) {
        equityCurveChart.dispose();
    }
    
    const chartDom = document.getElementById('equityCurveChart');
    if (!chartDom) return;
    
    equityCurveChart = echarts.init(chartDom);
    
    const equityCurve = backtestResult.equity_curve || [];
    const metrics = backtestResult.metrics || {};
    
    const dates = equityCurve.map(e => e.date);
    const equityValues = equityCurve.map(e => e.equity);
    const prices = equityCurve.map(e => e.price);
    const initialCapital = metrics.initial_capital || 100000;
    
    const option = {
        tooltip: {
            trigger: 'axis',
            axisPointer: {
                type: 'cross'
            },
            backgroundColor: 'rgba(255, 255, 255, 0.95)',
            borderColor: '#d9d9d9',
            borderWidth: 1,
            textStyle: {
                color: '#262626',
                fontSize: 12
            },
            padding: [10, 15],
            formatter: function(params) {
                let result = `<div style="font-weight:600;margin-bottom:5px;">${params[0].axisValue}</div>`;
                params.forEach(param => {
                    result += `<div style="margin:3px 0;"><span style="color:${param.color};">●</span><span style="margin-left:8px;color:#262626;">${param.seriesName}:</span><span style="margin-left:5px;color:${param.color};">¥${param.value.toLocaleString()}</span></div>`;
                });
                return result;
            }
        },
        legend: {
            data: ['资金曲线', '基准线', '股价'],
            top: 10,
            textStyle: {
                color: '#666',
                fontSize: 12
            }
        },
        grid: {
            left: '3%',
            right: '4%',
            bottom: '3%',
            containLabel: true
        },
        xAxis: {
            type: 'category',
            data: dates,
            boundaryGap: false,
            axisLine: {
                lineStyle: {
                    color: '#d9d9d9'
                }
            },
            axisTick: {
                show: false
            },
            axisLabel: {
                color: '#8c8c8c',
                fontSize: 10,
                rotate: 45
            },
            splitLine: {
                show: false
            }
        },
        yAxis: [
            {
                type: 'value',
                name: '资金',
                position: 'left',
                axisLine: {
                    show: false
                },
                axisTick: {
                    show: false
                },
                axisLabel: {
                    color: '#8c8c8c',
                    fontSize: 10,
                    formatter: '¥{value}'
                },
                splitLine: {
                    lineStyle: {
                        color: '#f0f0f0',
                        type: 'dashed'
                    }
                }
            },
            {
                type: 'value',
                name: '股价',
                position: 'right',
                axisLine: {
                    show: false
                },
                axisTick: {
                    show: false
                },
                axisLabel: {
                    color: '#8c8c8c',
                    fontSize: 10,
                    formatter: '¥{value}'
                },
                splitLine: {
                    show: false
                }
            }
        ],
        series: [
            {
                name: '资金曲线',
                type: 'line',
                data: equityValues,
                smooth: true,
                lineStyle: {
                    width: 2,
                    color: '#3498db'
                },
                areaStyle: {
                    color: {
                        type: 'linear',
                        x: 0,
                        y: 0,
                        x2: 0,
                        y2: 1,
                        colorStops: [
                            { offset: 0, color: 'rgba(52, 152, 219, 0.3)' },
                            { offset: 1, color: 'rgba(52, 152, 219, 0.05)' }
                        ]
                    }
                }
            },
            {
                name: '基准线',
                type: 'line',
                data: Array(dates.length).fill(initialCapital),
                lineStyle: {
                    type: 'dashed',
                    color: '#95a5a6'
                },
                symbol: 'none'
            },
            {
                name: '股价',
                type: 'line',
                yAxisIndex: 1,
                data: prices,
                lineStyle: {
                    width: 1,
                    color: '#e74c3c',
                    opacity: 0.5
                },
                symbol: 'none'
            }
        ]
    };
    
    equityCurveChart.setOption(option);
}

function initDrawdownChart(backtestResult) {
    if (drawdownChart) {
        drawdownChart.dispose();
    }
    
    const chartDom = document.getElementById('drawdownChart');
    if (!chartDom) return;
    
    drawdownChart = echarts.init(chartDom);
    
    const equityCurve = backtestResult.equity_curve || [];
    
    if (equityCurve.length === 0) return;
    
    const dates = equityCurve.map(e => e.date);
    const equityValues = equityCurve.map(e => e.equity);
    
    let maxEquity = equityValues[0];
    const drawdowns = equityValues.map((equity, idx) => {
        if (equity > maxEquity) {
            maxEquity = equity;
        }
        return ((equity - maxEquity) / maxEquity * 100);
    });
    
    const avgDrawdown = drawdowns.reduce((a, b) => a + b, 0) / drawdowns.length;
    document.getElementById('avgDrawdown').textContent = avgDrawdown.toFixed(2) + '%';
    
    const drawdownCount = drawdowns.filter(d => d < -1).length;
    document.getElementById('drawdownCount').textContent = drawdownCount;
    
    const option = {
        tooltip: {
            trigger: 'axis',
            backgroundColor: 'rgba(255, 255, 255, 0.95)',
            borderColor: '#d9d9d9',
            borderWidth: 1,
            textStyle: {
                color: '#262626',
                fontSize: 12
            },
            padding: [10, 15],
            formatter: function(params) {
                return `<div style="font-weight:600;margin-bottom:5px;">${params[0].axisValue}</div>` +
                       `<div style="margin:3px 0;"><span style="color:${params[0].color};">●</span><span style="margin-left:8px;color:#262626;">回撤:</span><span style="margin-left:5px;color:${params[0].color};">${params[0].value.toFixed(2)}%</span></div>`;
            }
        },
        grid: {
            left: '3%',
            right: '4%',
            bottom: '3%',
            containLabel: true
        },
        xAxis: {
            type: 'category',
            data: dates,
            boundaryGap: false,
            axisLine: {
                lineStyle: {
                    color: '#d9d9d9'
                }
            },
            axisTick: {
                show: false
            },
            axisLabel: {
                color: '#8c8c8c',
                fontSize: 10,
                rotate: 45
            },
            splitLine: {
                show: false
            }
        },
        yAxis: {
            type: 'value',
            name: '回撤(%)',
            axisLine: {
                show: false
            },
            axisTick: {
                show: false
            },
            axisLabel: {
                color: '#8c8c8c',
                fontSize: 10,
                formatter: '{value}%'
            },
            splitLine: {
                lineStyle: {
                    color: '#f0f0f0',
                    type: 'dashed'
                }
            }
        },
        series: [
            {
                name: '回撤',
                type: 'line',
                data: drawdowns,
                smooth: true,
                lineStyle: {
                    width: 2,
                    color: '#e74c3c'
                },
                areaStyle: {
                    color: {
                        type: 'linear',
                        x: 0,
                        y: 0,
                        x2: 0,
                        y2: 1,
                        colorStops: [
                            { offset: 0, color: 'rgba(231, 76, 60, 0.3)' },
                            { offset: 1, color: 'rgba(231, 76, 60, 0.05)' }
                        ]
                    }
                },
                markLine: {
                    data: [
                        { type: 'average', name: '平均回撤' }
                    ],
                    lineStyle: {
                        color: '#f39c12',
                        type: 'dashed'
                    },
                    label: {
                        formatter: '平均: {c}%'
                    }
                }
            }
        ]
    };
    
    drawdownChart.setOption(option);
}

function initTradeDistributionChart(backtestResult) {
    if (tradeDistributionChart) {
        tradeDistributionChart.dispose();
    }
    
    const chartDom = document.getElementById('tradeDistributionChart');
    if (!chartDom) return;
    
    tradeDistributionChart = echarts.init(chartDom);
    
    const metrics = backtestResult.metrics || {};
    const completedTrades = metrics.completed_trades || [];
    
    if (completedTrades.length === 0) return;
    
    const tradeReturns = completedTrades.map(t => t.profit_pct || 0);
    const tradeDates = completedTrades.map(t => t.buy_date);
    
    const winTrades = tradeReturns.filter(r => r > 0).length;
    const lossTrades = tradeReturns.filter(r => r <= 0).length;
    
    document.getElementById('winTrades').textContent = winTrades;
    document.getElementById('lossTrades').textContent = lossTrades;
    
    const colors = tradeReturns.map(r => r >= 0 ? '#52c41a' : '#f5222d');
    
    const option = {
        tooltip: {
            trigger: 'axis',
            backgroundColor: 'rgba(255, 255, 255, 0.95)',
            borderColor: '#d9d9d9',
            borderWidth: 1,
            textStyle: {
                color: '#262626',
                fontSize: 12
            },
            padding: [10, 15],
            formatter: function(params) {
                return `<div style="font-weight:600;margin-bottom:5px;">${params[0].axisValue}</div>` +
                       `<div style="margin:3px 0;"><span style="color:${params[0].color};">●</span><span style="margin-left:8px;color:#262626;">收益率:</span><span style="margin-left:5px;color:${params[0].color};">${params[0].value.toFixed(2)}%</span></div>`;
            }
        },
        grid: {
            left: '3%',
            right: '4%',
            bottom: '3%',
            containLabel: true
        },
        xAxis: {
            type: 'category',
            data: tradeDates,
            axisLine: {
                lineStyle: {
                    color: '#d9d9d9'
                }
            },
            axisTick: {
                show: false
            },
            axisLabel: {
                color: '#8c8c8c',
                fontSize: 10,
                rotate: 45
            },
            splitLine: {
                show: false
            }
        },
        yAxis: {
            type: 'value',
            name: '收益率(%)',
            axisLine: {
                show: false
            },
            axisTick: {
                show: false
            },
            axisLabel: {
                color: '#8c8c8c',
                fontSize: 10,
                formatter: '{value}%'
            },
            splitLine: {
                lineStyle: {
                    color: '#f0f0f0',
                    type: 'dashed'
                }
            }
        },
        series: [
            {
                name: '收益率',
                type: 'bar',
                data: tradeReturns.map((r, idx) => ({
                    value: r,
                    itemStyle: { color: colors[idx] }
                })),
                barWidth: '60%',
                markLine: {
                    data: [
                        { yAxis: 0, name: '盈亏平衡线' }
                    ],
                    lineStyle: {
                        color: '#666',
                        type: 'solid'
                    },
                    label: {
                        show: false
                    }
                }
            }
        ]
    };
    
    tradeDistributionChart.setOption(option);
}

function initMetricsRadarChart(backtestResult) {
    if (metricsRadarChart) {
        metricsRadarChart.dispose();
    }
    
    const chartDom = document.getElementById('metricsRadarChart');
    if (!chartDom) return;
    
    metricsRadarChart = echarts.init(chartDom);
    
    const metrics = backtestResult.metrics || {};
    
    const totalReturn = Math.abs(metrics.total_return || 0);
    const winRate = metrics.trade_win_rate || 0;
    const sharpeRatio = Math.max(0, metrics.sharpe_ratio || 0);
    const profitLossRatio = metrics.profit_loss_ratio || 0;
    
    const score = (totalReturn * 0.3 + winRate * 0.3 + Math.min(sharpeRatio, 3) / 3 * 100 * 0.2 + Math.min(profitLossRatio, 5) / 5 * 100 * 0.2);
    document.getElementById('backtestScore').textContent = score.toFixed(1);
    
    document.getElementById('totalTrades').textContent = metrics.total_trades || 0;
    
    const option = {
        tooltip: {
            backgroundColor: 'rgba(255, 255, 255, 0.95)',
            borderColor: '#d9d9d9',
            borderWidth: 1,
            textStyle: {
                color: '#262626',
                fontSize: 12
            },
            padding: [10, 15]
        },
        radar: {
            indicator: [
                { name: '总收益率', max: 100 },
                { name: '胜率', max: 100 },
                { name: '夏普比率', max: 3 },
                { name: '盈亏比', max: 5 },
                { name: '交易胜率', max: 100 }
            ],
            shape: 'polygon',
            splitNumber: 5,
            name: {
                textStyle: {
                    color: '#666',
                    fontSize: 11
                }
            },
            splitLine: {
                lineStyle: {
                    color: ['#eee', '#ddd', '#ccc']
                }
            },
            splitArea: {
                show: true,
                areaStyle: {
                    color: ['rgba(114, 172, 209, 0.1)', 'rgba(114, 172, 209, 0.05)']
                }
            },
            axisLine: {
                lineStyle: {
                    color: '#d9d9d9'
                }
            }
        },
        series: [
            {
                name: '回测指标',
                type: 'radar',
                data: [
                    {
                        value: [
                            totalReturn,
                            winRate,
                            sharpeRatio,
                            profitLossRatio,
                            winRate
                        ],
                        name: '当前策略',
                        areaStyle: {
                            color: 'rgba(52, 152, 219, 0.3)'
                        },
                        lineStyle: {
                            width: 2,
                            color: '#3498db'
                        },
                        itemStyle: {
                            color: '#3498db'
                        }
                    }
                ]
            }
        ]
    };
    
    metricsRadarChart.setOption(option);
}

function populateTradesTable(backtestResult) {
    const metrics = backtestResult.metrics || {};
    const completedTrades = metrics.completed_trades || [];
    
    const tbody = document.getElementById('tradesTableBody');
    tbody.innerHTML = '';
    
    if (completedTrades.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;color:#999;">暂无交易记录</td></tr>';
        return;
    }
    
    completedTrades.forEach((trade, index) => {
        const row = document.createElement('tr');
        row.dataset.profit = trade.profit_pct >= 0 ? 'profit' : 'loss';
        
        const profitClass = trade.profit_pct >= 0 ? 'trade-profit' : 'trade-loss';
        const profitSign = trade.profit_pct >= 0 ? '+' : '';
        
        row.innerHTML = `
            <td>${index + 1}</td>
            <td>${trade.buy_date}</td>
            <td>${trade.sell_date}</td>
            <td>¥${trade.buy_price.toFixed(2)}</td>
            <td>¥${trade.sell_price.toFixed(2)}</td>
            <td>${trade.holding_days}天</td>
            <td class="${profitClass}">${profitSign}${trade.profit_pct.toFixed(2)}%</td>
            <td class="${profitClass}">${profitSign}¥${trade.profit.toFixed(2)}</td>
        `;
        
        tbody.appendChild(row);
    });
}

function filterTradesTable() {
    const filter = document.getElementById('tradesFilter').value;
    const tbody = document.getElementById('tradesTableBody');
    const rows = tbody.querySelectorAll('tr');
    
    rows.forEach(row => {
        if (filter === 'all') {
            row.style.display = '';
        } else if (filter === 'profit') {
            row.style.display = row.dataset.profit === 'profit' ? '' : 'none';
        } else if (filter === 'loss') {
            row.style.display = row.dataset.profit === 'loss' ? '' : 'none';
        }
    });
}

function downloadBacktestReport() {
    if (!currentBacktestResult) {
        alert('请先运行回测');
        return;
    }
    
    const metrics = currentBacktestResult.metrics || {};
    const completedTrades = metrics.completed_trades || [];
    
    let report = '回测结果报告\n';
    report += '='.repeat(50) + '\n\n';
    report += '关键指标:\n';
    report += '-'.repeat(30) + '\n';
    report += `总收益率: ${metrics.total_return.toFixed(2)}%\n`;
    report += `年化收益率: ${metrics.annual_return.toFixed(2)}%\n`;
    report += `最大回撤: ${metrics.max_drawdown.toFixed(2)}%\n`;
    report += `夏普比率: ${metrics.sharpe_ratio.toFixed(2)}\n`;
    report += `胜率: ${metrics.trade_win_rate.toFixed(1)}%\n`;
    report += `盈亏比: ${metrics.profit_loss_ratio.toFixed(2)}\n`;
    report += `交易次数: ${metrics.total_trades}\n\n`;
    
    report += '交易明细:\n';
    report += '-'.repeat(30) + '\n';
    completedTrades.forEach((trade, index) => {
        report += `交易 ${index + 1}:\n`;
        report += `  买入日期: ${trade.buy_date}\n`;
        report += `  卖出日期: ${trade.sell_date}\n`;
        report += `  买入价格: ¥${trade.buy_price.toFixed(2)}\n`;
        report += `  卖出价格: ¥${trade.sell_price.toFixed(2)}\n`;
        report += `  持仓天数: ${trade.holding_days}天\n`;
        report += `  收益率: ${trade.profit_pct.toFixed(2)}%\n`;
        report += `  盈亏: ¥${trade.profit.toFixed(2)}\n\n`;
    });
    
    const blob = new Blob([report], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `backtest_report_${new Date().toISOString().split('T')[0]}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

function showComparisonSection() {
    document.getElementById('comparisonSection').style.display = 'block';
    document.getElementById('comparisonSection').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

async function addComparisonStock() {
    const stockCode = document.getElementById('comparisonStockCode').value.trim();
    if (!stockCode) {
        alert('请输入股票代码');
        return;
    }
    
    if (comparisonStocks.some(s => s.code === stockCode)) {
        alert('该股票已在对比列表中');
        return;
    }
    
    try {
        const response = await fetch('/api/stock_data', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                stock_code: stockCode,
                session_id: socket.id
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            const stockData = result.data;
            comparisonStocks.push({
                code: stockCode,
                name: stockData.name || stockCode,
                data: stockData.kline_data || [],
                metrics: calculateStockMetrics(stockData.kline_data || [])
            });
            
            updateComparisonStockList();
            updateComparisonCharts();
            
            document.getElementById('comparisonStockCode').value = '';
            document.getElementById('comparisonInputArea').style.display = 'none';
            
            if (comparisonStocks.length > 0) {
                document.getElementById('comparisonChartsContainer').style.display = 'block';
            }
        } else {
            alert('获取股票数据失败: ' + result.message);
        }
    } catch (error) {
        console.error('添加对比股票错误:', error);
        alert('获取股票数据失败，请稍后重试');
    }
}

function calculateStockMetrics(klineData) {
    if (!klineData || klineData.length === 0) {
        return {};
    }
    
    const firstPrice = klineData[0].close;
    const lastPrice = klineData[klineData.length - 1].close;
    const returnRate = ((lastPrice - firstPrice) / firstPrice) * 100;
    
    const volumes = klineData.map(d => d.volume);
    const avgVolume = volumes.reduce((a, b) => a + b, 0) / volumes.length;
    
    const highs = klineData.map(d => d.high);
    const lows = klineData.map(d => d.low);
    const maxPrice = Math.max(...highs);
    const minPrice = Math.min(...lows);
    const volatility = ((maxPrice - minPrice) / minPrice) * 100;
    
    let maxDrawdown = 0;
    let peak = firstPrice;
    for (const data of klineData) {
        if (data.close > peak) {
            peak = data.close;
        }
        const drawdown = ((peak - data.close) / peak) * 100;
        if (drawdown > maxDrawdown) {
            maxDrawdown = drawdown;
        }
    }
    
    return {
        returnRate: returnRate,
        avgVolume: avgVolume,
        volatility: volatility,
        maxDrawdown: maxDrawdown,
        firstPrice: firstPrice,
        lastPrice: lastPrice,
        maxPrice: maxPrice,
        minPrice: minPrice
    };
}

function updateComparisonStockList() {
    const listContainer = document.getElementById('comparisonStockList');
    
    if (comparisonStocks.length === 0) {
        listContainer.innerHTML = '<p class="no-comparison">暂无对比股票，点击"添加对比股票"开始比较</p>';
        return;
    }
    
    listContainer.innerHTML = comparisonStocks.map((stock, index) => `
        <div class="comparison-stock-card" data-index="${index}">
            <button class="remove-btn" onclick="removeComparisonStock(${index})">×</button>
            <div class="stock-header">
                <div class="stock-icon">${stock.name.substring(0, 2)}</div>
                <div class="stock-info">
                    <h4>${stock.name}</h4>
                    <p>${stock.code}</p>
                </div>
            </div>
            <div class="stock-metrics">
                <div class="metric-item">
                    <div class="metric-label">收益率</div>
                    <div class="metric-value ${stock.metrics.returnRate >= 0 ? 'positive' : 'negative'}">${stock.metrics.returnRate.toFixed(2)}%</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">波动率</div>
                    <div class="metric-value">${stock.metrics.volatility.toFixed(2)}%</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">最大回撤</div>
                    <div class="metric-value ${stock.metrics.maxDrawdown >= 0 ? 'negative' : 'positive'}">${stock.metrics.maxDrawdown.toFixed(2)}%</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">平均成交量</div>
                    <div class="metric-value">${(stock.metrics.avgVolume / 10000).toFixed(0)}万</div>
                </div>
            </div>
        </div>
    `).join('');
}

function removeComparisonStock(index) {
    comparisonStocks.splice(index, 1);
    updateComparisonStockList();
    updateComparisonCharts();
    
    if (comparisonStocks.length === 0) {
        document.getElementById('comparisonChartsContainer').style.display = 'none';
    }
}

function clearComparison() {
    comparisonStocks = [];
    updateComparisonStockList();
    document.getElementById('comparisonChartsContainer').style.display = 'none';
    
    if (priceComparisonChart) {
        priceComparisonChart.dispose();
        priceComparisonChart = null;
    }
    if (performanceComparisonChart) {
        performanceComparisonChart.dispose();
        performanceComparisonChart = null;
    }
    if (metricsComparisonChart) {
        metricsComparisonChart.dispose();
        metricsComparisonChart = null;
    }
}

function updateComparisonCharts() {
    if (comparisonStocks.length === 0) {
        return;
    }
    
    initPriceComparisonChart();
    initPerformanceComparisonChart();
    initMetricsComparisonChart();
    updateComparisonStats();
}

function initPriceComparisonChart() {
    if (priceComparisonChart) {
        priceComparisonChart.dispose();
    }
    
    const chartDom = document.getElementById('priceComparisonChart');
    if (!chartDom) return;
    
    priceComparisonChart = echarts.init(chartDom);
    
    const dates = comparisonStocks[0].data.map(d => d.date);
    
    const series = comparisonStocks.map(stock => ({
        name: stock.name,
        type: 'line',
        data: stock.data.map(d => d.close),
        smooth: true,
        lineStyle: {
            width: 2
        },
        symbol: 'none'
    }));
    
    const colors = ['#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de', '#3ba272', '#fc8452', '#9a60b4'];
    
    const option = {
        tooltip: {
            trigger: 'axis',
            axisPointer: {
                type: 'cross'
            },
            backgroundColor: 'rgba(255, 255, 255, 0.95)',
            borderColor: '#d9d9d9',
            borderWidth: 1,
            textStyle: {
                color: '#262626',
                fontSize: 12
            },
            padding: [10, 15]
        },
        legend: {
            data: comparisonStocks.map(s => s.name),
            top: 10,
            textStyle: {
                color: '#666',
                fontSize: 12
            }
        },
        grid: {
            left: '3%',
            right: '4%',
            bottom: '3%',
            containLabel: true
        },
        xAxis: {
            type: 'category',
            data: dates,
            boundaryGap: false,
            axisLine: {
                lineStyle: {
                    color: '#d9d9d9'
                }
            },
            axisTick: {
                show: false
            },
            axisLabel: {
                color: '#8c8c8c',
                fontSize: 10,
                rotate: 45
            },
            splitLine: {
                show: false
            }
        },
        yAxis: {
            type: 'value',
            axisLine: {
                show: false
            },
            axisTick: {
                show: false
            },
            axisLabel: {
                color: '#8c8c8c',
                fontSize: 10,
                formatter: '¥{value}'
            },
            splitLine: {
                lineStyle: {
                    color: '#f0f0f0',
                    type: 'dashed'
                }
            }
        },
        series: series,
        color: colors
    };
    
    priceComparisonChart.setOption(option);
}

function initPerformanceComparisonChart() {
    if (performanceComparisonChart) {
        performanceComparisonChart.dispose();
    }
    
    const chartDom = document.getElementById('performanceComparisonChart');
    if (!chartDom) return;
    
    performanceComparisonChart = echarts.init(chartDom);
    
    const dates = comparisonStocks[0].data.map(d => d.date);
    
    const series = comparisonStocks.map(stock => {
        const basePrice = stock.data[0].close;
        return {
            name: stock.name,
            type: 'line',
            data: stock.data.map(d => ((d.close - basePrice) / basePrice * 100)),
            smooth: true,
            lineStyle: {
                width: 2
            },
            symbol: 'none'
        };
    });
    
    const colors = ['#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de', '#3ba272', '#fc8452', '#9a60b4'];
    
    const option = {
        tooltip: {
            trigger: 'axis',
            axisPointer: {
                type: 'cross'
            },
            backgroundColor: 'rgba(255, 255, 255, 0.95)',
            borderColor: '#d9d9d9',
            borderWidth: 1,
            textStyle: {
                color: '#262626',
                fontSize: 12
            },
            padding: [10, 15],
            formatter: function(params) {
                let result = `<div style="font-weight:600;margin-bottom:5px;">${params[0].axisValue}</div>`;
                params.forEach(param => {
                    result += `<div style="margin:3px 0;"><span style="color:${param.color};">●</span><span style="margin-left:8px;color:#262626;">${param.seriesName}:</span><span style="margin-left:5px;color:${param.color};">${param.value.toFixed(2)}%</span></div>`;
                });
                return result;
            }
        },
        legend: {
            data: comparisonStocks.map(s => s.name),
            top: 10,
            textStyle: {
                color: '#666',
                fontSize: 12
            }
        },
        grid: {
            left: '3%',
            right: '4%',
            bottom: '3%',
            containLabel: true
        },
        xAxis: {
            type: 'category',
            data: dates,
            boundaryGap: false,
            axisLine: {
                lineStyle: {
                    color: '#d9d9d9'
                }
            },
            axisTick: {
                show: false
            },
            axisLabel: {
                color: '#8c8c8c',
                fontSize: 10,
                rotate: 45
            },
            splitLine: {
                show: false
            }
        },
        yAxis: {
            type: 'value',
            axisLine: {
                show: false
            },
            axisTick: {
                show: false
            },
            axisLabel: {
                color: '#8c8c8c',
                fontSize: 10,
                formatter: '{value}%'
            },
            splitLine: {
                lineStyle: {
                    color: '#f0f0f0',
                    type: 'dashed'
                }
            }
        },
        series: series,
        color: colors
    };
    
    performanceComparisonChart.setOption(option);
}

function initMetricsComparisonChart() {
    if (metricsComparisonChart) {
        metricsComparisonChart.dispose();
    }
    
    const chartDom = document.getElementById('metricsComparisonChart');
    if (!chartDom) return;
    
    metricsComparisonChart = echarts.init(chartDom);
    
    const indicators = ['收益率', '波动率', '最大回撤', '平均成交量(万)'];
    
    const maxReturn = Math.max(...comparisonStocks.map(s => Math.abs(s.metrics.returnRate)));
    const maxVolatility = Math.max(...comparisonStocks.map(s => s.metrics.volatility));
    const maxDrawdown = Math.max(...comparisonStocks.map(s => Math.abs(s.metrics.maxDrawdown)));
    const maxVolume = Math.max(...comparisonStocks.map(s => s.metrics.avgVolume / 10000));
    
    const series = comparisonStocks.map(stock => {
        const normalizedVolume = (stock.metrics.avgVolume / 10000) / maxVolume * 100;
        const normalizedReturn = (stock.metrics.returnRate / maxReturn) * 100;
        const normalizedVolatility = (stock.metrics.volatility / maxVolatility) * 100;
        const normalizedDrawdown = (Math.abs(stock.metrics.maxDrawdown) / maxDrawdown) * 100;
        
        return {
            name: stock.name,
            type: 'radar',
            data: [{
                value: [normalizedReturn, normalizedVolatility, normalizedDrawdown, normalizedVolume],
                name: stock.name
            }],
            lineStyle: {
                width: 2
            },
            areaStyle: {
                opacity: 0.2
            }
        };
    });
    
    const colors = ['#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de', '#3ba272', '#fc8452', '#9a60b4'];
    
    const option = {
        tooltip: {
            trigger: 'item',
            backgroundColor: 'rgba(255, 255, 255, 0.95)',
            borderColor: '#d9d9d9',
            borderWidth: 1,
            textStyle: {
                color: '#262626',
                fontSize: 12
            },
            padding: [10, 15]
        },
        legend: {
            data: comparisonStocks.map(s => s.name),
            top: 10,
            textStyle: {
                color: '#666',
                fontSize: 12
            }
        },
        radar: {
            indicator: indicators.map(name => ({
                name: name,
                max: 100
            })),
            center: ['50%', '55%'],
            radius: '65%',
            axisName: {
                color: '#666',
                fontSize: 12,
                fontWeight: 600
            },
            splitArea: {
                areaStyle: {
                    color: ['rgba(102, 126, 234, 0.05)', 'rgba(102, 126, 234, 0.1)', 'rgba(102, 126, 234, 0.15)', 'rgba(102, 126, 234, 0.2)']
                }
            },
            splitLine: {
                lineStyle: {
                    color: 'rgba(102, 126, 234, 0.2)'
                }
            },
            axisLine: {
                lineStyle: {
                    color: 'rgba(102, 126, 234, 0.3)'
                }
            }
        },
        series: series,
        color: colors
    };
    
    metricsComparisonChart.setOption(option);
}

function updateComparisonStats() {
    if (comparisonStocks.length === 0) {
        return;
    }
    
    const returns = comparisonStocks.map(s => s.metrics.returnRate);
    const highestReturnStock = comparisonStocks.reduce((a, b) => a.metrics.returnRate > b.metrics.returnRate ? a : b);
    const lowestReturnStock = comparisonStocks.reduce((a, b) => a.metrics.returnRate < b.metrics.returnRate ? a : b);
    const avgReturnRate = returns.reduce((a, b) => a + b, 0) / returns.length;
    
    document.getElementById('highestReturnStock').textContent = `${highestReturnStock.name} (${highestReturnStock.metrics.returnRate.toFixed(2)}%)`;
    document.getElementById('highestReturnStock').className = 'comparison-stat-value positive';
    
    document.getElementById('lowestReturnStock').textContent = `${lowestReturnStock.name} (${lowestReturnStock.metrics.returnRate.toFixed(2)}%)`;
    document.getElementById('lowestReturnStock').className = 'comparison-stat-value ' + (lowestReturnStock.metrics.returnRate >= 0 ? 'positive' : 'negative');
    
    document.getElementById('avgReturnRate').textContent = `${avgReturnRate.toFixed(2)}%`;
    document.getElementById('avgReturnRate').className = 'comparison-stat-value ' + (avgReturnRate >= 0 ? 'positive' : 'negative');
}

let portfolioStocks = [];
let portfolioAllocationChart = null;
let portfolioPerformanceChart = null;
let portfolioRiskChart = null;
let portfolioCorrelationChart = null;

function showPortfolioSection() {
    document.getElementById('portfolioSection').style.display = 'block';
    document.getElementById('portfolioSection').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

async function addPortfolioStock() {
    const stockCode = document.getElementById('portfolioStockCode').value.trim();
    const quantity = parseInt(document.getElementById('portfolioStockQuantity').value);
    const buyPrice = parseFloat(document.getElementById('portfolioStockPrice').value);
    
    if (!stockCode || !quantity || !buyPrice) {
        alert('请填写完整的股票信息');
        return;
    }
    
    if (portfolioStocks.some(s => s.code === stockCode)) {
        alert('该股票已在组合中');
        return;
    }
    
    try {
        const response = await fetch('/api/stock_data', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                stock_code: stockCode,
                session_id: socket.id
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            const stockData = result.data;
            const currentPrice = stockData.kline_data && stockData.kline_data.length > 0 
                ? stockData.kline_data[stockData.kline_data.length - 1].close 
                : buyPrice;
            
            portfolioStocks.push({
                code: stockCode,
                name: stockData.name || stockCode,
                quantity: quantity,
                buyPrice: buyPrice,
                currentPrice: currentPrice,
                data: stockData.kline_data || [],
                marketValue: currentPrice * quantity,
                profit: (currentPrice - buyPrice) * quantity,
                profitRate: ((currentPrice - buyPrice) / buyPrice) * 100
            });
            
            updatePortfolioStockList();
            updatePortfolioSummary();
            
            document.getElementById('portfolioStockCode').value = '';
            document.getElementById('portfolioStockQuantity').value = '';
            document.getElementById('portfolioStockPrice').value = '';
            document.getElementById('portfolioInputArea').style.display = 'none';
            
            if (portfolioStocks.length > 0) {
                document.getElementById('portfolioSummary').style.display = 'block';
            }
        } else {
            alert('获取股票数据失败: ' + result.message);
        }
    } catch (error) {
        console.error('添加持仓股票错误:', error);
        alert('获取股票数据失败，请稍后重试');
    }
}

function removePortfolioStock(index) {
    portfolioStocks.splice(index, 1);
    updatePortfolioStockList();
    updatePortfolioSummary();
    
    if (portfolioStocks.length === 0) {
        document.getElementById('portfolioSummary').style.display = 'none';
        document.getElementById('portfolioChartsContainer').style.display = 'none';
    }
}

function clearPortfolio() {
    portfolioStocks = [];
    updatePortfolioStockList();
    updatePortfolioSummary();
    document.getElementById('portfolioSummary').style.display = 'none';
    document.getElementById('portfolioChartsContainer').style.display = 'none';
}

function updatePortfolioStockList() {
    const listContainer = document.getElementById('portfolioStockList');
    
    if (portfolioStocks.length === 0) {
        listContainer.innerHTML = '<p class="no-portfolio">暂无持仓股票，点击"添加持仓股票"开始构建组合</p>';
        return;
    }
    
    listContainer.innerHTML = portfolioStocks.map((stock, index) => `
        <div class="portfolio-stock-card">
            <div class="portfolio-stock-card-header">
                <div class="portfolio-stock-info">
                    <h4>${stock.name}</h4>
                    <span>${stock.code}</span>
                </div>
                <button class="portfolio-stock-remove" onclick="removePortfolioStock(${index})">移除</button>
            </div>
            <div class="portfolio-stock-metrics">
                <div class="portfolio-stock-metric">
                    <span class="portfolio-stock-metric-label">持仓数量</span>
                    <span class="portfolio-stock-metric-value">${stock.quantity}</span>
                </div>
                <div class="portfolio-stock-metric">
                    <span class="portfolio-stock-metric-label">买入价格</span>
                    <span class="portfolio-stock-metric-value">¥${stock.buyPrice.toFixed(2)}</span>
                </div>
                <div class="portfolio-stock-metric">
                    <span class="portfolio-stock-metric-label">当前价格</span>
                    <span class="portfolio-stock-metric-value">¥${stock.currentPrice.toFixed(2)}</span>
                </div>
                <div class="portfolio-stock-metric">
                    <span class="portfolio-stock-metric-label">市值</span>
                    <span class="portfolio-stock-metric-value">¥${stock.marketValue.toFixed(2)}</span>
                </div>
                <div class="portfolio-stock-metric">
                    <span class="portfolio-stock-metric-label">盈亏</span>
                    <span class="portfolio-stock-metric-value ${stock.profit >= 0 ? 'positive' : 'negative'}">¥${stock.profit.toFixed(2)}</span>
                </div>
                <div class="portfolio-stock-metric">
                    <span class="portfolio-stock-metric-label">收益率</span>
                    <span class="portfolio-stock-metric-value ${stock.profitRate >= 0 ? 'positive' : 'negative'}">${stock.profitRate.toFixed(2)}%</span>
                </div>
            </div>
        </div>
    `).join('');
}

function updatePortfolioSummary() {
    if (portfolioStocks.length === 0) {
        return;
    }
    
    const totalValue = portfolioStocks.reduce((sum, s) => sum + s.marketValue, 0);
    const totalProfit = portfolioStocks.reduce((sum, s) => sum + s.profit, 0);
    const totalCost = portfolioStocks.reduce((sum, s) => sum + s.buyPrice * s.quantity, 0);
    const returnRate = totalCost > 0 ? (totalProfit / totalCost) * 100 : 0;
    
    let maxDrawdown = 0;
    portfolioStocks.forEach(stock => {
        if (stock.data && stock.data.length > 0) {
            let peak = stock.data[0].close;
            for (const data of stock.data) {
                if (data.close > peak) {
                    peak = data.close;
                }
                const drawdown = ((peak - data.close) / peak) * 100;
                if (drawdown > maxDrawdown) {
                    maxDrawdown = drawdown;
                }
            }
        }
    });
    
    document.getElementById('portfolioTotalValue').textContent = `¥${totalValue.toFixed(2)}`;
    document.getElementById('portfolioTotalProfit').textContent = `¥${totalProfit.toFixed(2)}`;
    document.getElementById('portfolioTotalProfit').className = 'portfolio-card-value ' + (totalProfit >= 0 ? 'positive' : 'negative');
    document.getElementById('portfolioReturnRate').textContent = `${returnRate.toFixed(2)}%`;
    document.getElementById('portfolioReturnRate').className = 'portfolio-card-value ' + (returnRate >= 0 ? 'positive' : 'negative');
    document.getElementById('portfolioMaxDrawdown').textContent = `${maxDrawdown.toFixed(2)}%`;
}

async function analyzePortfolio() {
    if (portfolioStocks.length === 0) {
        alert('请先添加持仓股票');
        return;
    }
    
    document.getElementById('portfolioChartsContainer').style.display = 'block';
    updatePortfolioCharts();
}

function updatePortfolioCharts() {
    if (portfolioStocks.length === 0) {
        return;
    }
    
    initPortfolioAllocationChart();
    initPortfolioPerformanceChart();
    initPortfolioRiskChart();
    initPortfolioCorrelationChart();
    updatePortfolioStats();
}

function initPortfolioAllocationChart() {
    if (portfolioAllocationChart) {
        portfolioAllocationChart.dispose();
    }
    
    const chartDom = document.getElementById('portfolioAllocationChart');
    if (!chartDom) return;
    
    portfolioAllocationChart = echarts.init(chartDom);
    
    const data = portfolioStocks.map(stock => ({
        name: stock.name,
        value: stock.marketValue
    }));
    
    const colors = ['#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de', '#3ba272', '#fc8452', '#9a60b4'];
    
    const option = {
        tooltip: {
            trigger: 'item',
            formatter: '{b}: ¥{c} ({d}%)',
            backgroundColor: 'rgba(255, 255, 255, 0.95)',
            borderColor: '#d9d9d9',
            borderWidth: 1,
            textStyle: {
                color: '#262626',
                fontSize: 12
            },
            padding: [10, 15]
        },
        legend: {
            orient: 'vertical',
            right: '5%',
            top: 'center',
            textStyle: {
                color: '#666',
                fontSize: 12
            }
        },
        series: [
            {
                name: '资产配置',
                type: 'pie',
                radius: ['40%', '70%'],
                center: ['40%', '50%'],
                avoidLabelOverlap: false,
                itemStyle: {
                    borderRadius: 10,
                    borderColor: '#fff',
                    borderWidth: 2
                },
                label: {
                    show: false,
                    position: 'center'
                },
                emphasis: {
                    label: {
                        show: true,
                        fontSize: 20,
                        fontWeight: 'bold',
                        color: '#262626'
                    }
                },
                labelLine: {
                    show: false
                },
                data: data
            }
        ],
        color: colors
    };
    
    portfolioAllocationChart.setOption(option);
}

function initPortfolioPerformanceChart() {
    if (portfolioPerformanceChart) {
        portfolioPerformanceChart.dispose();
    }
    
    const chartDom = document.getElementById('portfolioPerformanceChart');
    if (!chartDom) return;
    
    portfolioPerformanceChart = echarts.init(chartDom);
    
    const dates = [];
    const portfolioValues = [];
    
    if (portfolioStocks.length > 0 && portfolioStocks[0].data && portfolioStocks[0].data.length > 0) {
        const stockData = portfolioStocks[0].data;
        stockData.forEach(data => {
            dates.push(data.date);
            let portfolioValue = 0;
            portfolioStocks.forEach(stock => {
                const stockData = stock.data.find(d => d.date === data.date);
                if (stockData) {
                    portfolioValue += stockData.close * stock.quantity;
                }
            });
            portfolioValues.push(portfolioValue);
        });
    }
    
    const option = {
        tooltip: {
            trigger: 'axis',
            axisPointer: {
                type: 'cross'
            },
            backgroundColor: 'rgba(255, 255, 255, 0.95)',
            borderColor: '#d9d9d9',
            borderWidth: 1,
            textStyle: {
                color: '#262626',
                fontSize: 12
            },
            padding: [10, 15],
            formatter: function(params) {
                const date = params[0].name;
                const value = params[0].value;
                const totalCost = portfolioStocks.reduce((sum, s) => sum + s.buyPrice * s.quantity, 0);
                const profit = value - totalCost;
                const profitRate = ((profit / totalCost) * 100).toFixed(2);
                return `${date}<br/>组合净值: ¥${value.toFixed(2)}<br/>盈亏: ¥${profit.toFixed(2)}<br/>收益率: ${profitRate}%`;
            }
        },
        grid: {
            left: '3%',
            right: '4%',
            bottom: '3%',
            containLabel: true
        },
        xAxis: {
            type: 'category',
            data: dates,
            boundaryGap: false,
            axisLine: {
                lineStyle: {
                    color: '#d9d9d9'
                }
            },
            axisTick: {
                show: false
            },
            axisLabel: {
                color: '#8c8c8c',
                fontSize: 10,
                rotate: 45
            },
            splitLine: {
                show: false
            }
        },
        yAxis: {
            type: 'value',
            axisLine: {
                show: false
            },
            axisTick: {
                show: false
            },
            axisLabel: {
                color: '#8c8c8c',
                fontSize: 10,
                formatter: '¥{value}'
            },
            splitLine: {
                lineStyle: {
                    color: '#f0f0f0',
                    type: 'dashed'
                }
            }
        },
        series: [
            {
                name: '组合净值',
                type: 'line',
                data: portfolioValues,
                smooth: true,
                lineStyle: {
                    width: 3,
                    color: '#667eea'
                },
                areaStyle: {
                    color: {
                        type: 'linear',
                        x: 0,
                        y: 0,
                        x2: 0,
                        y2: 1,
                        colorStops: [
                            { offset: 0, color: 'rgba(102, 126, 234, 0.3)' },
                            { offset: 1, color: 'rgba(102, 126, 234, 0.05)' }
                        ]
                    }
                },
                symbol: 'none'
            }
        ]
    };
    
    portfolioPerformanceChart.setOption(option);
}

function initPortfolioRiskChart() {
    if (portfolioRiskChart) {
        portfolioRiskChart.dispose();
    }
    
    const chartDom = document.getElementById('portfolioRiskChart');
    if (!chartDom) return;
    
    portfolioRiskChart = echarts.init(chartDom);
    
    const indicators = ['收益率', '波动率', '最大回撤', '夏普比率', 'Beta系数', '信息比率'];
    
    const stockMetrics = portfolioStocks.map(stock => {
        let returnRate = stock.profitRate;
        let volatility = 0;
        let maxDrawdown = 0;
        
        if (stock.data && stock.data.length > 0) {
            const returns = [];
            for (let i = 1; i < stock.data.length; i++) {
                returns.push((stock.data[i].close - stock.data[i-1].close) / stock.data[i-1].close);
            }
            const mean = returns.reduce((a, b) => a + b, 0) / returns.length;
            const variance = returns.reduce((sum, r) => sum + Math.pow(r - mean, 2), 0) / returns.length;
            volatility = Math.sqrt(variance) * 100;
            
            let peak = stock.data[0].close;
            for (const data of stock.data) {
                if (data.close > peak) {
                    peak = data.close;
                }
                const drawdown = ((peak - data.close) / peak) * 100;
                if (drawdown > maxDrawdown) {
                    maxDrawdown = drawdown;
                }
            }
        }
        
        const sharpeRatio = volatility > 0 ? (returnRate / volatility) : 0;
        const beta = volatility > 0 ? (volatility / 20) : 1;
        const infoRatio = volatility > 0 ? (returnRate / volatility) : 0;
        
        return {
            name: stock.name,
            metrics: [returnRate, volatility, maxDrawdown, sharpeRatio * 10, beta * 10, infoRatio * 10]
        };
    });
    
    const maxValues = [100, 100, 100, 100, 100, 100];
    stockMetrics.forEach(stock => {
        stock.metrics.forEach((value, index) => {
            if (Math.abs(value) > maxValues[index]) {
                maxValues[index] = Math.abs(value);
            }
        });
    });
    
    const normalizedData = stockMetrics.map(stock => {
        return {
            name: stock.name,
            value: stock.metrics.map((v, i) => (Math.abs(v) / maxValues[i]) * 100)
        };
    });
    
    const colors = ['#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de', '#3ba272', '#fc8452', '#9a60b4'];
    
    const option = {
        tooltip: {
            trigger: 'item',
            backgroundColor: 'rgba(255, 255, 255, 0.95)',
            borderColor: '#d9d9d9',
            borderWidth: 1,
            textStyle: {
                color: '#262626',
                fontSize: 12
            },
            padding: [10, 15]
        },
        legend: {
            data: stockMetrics.map(s => s.name),
            top: 10,
            textStyle: {
                color: '#666',
                fontSize: 12
            }
        },
        radar: {
            indicator: indicators.map(name => ({
                name: name,
                max: 100
            })),
            center: ['50%', '55%'],
            radius: '65%',
            axisName: {
                color: '#666',
                fontSize: 12,
                fontWeight: 600
            },
            splitArea: {
                areaStyle: {
                    color: ['rgba(102, 126, 234, 0.05)', 'rgba(102, 126, 234, 0.1)', 'rgba(102, 126, 234, 0.15)', 'rgba(102, 126, 234, 0.2)']
                }
            },
            splitLine: {
                lineStyle: {
                    color: 'rgba(102, 126, 234, 0.2)'
                }
            },
            axisLine: {
                lineStyle: {
                    color: 'rgba(102, 126, 234, 0.3)'
                }
            }
        },
        series: [
            {
                type: 'radar',
                data: normalizedData.map(item => ({
                    name: item.name,
                    value: item.value
                })),
                lineStyle: {
                    width: 2
                },
                areaStyle: {
                    opacity: 0.2
                }
            }
        ],
        color: colors
    };
    
    portfolioRiskChart.setOption(option);
}

function initPortfolioCorrelationChart() {
    if (portfolioCorrelationChart) {
        portfolioCorrelationChart.dispose();
    }
    
    const chartDom = document.getElementById('portfolioCorrelationChart');
    if (!chartDom) return;
    
    portfolioCorrelationChart = echarts.init(chartDom);
    
    const stockNames = portfolioStocks.map(s => s.name);
    const correlationData = [];
    
    for (let i = 0; i < portfolioStocks.length; i++) {
        for (let j = 0; j < portfolioStocks.length; j++) {
            if (i === j) {
                correlationData.push([i, j, 1]);
            } else {
                const correlation = calculateCorrelation(portfolioStocks[i], portfolioStocks[j]);
                correlationData.push([i, j, correlation]);
            }
        }
    }
    
    const option = {
        tooltip: {
            position: 'top',
            formatter: function(params) {
                const stock1 = stockNames[params.value[0]];
                const stock2 = stockNames[params.value[1]];
                const correlation = params.value[2].toFixed(2);
                return `${stock1} vs ${stock2}<br/>相关系数: ${correlation}`;
            },
            backgroundColor: 'rgba(255, 255, 255, 0.95)',
            borderColor: '#d9d9d9',
            borderWidth: 1,
            textStyle: {
                color: '#262626',
                fontSize: 12
            },
            padding: [10, 15]
        },
        grid: {
            height: '50%',
            top: '10%'
        },
        xAxis: {
            type: 'category',
            data: stockNames,
            splitArea: {
                show: true
            },
            axisLabel: {
                color: '#666',
                fontSize: 11,
                rotate: 45
            }
        },
        yAxis: {
            type: 'category',
            data: stockNames,
            splitArea: {
                show: true
            },
            axisLabel: {
                color: '#666',
                fontSize: 11
            }
        },
        visualMap: {
            min: -1,
            max: 1,
            calculable: true,
            orient: 'horizontal',
            left: 'center',
            bottom: '0%',
            inRange: {
                color: ['#313695', '#4575b4', '#74add1', '#abd9e9', '#e0f3f8', '#ffffbf', '#fee090', '#fdae61', '#f46d43', '#d73027', '#a50026']
            }
        },
        series: [
            {
                name: '相关性',
                type: 'heatmap',
                data: correlationData,
                label: {
                    show: true,
                    formatter: function(params) {
                        return params.value[2].toFixed(2);
                    },
                    color: '#fff',
                    fontSize: 11,
                    fontWeight: 600
                },
                emphasis: {
                    itemStyle: {
                        shadowBlur: 10,
                        shadowColor: 'rgba(0, 0, 0, 0.5)'
                    }
                }
            }
        ]
    };
    
    portfolioCorrelationChart.setOption(option);
}

function calculateCorrelation(stock1, stock2) {
    if (!stock1.data || !stock2.data || stock1.data.length === 0 || stock2.data.length === 0) {
        return 0;
    }
    
    const minLength = Math.min(stock1.data.length, stock2.data.length);
    const returns1 = [];
    const returns2 = [];
    
    for (let i = 1; i < minLength; i++) {
        returns1.push((stock1.data[i].close - stock1.data[i-1].close) / stock1.data[i-1].close);
        returns2.push((stock2.data[i].close - stock2.data[i-1].close) / stock2.data[i-1].close);
    }
    
    const mean1 = returns1.reduce((a, b) => a + b, 0) / returns1.length;
    const mean2 = returns2.reduce((a, b) => a + b, 0) / returns2.length;
    
    let numerator = 0;
    let denominator1 = 0;
    let denominator2 = 0;
    
    for (let i = 0; i < returns1.length; i++) {
        numerator += (returns1[i] - mean1) * (returns2[i] - mean2);
        denominator1 += Math.pow(returns1[i] - mean1, 2);
        denominator2 += Math.pow(returns2[i] - mean2, 2);
    }
    
    const denominator = Math.sqrt(denominator1 * denominator2);
    
    if (denominator === 0) {
        return 0;
    }
    
    return numerator / denominator;
}

function updatePortfolioStats() {
    if (portfolioStocks.length === 0) {
        return;
    }
    
    const totalCost = portfolioStocks.reduce((sum, s) => sum + s.buyPrice * s.quantity, 0);
    const totalValue = portfolioStocks.reduce((sum, s) => sum + s.marketValue, 0);
    const cumulativeReturn = ((totalValue - totalCost) / totalCost) * 100;
    
    let annualReturn = 0;
    if (portfolioStocks[0].data && portfolioStocks[0].data.length > 0) {
        const days = portfolioStocks[0].data.length;
        const years = days / 252;
        if (years > 0) {
            annualReturn = (Math.pow(1 + cumulativeReturn / 100, 1 / years) - 1) * 100;
        }
    }
    
    let sharpeRatio = 0;
    let volatility = 0;
    if (portfolioStocks[0].data && portfolioStocks[0].data.length > 1) {
        const returns = [];
        for (let i = 1; i < portfolioStocks[0].data.length; i++) {
            returns.push((portfolioStocks[0].data[i].close - portfolioStocks[0].data[i-1].close) / portfolioStocks[0].data[i-1].close);
        }
        const mean = returns.reduce((a, b) => a + b, 0) / returns.length;
        const variance = returns.reduce((sum, r) => sum + Math.pow(r - mean, 2), 0) / returns.length;
        volatility = Math.sqrt(variance);
        sharpeRatio = volatility > 0 ? (mean / volatility) * Math.sqrt(252) : 0;
    }
    
    document.getElementById('portfolioCumulativeReturn').textContent = `${cumulativeReturn.toFixed(2)}%`;
    document.getElementById('portfolioCumulativeReturn').className = 'portfolio-stat-value ' + (cumulativeReturn >= 0 ? 'positive' : 'negative');
    
    document.getElementById('portfolioAnnualReturn').textContent = `${annualReturn.toFixed(2)}%`;
    document.getElementById('portfolioAnnualReturn').className = 'portfolio-stat-value ' + (annualReturn >= 0 ? 'positive' : 'negative');
    
    document.getElementById('portfolioSharpeRatio').textContent = sharpeRatio.toFixed(2);
    document.getElementById('portfolioSharpeRatio').className = 'portfolio-stat-value ' + (sharpeRatio >= 0 ? 'positive' : 'negative');
}

document.addEventListener('DOMContentLoaded', function() {
    const navButtons = document.querySelectorAll('.nav-btn');
    
    function showSection(section) {
        document.getElementById('chartSection').style.display = 'none';
        document.getElementById('backtestSection').style.display = 'none';
        document.getElementById('comparisonSection').style.display = 'none';
        document.getElementById('portfolioSection').style.display = 'none';
        
        if (section === 'analysis') {
            document.getElementById('chartSection').style.display = 'block';
            
            setTimeout(() => {
                if (klineChart) klineChart.resize();
                if (radarChart) radarChart.resize();
                if (trendChart) trendChart.resize();
                if (volumeChart) volumeChart.resize();
                if (macdChart) macdChart.resize();
                if (rsiChart) rsiChart.resize();
                if (allocationChart) allocationChart.resize();
            }, 100);
        } else if (section === 'backtest') {
            document.getElementById('backtestSection').style.display = 'block';
            
            setTimeout(() => {
                if (equityCurveChart) equityCurveChart.resize();
                if (drawdownChart) drawdownChart.resize();
                if (tradeDistributionChart) tradeDistributionChart.resize();
                if (metricsRadarChart) metricsRadarChart.resize();
            }, 100);
        } else if (section === 'comparison') {
            document.getElementById('comparisonSection').style.display = 'block';
            
            setTimeout(() => {
                if (priceComparisonChart) priceComparisonChart.resize();
                if (performanceComparisonChart) performanceComparisonChart.resize();
                if (metricsComparisonChart) metricsComparisonChart.resize();
            }, 100);
        } else if (section === 'portfolio') {
            document.getElementById('portfolioSection').style.display = 'block';
            
            setTimeout(() => {
                if (portfolioAllocationChart) portfolioAllocationChart.resize();
                if (portfolioPerformanceChart) portfolioPerformanceChart.resize();
                if (portfolioRiskChart) portfolioRiskChart.resize();
                if (portfolioCorrelationChart) portfolioCorrelationChart.resize();
            }, 100);
        }
    }
    
    navButtons.forEach(button => {
        button.addEventListener('click', function() {
            navButtons.forEach(btn => btn.classList.remove('active'));
            this.classList.add('active');
            
            const section = this.getAttribute('data-section');
            showSection(section);
        });
    });
    
    showSection('analysis');
    
    const addPortfolioStockBtn = document.getElementById('addPortfolioStockBtn');
    if (addPortfolioStockBtn) {
        addPortfolioStockBtn.addEventListener('click', function() {
            document.getElementById('portfolioInputArea').style.display = 'block';
        });
    }
    
    const confirmAddPortfolioBtn = document.getElementById('confirmAddPortfolioBtn');
    if (confirmAddPortfolioBtn) {
        confirmAddPortfolioBtn.addEventListener('click', addPortfolioStock);
    }
    
    const cancelAddPortfolioBtn = document.getElementById('cancelAddPortfolioBtn');
    if (cancelAddPortfolioBtn) {
        cancelAddPortfolioBtn.addEventListener('click', function() {
            document.getElementById('portfolioInputArea').style.display = 'none';
        });
    }
    
    const clearPortfolioBtn = document.getElementById('clearPortfolioBtn');
    if (clearPortfolioBtn) {
        clearPortfolioBtn.addEventListener('click', clearPortfolio);
    }
    
    const analyzePortfolioBtn = document.getElementById('analyzePortfolioBtn');
    if (analyzePortfolioBtn) {
        analyzePortfolioBtn.addEventListener('click', analyzePortfolio);
    }
    
    const portfolioTabButtons = document.querySelectorAll('.portfolio-tab-btn');
    portfolioTabButtons.forEach(button => {
        button.addEventListener('click', function() {
            portfolioTabButtons.forEach(btn => btn.classList.remove('active'));
            this.classList.add('active');
            
            const tab = this.getAttribute('data-tab');
            document.querySelectorAll('.portfolio-chart-panel').forEach(panel => {
                panel.classList.remove('active');
            });
            document.getElementById(tab + 'Panel').classList.add('active');
        });
    });
});
