// State variables
let state = {
    segments: [],
    cardPath: '',
    tzOffset: 0,
    recentExports: []
};

// DOM Elements
const dom = {
    cardPath: document.getElementById('cardPath'),
    tzOffset: document.getElementById('tzOffset'),
    btnScan: document.getElementById('btnScan'),
    timelineBars: document.getElementById('timelineBars'),
    segmentsCount: document.getElementById('segmentsCount'),
    segmentsList: document.getElementById('segmentsList'),
    exportStart: document.getElementById('exportStart'),
    exportEnd: document.getElementById('exportEnd'),
    overlapInfo: document.getElementById('overlapInfo'),
    btnExport: document.getElementById('btnExport'),
    recentExportsList: document.getElementById('recentExportsList'),
    exportModal: document.getElementById('exportModal'),
    previewModal: document.getElementById('previewModal'),
    previewVideo: document.getElementById('previewVideo'),
    playerFilename: document.getElementById('playerFilename'),
    playerDownloadBtn: document.getElementById('playerDownloadBtn'),
    btnExitPlayer: document.getElementById('btnExitPlayer'),
    notification: document.getElementById('notification'),
    segmentSearch: document.getElementById('segmentSearch'),
    btnRanges: document.querySelectorAll('.btn-range'),
    btnBrowse: document.getElementById('btnBrowse'),
    browseModal: document.getElementById('browseModal'),
    formatType: document.getElementById('formatType')
};

// Event Listeners
document.addEventListener('DOMContentLoaded', () => {
    dom.btnScan.addEventListener('click', scanCard);
    dom.btnExport.addEventListener('click', exportRange);
    dom.btnExitPlayer.addEventListener('click', closePlayer);
    
    // Browser modal events
    dom.btnBrowse.addEventListener('click', () => openFolderBrowser(dom.cardPath.value.trim()));
    document.getElementById('btnExitBrowser').addEventListener('click', () => dom.browseModal.classList.remove('active'));
    document.getElementById('btnBrowserCancel').addEventListener('click', () => dom.browseModal.classList.remove('active'));
    document.getElementById('btnBrowserUp').addEventListener('click', () => {
        if (browserState.parentPath) {
            loadDirectory(browserState.parentPath);
        }
    });
    document.getElementById('btnBrowserSelect').addEventListener('click', () => {
        dom.cardPath.value = browserState.currentPath;
        dom.browseModal.classList.remove('active');
        showNotification('Başarılı', 'Klasör seçildi: ' + browserState.currentPath, 'success');
        scanCard();
    });
    
    // Sidebar shortcuts
    document.querySelectorAll('.sidebar-item').forEach(item => {
        item.addEventListener('click', (e) => {
            loadDirectory(e.currentTarget.dataset.path);
        });
    });

    dom.segmentSearch.addEventListener('input', filterSegmentsList);
    
    // Inputs change validation
    dom.exportStart.addEventListener('change', checkOverlaps);
    dom.exportEnd.addEventListener('change', checkOverlaps);
    
    // Quick ranges shortcuts
    dom.btnRanges.forEach(btn => {
        btn.addEventListener('click', (e) => {
            const minutes = parseInt(e.target.dataset.duration);
            applyQuickRange(minutes);
        });
    });
    
    // Close modal on click outside content
    window.addEventListener('click', (e) => {
        if (e.target === dom.previewModal) closePlayer();
    });

    // Auto-scan on load to show initial card state if valid
    if (dom.cardPath.value.trim()) {
        scanCard();
    }
});

let browserState = {
    currentPath: '',
    parentPath: null
};

// Open custom web folder browser
async function openFolderBrowser(startPath = '') {
    dom.browseModal.classList.add('active');
    await loadDirectory(startPath);
}

