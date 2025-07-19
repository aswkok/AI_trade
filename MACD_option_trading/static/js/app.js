// MACD Options Trading System Web Display

// Global variables
let selectedSymbol = '';
let updateInterval = 5000;  // 5 seconds by default
let priceChart = null;
let macdChart = null;
let isUpdating = true;
let updateTimer = null;

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    // Set up event listeners
    setupEventListeners();
    
    // Update current time
    updateCurrentTime();
    setInterval(updateCurrentTime, 1000);
    
    // Load initial data
    loadInitialData();
    
    // Set up auto-refresh
    startAutoRefresh();
});

// Set up event listeners
function setupEventListeners() {
    // Symbol selection
    document.querySelectorAll('.symbol-item').forEach(item => {
        item.addEventListener('click', function(e) {
            e.preventDefault();
            selectedSymbol = this.getAttribute('data-symbol');
            document.getElementById('symbolDropdown').textContent = selectedSymbol;
            loadSymbolData(selectedSymbol);
        });
    });
    
    // Refresh button
    document.getElementById('refreshButton').addEventListener('click', function() {
        refreshData();
    });
    
    // View all messages button
    document.getElementById('viewAllMessages').addEventListener('click', function() {
        document.querySelector('a[href="#messages"]').click();
    });
    
    // Clear messages button
    document.getElementById('clearMessages').addEventListener('click', function() {
        clearMessages();
    });
    
    // Message filtering
    document.getElementById('applyFilter').addEventListener('click', function() {
        loadMessages();
    });
    
    document.getElementById('clearFilter').addEventListener('click', function() {
        document.getElementById('messageFilter').value = '';
        loadMessages();
    });
    
    // Message type filters
    document.getElementById('showAll').addEventListener('click', function() {
        document.getElementById('messageFilter').value = '';
        loadMessages();
    });
    
    document.getElementById('showBullish').addEventListener('click', function() {
        document.getElementById('messageFilter').value = 'BULLISH';
        loadMessages();
    });
    
    document.getElementById('showBearish').addEventListener('click', function() {
        document.getElementById('messageFilter').value = 'BEARISH';
        loadMessages();
    });
    
    document.getElementById('showTrades').addEventListener('click', function() {
        document.getElementById('messageFilter').value = 'TRADE';
        loadMessages();
    });
    
    // Tab change event
    document.querySelectorAll('a[data-bs-toggle="tab"]').forEach(tab => {
        tab.addEventListener('shown.bs.tab', function(e) {
            const targetId = e.target.getAttribute('href').substring(1);
            if (targetId === 'history' && selectedSymbol) {
                loadHistoryData(selectedSymbol);
            } else if (targetId === 'trades') {
                loadTradeHistory();
            } else if (targetId === 'messages') {
                loadMessages();
            }
        });
    });
}

// Update current time
function updateCurrentTime() {
    const now = new Date();
    document.getElementById('currentTime').textContent = now.toLocaleString();
}

// Load initial data
function loadInitialData() {
    fetch('/api/data')
        .then(response => response.json())
        .then(data => {
            // Set selected symbol if available
            if (data.symbols && data.symbols.length > 0) {
                selectedSymbol = data.symbols[0];
                document.getElementById('symbolDropdown').textContent = selectedSymbol;
                loadSymbolData(selectedSymbol);
            }
            
            // Update recent messages
            updateRecentMessages(data.system_messages);
            
            // Update trade history
            updateTradeHistory(data.trade_history);
        })
        .catch(error => console.error('Error loading initial data:', error));
}

// Load symbol data
function loadSymbolData(symbol) {
    fetch(`/api/quotes/${symbol}`)
        .then(response => response.json())
        .then(data => {
            updateQuoteDisplay(symbol, data);
        })
        .catch(error => console.error(`Error loading data for ${symbol}:`, error));
}

// Load history data and update charts
function loadHistoryData(symbol) {
    fetch(`/api/history/${symbol}?limit=100`)
        .then(response => response.json())
        .then(data => {
            updateHistoryTable(data);
            updateCharts(data);
        })
        .catch(error => console.error(`Error loading history for ${symbol}:`, error));
}

