// Configuration
const API_BASE = '/api';
const REPORTS_BASE = '/reports';

// DOM Elements
const reportViewer = document.getElementById('report-viewer-content');
const reportTypeLabel = document.getElementById('viewing-report-type');
const reportsList = document.getElementById('reports-list');
const triggerBtn = document.getElementById('trigger-btn');
const triggerLoadingIcon = document.getElementById('trigger-loading-icon');
const viewLatestBtn = document.getElementById('view-latest-btn');

// Watchlist Elements
const watchlistDialog = document.getElementById('watchlist-dialog');
const stockSearchInput = document.getElementById('stock-search-input');
const searchResults = document.getElementById('search-results');
const watchlistItems = document.getElementById('watchlist-items');

// Schedule Elements
const scheduleDialog = document.getElementById('schedule-dialog');
const scheduleTimeInput = document.getElementById('schedule-time-input');
const addScheduleBtn = document.getElementById('add-schedule-btn');
const scheduleItems = document.getElementById('schedule-items');

// Kakao Elements
const startKakaoAuthBtn = document.getElementById('start-kakao-auth-btn');
const redirectUrlLabel = document.getElementById('kakao-redirect-url-label');

// State
let activeReportFile = 'index.html';

// ------------------------------------------------------------
// 1. Report Serving & Archives
// ------------------------------------------------------------

async function loadReport(fileName) {
    reportViewer.innerHTML = `<div class="text-center py-24 text-slate-500 text-sm">리포트 로드 중...</div>`;
    activeReportFile = fileName;
    
    if (fileName === 'index.html') {
        reportTypeLabel.textContent = '(최신 리포트)';
    } else {
        // extract time info from report_20260628_1540.html
        const match = fileName.match(/report_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})\.html/);
        if (match) {
            reportTypeLabel.textContent = `(${match[1]}-${match[2]}-${match[3]} ${match[4]}:${match[5]} 리포트)`;
        } else {
            reportTypeLabel.textContent = `(${fileName})`;
        }
    }

    try {
        const response = await fetch(`${REPORTS_BASE}/${fileName}?t=${Date.now()}`);
        if (!response.ok) {
            throw new Error('리포트 파일이 없거나 아직 첫 리포트가 발행되지 않았습니다.');
        }
        const html = await response.text();
        
        // Inject only the body portion or extract inside body to prevent head conflicts
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');
        const content = doc.querySelector('body')?.innerHTML || html;
        
        reportViewer.innerHTML = content;
        
        // Setup details (accordion) event listeners for accordion interactive state
        const detailsElements = reportViewer.querySelectorAll('details');
        detailsElements.forEach(detail => {
            detail.classList.add('glass', 'rounded-2xl', 'overflow-hidden', 'border', 'border-slate-800', 'p-4', 'mb-3');
            // Check list styling inside inject context
        });
    } catch (error) {
        reportViewer.innerHTML = `
            <div class="text-center py-16 px-6 glass rounded-2xl">
                <p class="text-slate-400 text-sm mb-4">${error.message}</p>
                <p class="text-xs text-slate-500">
                    스케줄러 동작 시점까지 기다리시거나 좌측 상단의 <strong>[보고서 즉시 발행]</strong> 버튼을 통해 수동 발행해 주세요.
                </p>
            </div>
        `;
    }
}

async function loadArchives() {
    try {
        const response = await fetch(`${API_BASE}/reports`);
        if (!response.ok) throw new Error('히스토리 로드 실패');
        const reports = await response.json();
        
        if (reports.length === 0) {
            reportsList.innerHTML = `<div class="text-center py-8 text-xs text-slate-500">생성된 보고서 기록이 없습니다.</div>`;
            return;
        }

        reportsList.innerHTML = reports.map(r => {
            const isActive = activeReportFile === r.file_name;
            const timeStr = r.created_at.split('.')[0].substring(5, 16).replace('T', ' '); // MM-DD HH:MM
            return `
                <button onclick="loadReport('${r.file_name}')" class="w-full text-left px-4 py-3 rounded-xl text-xs flex justify-between items-center transition duration-150 ${
                    isActive 
                    ? 'bg-indigo-900/30 text-indigo-300 font-semibold border border-indigo-700/50' 
                    : 'bg-slate-900/40 text-slate-300 hover:bg-slate-900/80 border border-transparent'
                }">
                    <span>${r.report_title}</span>
                    <span class="text-[10px] text-slate-500">${timeStr}</span>
                </button>
            `;
        }).join('');
    } catch (err) {
        reportsList.innerHTML = `<div class="text-center py-8 text-xs text-red-400">에러: ${err.message}</div>`;
    }
}