// Load directories from backend API
async function loadDirectory(path) {
    const listEl = document.getElementById('browserList');
    listEl.innerHTML = '<div style="color: var(--text-muted); padding: 12px; font-size: 13px;"><i class="fa-solid fa-spinner fa-spin"></i> Yükleniyor...</div>';
    
    try {
        const response = await fetch(`/api/list_dir?path=${encodeURIComponent(path)}`);
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Dizin yüklenemedi.');
        }
        
        browserState.currentPath = data.current_path;
        browserState.parentPath = data.parent_path;
        
        document.getElementById('browserPathInput').value = data.current_path;
        listEl.innerHTML = '';
        
        if (data.directories.length === 0) {
            listEl.innerHTML = '<div style="color: var(--text-muted); padding: 12px; font-size: 13px;">Bu dizinde alt klasör bulunmuyor.</div>';
        } else {
            data.directories.forEach(dir => {
                const item = document.createElement('div');
                item.className = 'browser-folder-item';
                item.innerHTML = `<i class="fa-solid fa-folder"></i> <span>${dir}</span>`;
                item.addEventListener('click', () => {
                    const separator = browserState.currentPath.endsWith('/') ? '' : '/';
                    const nextPath = browserState.currentPath + separator + dir;
                    loadDirectory(nextPath);
                });
                listEl.appendChild(item);
            });
        }
        
        // Enable/disable parent navigation button
        document.getElementById('btnBrowserUp').disabled = !browserState.parentPath;
        
    } catch (err) {
        showNotification('Hata', err.message, 'error');
        listEl.innerHTML = `<div style="color: var(--accent-red); padding: 12px; font-size: 13px;"><i class="fa-solid fa-triangle-exclamation"></i> Hata: ${err.message}</div>`;
    }
}


// Scan SD Card index
async function scanCard() {
    state.cardPath = dom.cardPath.value.trim();
    state.tzOffset = parseInt(dom.tzOffset.value);
    
    showNotification('Bilgi', 'SD Kart taranıyor...', 'info');
    
    try {
        const response = await fetch(`/api/scan?card_path=${encodeURIComponent(state.cardPath)}&tz_offset=${state.tzOffset}`);
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Tarama hatası oluştu.');
        }
        
        state.segments = data.segments || [];
        dom.segmentsCount.textContent = state.segments.length;
        
        renderTimeline();
        renderSegmentsList();
        checkOverlaps();
        
        showNotification('Başarılı', `Tarama tamamlandı. ${state.segments.length} kayıt dilimi bulundu.`, 'success');
    } catch (error) {
        showNotification('Hata', error.message, 'error');
        dom.segmentsList.innerHTML = `
            <div class="empty-state">
                <i class="fa-solid fa-triangle-exclamation" style="color: var(--accent-red)"></i>
                <p>${error.message}</p>
            </div>
        `;
        dom.timelineBars.innerHTML = `<div class="timeline-placeholder">Tarama yapılamadı. Dizin yolunu kontrol edin.</div>`;
    }
}

// Render Timeline Bars
function renderTimeline() {
    if (state.segments.length === 0) {
        dom.timelineBars.innerHTML = `<div class="timeline-placeholder">Kayıtlı veri bulunamadı.</div>`;
        return;
    }
    
    dom.timelineBars.innerHTML = '';
    
    const minTs = Math.min(...state.segments.map(s => s.start_ts));
    const maxTs = Math.max(...state.segments.map(s => s.end_ts));
    const totalDuration = maxTs - minTs;
    
    state.segments.forEach(seg => {
        const slot = document.createElement('div');
        slot.className = 'timeline-slot';
        
        // Compute relative percentages
        const left = ((seg.start_ts - minTs) / totalDuration) * 100;
        const width = ((seg.end_ts - seg.start_ts) / totalDuration) * 100;
        
        slot.style.left = `${left}%`;
        slot.style.width = `${Math.max(0.2, width)}%`; // guarantee visibility for very short clips
        
        slot.title = `Başlangıç: ${seg.start_local}\nBitiş: ${seg.end_local}\nSüre: ${formatDuration(seg.duration_sec)}`;
        
        slot.addEventListener('click', () => {
            selectSegment(seg.id);
        });
        
        dom.timelineBars.appendChild(slot);
    });
}