// Load trade history
function loadTradeHistory() {
    fetch('/api/trades?limit=100')
        .then(response => response.json())
        .then(data => {
            updateTradeHistory(data);
        })
        .catch(error => console.error('Error loading trade history:', error));
}

// Load system messages
function loadMessages() {
    const filter = document.getElementById('messageFilter').value;
    fetch(`/api/messages?limit=100&filter=${filter}`)
        .then(response => response.json())
        .then(data => {
            updateMessagesTable(data);
        })
        .catch(error => console.error('Error loading messages:', error));
}

// Clear all system messages
function clearMessages() {
    fetch('/api/clear_messages', {
        method: 'POST'
    })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                loadMessages();
                // Also update recent messages on the quotes tab
                updateRecentMessages([]);
            }
        })
        .catch(error => console.error('Error clearing messages:', error));
}

// Update quote display
function updateQuoteDisplay(symbol, data) {
    const quoteDataElement = document.getElementById('quoteData');
    const macdDataElement = document.getElementById('macdData');
    
    if (!data || data.error) {
        quoteDataElement.innerHTML = `<div class="alert alert-warning">No data available for ${symbol}</div>`;
        macdDataElement.innerHTML = `<div class="alert alert-warning">No MACD data available for ${symbol}</div>`;
        return;
    }
    
    // Format timestamp
    let timestampStr = 'Unknown';
    if (data.timestamp) {
        const timestamp = new Date(data.timestamp);
        timestampStr = timestamp.toLocaleString();
    }
    
    // Update quote data
    let quoteHtml = `
        <div class="quote-timestamp">Last updated: ${timestampStr}</div>
        <div class="price-info">
            <div class="price-box bid">
                <div class="price-label">Bid</div>
                <div class="price-value bid-price">$${data.bid ? data.bid.toFixed(2) : 'N/A'}</div>
            </div>
            <div class="price-box ask">
                <div class="price-label">Ask</div>
                <div class="price-value ask-price">$${data.ask ? data.ask.toFixed(2) : 'N/A'}</div>
            </div>`;
            
    if (data.bid && data.ask) {
        const spread = data.ask - data.bid;
        const spreadPct = (spread / data.bid) * 100;
        quoteHtml += `
            <div class="price-box spread">
                <div class="price-label">Spread</div>
                <div class="price-value">$${spread.toFixed(4)} (${spreadPct.toFixed(2)}%)</div>
            </div>`;
    }
    
    quoteHtml += `</div>`;
    
    // Add volume if available
    if (data.volume) {
        quoteHtml += `<div class="mt-3">Volume: ${data.volume.toLocaleString()}</div>`;
    }
    
    quoteDataElement.innerHTML = quoteHtml;
    
    // Update MACD data
    if (data.MACD !== undefined && data.signal !== undefined) {
        const macdPosition = data.MACD_position || (data.MACD > data.signal ? 'ABOVE' : 'BELOW');
        const positionClass = macdPosition === 'ABOVE' ? 'macd-above' : 'macd-below';
        
        let signalText = 'NEUTRAL';
        let signalClass = 'neutral-signal';
        
        if (data.crossover) {
            signalText = 'BULLISH SIGNAL: BUY';
            signalClass = 'bullish-signal';
        } else if (data.crossunder) {
            signalText = 'BEARISH SIGNAL: SELL';
            signalClass = 'bearish-signal';
        } else if (macdPosition === 'ABOVE') {
            signalText = 'CURRENT SIGNAL: HOLD LONG';
            signalClass = 'bullish-signal';
        } else if (macdPosition === 'BELOW') {
            signalText = 'CURRENT SIGNAL: HOLD SHORT';
            signalClass = 'bearish-signal';
        }
        
        let macdHtml = `
            <div class="macd-box">
                <div class="row">
                    <div class="col-md-4">
                        <div>MACD</div>
                        <div class="macd-value ${positionClass}">${data.MACD.toFixed(6)}</div>
                    </div>
                    <div class="col-md-4">
                        <div>Signal</div>
                        <div class="macd-value">${data.signal.toFixed(6)}</div>
                    </div>
                    <div class="col-md-4">
                        <div>Histogram</div>
                        <div class="macd-value ${data.histogram > 0 ? 'macd-above' : 'macd-below'}">${data.histogram.toFixed(6)}</div>
                    </div>
                </div>
                <div class="mt-3">
                    <div>Current Position: MACD is <span class="${positionClass}">${macdPosition}</span> signal line</div>
                </div>
                <div class="signal-box ${signalClass} mt-3">
                    ${signalText}
                </div>
            </div>`;
        
        macdDataElement.innerHTML = macdHtml;
    } else {
        macdDataElement.innerHTML = `<div class="alert alert-warning">No MACD data available for ${symbol}</div>`;
    }
}