// ------------------------------------------------------------
// 2. Watchlist Management
// ------------------------------------------------------------

async function loadWatchlist() {
    try {
        const response = await fetch(`${API_BASE}/watchlist`);
        if (!response.ok) throw new Error();
        const list = await response.json();
        
        if (list.length === 0) {
            watchlistItems.innerHTML = `<p class="text-center text-xs text-slate-500 py-4">추가된 종목이 없습니다.</p>`;
            return;
        }

        watchlistItems.innerHTML = list.map(item => `
            <div class="flex justify-between items-center bg-slate-900/60 border border-slate-800 px-4 py-3 rounded-2xl text-sm">
                <div>
                    <span class="font-semibold text-slate-200">${item.name}</span>
                    <span class="text-[10px] text-slate-500 uppercase ml-1.5">${item.market} • ${item.ticker}</span>
                </div>
                <button onclick="deleteStock(${item.id})" class="text-slate-500 hover:text-rose-400 text-xs px-2 py-1 transition duration-150">삭제</button>
            </div>
        `).join('');
    } catch (err) {
        watchlistItems.innerHTML = `<p class="text-center text-xs text-red-400 py-4">관심종목을 불러올 수 없습니다.</p>`;
    }
}

// Setup search debouncing
let searchTimeout = null;
stockSearchInput.addEventListener('input', (e) => {
    clearTimeout(searchTimeout);
    const q = e.target.value.trim();
    if (!q) {
        searchResults.classList.add('hidden');
        return;
    }

    searchTimeout = setTimeout(async () => {
        try {
            const response = await fetch(`${API_BASE}/search?q=${encodeURIComponent(q)}`);
            if (!response.ok) throw new Error();
            const results = await response.json();
            
            if (results.length === 0) {
                searchResults.innerHTML = `<div class="p-3 text-slate-500 text-center">검색 결과가 없습니다.</div>`;
                searchResults.classList.remove('hidden');
                return;
            }

            searchResults.innerHTML = results.map(item => `
                <div onclick="addStock('${item.ticker}', '${item.name}', '${item.market}')" class="p-3 hover:bg-indigo-950/30 hover:text-indigo-300 cursor-pointer flex justify-between items-center transition duration-150">
                    <div>
                        <span class="font-medium text-slate-200">${item.name}</span>
                        <span class="text-[9px] text-slate-500 uppercase ml-2">${item.ticker}</span>
                    </div>
                    <span class="text-[9px] bg-slate-800 text-slate-400 px-1.5 py-0.5 rounded font-bold uppercase">${item.display_market}</span>
                </div>
            `).join('');
            searchResults.classList.remove('hidden');
        } catch (err) {
            searchResults.innerHTML = `<div class="p-3 text-red-400 text-center">검색 도중 에러가 발생했습니다.</div>`;
            searchResults.classList.remove('hidden');
        }
    }, 400);
});

// Close search list on clicking outside
document.addEventListener('click', (e) => {
    if (e.target !== stockSearchInput && e.target !== searchResults) {
        searchResults.classList.add('hidden');
    }
});

async function addStock(ticker, name, market) {
    try {
        const response = await fetch(`${API_BASE}/watchlist`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ticker, name, market })
        });
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || '종목 추가 실패');
        }
        stockSearchInput.value = '';
        searchResults.classList.add('hidden');
        loadWatchlist();
    } catch (err) {
        alert(err.message);
    }
}

async function deleteStock(id) {
    if (!confirm('관심 종목에서 삭제하시겠습니까?')) return;
    try {
        const response = await fetch(`${API_BASE}/watchlist/${id}`, {
            method: 'DELETE'
        });
        if (!response.ok) throw new Error('종목 삭제 실패');
        loadWatchlist();
    } catch (err) {
        alert(err.message);
    }
}

// ------------------------------------------------------------
// 3. Schedule Management
// ------------------------------------------------------------