// Render Left Panel segments list
function renderSegmentsList(filterText = '') {
    if (state.segments.length === 0) {
        dom.segmentsList.innerHTML = `
            <div class="empty-state">
                <i class="fa-solid fa-folder-open"></i>
                <p>Gösterilecek kayıt dilimi yok.</p>
            </div>
        `;
        return;
    }
    
    dom.segmentsList.innerHTML = '';
    const query = filterText.toLowerCase();
    
    const filtered = state.segments.filter(s => 
        s.start_local.toLowerCase().includes(query) || 
        s.end_local.toLowerCase().includes(query)
    );
    
    if (filtered.length === 0) {
        dom.segmentsList.innerHTML = `
            <div class="empty-state">
                <i class="fa-solid fa-magnifying-glass"></i>
                <p>Arama kriterine uygun kayıt bulunamadı.</p>
            </div>
        `;
        return;
    }
    
    filtered.forEach(seg => {
        const card = document.createElement('div');
        card.className = 'segment-card';
        card.dataset.id = seg.id;
        
        card.innerHTML = `
            <div class="segment-thumb-container">
                <span class="thumb-loader"><i class="fa-solid fa-spinner fa-spin"></i></span>
                <img class="segment-thumb" id="thumb-${seg.id}" alt="Kamera Önizleme">
                <span class="duration-tag">${formatDuration(seg.duration_sec)}</span>
            </div>
            <div class="segment-details">
                <div class="segment-time-row">
                    ${seg.start_local.split(' ')[1]} <span>→</span> ${seg.end_local.split(' ')[1]}
                </div>
                <div class="segment-meta-row">
                    <span><i class="fa-solid fa-calendar"></i> ${seg.start_local.split(' ')[0]}</span>
                    <span><i class="fa-solid fa-weight-hanging"></i> ${seg.size_mb} MB</span>
                    <span><i class="fa-solid fa-file-video"></i> hiv${seg.file_num.toString().padStart(5, '0')}.mp4</span>
                </div>
            </div>
            <div class="segment-actions">
                <button class="btn-card-action" onclick="event.stopPropagation(); quickFillSegment(${seg.id})">
                    <i class="fa-solid fa-paste"></i> Seç
                </button>
            </div>
        `;
        
        card.addEventListener('click', () => {
            selectSegment(seg.id);
        });
        
        dom.segmentsList.appendChild(card);
        
        // Trigger thumbnail loading asynchronously
        loadThumbnail(seg.id);
    });
}

// Load Thumbnail Image
async function loadThumbnail(id) {
    const img = document.getElementById(`thumb-${id}`);
    const loader = img.previousElementSibling;
    
    try {
        const thumbUrl = `/api/thumbnail/${id}?card_path=${encodeURIComponent(state.cardPath)}`;
        img.src = thumbUrl;
        img.onload = () => {
            img.classList.add('loaded');
            if (loader) loader.style.display = 'none';
        };
        img.onerror = () => {
            if (loader) {
                loader.innerHTML = '<i class="fa-solid fa-image-slash"></i>';
                loader.style.color = 'var(--text-muted)';
            }
        };
    } catch (e) {
        if (loader) loader.innerHTML = '<i class="fa-solid fa-image-slash"></i>';
    }
}