// Update history table
function updateHistoryTable(data) {
    const tableBody = document.querySelector('#historyTable tbody');
    tableBody.innerHTML = '';
    
    data.reverse().forEach(item => {
        const row = document.createElement('tr');
        
        // Format timestamp
        let timestampStr = 'Unknown';
        if (item.timestamp) {
            const timestamp = new Date(item.timestamp);
            timestampStr = timestamp.toLocaleString();
        }
        
        // Create cells
        const timestampCell = document.createElement('td');
        timestampCell.textContent = timestampStr;
        
        const bidCell = document.createElement('td');
        bidCell.textContent = item.bid ? `$${item.bid.toFixed(2)}` : 'N/A';
        bidCell.classList.add('bid-price');
        
        const askCell = document.createElement('td');
        askCell.textContent = item.ask ? `$${item.ask.toFixed(2)}` : 'N/A';
        askCell.classList.add('ask-price');
        
        const midCell = document.createElement('td');
        midCell.textContent = item.mid ? `$${item.mid.toFixed(2)}` : 'N/A';
        
        const macdCell = document.createElement('td');
        macdCell.textContent = item.MACD !== undefined ? item.MACD.toFixed(6) : 'N/A';
        if (item.MACD !== undefined && item.signal !== undefined) {
            macdCell.classList.add(item.MACD > item.signal ? 'macd-above' : 'macd-below');
        }
        
        const signalCell = document.createElement('td');
        signalCell.textContent = item.signal !== undefined ? item.signal.toFixed(6) : 'N/A';
        
        const histogramCell = document.createElement('td');
        histogramCell.textContent = item.histogram !== undefined ? item.histogram.toFixed(6) : 'N/A';
        if (item.histogram !== undefined) {
            histogramCell.classList.add(item.histogram > 0 ? 'macd-above' : 'macd-below');
        }
        
        const positionCell = document.createElement('td');
        if (item.MACD_position) {
            positionCell.textContent = item.MACD_position;
            positionCell.classList.add(item.MACD_position === 'ABOVE' ? 'macd-above' : 'macd-below');
        } else if (item.MACD !== undefined && item.signal !== undefined) {
            const position = item.MACD > item.signal ? 'ABOVE' : 'BELOW';
            positionCell.textContent = position;
            positionCell.classList.add(position === 'ABOVE' ? 'macd-above' : 'macd-below');
        } else {
            positionCell.textContent = 'N/A';
        }
        
        // Add cells to row
        row.appendChild(timestampCell);
        row.appendChild(bidCell);
        row.appendChild(askCell);
        row.appendChild(midCell);
        row.appendChild(macdCell);
        row.appendChild(signalCell);
        row.appendChild(histogramCell);
        row.appendChild(positionCell);
        
        // Add row to table
        tableBody.appendChild(row);
    });
}

