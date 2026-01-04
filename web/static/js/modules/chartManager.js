// 图表管理模块
class ChartManager {
    constructor() {
        this.chartInstances = {
            klineChart: null,
            radarChart: null,
            trendChart: null,
            volumeChart: null,
            macdChart: null,
            rsiChart: null,
            kdjChart: null,
            allocationChart: null
        };
        
        this.chartsInitialized = {
            klineChart: false,
            radarChart: false,
            trendChart: false,
            volumeChart: false,
            macdChart: false,
            rsiChart: false,
            kdjChart: false,
            allocationChart: false
        };
        
        this.chartLoadingStatus = {
            volumeChart: false,
            macdChart: false,
            rsiChart: false,
            kdjChart: false,
            radarChart: false,
            trendChart: false,
            allocationChart: false
        };

        this.currentKlineData = null;

        this.echarts = null;
        this.echartsLoadingPromise = null;
        
        this.chartVisibilityObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const chartId = entry.target.id;
                    this.initOrUpdateChartByContainerId(chartId);
                    this.chartVisibilityObserver.unobserve(entry.target);
                }
            });
        }, { threshold: 0.1 });
        
        this.initChartContainerObserver();
    }
    
    initChartContainerObserver() {
        // 监听图表容器的可见性，实现按需加载
        const chartContainers = [
            'volumeChart',
            'macdChart',
            'rsiChart',
            'kdjChart',
            'radarChart',
            'trendChart',
            'allocationChart'
        ];
        
        chartContainers.forEach(chartId => {
            const container = document.getElementById(chartId);
            if (container) {
                // 设置观察，当容器可见时初始化图表
                this.chartVisibilityObserver.observe(container);
            }
        });
    }

    // 调整所有图表大小
    resizeAllCharts() {
        Object.values(this.chartInstances).forEach(instance => {
            if (instance) {
                instance.resize();
            }
        });
    }

    // 连接图表实现同步（联动）
    connectCharts() {
        if (!this.echarts) return;
        
        const groupCharts = [];
        // 将需要同步的图表放入一个数组
        const syncChartKeys = ['klineChart', 'volumeChart', 'macdChart', 'rsiChart', 'kdjChart'];
        
        syncChartKeys.forEach(key => {
            if (this.chartInstances[key]) {
                groupCharts.push(this.chartInstances[key]);
            }
        });
        
        if (groupCharts.length > 1) {
            // 设置相同的 group ID
            groupCharts.forEach(chart => {
                chart.group = 'stockGroup';
            });
            // 连接所有同组图表
            this.echarts.connect('stockGroup');
        }
    }

    async ensureEcharts() {
        if (this.echarts) return this.echarts;
        if (window.echarts) {
            this.echarts = window.echarts;
            return this.echarts;
        }
        if (this.echartsLoadingPromise) return this.echartsLoadingPromise;

        this.echartsLoadingPromise = new Promise((resolve, reject) => {
            const existing = document.querySelector('script[data-echarts-loader="true"]');
            if (existing) {
                existing.addEventListener('load', () => {
                    this.echarts = window.echarts;
                    resolve(this.echarts);
                });
                existing.addEventListener('error', () => reject(new Error('ECharts加载失败')));
                return;
            }

            const script = document.createElement('script');
            script.src = 'https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js';
            script.defer = true;
            script.dataset.echartsLoader = 'true';
            script.onload = () => {
                this.echarts = window.echarts;
                resolve(this.echarts);
            };
            script.onerror = () => reject(new Error('ECharts加载失败'));
            document.head.appendChild(script);
        }).finally(() => {
            this.echartsLoadingPromise = null;
        });

        return this.echartsLoadingPromise;
    }
    
    // 根据容器ID初始化或更新图表
    async initOrUpdateChartByContainerId(chartId) {
        if (!this.currentKlineData) return;
        
        switch (chartId) {
            case 'volumeChart':
                if (!this.chartsInitialized.volumeChart) {
                    await this.initVolumeChart(this.currentKlineData);
                }
                break;
            case 'macdChart':
                if (!this.chartsInitialized.macdChart) {
                    await this.initMACDChart(this.currentKlineData);
                }
                break;
            case 'rsiChart':
                if (!this.chartsInitialized.rsiChart) {
                    await this.initRSIChart(this.currentKlineData);
                }
                break;
            case 'kdjChart':
                if (!this.chartsInitialized.kdjChart) {
                    await this.initKDJChart(this.currentKlineData);
                }
                break;
            case 'allocationChart':
                if (!this.chartsInitialized.allocationChart) {
                    await this.initAllocationChart();
                }
                break;
            case 'radarChart':
                // 雷达图需要分析数据，暂时不自动初始化
                break;
            case 'trendChart':
                if (!this.chartsInitialized.trendChart) {
                    await this.updateTrendChart(this.currentKlineData);
                }
                break;
            default:
                break;
        }

        // 尝试连接图表实现联动
        this.connectCharts();
    }
    
    // K线图初始化
    async initKlineChart() {
        if (this.chartInstances.klineChart) return this.chartInstances.klineChart;
        
        const chartDom = document.getElementById('klineChart');
        if (!chartDom) {
            console.error('klineChart element not found');
            return null;
        }

        const echarts = await this.ensureEcharts();
        this.chartInstances.klineChart = echarts.init(chartDom, 'light', {
            renderer: 'canvas',
            width: chartDom.clientWidth,
            height: chartDom.clientHeight || 400
        });
        this.chartsInitialized.klineChart = true;
        
        // 监听窗口大小变化
        window.addEventListener('resize', () => {
            if (this.chartInstances.klineChart) {
                this.chartInstances.klineChart.resize();
            }
        });
        
        return this.chartInstances.klineChart;
    }
    
    // 更新K线图
    async updateKlineChart(klineData) {
        try {
            if (!klineData || !Array.isArray(klineData) || klineData.length === 0) {
                console.error('Invalid klineData for K-line chart');
                return;
            }
            
            // 确保K线图已初始化
            await this.initKlineChart();
            
            // 保存当前K线数据
            this.currentKlineData = klineData;
            
            const dates = klineData.map(item => item[0]);
            const closes = klineData.map(item => item[2]);
            const opens = klineData.map(item => item[1]);
            const highs = klineData.map(item => item[4]);
            const lows = klineData.map(item => item[3]);
            const volumes = klineData.map(item => item[5]);
            
            // 计算技术指标
            const ma5 = this.calculateMA(closes, 5);
            const ma10 = this.calculateMA(closes, 10);
            const ma20 = this.calculateMA(closes, 20);
            const ma30 = this.calculateMA(closes, 30);
            const boll = this.calculateBOLL(closes, 20, 2);
            
            // 计算BOLL信号
            const lastClose = closes[closes.length - 1];
            const lastUpper = boll.upper[boll.upper.length - 1];
            const lastLower = boll.lower[boll.lower.length - 1];
            const lastMid = boll.mid[boll.mid.length - 1];
            
            let bollSignal = '区间震荡';
            let bollSignalColor = '#8c8c8c';
            
            if (lastClose > lastUpper) {
                bollSignal = '触及上轨(压力)';
                bollSignalColor = '#f5222d';
            } else if (lastClose < lastLower) {
                bollSignal = '触及下轨(支撑)';
                bollSignalColor = '#52c41a';
            } else if (lastClose > lastMid) {
                bollSignal = '多头区域';
                bollSignalColor = '#f5222d';
            } else if (lastClose < lastMid) {
                bollSignal = '空头区域';
                bollSignalColor = '#52c41a';
            }
            
            const bollSignalElement = document.getElementById('bollSignal');
            if (bollSignalElement) {
                bollSignalElement.textContent = bollSignal;
                bollSignalElement.style.color = bollSignalColor;
            }
            
            const option = {
                legend: {
                    data: ['K线', 'MA5', 'MA10', 'MA20', 'MA30', 'BOLL中轨', 'BOLL上轨', 'BOLL下轨'],
                    selected: {
                        'MA5': true,
                        'MA10': true,
                        'MA20': true,
                        'MA30': true,
                        'BOLL中轨': false,
                        'BOLL上轨': false,
                        'BOLL下轨': false
                    },
                    top: '2%',
                    textStyle: { color: '#8c8c8c', fontSize: 10 }
                },
                tooltip: {
                    trigger: 'axis',
                    axisPointer: {
                        type: 'cross'
                    },
                    backgroundColor: 'rgba(255, 255, 255, 0.9)',
                    borderWidth: 1,
                    borderColor: '#ccc',
                    padding: 10,
                    textStyle: {
                        color: '#000'
                    },
                    position: function (pos, params, el, elRect, size) {
                        const obj = { top: 10 };
                        obj[['left', 'right'][+(pos[0] < size.viewSize[0] / 2)]] = 5;
                        return obj;
                    },
                    formatter: (params) => {
                        let res = `<div style="font-weight: bold; border-bottom: 1px solid #eee; padding-bottom: 5px; margin-bottom: 5px;">${params[0].name}</div>`;
                        
                        // 分组显示
                        const groups = {
                            'K线': [],
                            'MA': [],
                            'BOLL': [],
                            '其他': []
                        };
                        
                        params.forEach(item => {
                            if (item.value === null || item.value === undefined) return;
                            
                            if (item.seriesName === 'K线') {
                                groups['K线'].push(item);
                            } else if (item.seriesName.startsWith('MA')) {
                                groups['MA'].push(item);
                            } else if (item.seriesName.startsWith('BOLL')) {
                                groups['BOLL'].push(item);
                            } else {
                                groups['其他'].push(item);
                            }
                        });
                        
                        // 渲染K线数据
                        if (groups['K线'].length > 0) {
                            const val = groups['K线'][0].value;
                            res += `<div style="color: #595959; margin-bottom: 5px;">
                                <span style="display:inline-block;width:30px">开:</span><span style="color:${val[1]>=val[0]?'#f5222d':'#52c41a'}">${val[1]}</span>
                                <span style="display:inline-block;width:30px;margin-left:10px">收:</span><span style="color:${val[2]>=val[1]?'#f5222d':'#52c41a'}">${val[2]}</span><br/>
                                <span style="display:inline-block;width:30px">低:</span><span style="color:#52c41a">${val[3]}</span>
                                <span style="display:inline-block;width:30px;margin-left:10px">高:</span><span style="color:#f5222d">${val[4]}</span>
                            </div>`;
                        }
                        
                        // 渲染MA数据
                        if (groups['MA'].length > 0) {
                            res += `<div style="border-top: 1px dashed #eee; padding-top: 5px; margin-top: 5px;">`;
                            groups['MA'].forEach(item => {
                                res += `<span style="display:inline-block;margin-right:10px;font-size:11px">
                                    <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background-color:${item.color};margin-right:4px"></span>
                                    ${item.seriesName}: ${typeof item.value === 'number' ? item.value.toFixed(2) : item.value}
                                </span>`;
                            });
                            res += `</div>`;
                        }
                        
                        // 渲染BOLL数据
                        if (groups['BOLL'].length > 0) {
                            res += `<div style="border-top: 1px dashed #eee; padding-top: 5px; margin-top: 5px;">`;
                            groups['BOLL'].forEach(item => {
                                res += `<span style="display:inline-block;margin-right:10px;font-size:11px">
                                    <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background-color:${item.color};margin-right:4px"></span>
                                    ${item.seriesName}: ${typeof item.value === 'number' ? item.value.toFixed(2) : item.value}
                                </span>`;
                            });
                            res += `</div>`;
                        }
                        
                        return res;
                    }
                },
                grid: [
                    {
                        left: '8%',
                        right: '8%',
                        top: '12%',
                        height: '45%'
                    },
                    {
                        left: '8%',
                        right: '8%',
                        top: '62%',
                        height: '12%'
                    },
                    {
                        left: '8%',
                        right: '8%',
                        top: '77%',
                        height: '12%'
                    }
                ],
                xAxis: [
                    {
                        type: 'category',
                        data: dates,
                        scale: true,
                        boundaryGap: false,
                        axisLine: { onZero: false },
                        splitLine: { show: false },
                        splitNumber: 20,
                        min: 'dataMin',
                        max: 'dataMax',
                        axisLabel: {
                            color: '#8c8c8c',
                            fontSize: 10,
                            rotate: 30,
                            interval: 'auto',
                            formatter: function(value) {
                                if (value && value.length >= 10) {
                                    return value.substring(5, 10);
                                }
                                return value;
                            }
                        }
                    },
                    {
                        type: 'category',
                        gridIndex: 1,
                        data: dates,
                        scale: true,
                        boundaryGap: false,
                        axisLine: { onZero: false },
                        axisTick: { show: false },
                        splitLine: { show: false },
                        axisLabel: { show: false }
                    },
                    {
                        type: 'category',
                        gridIndex: 2,
                        data: dates,
                        scale: true,
                        boundaryGap: false,
                        axisLine: { onZero: false },
                        axisTick: { show: false },
                        splitLine: { show: false },
                        axisLabel: { show: false }
                    }
                ],
                yAxis: [
                    {
                        scale: true,
                        splitArea: { show: true },
                        axisLabel: {
                            color: '#8c8c8c',
                            fontSize: 10
                        }
                    },
                    {
                        scale: true,
                        gridIndex: 1,
                        splitNumber: 2,
                        axisLabel: {
                            show: false
                        },
                        axisLine: { show: false },
                        axisTick: { show: false },
                        splitLine: { show: false }
                    },
                    {
                        scale: true,
                        gridIndex: 2,
                        splitNumber: 2,
                        axisLabel: {
                            show: false
                        },
                        axisLine: { show: false },
                        axisTick: { show: false },
                        splitLine: { show: false }
                    }
                ],
                dataZoom: [
                    {
                        type: 'inside',
                        xAxisIndex: [0, 1, 2],
                        start: 65,
                        end: 100
                    },
                    {
                        show: true,
                        xAxisIndex: [0, 1, 2],
                        type: 'slider',
                        bottom: '0%',
                        start: 65,
                        end: 100
                    }
                ],
                series: [
                    {
                        name: 'K线',
                        type: 'candlestick',
                        data: klineData.map((item, index) => [
                            opens[index],
                            closes[index],
                            lows[index],
                            highs[index]
                        ]),
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
                        data: ma5,
                        smooth: true,
                        showSymbol: false,
                        lineStyle: { width: 1, opacity: 0.5 }
                    },
                    {
                        name: 'MA10',
                        type: 'line',
                        data: ma10,
                        smooth: true,
                        showSymbol: false,
                        lineStyle: { width: 1, opacity: 0.5 }
                    },
                    {
                        name: 'MA20',
                        type: 'line',
                        data: ma20,
                        smooth: true,
                        showSymbol: false,
                        lineStyle: { width: 1, opacity: 0.5 }
                    },
                    {
                        name: 'MA30',
                        type: 'line',
                        data: ma30,
                        smooth: true,
                        showSymbol: false,
                        lineStyle: { width: 1, opacity: 0.5 }
                    },
                    {
                        name: 'BOLL上轨',
                        type: 'line',
                        data: boll.upper,
                        smooth: true,
                        showSymbol: false,
                        lineStyle: { width: 1, opacity: 0.5, type: 'dashed' }
                    },
                    {
                        name: 'BOLL中轨',
                        type: 'line',
                        data: boll.mid,
                        smooth: true,
                        showSymbol: false,
                        lineStyle: { width: 1, opacity: 0.5, type: 'dashed' }
                    },
                    {
                        name: 'BOLL下轨',
                        type: 'line',
                        data: boll.lower,
                        smooth: true,
                        showSymbol: false,
                        lineStyle: { width: 1, opacity: 0.5, type: 'dashed' }
                    },
                    {
                        name: '成交量',
                        type: 'bar',
                        xAxisIndex: 1,
                        yAxisIndex: 1,
                        data: volumes,
                        itemStyle: {
                            color: (params) => {
                                const dataIndex = params.dataIndex;
                                if (opens[dataIndex] <= closes[dataIndex]) {
                                    return '#f5222d';
                                } else {
                                    return '#52c41a';
                                }
                            }
                        }
                    },
                    {
                        name: '收盘价',
                        type: 'line',
                        xAxisIndex: 2,
                        yAxisIndex: 2,
                        data: closes,
                        smooth: true,
                        showSymbol: false,
                        lineStyle: {
                            color: '#667eea',
                            width: 2
                        }
                    }
                ]
            };
            
            this.chartInstances.klineChart.setOption(option);
        } catch (error) {
            console.error('更新K线图失败:', error);
        }
    }
    
    // 初始化成交量图表
    async initVolumeChart(klineData) {
        try {
            if (!klineData || !Array.isArray(klineData) || klineData.length === 0) {
                console.error('Invalid klineData for volume chart');
                return;
            }
            
            const chartDom = document.getElementById('volumeChart');
            if (!chartDom) {
                console.error('volumeChart element not found');
                return;
            }
            
            const echarts = await this.ensureEcharts();

            // 只在图表不存在时创建，否则复用
            if (!this.chartInstances.volumeChart) {
                this.chartInstances.volumeChart = echarts.init(chartDom);
            }
            
            const dates = klineData.map(item => item[0]);
            const volumes = klineData.map(item => item[5]);
            const opens = klineData.map(item => item[1]);
            const closes = klineData.map(item => item[2]);
            
            if (volumes.length === 0 || closes.length === 0) {
                console.error('Empty volumes or closes data');
                return;
            }
            
            // 计算成交量均线
            const vma5 = this.calculateMA(volumes, 5);
            const vma10 = this.calculateMA(volumes, 10);
            
            const avgVolume = volumes.reduce((a, b) => a + b, 0) / volumes.length;
            const avgVolumeElement = document.getElementById('avgVolume');
            if (avgVolumeElement) {
                avgVolumeElement.textContent = this.formatVolume(avgVolume);
            }
            
            const recentVolumes = volumes.slice(-10);
            const earlierVolumes = volumes.slice(-20, -10);
            
            if (recentVolumes.length > 0 && earlierVolumes.length > 0) {
                const recentAvg = recentVolumes.reduce((a, b) => a + b, 0) / recentVolumes.length;
                const earlierAvg = earlierVolumes.reduce((a, b) => a + b, 0) / earlierVolumes.length;
                
                const volumeTrendElement = document.getElementById('volumeTrend');
                if (volumeTrendElement) {
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
                }
                
                const recentPriceChange = closes[closes.length - 1] - closes[closes.length - 10];
                const priceVolumeRelationElement = document.getElementById('priceVolumeRelation');
                if (priceVolumeRelationElement) {
                    if ((recentPriceChange > 0 && recentAvg > earlierAvg) || (recentPriceChange < 0 && recentAvg < earlierAvg)) {
                        priceVolumeRelationElement.textContent = '量价配合';
                        priceVolumeRelationElement.style.color = '#52c41a';
                    } else {
                        priceVolumeRelationElement.textContent = '量价背离';
                        priceVolumeRelationElement.style.color = '#faad14';
                    }
                }
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
                    let res = `<div style="font-weight:600;margin-bottom:5px;">${params[0].axisValue}</div>`;
                    params.forEach(item => {
                        const val = typeof item.value === 'number' ? this.formatVolume(item.value) : item.value;
                        res += `<div style="margin:3px 0;">
                            <span style="color:${item.color};">●</span>
                            <span style="margin-left:8px;color:#262626;">${item.seriesName}:</span>
                            <span style="margin-left:5px;color:${item.color};font-weight:500;">${val}</span>
                        </div>`;
                    });
                    return res;
                }.bind(this)
            },
            legend: {
                data: ['成交量', 'VMA5', 'VMA10'],
                top: 5,
                textStyle: { color: '#595959', fontSize: 11 }
            },
            grid: {
                left: '8%',
                right: '5%',
                top: '15%',
                bottom: '15%',
                containLabel: true
            },
            xAxis: {
                type: 'category',
                data: dates,
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
            dataZoom: [
                {
                    type: 'inside',
                    start: 65,
                    end: 100
                },
                {
                    show: false,
                    type: 'slider',
                    start: 65,
                    end: 100
                }
            ],
            series: [
                {
                    name: '成交量',
                    type: 'bar',
                    data: volumes.map((vol, idx) => {
                        const open = opens[idx];
                        const close = closes[idx];
                        return {
                            value: vol,
                            itemStyle: {
                                color: close >= open ? '#f5222d' : '#52c41a'
                            }
                        };
                    }),
                    barWidth: '60%'
                },
                {
                    name: 'VMA5',
                    type: 'line',
                    data: vma5,
                    smooth: true,
                    showSymbol: false,
                    lineStyle: { width: 1.5, color: '#1890ff' },
                    itemStyle: { color: '#1890ff' }
                },
                {
                    name: 'VMA10',
                    type: 'line',
                    data: vma10,
                    smooth: true,
                    showSymbol: false,
                    lineStyle: { width: 1.5, color: '#faad14' },
                    itemStyle: { color: '#faad14' }
                }
            ]
        };
        
        this.chartInstances.volumeChart.setOption(option);
        // 更新初始化标志
        this.chartsInitialized.volumeChart = true;
        } catch (error) {
            console.error('初始化成交量图表失败:', error);
        }
    }
    
    // 初始化MACD图表
    async initMACDChart(klineData) {
        try {
            if (!klineData || !Array.isArray(klineData) || klineData.length === 0) {
                console.error('Invalid klineData for MACD chart');
                return;
            }
            
            const chartDom = document.getElementById('macdChart');
            if (!chartDom) {
                console.error('macdChart element not found');
                return;
            }
            
            const echarts = await this.ensureEcharts();

            // 只在图表不存在时创建，否则复用
            if (!this.chartInstances.macdChart) {
                this.chartInstances.macdChart = echarts.init(chartDom);
            }
            
            const closes = klineData.map(item => item[2]);
            
            if (closes.length < 26) {
                console.error('Insufficient data for MACD calculation');
                return;
            }
            
            const macdResult = this.calculateMACD(closes, 12, 26, 9);
            const dif = macdResult.dif;
            const dea = macdResult.dea;
            const macd = macdResult.macd;
            
            if (dif.length === 0 || dea.length === 0 || macd.length === 0) {
                console.error('MACD calculation failed');
                return;
            }
            
            const lastDif = dif[dif.length - 1];
            const lastDea = dea[dea.length - 1];
            const lastMACD = macd[macd.length - 1];
            
            const difValueElement = document.getElementById('difValue');
            const deaValueElement = document.getElementById('deaValue');
            if (difValueElement) difValueElement.textContent = lastDif.toFixed(4);
            if (deaValueElement) deaValueElement.textContent = lastDea.toFixed(4);
            
            const macdSignalElement = document.getElementById('macdSignal');
            if (macdSignalElement) {
                let signal = '震荡整理';
                let color = '#8c8c8c';
                
                const isGoldCross = lastDif > lastDea && dif[dif.length - 2] <= dea[dea.length - 2];
                const isDeadCross = lastDif < lastDea && dif[dif.length - 2] >= dea[dea.length - 2];
                
                if (isGoldCross) {
                    signal = lastDif < 0 ? '零轴下金叉(转强)' : '零轴上金叉(强势)';
                    color = '#f5222d';
                } else if (isDeadCross) {
                    signal = lastDif > 0 ? '零轴上死叉(回调)' : '零轴下死叉(走弱)';
                    color = '#52c41a';
                } else if (lastDif > lastDea) {
                    signal = lastDif > 0 ? '多头强势' : '多头回升';
                    color = '#f5222d';
                } else if (lastDif < lastDea) {
                    signal = lastDif < 0 ? '空头强势' : '空头回调';
                    color = '#52c41a';
                }
                
                macdSignalElement.textContent = signal;
                macdSignalElement.style.color = color;
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
                padding: [10, 15],
                formatter: function(params) {
                    let res = `<div style="font-weight:600;margin-bottom:5px;">${params[0].axisValue}</div>`;
                    params.forEach(item => {
                        res += `<div style="margin:3px 0;">
                            <span style="color:${item.color};">●</span>
                            <span style="margin-left:8px;color:#262626;">${item.seriesName}:</span>
                            <span style="margin-left:5px;color:${item.color};font-weight:500;">${typeof item.value === 'number' ? item.value.toFixed(4) : item.value}</span>
                        </div>`;
                    });
                    return res;
                }
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
                data: dates,
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
            dataZoom: [
                {
                    type: 'inside',
                    start: 65,
                    end: 100
                },
                {
                    show: false,
                    type: 'slider',
                    start: 65,
                    end: 100
                }
            ],
            series: [
                {
                    name: 'DIF',
                    type: 'line',
                    data: dif,
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
                    data: dea,
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
                    data: macd.map(val => ({
                        value: val,
                        itemStyle: {
                            color: val >= 0 ? '#f5222d' : '#52c41a'
                        }
                    })),
                    barWidth: '40%'
                }
            ]
        };
        
        this.chartInstances.macdChart.setOption(option);
        // 更新初始化标志
        this.chartsInitialized.macdChart = true;
        } catch (error) {
            console.error('初始化MACD图表失败:', error);
        }
    }
    
    // 初始化RSI图表
    async initRSIChart(klineData) {
        try {
            if (!klineData || !Array.isArray(klineData) || klineData.length === 0) {
                console.error('Invalid klineData for RSI chart');
                return;
            }
            
            const chartDom = document.getElementById('rsiChart');
            if (!chartDom) {
                console.error('rsiChart element not found');
                return;
            }
            
            const echarts = await this.ensureEcharts();

            // 只在图表不存在时创建，否则复用
            if (!this.chartInstances.rsiChart) {
                this.chartInstances.rsiChart = echarts.init(chartDom);
            }
            
            const closes = klineData.map(item => item[2]);
            
            if (closes.length < 24) {
                console.error('Insufficient data for RSI calculation');
                return;
            }
            
            const rsi6 = this.calculateRSI(closes, 6);
            const rsi12 = this.calculateRSI(closes, 12);
            const rsi24 = this.calculateRSI(closes, 24);
            
            if (rsi6.length === 0 || rsi12.length === 0 || rsi24.length === 0) {
                console.error('RSI calculation failed');
                return;
            }
            
            const rsi6ValueElement = document.getElementById('rsi6Value');
            const rsi12ValueElement = document.getElementById('rsi12Value');
            const rsi24ValueElement = document.getElementById('rsi24Value');
            if (rsi6ValueElement) rsi6ValueElement.textContent = rsi6[rsi6.length - 1].toFixed(2);
            if (rsi12ValueElement) rsi12ValueElement.textContent = rsi12[rsi12.length - 1].toFixed(2);
            if (rsi24ValueElement) rsi24ValueElement.textContent = rsi24[rsi24.length - 1].toFixed(2);
            
            // 计算RSI信号
            const lastRsi6 = rsi6[rsi6.length - 1];
            const lastRsi12 = rsi12[rsi12.length - 1];
            const rsiSignalElement = document.getElementById('rsiSignal');
            
            if (rsiSignalElement) {
                let rsiSignal = '走势平稳';
                let rsiSignalColor = '#8c8c8c';
                
                if (lastRsi6 > 80) {
                    rsiSignal = '超买风险';
                    rsiSignalColor = '#f5222d';
                } else if (lastRsi6 < 20) {
                    rsiSignal = '超卖机会';
                    rsiSignalColor = '#52c41a';
                } else if (lastRsi6 > lastRsi12) {
                    rsiSignal = '多头增强';
                    rsiSignalColor = '#f5222d';
                } else if (lastRsi6 < lastRsi12) {
                    rsiSignal = '空头增强';
                    rsiSignalColor = '#52c41a';
                }
                
                rsiSignalElement.textContent = rsiSignal;
                rsiSignalElement.style.color = rsiSignalColor;
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
                padding: [10, 15],
                formatter: function(params) {
                    let res = `<div style="font-weight:600;margin-bottom:5px;">${params[0].axisValue}</div>`;
                    params.forEach(item => {
                        res += `<div style="margin:3px 0;">
                            <span style="color:${item.color};">●</span>
                            <span style="margin-left:8px;color:#262626;">${item.seriesName}:</span>
                            <span style="margin-left:5px;color:${item.color};font-weight:500;">${typeof item.value === 'number' ? item.value.toFixed(2) : item.value}</span>
                        </div>`;
                    });
                    return res;
                }
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
                data: dates,
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
            dataZoom: [
                {
                    type: 'inside',
                    start: 65,
                    end: 100
                },
                {
                    show: false,
                    type: 'slider',
                    start: 65,
                    end: 100
                }
            ],
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
                    data: rsi6,
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
                    data: rsi12,
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
                    data: rsi24,
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
        
        this.chartInstances.rsiChart.setOption(option);
        // 更新初始化标志
        this.chartsInitialized.rsiChart = true;
        } catch (error) {
            console.error('初始化RSI图表失败:', error);
        }
    }
    
    // 初始化KDJ图表
    async initKDJChart(klineData) {
        try {
            if (!klineData || !Array.isArray(klineData) || klineData.length === 0) {
                console.error('Invalid klineData for KDJ chart');
                return;
            }
            
            const chartDom = document.getElementById('kdjChart');
            if (!chartDom) {
                console.error('kdjChart element not found');
                return;
            }
            
            const echarts = await this.ensureEcharts();

            if (!this.chartInstances.kdjChart) {
                this.chartInstances.kdjChart = echarts.init(chartDom);
            }
            
            const closes = klineData.map(item => item[2]);
            const highs = klineData.map(item => item[4]);
            const lows = klineData.map(item => item[3]);
            
            if (closes.length < 9) {
                console.error('Insufficient data for KDJ calculation');
                return;
            }
            
            const kdj = this.calculateKDJ(highs, lows, closes, 9, 3, 3);
        
        // 计算KDJ信号
        const lastK = kdj.k[kdj.k.length - 1];
        const lastD = kdj.d[kdj.d.length - 1];
        const prevK = kdj.k[kdj.k.length - 2];
        const prevD = kdj.d[kdj.d.length - 2];
        
        let kdjSignal = '持币';
        let kdjSignalColor = '#8c8c8c';
        
        if (prevK < prevD && lastK > lastD && lastK < 30) {
            kdjSignal = '低位金叉';
            kdjSignalColor = '#f5222d';
        } else if (prevK > prevD && lastK < lastD && lastK > 70) {
            kdjSignal = '高位死叉';
            kdjSignalColor = '#52c41a';
        } else if (lastK > lastD) {
            kdjSignal = '多头态势';
            kdjSignalColor = '#f5222d';
        } else if (lastK < lastD) {
            kdjSignal = '空头态势';
            kdjSignalColor = '#52c41a';
        }

        const kValueElement = document.getElementById('kValue');
        const dValueElement = document.getElementById('dValue');
        const jValueElement = document.getElementById('jValue');
        const kdjSignalElement = document.getElementById('kdjSignal');

        if (kValueElement) kValueElement.textContent = lastK.toFixed(2);
        if (dValueElement) dValueElement.textContent = lastD.toFixed(2);
        if (jValueElement) jValueElement.textContent = kdj.j[kdj.j.length - 1].toFixed(2);
        if (kdjSignalElement) {
            kdjSignalElement.textContent = kdjSignal;
            kdjSignalElement.style.color = kdjSignalColor;
        }
            
            const dates = klineData.map(item => item[0]);
        
            const option = {
                tooltip: {
                    trigger: 'axis',
                    axisPointer: { type: 'cross' },
                    backgroundColor: 'rgba(255, 255, 255, 0.95)',
                    borderColor: '#d9d9d9',
                    borderWidth: 1,
                    textStyle: { color: '#262626', fontSize: 12 },
                    padding: [10, 15],
                    formatter: function(params) {
                        let res = `<div style="font-weight:600;margin-bottom:5px;">${params[0].axisValue}</div>`;
                        params.forEach(item => {
                            res += `<div style="margin:3px 0;">
                                <span style="color:${item.color};">●</span>
                                <span style="margin-left:8px;color:#262626;">${item.seriesName}:</span>
                                <span style="margin-left:5px;color:${item.color};font-weight:500;">${typeof item.value === 'number' ? item.value.toFixed(2) : item.value}</span>
                            </div>`;
                        });
                        return res;
                    }
                },
                legend: {
                    data: ['K', 'D', 'J'],
                    top: 5,
                    textStyle: { color: '#595959', fontSize: 11 }
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
                    data: dates,
                    axisLine: { lineStyle: { color: '#d9d9d9' } },
                    axisLabel: { color: '#8c8c8c', fontSize: 10, rotate: 45 }
                },
                yAxis: {
                    type: 'value',
                    min: 0,
                    max: 100,
                    axisLine: { show: false },
                    axisLabel: { color: '#8c8c8c', fontSize: 10 },
                    splitLine: { lineStyle: { color: '#f0f0f0', type: 'dashed' } }
                },
                dataZoom: [
                    {
                        type: 'inside',
                        start: 65,
                        end: 100
                    },
                    {
                        show: false,
                        type: 'slider',
                        start: 65,
                        end: 100
                    }
                ],
                series: [
                    {
                        name: 'K',
                        type: 'line',
                        data: kdj.k,
                        smooth: true,
                        showSymbol: false,
                        lineStyle: { width: 2, color: '#667eea' }
                    },
                    {
                        name: 'D',
                        type: 'line',
                        data: kdj.d,
                        smooth: true,
                        showSymbol: false,
                        lineStyle: { width: 2, color: '#f5222d' }
                    },
                    {
                        name: 'J',
                        type: 'line',
                        data: kdj.j,
                        smooth: true,
                        showSymbol: false,
                        lineStyle: { width: 2, color: '#52c41a' }
                    }
                ]
            };
            
            this.chartInstances.kdjChart.setOption(option);
            this.chartsInitialized.kdjChart = true;
        } catch (error) {
            console.error('初始化KDJ图表失败:', error);
        }
    }

    // 计算KDJ
    calculateKDJ(highs, lows, closes, n = 9, m1 = 3, m2 = 3) {
        const k = [];
        const d = [];
        const j = [];
        
        let prevK = 50;
        let prevD = 50;
        
        for (let i = 0; i < closes.length; i++) {
            if (i < n - 1) {
                k.push(50);
                d.push(50);
                j.push(50);
                continue;
            }
            
            let recentHigh = highs[i];
            let recentLow = lows[i];
            for (let l = 1; l < n; l++) {
                recentHigh = Math.max(recentHigh, highs[i - l]);
                recentLow = Math.min(recentLow, lows[i - l]);
            }
            
            const rsv = recentHigh === recentLow ? 50 : ((closes[i] - recentLow) / (recentHigh - recentLow)) * 100;
            const currentK = (rsv + (m1 - 1) * prevK) / m1;
            const currentD = (currentK + (m2 - 1) * prevD) / m2;
            const currentJ = 3 * currentK - 2 * currentD;
            
            k.push(currentK);
            d.push(currentD);
            j.push(currentJ);
            
            prevK = currentK;
            prevD = currentD;
        }
        
        return { k, d, j };
    }

    // 更新雷达图
    async updateRadarChart(technicalAnalyst, fundamentalAnalyst, sentimentAnalyst, riskManager) {
        try {
            const chartDom = document.getElementById('radarChart');
            if (!chartDom) {
                console.error('radarChart element not found');
                return;
            }
            
            const echarts = await this.ensureEcharts();

            // 只在图表不存在时创建，否则复用
            if (!this.chartInstances.radarChart) {
                this.chartInstances.radarChart = echarts.init(chartDom);
            }
            
            // 默认值，避免为空
            const techScore = technicalAnalyst?.result?.score || 5;
            const fundScore = fundamentalAnalyst?.result?.score || 5;
            const sentiScore = sentimentAnalyst?.result?.score || 5;
            const riskScore = riskManager?.result?.score || 5;
            
            const option = {
                radar: {
                    indicator: [
                        { name: '技术分析', max: 10 },
                        { name: '基本面分析', max: 10 },
                        { name: '市场情绪', max: 10 },
                        { name: '风险评估', max: 10 }
                    ],
                    splitArea: {
                        show: true,
                        areaStyle: {
                            color: ['#f0f5ff', '#fff0f5', '#f5fff0', '#fffbe6']
                        }
                    }
                },
                series: [
                    {
                        name: '分析师评分',
                        type: 'radar',
                        data: [
                            {
                                value: [techScore, fundScore, sentiScore, riskScore],
                                name: '综合评分',
                                areaStyle: {
                                    color: 'rgba(102, 126, 234, 0.3)'
                                },
                                lineStyle: {
                                    color: '#667eea',
                                    width: 2
                                },
                                itemStyle: {
                                    color: '#667eea'
                                }
                            }
                        ]
                    }
                ]
            };
            
            this.chartInstances.radarChart.setOption(option);
            this.chartsInitialized.radarChart = true;
        } catch (error) {
            console.error('更新雷达图失败:', error);
        }
    }
    
    // 更新趋势图
    async updateTrendChart(klineData) {
        try {
            if (!klineData || !Array.isArray(klineData) || klineData.length === 0) {
                console.error('Invalid klineData for trend chart');
                return;
            }
            
            const chartDom = document.getElementById('trendChart');
            if (!chartDom) {
                console.error('trendChart element not found');
                return;
            }
            
            const echarts = await this.ensureEcharts();

            // 只在图表不存在时创建，否则复用
            if (!this.chartInstances.trendChart) {
                this.chartInstances.trendChart = echarts.init(chartDom);
            }
            
            const dates = klineData.map(item => item[0]);
            const closes = klineData.map(item => item[2]);
            
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
                        let res = `<div style="font-weight:600;margin-bottom:5px;">${params[0].axisValue}</div>`;
                        params.forEach(item => {
                            res += `<div style="margin:3px 0;">
                                <span style="color:${item.color};">●</span>
                                <span style="margin-left:8px;color:#262626;">${item.seriesName}:</span>
                                <span style="margin-left:5px;color:${item.color};font-weight:500;">${typeof item.value === 'number' ? item.value.toFixed(2) : item.value}</span>
                            </div>`;
                        });
                        return res;
                    }
                },
                grid: {
                    left: '8%',
                    right: '5%',
                    top: '15%',
                    bottom: '15%',
                    containLabel: true
                },
                xAxis: {
                    type: 'category',
                    data: dates,
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
                dataZoom: [
                    {
                        type: 'inside',
                        start: 65,
                        end: 100
                    },
                    {
                        show: false,
                        type: 'slider',
                        start: 65,
                        end: 100
                    }
                ],
                series: [
                    {
                        name: '价格走势',
                        type: 'line',
                        data: closes,
                        smooth: true,
                        symbol: 'circle',
                        symbolSize: 4,
                        lineStyle: {
                            width: 2,
                            color: '#667eea'
                        },
                        areaStyle: {
                            color: {
                                type: 'linear',
                                x: 0,
                                y: 0,
                                x2: 0,
                                y2: 1,
                                colorStops: [{
                                    offset: 0, color: 'rgba(102, 126, 234, 0.3)' // 起始颜色
                                }, {
                                    offset: 1, color: 'rgba(102, 126, 234, 0)' // 结束颜色
                                }]
                            }
                        },
                        itemStyle: {
                            color: '#667eea'
                        }
                    }
                ]
            };
            
            this.chartInstances.trendChart.setOption(option);
            this.chartsInitialized.trendChart = true;
        } catch (error) {
            console.error('更新趋势图失败:', error);
        }
    }
    
    // 初始化分配图
    async initAllocationChart() {
        try {
            const chartDom = document.getElementById('allocationChart');
            if (!chartDom) {
                console.error('allocationChart element not found');
                return;
            }
            
            const echarts = await this.ensureEcharts();

            // 只在图表不存在时创建，否则复用
            if (!this.chartInstances.allocationChart) {
                this.chartInstances.allocationChart = echarts.init(chartDom);
            }
            
            const positionElement = document.getElementById('positionValue');
            const position = positionElement ? positionElement.textContent : '--';
            const positionNum = position !== '--' ? parseInt(position) : 50;
            
            const suggestedPositionElement = document.getElementById('suggestedPosition');
            if (suggestedPositionElement) {
                suggestedPositionElement.textContent = position;
            }
            
            const riskControlElement = document.getElementById('riskControl');
            if (riskControlElement) {
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
            }
            
            const currentPriceElement = document.getElementById('chartCurrentPrice');
            const stopLossElement = document.getElementById('stopLoss');
            if (stopLossElement && currentPriceElement) {
                const currentPrice = currentPriceElement.textContent;
                if (currentPrice !== '--') {
                    const price = parseFloat(currentPrice);
                    const stopLossPrice = (price * 0.95).toFixed(2);
                    stopLossElement.textContent = stopLossPrice;
                    stopLossElement.style.color = '#faad14';
                } else {
                    stopLossElement.textContent = '--';
                }
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
        
        this.chartInstances.allocationChart.setOption(option);
        // 更新初始化标志
        this.chartsInitialized.allocationChart = true;
        } catch (error) {
            console.error('初始化仓位配置图表失败:', error);
        }
    }
    
    // 初始化分析图表
    async initAnalysisCharts(klineData) {
        // 保存K线数据供后续使用
        this.currentKlineData = klineData;
        
        // 立即初始化分配图，因为它依赖于DOM元素的内容
        await this.initAllocationChart();
    }
    
    // 计算MACD
    calculateMACD(closes, shortPeriod, longPeriod, signalPeriod) {
        const emaShort = this.calculateEMA(closes, shortPeriod);
        const emaLong = this.calculateEMA(closes, longPeriod);
        const dif = emaShort.map((val, idx) => val - emaLong[idx]);
        const dea = this.calculateEMA(dif, signalPeriod);
        const macd = dif.map((val, idx) => (val - dea[idx]) * 2);
        
        return { dif, dea, macd };
    }
    
    // 计算MA
    calculateMA(data, period) {
        const ma = [];
        for (let i = 0; i < data.length; i++) {
            if (i < period - 1) {
                ma.push(null);
                continue;
            }
            let sum = 0;
            for (let j = 0; j < period; j++) {
                sum += data[i - j];
            }
            ma.push(parseFloat((sum / period).toFixed(3)));
        }
        return ma;
    }

    // 计算BOLL
    calculateBOLL(data, period = 20, stdDevMultiplier = 2) {
        const mid = this.calculateMA(data, period);
        const upper = [];
        const lower = [];

        for (let i = 0; i < data.length; i++) {
            if (mid[i] === null) {
                upper.push(null);
                lower.push(null);
                continue;
            }

            let sumSquareDiff = 0;
            for (let j = 0; j < period; j++) {
                sumSquareDiff += Math.pow(data[i - j] - mid[i], 2);
            }
            const stdDev = Math.sqrt(sumSquareDiff / period);
            upper.push(parseFloat((mid[i] + stdDevMultiplier * stdDev).toFixed(3)));
            lower.push(parseFloat((mid[i] - stdDevMultiplier * stdDev).toFixed(3)));
        }

        return { mid, upper, lower };
    }

    // 计算EMA
    calculateEMA(data, period) {
        const k = 2 / (period + 1);
        const ema = [data[0]];
        
        for (let i = 1; i < data.length; i++) {
            ema.push(data[i] * k + ema[i - 1] * (1 - k));
        }
        
        return ema;
    }
    
    // 计算RSI
    calculateRSI(closes, period) {
        const rsi = [];
        const changes = [];
        
        for (let i = 1; i < closes.length; i++) {
            changes.push(closes[i] - closes[i - 1]);
        }
        
        let avgGain = 0;
        let avgLoss = 0;
        
        for (let i = 0; i < changes.length; i++) {
            if (changes[i] > 0) {
                avgGain += changes[i];
            } else {
                avgLoss -= changes[i];
            }
            
            if (i < period - 1) {
                rsi.push(50);
                continue;
            }
            
            if (i === period - 1) {
                avgGain = avgGain / period;
                avgLoss = avgLoss / period;
            } else {
                const prevGain = avgGain;
                const prevLoss = avgLoss;
                
                if (changes[i] > 0) {
                    avgGain = (prevGain * (period - 1) + changes[i]) / period;
                    avgLoss = (prevLoss * (period - 1)) / period;
                } else {
                    avgGain = (prevGain * (period - 1)) / period;
                    avgLoss = (prevLoss * (period - 1) - changes[i]) / period;
                }
            }
            
            if (avgLoss === 0) {
                rsi.push(100);
            } else {
                const rs = avgGain / avgLoss;
                rsi.push(100 - (100 / (1 + rs)));
            }
        }
        
        rsi.unshift(50);
        
        return rsi;
    }
    
    // 格式化成交量
    formatVolume(volume) {
        if (volume >= 100000000) {
            return (volume / 100000000).toFixed(2) + '亿';
        } else if (volume >= 10000) {
            return (volume / 10000).toFixed(2) + '万';
        }
        return volume.toFixed(0);
    }

    formatAmount(amount) {
        if (amount >= 100000000) {
            return (amount / 100000000).toFixed(2) + '亿';
        } else if (amount >= 10000) {
            return (amount / 10000).toFixed(2) + '万';
        }
        return amount.toFixed(0);
    }
    
    // 清除所有图表实例
    clearCharts() {
        for (const chartName in this.chartInstances) {
            if (this.chartInstances[chartName]) {
                this.chartInstances[chartName].dispose();
                this.chartInstances[chartName] = null;
            }
        }
        
        // 重置初始化标志
        for (const chartName in this.chartsInitialized) {
            this.chartsInitialized[chartName] = false;
        }
        
        // 重置当前K线数据
        this.currentKlineData = null;
    }
    
    // 更新图表信息
    updateChartInfo(stockData) {
        try {
            if (!stockData) return;
            
            const stockNameElement = document.getElementById('chartStockName');
            const stockCodeElement = document.getElementById('chartStockCode');
            const currentPriceElement = document.getElementById('chartCurrentPrice');
            const changeElement = document.getElementById('chartChange');
            const changePercentElement = document.getElementById('chartChangePercent');
            const volumeElement = document.getElementById('chartVolume');
            const amountElement = document.getElementById('chartAmount');
            
            if (stockNameElement) stockNameElement.textContent = stockData.stock_name || '--';
            if (stockCodeElement) stockCodeElement.textContent = stockData.stock_code || '--';
            if (currentPriceElement) {
                currentPriceElement.textContent = stockData.current_price || '--';
            }

            const changeValue = Number(stockData.change);
            const changePercentValue = Number(stockData.change_percent);
            const currentPriceValue = Number(stockData.current_price);

            if (changeElement) {
                changeElement.textContent = Number.isFinite(changeValue) ? changeValue.toFixed(2) : (stockData.change || '--');
                changeElement.classList.toggle('rise', Number.isFinite(changeValue) && changeValue > 0);
                changeElement.classList.toggle('fall', Number.isFinite(changeValue) && changeValue < 0);
            }

            if (changePercentElement) {
                changePercentElement.textContent = Number.isFinite(changePercentValue) ? `${changePercentValue.toFixed(2)}%` : (stockData.change_percent || '--');
                changePercentElement.classList.toggle('rise', Number.isFinite(changePercentValue) && changePercentValue > 0);
                changePercentElement.classList.toggle('fall', Number.isFinite(changePercentValue) && changePercentValue < 0);
            }

            if (currentPriceElement) {
                currentPriceElement.classList.toggle('rise', Number.isFinite(changeValue) ? changeValue > 0 : false);
                currentPriceElement.classList.toggle('fall', Number.isFinite(changeValue) ? changeValue < 0 : false);
            }

            if (volumeElement) {
                const volumeValue = Number(stockData.volume);
                volumeElement.textContent = Number.isFinite(volumeValue) ? this.formatVolume(volumeValue) : (stockData.volume || '--');
            }

            if (amountElement) {
                const amountValue = Number(stockData.amount);
                amountElement.textContent = Number.isFinite(amountValue) ? this.formatAmount(amountValue) : (stockData.amount || '--');
            }

            if (Number.isFinite(currentPriceValue)) {
                const stopLossElement = document.getElementById('stopLoss');
                if (stopLossElement) {
                    stopLossElement.textContent = (currentPriceValue * 0.95).toFixed(2);
                    stopLossElement.style.color = '#faad14';
                }
            }
        } catch (error) {
            console.error('更新图表信息失败:', error);
        }
    }
}

const chartManager = new ChartManager();
window.chartManager = chartManager;