// Highlight Segment and set datetime forms
function selectSegment(id) {
    document.querySelectorAll('.segment-card').forEach(c => c.classList.remove('selected'));
    
    const card = document.querySelector(`.segment-card[data-id="${id}"]`);
    if (card) {
        card.classList.add('selected');
        card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
    
    quickFillSegment(id);
}

// Prefill form datetime pickers based on segment
function quickFillSegment(id) {
    const seg = state.segments.find(s => s.id === id);
    if (!seg) return;
    
    // Format local datetime strings for datetime-local value (YYYY-MM-DDTHH:MM:SS)
    const formatForInput = (localStr) => {
        return localStr.replace(' ', 'T');
    };
    
    dom.exportStart.value = formatForInput(seg.start_local);
    dom.exportEnd.value = formatForInput(seg.end_local);
    
    checkOverlaps();
}

// Helper to parse datetime-local string to UTC timestamp timezone-independently
function getLocalTimestamp(dateTimeStr, tzOffset) {
    if (!dateTimeStr) return null;
    let s = dateTimeStr;
    if (s.length === 16) {
        s += ":00";
    }
    const utcMs = new Date(s + "Z").getTime();
    return Math.floor((utcMs - tzOffset * 3600 * 1000) / 1000);
}

// Quick range shortcut helper
function applyQuickRange(minutes) {
    if (!dom.exportStart.value) {
        showNotification('Bilgi', 'Lütfen önce bir başlangıç zamanı seçin.', 'info');
        return;
    }
    
    let startStr = dom.exportStart.value;
    if (startStr.length === 16) {
        startStr += ":00";
    }
    const startDt = new Date(startStr + "Z");
    const endDt = new Date(startDt.getTime() + minutes * 60 * 1000);
    
    // Format as YYYY-MM-DDTHH:MM:SS
    const pad = (n) => n.toString().padStart(2, '0');
    const localISO = endDt.getUTCFullYear() + '-' +
        pad(endDt.getUTCMonth() + 1) + '-' +
        pad(endDt.getUTCDate()) + 'T' +
        pad(endDt.getUTCHours()) + ':' +
        pad(endDt.getUTCMinutes()) + ':' +
        pad(endDt.getUTCSeconds());
        
    dom.exportEnd.value = localISO;
    checkOverlaps();
}

// Find intersections between requested range and segments
function checkOverlaps() {
    const startVal = dom.exportStart.value;
    const endVal = dom.exportEnd.value;
    
    if (!startVal || !endVal) {
        dom.overlapInfo.style.display = 'none';
        dom.btnExport.disabled = true;
        return;
    }
    
    const reqStartTs = getLocalTimestamp(startVal, state.tzOffset);
    const reqEndTs = getLocalTimestamp(endVal, state.tzOffset);
    
    if (reqEndTs <= reqStartTs) {
        dom.overlapInfo.textContent = 'Bitiş zamanı başlangıç zamanından sonra olmalıdır.';
        dom.overlapInfo.className = 'overlap-info warning';
        dom.overlapInfo.style.display = 'flex';
        dom.btnExport.disabled = true;
        return;
    }
    
    // Check overlap
    const overlaps = state.segments.filter(s => s.start_ts < reqEndTs && s.end_ts > reqStartTs);
    
    if (overlaps.length === 0) {
        dom.overlapInfo.innerHTML = '<i class="fa-solid fa-circle-xmark"></i> Seçtiğiniz aralıkta kaydedilmiş görüntü bulunmamaktadır.';
        dom.overlapInfo.className = 'overlap-info warning';
        dom.overlapInfo.style.display = 'flex';
        dom.btnExport.disabled = true;
    } else {
        dom.overlapInfo.innerHTML = `<i class="fa-solid fa-circle-check"></i> Seçilen aralıkta kayıt bulundu! (${overlaps.length} segment etkilenecek)`;
        dom.overlapInfo.className = 'overlap-info success';
        dom.overlapInfo.style.display = 'flex';
        dom.btnExport.disabled = false;
    }
}

// Export Video Range
async function exportRange() {
    const startVal = dom.exportStart.value;
    const endVal = dom.exportEnd.value;
    
    if (!startVal || !endVal) return;
    
    const reqStartTs = getLocalTimestamp(startVal, state.tzOffset);
    const reqEndTs = getLocalTimestamp(endVal, state.tzOffset);
    
    // Show Loading Overlay
    dom.exportModal.classList.add('active');
    updateProgress(10, 'SD Karttan veri blokları okunuyor...');
    
    try {
        const response = await fetch('/api/export', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                card_path: state.cardPath,
                start_ts: reqStartTs,
                end_ts: reqEndTs,
                tz_offset: state.tzOffset,
                format_type: dom.formatType ? dom.formatType.value : 'mpeg'
            })
        });
        
        updateProgress(50, 'Ham video akışı çözümleniyor...');
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Dışarı aktarma sırasında hata oluştu.');
        }
        
        updateProgress(90, 'MP4 dosyası kaydediliyor...');
        setTimeout(() => {
            dom.exportModal.classList.remove('active');
            
            // Add to recent exports
            addRecentExport(data.filename, data.output_path, data.size_mb);
            showNotification('Başarılı', 'Video aktarımı tamamlandı! Dosya Downloads klasörüne kaydedildi.', 'success');
        }, 1000);
        
    } catch (error) {
        dom.exportModal.classList.remove('active');
        showNotification('Hata', error.message, 'error');
    }
}