// Update charts
function updateCharts(data) {
    // Prepare data for charts
    const timestamps = [];
    const prices = [];
    const macdValues = [];
    const signalValues = [];
    const histogramValues = [];
    
    data.forEach(item => {
        if (item.timestamp) {
            const timestamp = new Date(item.timestamp);
            timestamps.push(timestamp);
            
            // Price data (use mid price if available, otherwise calculate from bid/ask)
            if (item.mid) {
                prices.push(item.mid);
            } else if (item.bid && item.ask) {
                prices.push((item.bid + item.ask) / 2);
            } else {
                prices.push(null);
            }
            
            // MACD data
            macdValues.push(item.MACD !== undefined ? item.MACD : null);
            signalValues.push(item.signal !== undefined ? item.signal : null);
            histogramValues.push(item.histogram !== undefined ? item.histogram : null);
        }
    });
    
    // Create price chart
    if (priceChart) {
        priceChart.destroy();
    }
    
    const priceCtx = document.getElementById('priceChart').getContext('2d');
    priceChart = new Chart(priceCtx, {
        type: 'line',
        data: {
            labels: timestamps,
            datasets: [{
                label: 'Price',
                data: prices,
                borderColor: 'rgba(54, 162, 235, 1)',
                backgroundColor: 'rgba(54, 162, 235, 0.2)',
                borderWidth: 2,
                pointRadius: 1,
                fill: true
            }]
        },
        options: {
            responsive: true,
            plugins: {
                title: {
                    display: true,
                    text: `${selectedSymbol} Price Chart`
                },
                tooltip: {
                    mode: 'index',
                    intersect: false
                }
            },
            scales: {
                x: {
                    type: 'time',
                    time: {
                        unit: 'minute'
                    },
                    title: {
                        display: true,
                        text: 'Time'
                    }
                },
                y: {
                    title: {
                        display: true,
                        text: 'Price ($)'
                    }
                }
            }
        }
    });
    
    // Create MACD chart
    if (macdChart) {
        macdChart.destroy();
    }
    
    const macdCtx = document.getElementById('macdChart').getContext('2d');
    macdChart = new Chart(macdCtx, {
        type: 'line',
        data: {
            labels: timestamps,
            datasets: [
                {
                    label: 'MACD',
                    data: macdValues,
                    borderColor: 'rgba(54, 162, 235, 1)',
                    backgroundColor: 'rgba(54, 162, 235, 0.2)',
                    borderWidth: 2,
                    pointRadius: 1,
                    yAxisID: 'y'
                },
                {
                    label: 'Signal',
                    data: signalValues,
                    borderColor: 'rgba(255, 99, 132, 1)',
                    backgroundColor: 'rgba(255, 99, 132, 0.2)',
                    borderWidth: 2,
                    pointRadius: 1,
                    yAxisID: 'y'
                },
                {
                    label: 'Histogram',
                    data: histogramValues,
                    type: 'bar',
                    backgroundColor: function(context) {
                        const index = context.dataIndex;
                        const value = context.dataset.data[index];
                        return value >= 0 ? 'rgba(40, 167, 69, 0.5)' : 'rgba(220, 53, 69, 0.5)';
                    },
                    yAxisID: 'y1'
                }
            ]
        },
        options: {
            responsive: true,
            plugins: {
                title: {
                    display: true,
                    text: `${selectedSymbol} MACD Chart`
                },
                tooltip: {
                    mode: 'index',
                    intersect: false
                }
            },
            scales: {
                x: {
                    type: 'time',
                    time: {
                        unit: 'minute'
                    },
                    title: {
                        display: true,
                        text: 'Time'
                    }
                },
                y: {
                    title: {
                        display: true,
                        text: 'MACD & Signal'
                    },
                    position: 'left'
                },
                y1: {
                    title: {
                        display: true,
                        text: 'Histogram'
                    },
                    position: 'right',
                    grid: {
                        drawOnChartArea: false
                    }
                }
            }
        }
    });
}

// Update trade history
function updateTradeHistory(data) {
    const tableBody = document.querySelector('#tradesTable tbody');
    tableBody.innerHTML = '';
    
    data.reverse().forEach(trade => {
        const row = document.createElement('tr');
        
        // Format timestamp
        let timestampStr = 'Unknown';
        if (trade.timestamp) {
            const timestamp = new Date(trade.timestamp);
            timestampStr = timestamp.toLocaleString();
        }
        
        // Create cells
        const timestampCell = document.createElement('td');
        timestampCell.textContent = timestampStr;
        
        const symbolCell = document.createElement('td');
        symbolCell.textContent = trade.symbol || 'N/A';
        
        const actionCell = document.createElement('td');
        actionCell.textContent = trade.action || 'N/A';
        if (trade.action) {
            if (trade.action.toUpperCase().includes('BUY')) {
                actionCell.classList.add('bullish');
            } else if (trade.action.toUpperCase().includes('SELL')) {
                actionCell.classList.add('bearish');
            }
        }
        
        const quantityCell = document.createElement('td');
        quantityCell.textContent = trade.quantity || 'N/A';
        
        const priceCell = document.createElement('td');
        priceCell.textContent = trade.price ? `$${trade.price.toFixed(2)}` : 'N/A';
        
        const strategyCell = document.createElement('td');
        strategyCell.textContent = trade.strategy || 'N/A';
        
        // Add cells to row
        row.appendChild(timestampCell);
        row.appendChild(symbolCell);
        row.appendChild(actionCell);
        row.appendChild(quantityCell);
        row.appendChild(priceCell);
        row.appendChild(strategyCell);
        
        // Add row to table
        tableBody.appendChild(row);
    });
}