async function loadSchedules() {
    try {
        const response = await fetch(`${API_BASE}/schedules`);
        if (!response.ok) throw new Error();
        const list = await response.json();
        
        if (list.length === 0) {
            scheduleItems.innerHTML = `<p class="text-center text-xs text-slate-500 py-4">추가된 스케줄이 없습니다.</p>`;
            return;
        }

        scheduleItems.innerHTML = list.map(item => `
            <div class="flex justify-between items-center bg-slate-900/60 border border-slate-800 px-4 py-3 rounded-2xl text-sm">
                <div class="flex items-center gap-3">
                    <input type="checkbox" onchange="toggleSchedule(${item.id}, this.checked)" ${item.is_active ? 'checked' : ''} class="w-4 h-4 rounded border-slate-700 bg-slate-900 text-indigo-600 focus:ring-indigo-500 focus:ring-offset-slate-900">
                    <span class="font-bold text-slate-200 text-base">${item.time_str}</span>
                </div>
                <button onclick="deleteSchedule(${item.id})" class="text-slate-500 hover:text-rose-400 text-xs px-2 py-1 transition duration-150">삭제</button>
            </div>
        `).join('');
    } catch (err) {
        scheduleItems.innerHTML = `<p class="text-center text-xs text-red-400 py-4">스케줄 목록을 불러올 수 없습니다.</p>`;
    }
}

addScheduleBtn.addEventListener('click', async () => {
    const val = scheduleTimeInput.value;
    if (!val) return;
    try {
        const response = await fetch(`${API_BASE}/schedules`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ time_str: val })
        });
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || '스케줄 추가 실패');
        }
        scheduleTimeInput.value = '';
        loadSchedules();
    } catch (err) {
        alert(err.message);
    }
});

async function toggleSchedule(id, checked) {
    try {
        const response = await fetch(`${API_BASE}/schedules/${id}/toggle?is_active=${checked}`, {
            method: 'PUT'
        });
        if (!response.ok) throw new Error('토글 설정 실패');
        loadSchedules();
    } catch (err) {
        alert(err.message);
        loadSchedules(); // revert check state
    }
}

async function deleteSchedule(id) {
    if (!confirm('스케줄을 삭제하시겠습니까?')) return;
    try {
        const response = await fetch(`${API_BASE}/schedules/${id}`, {
            method: 'DELETE'
        });
        if (!response.ok) throw new Error('스케줄 삭제 실패');
        loadSchedules();
    } catch (err) {
        alert(err.message);
    }
}

// ------------------------------------------------------------
// 4. Manual Trigger
// ------------------------------------------------------------

triggerBtn.addEventListener('click', async () => {
    triggerBtn.disabled = true;
    triggerLoadingIcon.classList.remove('hidden');
    
    try {
        const response = await fetch(`${API_BASE}/trigger`, { method: 'POST' });
        if (!response.ok) throw new Error('작업 트리거 실패');
        
        alert('보고서 생성을 요청했습니다! 약 5~10초 후 완료되면 메인 화면과 아카이브가 갱신됩니다.');
        
        // Wait 8 seconds then refresh report and archives
        setTimeout(() => {
            loadReport('index.html');
            loadArchives();
            triggerBtn.disabled = false;
            triggerLoadingIcon.classList.add('hidden');
        }, 8000);
    } catch (err) {
        alert(err.message);
        triggerBtn.disabled = false;
        triggerLoadingIcon.classList.add('hidden');
    }
});

viewLatestBtn.addEventListener('click', () => {
    loadReport('index.html');
    loadArchives();
});

// ------------------------------------------------------------
// 5. Kakao Authentication
// ------------------------------------------------------------

startKakaoAuthBtn.addEventListener('click', () => {
    fetch(`${API_BASE}/kakao/auth-url`)
        .then(res => res.json())
        .then(data => {
            if (data.url) {
                window.open(data.url, '_blank');
            } else {
                alert('카카오 REST API Key가 설정되지 않았습니다.');
            }
        })
        .catch(() => {
            alert('카카오 연동 정보를 가져올 수 없습니다. 백엔드가 정상적으로 작동 중인지 확인해 주세요.');
        });
});

// ------------------------------------------------------------
// 6. Initialization
// ------------------------------------------------------------

function init() {
    loadReport('index.html');
    loadArchives();
    
    // Set dynamic redirect url label on Kakao dialog based on current window location
    const redirectUri = `${window.location.origin}/api/kakao/callback`;
    redirectUrlLabel.textContent = redirectUri;

    // Load watchlist when watchlist dialog opens
    watchlistDialog.addEventListener('command', (e) => {
        if (e.command === 'show-modal') {
            loadWatchlist();
        }
    });

    // Load schedules when schedule dialog opens
    scheduleDialog.addEventListener('command', (e) => {
        if (e.command === 'show-modal') {
            loadSchedules();
        }
    });
}

window.addEventListener('DOMContentLoaded', init);
window.loadReport = loadReport;
window.deleteStock = deleteStock;
window.addStock = addStock;
window.deleteSchedule = deleteSchedule;
window.toggleSchedule = toggleSchedule;