// Progress Bar Helper
function updateProgress(percent, statusText) {
    const fill = dom.exportModal.querySelector('.progress-fill');
    const status = dom.exportModal.querySelector('.progress-status');
    if (fill) fill.style.width = `${percent}%`;
    if (status) status.textContent = statusText;
}

// Add item to recent exports panel
function addRecentExport(filename, fullPath, sizeMb) {
    // Remove no-exports placeholder
    const noExports = dom.recentExportsList.querySelector('.no-exports');
    if (noExports) noExports.remove();
    
    const item = document.createElement('div');
    item.className = 'recent-export-item';
    
    item.innerHTML = `
        <div class="export-item-info">
            <span>${filename}</span>
            <small>${sizeMb} MB | ${new Date().toLocaleTimeString()}</small>
        </div>
         <div class="export-item-actions">
            <button class="btn-icon play-btn" title="Oynat" onclick="playExportedVideo('${filename}')">
                <i class="fa-solid fa-circle-play"></i>
            </button>
            <a class="btn-icon download-btn" title="İndir" href="/api/download?filename=${encodeURIComponent(filename)}" download>
                <i class="fa-solid fa-download"></i>
            </a>
        </div>
    `;
    
    dom.recentExportsList.insertBefore(item, dom.recentExportsList.firstChild);
}

// Play video inside the web player modal
function playExportedVideo(filename) {
    const encodedName = encodeURIComponent(filename);
    dom.playerFilename.textContent = filename;
    dom.playerDownloadBtn.href = `/api/download?filename=${encodedName}`;
    
    // Set video src pointing to local API
    dom.previewVideo.src = `/api/download?filename=${encodedName}`;
    dom.previewModal.classList.add('active');
    dom.previewVideo.play();
}

// Close Video Player Modal
function closePlayer() {
    dom.previewVideo.pause();
    dom.previewVideo.src = '';
    dom.previewModal.classList.remove('active');
}

// Search filter for list
function filterSegmentsList() {
    renderSegmentsList(dom.segmentSearch.value);
}

// Helper: Format duration from seconds
function formatDuration(seconds) {
    if (seconds < 60) return `${seconds} sn`;
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    if (mins < 60) {
        return `${mins}:${secs.toString().padStart(2, '0')} dk`;
    }
    const hrs = Math.floor(mins / 60);
    const remMins = mins % 60;
    return `${hrs}:${remMins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')} sa`;
}

// Floating Toast Notification system
function showNotification(title, msg, type = 'success') {
    const icon = dom.notification.querySelector('.notification-icon');
    const titleDom = dom.notification.querySelector('.notification-title');
    const msgDom = dom.notification.querySelector('.notification-msg');
    
    dom.notification.className = 'notification';
    if (type === 'error') {
        dom.notification.classList.add('error');
        icon.className = 'notification-icon fa-solid fa-circle-exclamation';
    } else if (type === 'info') {
        dom.notification.classList.add('info');
        icon.className = 'notification-icon fa-solid fa-circle-info';
    } else {
        icon.className = 'notification-icon fa-solid fa-circle-check';
    }
    
    titleDom.textContent = title;
    msgDom.textContent = msg;
    
    dom.notification.classList.add('show');
    
    // Auto hide after 4 seconds
    setTimeout(() => {
        dom.notification.classList.remove('show');
    }, 4500);
}