// Update recent messages
function updateRecentMessages(messages) {
    const tableBody = document.querySelector('#recentMessagesTable tbody');
    tableBody.innerHTML = '';
    
    // Take the 5 most recent messages
    const recentMessages = messages.slice(-5).reverse();
    
    recentMessages.forEach(message => {
        const row = document.createElement('tr');
        
        // Split timestamp and message content
        const parts = message.split(' - ', 2);
        const timestamp = parts[0];
        const content = parts.length > 1 ? parts[1] : message;
        
        // Create timestamp cell
        const timestampCell = document.createElement('td');
        timestampCell.textContent = timestamp;
        timestampCell.style.whiteSpace = 'nowrap';
        
        // Create message cell with appropriate styling
        const messageCell = document.createElement('td');
        messageCell.textContent = content;
        
        if (content.includes('BULLISH') || content.includes('BUY')) {
            messageCell.classList.add('bullish');
        } else if (content.includes('BEARISH') || content.includes('SELL')) {
            messageCell.classList.add('bearish');
        } else if (content.includes('TRADE')) {
            messageCell.classList.add('trade');
        }
        
        // Add cells to row
        row.appendChild(timestampCell);
        row.appendChild(messageCell);
        
        // Add row to table
        tableBody.appendChild(row);
    });
}

// Update messages table
function updateMessagesTable(messages) {
    const tableBody = document.querySelector('#messagesTable tbody');
    tableBody.innerHTML = '';
    
    // Update message count
    document.getElementById('messageCount').textContent = messages.length;
    
    messages.forEach(message => {
        const row = document.createElement('tr');
        
        // Split timestamp and message content
        const parts = message.split(' - ', 2);
        const timestamp = parts[0];
        const content = parts.length > 1 ? parts[1] : message;
        
        // Create timestamp cell
        const timestampCell = document.createElement('td');
        timestampCell.textContent = timestamp;
        timestampCell.style.whiteSpace = 'nowrap';
        
        // Create message cell with appropriate styling
        const messageCell = document.createElement('td');
        messageCell.textContent = content;
        
        if (content.includes('BULLISH') || content.includes('BUY')) {
            messageCell.classList.add('bullish');
        } else if (content.includes('BEARISH') || content.includes('SELL')) {
            messageCell.classList.add('bearish');
        } else if (content.includes('TRADE')) {
            messageCell.classList.add('trade');
        }
        
        // Add cells to row
        row.appendChild(timestampCell);
        row.appendChild(messageCell);
        
        // Add row to table
        tableBody.appendChild(row);
    });
}

// Refresh all data
function refreshData() {
    if (selectedSymbol) {
        loadSymbolData(selectedSymbol);
        
        // If on history tab, refresh history data
        if (document.querySelector('#history').classList.contains('active')) {
            loadHistoryData(selectedSymbol);
        }
    }
    
    // If on trades tab, refresh trade history
    if (document.querySelector('#trades').classList.contains('active')) {
        loadTradeHistory();
    }
    
    // If on messages tab, refresh messages
    if (document.querySelector('#messages').classList.contains('active')) {
        loadMessages();
    }
    
    // Always refresh recent messages
    fetch('/api/messages?limit=5')
        .then(response => response.json())
        .then(data => {
            updateRecentMessages(data);
        })
        .catch(error => console.error('Error loading recent messages:', error));
}

// Start auto-refresh
function startAutoRefresh() {
    if (updateTimer) {
        clearInterval(updateTimer);
    }
    
    updateTimer = setInterval(() => {
        if (isUpdating) {
            refreshData();
        }
    }, updateInterval);
}
