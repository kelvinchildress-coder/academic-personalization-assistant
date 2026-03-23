(function() {
    'use strict';

    // === Domain check ===
    if (!window.location.hostname.includes('timeback.com')) {
        alert('Please navigate to TimeBack (alpha.timeback.com) first, then click this bookmarklet again.');
        window.open('https://alpha.timeback.com', '_blank');
        return;
    }

    // === Toggle: remove if already injected ===
    if (document.getElementById('tb-dash-overlay')) {
        document.getElementById('tb-dash-overlay').remove();
        if (document.getElementById('tb-dash-styles')) document.getElementById('tb-dash-styles').remove();
        return;
    }

    // === Inject CSS ===
    const styleEl = document.createElement('style');
    styleEl.id = 'tb-dash-styles';
    styleEl.textContent = `
        #tb-dash-overlay {
            --bg-primary: #0a0e1a;
            --bg-secondary: #0f1629;
            --bg-card: rgba(15, 23, 42, 0.7);
            --bg-card-hover: rgba(20, 30, 55, 0.8);
            --bg-glass: rgba(255, 255, 255, 0.03);
            --border: rgba(255, 255, 255, 0.06);
            --border-hover: rgba(255, 255, 255, 0.12);
            --text-primary: #f1f5f9;
            --text-secondary: #94a3b8;
            --text-muted: #475569;
            --accent-blue: #3b82f6;
            --accent-blue-glow: rgba(59, 130, 246, 0.15);
            --accent-emerald: #10b981;
            --accent-emerald-glow: rgba(16, 185, 129, 0.15);
            --accent-amber: #f59e0b;
            --accent-amber-glow: rgba(245, 158, 11, 0.15);
            --accent-rose: #f43f5e;
            --accent-rose-glow: rgba(244, 63, 94, 0.15);
            --accent-purple: #a855f7;
            --accent-cyan: #06b6d4;
            --radius: 12px;
            --radius-lg: 16px;
            position: fixed;
            inset: 0;
            z-index: 999999;
            overflow-y: auto;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
        }
        #tb-dash-overlay::before {
            content: '';
            position: fixed;
            inset: 0;
            background:
                radial-gradient(ellipse at 20% 0%, rgba(59, 130, 246, 0.08) 0%, transparent 50%),
                radial-gradient(ellipse at 80% 100%, rgba(168, 85, 247, 0.06) 0%, transparent 50%);
            pointer-events: none;
            z-index: 0;
        }
        #tb-dash-overlay::after {
            content: '';
            position: fixed;
            inset: 0;
            background-image: radial-gradient(rgba(255,255,255,0.03) 1px, transparent 1px);
            background-size: 24px 24px;
            pointer-events: none;
            z-index: 0;
        }
        #tb-dash-overlay * { margin: 0; padding: 0; box-sizing: border-box; }
        #tb-dash-overlay .app { position: relative; z-index: 1; }
        #tb-dash-overlay .section-header {
            font-size: 14px; font-weight: 700; color: var(--text-secondary);
            letter-spacing: 0.5px; text-transform: uppercase;
            margin: 24px 0 12px; padding-bottom: 8px;
            border-bottom: 1px solid var(--border);
            display: flex; align-items: center; gap: 8px;
        }
        #tb-dash-overlay .section-header:first-child { margin-top: 8px; }
        #tb-dash-overlay .section-header .section-date {
            color: var(--accent-blue); font-weight: 600;
            text-transform: none; letter-spacing: 0;
        }
        #tb-dash-overlay .topbar {
            display: flex; align-items: center; justify-content: space-between;
            padding: 16px 32px; background: rgba(10, 14, 26, 0.8);
            backdrop-filter: blur(20px); border-bottom: 1px solid var(--border);
            position: sticky; top: 0; z-index: 100;
        }
        #tb-dash-overlay .topbar-left { display: flex; align-items: center; gap: 12px; }
        #tb-dash-overlay .logo {
            width: 36px; height: 36px;
            background: linear-gradient(135deg, var(--accent-blue), var(--accent-purple));
            border-radius: 10px; display: flex; align-items: center; justify-content: center;
            font-weight: 800; font-size: 16px; color: white;
        }
        #tb-dash-overlay .app-title {
            font-size: 18px; font-weight: 700;
            background: linear-gradient(135deg, var(--text-primary), var(--text-secondary));
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        }
        #tb-dash-overlay .topbar-right { display: flex; align-items: center; gap: 16px; }
        #tb-dash-overlay .timestamp { font-size: 12px; color: var(--text-muted); }
        #tb-dash-overlay .status-dot {
            width: 8px; height: 8px; border-radius: 50%;
            background: var(--accent-emerald); box-shadow: 0 0 8px var(--accent-emerald);
            animation: tb-pulse-glow 2s ease-in-out infinite;
        }
        #tb-dash-overlay .status-dot.offline { background: var(--text-muted); box-shadow: none; animation: none; }
        #tb-dash-overlay .status-dot.loading { background: var(--accent-amber); box-shadow: 0 0 8px var(--accent-amber); }
        @keyframes tb-pulse-glow { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        #tb-dash-overlay .btn-icon {
            width: 36px; height: 36px; border-radius: 10px; border: 1px solid var(--border);
            background: var(--bg-glass); color: var(--text-secondary); cursor: pointer;
            display: flex; align-items: center; justify-content: center; transition: all 0.2s;
        }
        #tb-dash-overlay .btn-icon:hover {
            background: var(--bg-card-hover); border-color: var(--border-hover); color: var(--text-primary);
        }
        #tb-dash-overlay .controls {
            display: flex; align-items: center; gap: 12px; padding: 16px 32px;
            background: rgba(15, 22, 41, 0.5); border-bottom: 1px solid var(--border); flex-wrap: wrap;
        }
        #tb-dash-overlay .date-group { display: flex; align-items: center; gap: 8px; }
        #tb-dash-overlay .date-label {
            font-size: 12px; color: var(--text-muted); font-weight: 500;
            text-transform: uppercase; letter-spacing: 0.5px;
        }
        #tb-dash-overlay input[type="date"] {
            background: var(--bg-card); border: 1px solid var(--border); color: var(--text-primary);
            padding: 8px 12px; border-radius: 8px; font-family: inherit; font-size: 13px;
            outline: none; transition: border-color 0.2s;
        }
        #tb-dash-overlay input[type="date"]:focus { border-color: var(--accent-blue); }
        #tb-dash-overlay input[type="date"]::-webkit-calendar-picker-indicator { filter: invert(0.7); }
        #tb-dash-overlay .presets { display: flex; gap: 6px; margin-left: 8px; }
        #tb-dash-overlay .preset-btn {
            padding: 7px 14px; border-radius: 8px; border: 1px solid var(--border);
            background: var(--bg-glass); color: var(--text-secondary); font-size: 12px;
            font-weight: 500; cursor: pointer; transition: all 0.2s; font-family: inherit;
        }
        #tb-dash-overlay .preset-btn:hover {
            background: var(--bg-card-hover); border-color: var(--border-hover); color: var(--text-primary);
        }
        #tb-dash-overlay .preset-btn.active {
            background: var(--accent-blue-glow); border-color: var(--accent-blue); color: var(--accent-blue);
        }
        #tb-dash-overlay .btn-pull {
            padding: 8px 24px; border-radius: 8px; border: none;
            background: linear-gradient(135deg, var(--accent-blue), #2563eb); color: white;
            font-size: 13px; font-weight: 600; cursor: pointer; transition: all 0.25s;
            font-family: inherit; display: flex; align-items: center; gap: 8px;
            margin-left: auto; box-shadow: 0 0 20px rgba(59, 130, 246, 0.2);
        }
        #tb-dash-overlay .btn-pull:hover { transform: translateY(-1px); box-shadow: 0 0 30px rgba(59, 130, 246, 0.35); }
        #tb-dash-overlay .btn-pull:active { transform: translateY(0); }
        #tb-dash-overlay .btn-pull:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
        #tb-dash-overlay .btn-pull svg { transition: transform 0.3s; }
        #tb-dash-overlay .btn-pull.loading svg { animation: tb-spin 1s linear infinite; }
        @keyframes tb-spin { to { transform: rotate(360deg); } }
        #tb-dash-overlay .main { padding: 24px 32px; }
        #tb-dash-overlay .summary-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
        #tb-dash-overlay .summary-card {
            background: var(--bg-card); backdrop-filter: blur(12px); border: 1px solid var(--border);
            border-radius: var(--radius-lg); padding: 20px; transition: all 0.3s;
        }
        #tb-dash-overlay .summary-card:hover { border-color: var(--border-hover); transform: translateY(-2px); }
        #tb-dash-overlay .summary-label {
            font-size: 11px; font-weight: 600; text-transform: uppercase;
            letter-spacing: 0.8px; color: var(--text-muted); margin-bottom: 8px;
        }
        #tb-dash-overlay .summary-value { font-size: 32px; font-weight: 800; line-height: 1; }
        #tb-dash-overlay .summary-sub { font-size: 12px; color: var(--text-muted); margin-top: 6px; }
        #tb-dash-overlay .summary-card.blue .summary-value { color: var(--accent-blue); }
        #tb-dash-overlay .summary-card.emerald .summary-value { color: var(--accent-emerald); }
        #tb-dash-overlay .summary-card.amber .summary-value { color: var(--accent-amber); }
        #tb-dash-overlay .summary-card.purple .summary-value { color: var(--accent-purple); }
        #tb-dash-overlay .summary-card.blue { box-shadow: inset 0 1px 0 var(--accent-blue-glow); }
        #tb-dash-overlay .summary-card.emerald { box-shadow: inset 0 1px 0 var(--accent-emerald-glow); }
        #tb-dash-overlay .summary-card.amber { box-shadow: inset 0 1px 0 var(--accent-amber-glow); }
        #tb-dash-overlay .summary-card.purple { box-shadow: inset 0 1px 0 rgba(168,85,247,0.15); }
        #tb-dash-overlay .day-tabs { display: flex; gap: 8px; margin-bottom: 20px; overflow-x: auto; padding-bottom: 4px; }
        #tb-dash-overlay .day-tab {
            padding: 12px 20px; border-radius: var(--radius); border: 1px solid var(--border);
            background: var(--bg-card); color: var(--text-secondary); cursor: pointer;
            font-size: 13px; font-weight: 500; transition: all 0.25s; white-space: nowrap;
            font-family: inherit; min-width: 120px; text-align: center;
        }
        #tb-dash-overlay .day-tab:hover { border-color: var(--border-hover); background: var(--bg-card-hover); }
        #tb-dash-overlay .day-tab.active {
            background: var(--accent-blue-glow); border-color: var(--accent-blue);
            color: var(--accent-blue); box-shadow: 0 0 20px rgba(59, 130, 246, 0.1);
        }
        #tb-dash-overlay .day-tab-name { font-weight: 600; font-size: 14px; }
        #tb-dash-overlay .day-tab-xp { font-size: 11px; margin-top: 4px; opacity: 0.7; }
        #tb-dash-overlay .student-grid {
            display: grid; grid-template-columns: repeat(auto-fill, minmax(min(380px, 100%), 1fr));
            gap: 16px; margin-bottom: 32px;
        }
        #tb-dash-overlay .student-card {
            background: var(--bg-card); backdrop-filter: blur(12px); border: 1px solid var(--border);
            border-radius: var(--radius-lg); overflow: visible; transition: all 0.3s;
            animation: tb-fadeIn 0.4s ease forwards; opacity: 0; min-width: 0;
        }
        #tb-dash-overlay .student-card:hover {
            border-color: var(--border-hover); transform: translateY(-2px);
            box-shadow: 0 8px 32px rgba(0,0,0,0.2);
        }
        #tb-dash-overlay .student-card:nth-child(1) { animation-delay: 0s; }
        #tb-dash-overlay .student-card:nth-child(2) { animation-delay: 0.05s; }
        #tb-dash-overlay .student-card:nth-child(3) { animation-delay: 0.1s; }
        #tb-dash-overlay .student-card:nth-child(4) { animation-delay: 0.15s; }
        #tb-dash-overlay .student-card:nth-child(5) { animation-delay: 0.2s; }
        #tb-dash-overlay .student-card:nth-child(6) { animation-delay: 0.25s; }
        #tb-dash-overlay .student-card.flag-red { border-left: 3px solid var(--accent-rose); }
        #tb-dash-overlay .student-card.flag-yellow { border-left: 3px solid var(--accent-amber); }
        #tb-dash-overlay .student-card.flag-green { border-left: 3px solid var(--accent-emerald); }
        #tb-dash-overlay .student-card.flag-absent {
            border-left: 3px solid var(--accent-rose); background: rgba(244, 63, 94, 0.06); position: relative;
        }
        #tb-dash-overlay .absent-banner {
            background: rgba(244, 63, 94, 0.12); color: var(--accent-rose);
            font-size: 12px; font-weight: 600; padding: 8px 20px;
            display: flex; align-items: center; gap: 6px; letter-spacing: 0.3px;
        }
        #tb-dash-overlay .student-header {
            padding: 16px 20px; display: flex; align-items: center;
            justify-content: space-between; border-bottom: 1px solid var(--border);
            flex-wrap: wrap; gap: 8px;
        }
        #tb-dash-overlay .student-name { font-size: 16px; font-weight: 700; white-space: nowrap; }
        #tb-dash-overlay .student-badges { display: flex; gap: 8px; flex-wrap: wrap; }
        #tb-dash-overlay .badge { padding: 4px 10px; border-radius: 20px; font-size: 11px; font-weight: 600; letter-spacing: 0.3px; }
        #tb-dash-overlay .badge-xp { background: var(--accent-blue-glow); color: var(--accent-blue); border: 1px solid rgba(59,130,246,0.2); }
        #tb-dash-overlay .badge-acc { border: 1px solid; }
        #tb-dash-overlay .badge-acc.good { background: var(--accent-emerald-glow); color: var(--accent-emerald); border-color: rgba(16,185,129,0.2); }
        #tb-dash-overlay .badge-acc.warn { background: var(--accent-rose-glow); color: var(--accent-rose); border-color: rgba(244,63,94,0.2); }
        #tb-dash-overlay .badge-min { border: 1px solid; }
        #tb-dash-overlay .badge-min.good { background: rgba(168,85,247,0.12); color: var(--accent-purple); border-color: rgba(168,85,247,0.2); }
        #tb-dash-overlay .badge-min.warn { background: var(--accent-amber-glow); color: var(--accent-amber); border-color: rgba(245,158,11,0.2); }
        #tb-dash-overlay .student-subjects { padding: 12px 20px 16px; }
        #tb-dash-overlay .subject-row {
            display: flex; align-items: center; padding: 8px 0;
            border-bottom: 1px solid rgba(255,255,255,0.03); gap: 12px;
            flex-wrap: wrap; min-width: 0;
        }
        #tb-dash-overlay .view-toggle-bar {
            display: flex; gap: 8px; margin-bottom: 16px;
        }
        #tb-dash-overlay .view-toggle-btn {
            padding: 8px 16px; border-radius: 8px; border: 1px solid var(--border);
            background: var(--bg-card); color: var(--text-secondary); font-size: 12px;
            font-weight: 600; cursor: pointer; font-family: inherit; transition: all 0.2s;
        }
        #tb-dash-overlay .view-toggle-btn:hover { border-color: var(--border-hover); color: var(--text-primary); }
        #tb-dash-overlay .view-toggle-btn.active {
            background: var(--accent-blue); color: white; border-color: var(--accent-blue);
        }
        #tb-dash-overlay .subject-totals-table {
            width: 100%; border-collapse: separate; border-spacing: 0;
            background: var(--bg-card); border: 1px solid var(--border);
            border-radius: var(--radius-lg); overflow: hidden; margin-bottom: 24px;
        }
        #tb-dash-overlay .subject-totals-table th {
            text-align: left; padding: 12px 14px; font-size: 11px; font-weight: 700;
            text-transform: uppercase; letter-spacing: 0.5px; color: var(--text-muted);
            background: rgba(255,255,255,0.03); border-bottom: 1px solid var(--border);
        }
        #tb-dash-overlay .subject-totals-table td {
            padding: 10px 14px; font-size: 13px; border-bottom: 1px solid rgba(255,255,255,0.03);
        }
        #tb-dash-overlay .subject-totals-table tr:last-child td { border-bottom: none; }
        #tb-dash-overlay .subject-totals-table .student-name-cell {
            font-weight: 600; color: var(--text-primary); white-space: nowrap;
            position: sticky; left: 0; background: var(--bg-card); z-index: 1;
        }
        #tb-dash-overlay .subject-totals-table .xp-cell {
            text-align: center; font-weight: 600; color: var(--accent-blue); font-size: 13px;
        }
        #tb-dash-overlay .subject-totals-table .xp-cell.zero { color: var(--text-muted); opacity: 0.4; }
        #tb-dash-overlay .subject-totals-table .total-cell {
            text-align: center; font-weight: 700; color: var(--text-primary); font-size: 14px;
            background: rgba(59, 130, 246, 0.06);
        }
        #tb-dash-overlay .subject-totals-table .total-row td {
            font-weight: 700; background: rgba(59, 130, 246, 0.08); border-top: 2px solid var(--border);
        }
        #tb-dash-overlay .subject-totals-wrapper {
            overflow-x: auto; -webkit-overflow-scrolling: touch; margin-bottom: 24px;
        }
        #tb-dash-overlay .subject-row:last-child { border-bottom: none; }
        #tb-dash-overlay .subject-row.no-data { opacity: 0.3; }
        #tb-dash-overlay .subject-row.has-test {
            background: rgba(234, 179, 8, 0.08);
            border: 1px solid rgba(234, 179, 8, 0.25);
            border-radius: 8px;
            padding: 8px 10px;
            margin: 4px -10px;
        }
        #tb-dash-overlay .test-badge {
            font-size: 10px; font-weight: 700; text-transform: uppercase;
            letter-spacing: 0.5px; color: #eab308; background: rgba(234, 179, 8, 0.15);
            border: 1px solid rgba(234, 179, 8, 0.3); border-radius: 4px;
            padding: 2px 6px; white-space: nowrap;
        }
        #tb-dash-overlay .subject-name { font-size: 13px; font-weight: 500; min-width: 80px; max-width: 110px; color: var(--text-secondary); flex-shrink: 0; }
        #tb-dash-overlay .subject-metrics { display: flex; gap: 12px; flex: 1; flex-wrap: wrap; align-items: center; }
        #tb-dash-overlay .metric { display: flex; align-items: center; gap: 4px; font-size: 12px; white-space: nowrap; }
        #tb-dash-overlay .metric-bar { width: 50px; height: 4px; background: rgba(255,255,255,0.06); border-radius: 2px; overflow: hidden; flex-shrink: 0; }
        #tb-dash-overlay .metric-bar-fill { height: 100%; border-radius: 2px; transition: width 0.5s ease; }
        #tb-dash-overlay .metric-bar-fill.blue { background: var(--accent-blue); }
        #tb-dash-overlay .metric-bar-fill.emerald { background: var(--accent-emerald); }
        #tb-dash-overlay .metric-bar-fill.amber { background: var(--accent-amber); }
        #tb-dash-overlay .metric-bar-fill.rose { background: var(--accent-rose); }
        #tb-dash-overlay .metric-bar-fill.purple { background: var(--accent-purple); }
        #tb-dash-overlay .metric-value { font-weight: 600; min-width: 32px; text-align: right; }
        #tb-dash-overlay .metric-value.good { color: var(--accent-emerald); }
        #tb-dash-overlay .metric-value.warn { color: var(--accent-rose); }
        #tb-dash-overlay .metric-value.low-min { color: var(--accent-amber); }
        #tb-dash-overlay .metric-unit { color: var(--text-muted); font-size: 10px; }
        #tb-dash-overlay .trends-section { margin-top: 8px; }
        #tb-dash-overlay .section-title {
            font-size: 18px; font-weight: 700; margin-bottom: 16px;
            display: flex; align-items: center; gap: 10px;
        }
        #tb-dash-overlay .section-title-icon {
            width: 28px; height: 28px; border-radius: 8px;
            display: flex; align-items: center; justify-content: center; font-size: 14px;
        }
        #tb-dash-overlay .trends-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 32px; }
        #tb-dash-overlay .trend-panel {
            background: var(--bg-card); backdrop-filter: blur(12px);
            border: 1px solid var(--border); border-radius: var(--radius-lg); overflow: hidden;
        }
        #tb-dash-overlay .trend-panel-header {
            padding: 16px 20px; border-bottom: 1px solid var(--border);
            font-size: 14px; font-weight: 700; display: flex; align-items: center; gap: 10px;
        }
        #tb-dash-overlay .trend-panel.alert .trend-panel-header {
            background: linear-gradient(135deg, rgba(244,63,94,0.06), rgba(245,158,11,0.04));
            color: var(--accent-rose);
        }
        #tb-dash-overlay .trend-panel.success .trend-panel-header {
            background: linear-gradient(135deg, rgba(16,185,129,0.06), rgba(59,130,246,0.04));
            color: var(--accent-emerald);
        }
        #tb-dash-overlay .trend-panel-body { padding: 16px 20px; }
        #tb-dash-overlay .trend-category { margin-bottom: 16px; }
        #tb-dash-overlay .trend-category:last-child { margin-bottom: 0; }
        #tb-dash-overlay .trend-category-title {
            font-size: 11px; font-weight: 600; text-transform: uppercase;
            letter-spacing: 0.8px; color: var(--text-muted); margin-bottom: 8px;
        }
        #tb-dash-overlay .trend-item {
            display: flex; align-items: center; justify-content: space-between;
            padding: 8px 12px; border-radius: 8px; background: var(--bg-glass);
            margin-bottom: 6px; transition: background 0.2s;
        }
        #tb-dash-overlay .trend-item:hover { background: rgba(255,255,255,0.04); }
        #tb-dash-overlay .trend-item-name { font-size: 13px; font-weight: 500; }
        #tb-dash-overlay .trend-item-value { font-size: 13px; font-weight: 700; }
        #tb-dash-overlay .trend-item-value.alert { color: var(--accent-rose); }
        #tb-dash-overlay .trend-item-value.warn { color: var(--accent-amber); }
        #tb-dash-overlay .trend-item-value.good { color: var(--accent-emerald); }
        #tb-dash-overlay .trend-item-value.blue { color: var(--accent-blue); }
        #tb-dash-overlay .empty-state { text-align: center; padding: 80px 20px; color: var(--text-muted); }
        #tb-dash-overlay .empty-icon { font-size: 48px; margin-bottom: 16px; opacity: 0.3; }
        #tb-dash-overlay .empty-title { font-size: 18px; font-weight: 600; color: var(--text-secondary); margin-bottom: 8px; }
        #tb-dash-overlay .modal-overlay {
            position: fixed; inset: 0; background: rgba(0,0,0,0.6);
            backdrop-filter: blur(8px); z-index: 1000002; display: none;
            align-items: center; justify-content: center; opacity: 0; transition: opacity 0.25s;
        }
        #tb-dash-overlay .modal-overlay.show { display: flex; opacity: 1; }
        #tb-dash-overlay .modal {
            background: var(--bg-secondary); border: 1px solid var(--border);
            border-radius: var(--radius-lg); width: 440px; max-height: 80vh;
            overflow-y: auto; box-shadow: 0 24px 48px rgba(0,0,0,0.4);
        }
        #tb-dash-overlay .modal-header {
            padding: 20px 24px; border-bottom: 1px solid var(--border);
            display: flex; align-items: center; justify-content: space-between;
        }
        #tb-dash-overlay .modal-title { font-size: 16px; font-weight: 700; }
        #tb-dash-overlay .modal-close {
            width: 32px; height: 32px; border-radius: 8px; border: none;
            background: var(--bg-glass); color: var(--text-secondary); cursor: pointer;
            font-size: 18px; display: flex; align-items: center; justify-content: center; transition: all 0.2s;
        }
        #tb-dash-overlay .modal-close:hover { background: rgba(255,255,255,0.08); color: var(--text-primary); }
        #tb-dash-overlay .modal-body { padding: 20px 24px; }
        #tb-dash-overlay .student-list-item {
            display: flex; align-items: center; justify-content: space-between;
            padding: 10px 12px; border-radius: 8px; background: var(--bg-glass);
            margin-bottom: 6px; transition: background 0.2s;
        }
        #tb-dash-overlay .student-list-item:hover { background: rgba(255,255,255,0.04); }
        #tb-dash-overlay .student-list-name { font-size: 14px; font-weight: 500; }
        #tb-dash-overlay .btn-remove {
            width: 28px; height: 28px; border-radius: 6px; border: none;
            background: transparent; color: var(--text-muted); cursor: pointer;
            font-size: 16px; display: flex; align-items: center; justify-content: center; transition: all 0.2s;
        }
        #tb-dash-overlay .btn-remove:hover { background: var(--accent-rose-glow); color: var(--accent-rose); }
        #tb-dash-overlay .group-tabs-bar {
            display: flex; gap: 6px; padding: 0 32px 12px; overflow-x: auto; align-items: center;
        }
        #tb-dash-overlay .group-tab {
            padding: 6px 16px; border-radius: 20px; border: 1px solid var(--border);
            background: var(--bg-glass); color: var(--text-secondary); font-size: 13px;
            font-weight: 500; cursor: pointer; white-space: nowrap; transition: all 0.2s; font-family: inherit;
        }
        #tb-dash-overlay .group-tab:hover { border-color: var(--border-hover); color: var(--text-primary); }
        #tb-dash-overlay .group-tab.active { background: var(--accent-blue); border-color: var(--accent-blue); color: white; }
        #tb-dash-overlay .group-tab-manage {
            padding: 6px 12px; border-radius: 20px; border: 1px dashed var(--border);
            background: transparent; color: var(--text-muted); font-size: 12px;
            cursor: pointer; white-space: nowrap; transition: all 0.2s; font-family: inherit;
        }
        #tb-dash-overlay .group-tab-manage:hover { border-color: var(--accent-blue); color: var(--accent-blue); }
        #tb-dash-overlay .modal-tabs { display: flex; border-bottom: 1px solid var(--border); }
        #tb-dash-overlay .modal-tab {
            flex: 1; padding: 12px; text-align: center; font-size: 13px; font-weight: 600;
            color: var(--text-muted); cursor: pointer; border: none; background: none;
            font-family: inherit; transition: all 0.2s; border-bottom: 2px solid transparent;
        }
        #tb-dash-overlay .modal-tab:hover { color: var(--text-secondary); }
        #tb-dash-overlay .modal-tab.active { color: var(--accent-blue); border-bottom-color: var(--accent-blue); }
        #tb-dash-overlay .modal-section { display: none; }
        #tb-dash-overlay .modal-section.active { display: block; }
        #tb-dash-overlay .group-card {
            background: var(--bg-glass); border: 1px solid var(--border);
            border-radius: 10px; padding: 14px; margin-bottom: 10px;
        }
        #tb-dash-overlay .group-card-header {
            display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;
        }
        #tb-dash-overlay .group-card-name { font-size: 14px; font-weight: 600; }
        #tb-dash-overlay .group-card-count { font-size: 11px; color: var(--text-muted); }
        #tb-dash-overlay .group-card-students { display: flex; flex-wrap: wrap; gap: 4px; }
        #tb-dash-overlay .group-student-chip {
            background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px;
            padding: 3px 10px; font-size: 11px; color: var(--text-secondary);
            display: flex; align-items: center; gap: 4px;
        }
        #tb-dash-overlay .group-student-chip .chip-remove { cursor: pointer; color: var(--text-muted); font-size: 13px; line-height: 1; }
        #tb-dash-overlay .group-student-chip .chip-remove:hover { color: var(--accent-rose); }
        #tb-dash-overlay .new-group-form { border: 1px dashed var(--border); border-radius: 10px; padding: 14px; }
        #tb-dash-overlay .new-group-form input, #tb-dash-overlay .new-group-form select {
            width: 100%; background: var(--bg-card); border: 1px solid var(--border);
            color: var(--text-primary); padding: 8px 12px; border-radius: 8px;
            font-family: inherit; font-size: 13px; outline: none; margin-bottom: 8px;
        }
        #tb-dash-overlay .new-group-form input:focus { border-color: var(--accent-blue); }
        #tb-dash-overlay .new-group-form input::placeholder { color: var(--text-muted); }
        #tb-dash-overlay .student-checkbox-list { max-height: 200px; overflow-y: auto; margin-bottom: 10px; }
        #tb-dash-overlay .student-checkbox-item {
            display: flex; align-items: center; gap: 8px; padding: 6px 8px;
            border-radius: 6px; cursor: pointer; font-size: 13px; transition: background 0.15s;
        }
        #tb-dash-overlay .student-checkbox-item:hover { background: rgba(255,255,255,0.03); }
        #tb-dash-overlay .student-checkbox-item input[type="checkbox"] { accent-color: var(--accent-blue); }
        #tb-dash-overlay .add-student-row { position: relative; margin-top: 16px; }
        #tb-dash-overlay .add-student-input-row { display: flex; gap: 8px; }
        #tb-dash-overlay .add-student-row input[type="text"] {
            flex: 1; background: var(--bg-card); border: 1px solid var(--border);
            color: var(--text-primary); padding: 10px 14px; border-radius: 8px;
            font-family: inherit; font-size: 13px; outline: none;
        }
        #tb-dash-overlay .add-student-row input[type="text"]:focus { border-color: var(--accent-blue); }
        #tb-dash-overlay .add-student-row input[type="text"]::placeholder { color: var(--text-muted); }
        #tb-dash-overlay .btn-add {
            padding: 10px 18px; border-radius: 8px; border: none;
            background: var(--accent-blue); color: white; font-size: 13px;
            font-weight: 600; cursor: pointer; font-family: inherit; transition: all 0.2s;
            white-space: nowrap;
        }
        #tb-dash-overlay .btn-add:hover { background: #2563eb; }
        #tb-dash-overlay .search-results {
            position: absolute; top: 100%; left: 0; right: 0;
            background: var(--bg-secondary); border: 1px solid var(--border);
            border-radius: 8px; margin-top: 4px; max-height: 220px;
            overflow-y: auto; z-index: 10; display: none;
            box-shadow: 0 8px 24px rgba(0,0,0,0.4);
        }
        #tb-dash-overlay .search-results.show { display: block; }
        #tb-dash-overlay .search-result-item {
            padding: 10px 14px; cursor: pointer; font-size: 13px;
            color: var(--text-primary); transition: background 0.15s;
            display: flex; justify-content: space-between; align-items: center;
        }
        #tb-dash-overlay .search-result-item:hover { background: rgba(59, 130, 246, 0.1); }
        #tb-dash-overlay .search-result-item .result-name { font-weight: 500; }
        #tb-dash-overlay .search-result-item .result-role {
            font-size: 11px; color: var(--text-muted); text-transform: capitalize;
        }
        #tb-dash-overlay .search-result-item.already-added {
            opacity: 0.4; pointer-events: none;
        }
        #tb-dash-overlay .search-result-item.already-added::after {
            content: 'Added'; font-size: 10px; color: var(--accent-emerald);
            font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;
        }
        #tb-dash-overlay .search-loading {
            padding: 12px 14px; font-size: 12px; color: var(--text-muted); text-align: center;
        }
        #tb-dash-overlay .loading-overlay {
            position: fixed; inset: 0; background: rgba(10, 14, 26, 0.85);
            backdrop-filter: blur(4px); z-index: 1000003; display: none;
            align-items: center; justify-content: center; flex-direction: column; gap: 20px;
        }
        #tb-dash-overlay .loading-overlay.show { display: flex; }
        #tb-dash-overlay .spinner {
            width: 48px; height: 48px; border: 3px solid var(--border);
            border-top-color: var(--accent-blue); border-radius: 50%; animation: tb-spin 0.8s linear infinite;
        }
        #tb-dash-overlay .loading-text { font-size: 14px; color: var(--text-secondary); font-weight: 500; }
        #tb-dash-overlay .loading-sub { font-size: 12px; color: var(--text-muted); }
        @keyframes tb-fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
        #tb-dash-overlay .fade-in { animation: tb-fadeIn 0.4s ease forwards; }
        #tb-dash-overlay .chat-fab {
            position: fixed; bottom: 24px; right: 24px; width: 56px; height: 56px;
            border-radius: 50%; border: none;
            background: linear-gradient(135deg, var(--accent-blue), #2563eb); color: white;
            cursor: pointer; z-index: 1000004; display: flex; align-items: center; justify-content: center;
            box-shadow: 0 4px 24px rgba(59,130,246,0.4); transition: transform 0.2s, box-shadow 0.2s;
        }
        #tb-dash-overlay .chat-fab:hover { transform: scale(1.08); box-shadow: 0 6px 32px rgba(59,130,246,0.5); }
        #tb-dash-overlay .chat-fab.hidden { display: none; }
        #tb-dash-overlay .chat-panel {
            position: fixed; bottom: 24px; right: 24px; width: 400px; height: 500px;
            z-index: 1000004; background: rgba(15, 22, 41, 0.92); backdrop-filter: blur(20px);
            border: 1px solid var(--border-hover); border-radius: var(--radius-lg);
            display: flex; flex-direction: column; box-shadow: 0 16px 48px rgba(0,0,0,0.5);
            transform: translateY(20px); opacity: 0; pointer-events: none;
            transition: transform 0.3s ease, opacity 0.3s ease;
        }
        #tb-dash-overlay .chat-panel.open { transform: translateY(0); opacity: 1; pointer-events: auto; }
        #tb-dash-overlay .chat-header {
            padding: 16px 20px; border-bottom: 1px solid var(--border);
            display: flex; align-items: center; justify-content: space-between; flex-shrink: 0;
        }
        #tb-dash-overlay .chat-header-title { font-size: 15px; font-weight: 700; display: flex; align-items: center; gap: 8px; }
        #tb-dash-overlay .chat-header-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--accent-emerald); }
        #tb-dash-overlay .chat-close {
            width: 30px; height: 30px; border-radius: 8px; border: none;
            background: var(--bg-glass); color: var(--text-secondary); cursor: pointer;
            font-size: 18px; display: flex; align-items: center; justify-content: center; transition: all 0.2s;
        }
        #tb-dash-overlay .chat-close:hover { background: rgba(255,255,255,0.08); color: var(--text-primary); }
        #tb-dash-overlay .chat-messages {
            flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 12px;
        }
        #tb-dash-overlay .chat-suggestions { display: flex; flex-wrap: wrap; gap: 8px; padding: 0 16px 12px; }
        #tb-dash-overlay .chat-chip {
            padding: 6px 14px; border-radius: 20px; border: 1px solid var(--border-hover);
            background: var(--bg-glass); color: var(--text-secondary); font-size: 12px;
            font-family: inherit; cursor: pointer; transition: all 0.2s;
        }
        #tb-dash-overlay .chat-chip:hover {
            background: var(--accent-blue-glow); border-color: rgba(59,130,246,0.3); color: var(--accent-blue);
        }
        #tb-dash-overlay .chat-bubble {
            max-width: 85%; padding: 10px 14px; border-radius: 12px;
            font-size: 13px; line-height: 1.5; word-wrap: break-word; white-space: pre-wrap;
        }
        #tb-dash-overlay .chat-bubble.user {
            align-self: flex-end; background: linear-gradient(135deg, var(--accent-blue), #2563eb);
            color: white; border-bottom-right-radius: 4px;
        }
        #tb-dash-overlay .chat-bubble.assistant {
            align-self: flex-start; background: rgba(255,255,255,0.06);
            border: 1px solid var(--border); color: var(--text-primary); border-bottom-left-radius: 4px;
        }
        #tb-dash-overlay .chat-input-area {
            padding: 12px 16px; border-top: 1px solid var(--border);
            display: flex; gap: 8px; flex-shrink: 0;
        }
        #tb-dash-overlay .chat-input {
            flex: 1; background: var(--bg-card); border: 1px solid var(--border);
            color: var(--text-primary); padding: 10px 14px; border-radius: 10px;
            font-family: inherit; font-size: 13px; outline: none; transition: border-color 0.2s;
        }
        #tb-dash-overlay .chat-input:focus { border-color: var(--accent-blue); }
        #tb-dash-overlay .chat-input::placeholder { color: var(--text-muted); }
        #tb-dash-overlay .chat-send {
            width: 40px; height: 40px; border-radius: 10px; border: none;
            background: var(--accent-blue); color: white; cursor: pointer;
            display: flex; align-items: center; justify-content: center;
            transition: background 0.2s; flex-shrink: 0;
        }
        #tb-dash-overlay .chat-send:hover { background: #2563eb; }
        #tb-dash-close {
            position: fixed; top: 16px; right: 16px; z-index: 1000001;
            background: rgba(244,63,94,0.9); color: white; border: none;
            border-radius: 50%; width: 36px; height: 36px; font-size: 20px;
            cursor: pointer; display: flex; align-items: center; justify-content: center;
        }
        @media (max-width: 900px) {
            #tb-dash-overlay .summary-row { grid-template-columns: repeat(2, 1fr); }
            #tb-dash-overlay .student-grid { grid-template-columns: 1fr; }
            #tb-dash-overlay .trends-grid { grid-template-columns: 1fr; }
            #tb-dash-overlay .controls { padding: 12px 16px; }
            #tb-dash-overlay .main { padding: 16px; }
            #tb-dash-overlay .topbar { padding: 12px 16px; }
        }
        @media (max-width: 480px) {
            #tb-dash-overlay .chat-panel { width: calc(100vw - 16px); height: calc(100vh - 80px); bottom: 8px; right: 8px; }
        }
    `;
    document.head.appendChild(styleEl);

    // === Load Google Fonts ===
    if (!document.querySelector('link[href*="fonts.googleapis.com/css2?family=Inter"]')) {
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = 'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap';
        document.head.appendChild(link);
    }

    // === Create overlay ===
    const overlay = document.createElement('div');
    overlay.id = 'tb-dash-overlay';
    overlay.innerHTML = `
        <button id="tb-dash-close" title="Close Dashboard">\u2715</button>
        <div class="app">
            <div class="topbar">
                <div class="topbar-left">
                    <div class="logo">TB</div>
                    <span class="app-title">XP Quick View</span>
                </div>
                <div class="topbar-right">
                    <span class="timestamp" id="timestamp"></span>
                    <div class="status-dot" id="statusDot" title="Connected"></div>
                    <button class="btn-icon" onclick="openModal()" title="Manage Students">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
                    </button>
                    <button class="btn-icon" onclick="openSettings()" title="Settings">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.32 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
                    </button>
                </div>
            </div>
            <div class="controls">
                <div class="date-group">
                    <span class="date-label">From</span>
                    <input type="date" id="dateFrom">
                </div>
                <div class="date-group">
                    <span class="date-label">To</span>
                    <input type="date" id="dateTo">
                </div>
                <div class="presets">
                    <button class="preset-btn" onclick="setPreset('today', this)">Today</button>
                    <button class="preset-btn" onclick="setPreset('week', this)">This Week</button>
                    <button class="preset-btn" onclick="setPreset('last', this)">Last Week</button>
                </div>
                <button class="btn-pull" id="btnPull" onclick="pullData()">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
                    Pull Data
                </button>
            </div>
            <div class="group-tabs-bar" id="groupTabsBar"></div>
            <div class="main" id="mainContent">
                <div class="empty-state" id="emptyState">
                    <div class="empty-icon">&#9685;</div>
                    <div class="empty-title" id="emptyTitle">Welcome to XP Quick View</div>
                    <div id="emptyMessage">Checking connection...</div>
                </div>
            </div>
        </div>
        <button class="chat-fab" id="chatFab" onclick="toggleChat()" title="Data Assistant">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
        </button>
        <div class="chat-panel" id="chatPanel">
            <div class="chat-header">
                <span class="chat-header-title"><span class="chat-header-dot"></span> Data Assistant</span>
                <button class="chat-close" onclick="toggleChat()">&times;</button>
            </div>
            <div class="chat-messages" id="chatMessages"></div>
            <div class="chat-suggestions" id="chatSuggestions">
                <button class="chat-chip" onclick="sendChat('Lowest accuracy?')">Lowest accuracy?</button>
                <button class="chat-chip" onclick="sendChat('Who needs help?')">Who needs help?</button>
                <button class="chat-chip" onclick="sendChat('Best performer?')">Best performer?</button>
                <button class="chat-chip" onclick="sendChat('Weekly summary')">Weekly summary</button>
            </div>
            <div class="chat-input-area">
                <input class="chat-input" id="chatInput" type="text" placeholder="Ask about student data..." onkeydown="if(event.key==='Enter')sendChat()">
                <button class="chat-send" onclick="sendChat()">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
                </button>
            </div>
        </div>
        <div class="loading-overlay" id="loadingOverlay">
            <div class="spinner"></div>
            <div class="loading-text" id="loadingText">Pulling metrics from TimeBack...</div>
            <div class="loading-sub" id="loadingSub">Fetching data in the background</div>
        </div>
        <div class="modal-overlay" id="modalOverlay">
            <div class="modal">
                <div class="modal-header">
                    <span class="modal-title">Manage</span>
                    <button class="modal-close" onclick="closeModal()">&times;</button>
                </div>
                <div class="modal-tabs">
                    <button class="modal-tab active" onclick="switchModalTab('students', this)">Students</button>
                    <button class="modal-tab" onclick="switchModalTab('groups', this)">Groups</button>
                </div>
                <div class="modal-body">
                    <div class="modal-section active" id="modalStudents">
                        <div id="studentList"></div>
                        <div class="add-student-row">
                            <div class="add-student-input-row">
                                <input type="text" id="newStudentInput" placeholder="Search for a student..." autocomplete="off" oninput="searchStudents(this.value)" onkeydown="handleSearchKeydown(event)">
                                <button class="btn-add" onclick="addStudent()">Add</button>
                            </div>
                            <div class="search-results" id="searchResults"></div>
                        </div>
                    </div>
                    <div class="modal-section" id="modalGroups">
                        <div id="groupList"></div>
                        <div class="new-group-form" id="newGroupForm">
                            <input type="text" id="newGroupName" placeholder="Group name (e.g. Middle School)..." onkeydown="if(event.key==='Enter')document.getElementById('newGroupName').blur()">
                            <div class="student-checkbox-list" id="newGroupStudents"></div>
                            <button class="btn-add" onclick="createGroup()" style="width:100%">Create Group</button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
    document.body.appendChild(overlay);

    // === Close button ===
    document.getElementById('tb-dash-close').addEventListener('click', function() {
        document.getElementById('tb-dash-overlay').remove();
        if (document.getElementById('tb-dash-styles')) document.getElementById('tb-dash-styles').remove();
    });

    // === Modal overlay click-outside ===
    document.getElementById('modalOverlay').addEventListener('click', function(e) {
        if (e.target === e.currentTarget) closeModal();
    });

    // === Storage functions ===
    const STORAGE_PREFIX = 'tb-dash-';
    function getStudentsFromStorage() { return JSON.parse(localStorage.getItem(STORAGE_PREFIX + 'students') || '[]'); }
    function saveStudentsToStorage(s) { localStorage.setItem(STORAGE_PREFIX + 'students', JSON.stringify(s)); }
    function getGroupsFromStorage() { return JSON.parse(localStorage.getItem(STORAGE_PREFIX + 'groups') || '[]'); }
    function saveGroupsToStorage(g) { localStorage.setItem(STORAGE_PREFIX + 'groups', JSON.stringify(g)); }
    function getStudentIds() { return JSON.parse(localStorage.getItem(STORAGE_PREFIX + 'student-ids') || '{}'); }
    function saveStudentIds(ids) { localStorage.setItem(STORAGE_PREFIX + 'student-ids', JSON.stringify(ids)); }
    function getCachedDay(dateStr) {
        var raw = localStorage.getItem(STORAGE_PREFIX + 'cache-' + dateStr);
        if (!raw) return null;
        var parsed = JSON.parse(raw);
        // New format stores { _fetchedAt, students }; old format is just an array
        if (parsed && parsed._fetchedAt) return parsed;
        // Legacy: wrap old format
        return { students: parsed, _fetchedAt: 0 };
    }
    function saveCachedDay(dateStr, data) {
        localStorage.setItem(STORAGE_PREFIX + 'cache-' + dateStr, JSON.stringify({
            students: data,
            _fetchedAt: Date.now(),
        }));
    }
    function isCacheFresh(dateStr, cacheEntry) {
        // Cache is only trustworthy if data was fetched AFTER the day ended.
        // "Day ended" = midnight Pacific at the end of that date.
        if (!cacheEntry || !cacheEntry._fetchedAt) return false;
        var offset = getPacificOffsetHours(dateStr);
        // End of the day in UTC: next day at offset:00 UTC
        var nextDay = new Date(dateStr + 'T00:00:00');
        nextDay.setDate(nextDay.getDate() + 1);
        var dayEndUtc = new Date(nextDay.getFullYear() + '-' + String(nextDay.getMonth() + 1).padStart(2, '0') + '-' + String(nextDay.getDate()).padStart(2, '0') + 'T' + String(offset).padStart(2, '0') + ':00:00.000Z');
        return cacheEntry._fetchedAt > dayEndUtc.getTime();
    }
    function getLastData() { return JSON.parse(localStorage.getItem(STORAGE_PREFIX + 'last-data') || 'null'); }
    function saveLastData(d) { localStorage.setItem(STORAGE_PREFIX + 'last-data', JSON.stringify(d)); }

    // === API functions ===
    async function resolveStudentId(name) {
        var ids = getStudentIds();
        if (ids[name]) return ids[name];
        var resp = await fetch('/_serverFn/src_features_learning-metrics_components_fast-student-search_actions_client_ts--fetchUsersByRole_createServerFn_handler?createServerFn', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                data: { roles: ['student'], search: name, limit: { '$undefined': 0 }, orgSourcedIds: [] },
                context: {},
            }),
        });
        var data = await resp.json();
        var results = data.result || [];
        for (var ui = 0; ui < results.length; ui++) {
            var user = results[ui];
            var fullName = ((user.givenName || '') + ' ' + (user.familyName || '')).trim();
            if (fullName.toLowerCase() === name.toLowerCase()) {
                ids[name] = user.sourcedId;
                saveStudentIds(ids);
                return user.sourcedId;
            }
        }
        if (results.length) {
            ids[name] = results[0].sourcedId;
            saveStudentIds(ids);
            return results[0].sourcedId;
        }
        return null;
    }

    function getPacificOffsetHours(dateStr) {
        // Determine PDT (7) vs PST (8) for a given date using Intl API
        var formatted = new Intl.DateTimeFormat('en-US', {
            timeZone: 'America/Los_Angeles',
            timeZoneName: 'short'
        }).format(new Date(dateStr + 'T12:00:00'));
        return formatted.includes('PDT') ? 7 : 8;
    }

    function isWeekend(dateStr) {
        var d = new Date(dateStr + 'T12:00:00');
        var dow = d.getDay();
        return dow === 0 || dow === 6;
    }

    function getYesterday() {
        var now = new Date();
        now.setDate(now.getDate() - 1);
        return now.getFullYear() + '-' + String(now.getMonth() + 1).padStart(2, '0') + '-' + String(now.getDate()).padStart(2, '0');
    }

    async function fetchActivityMetrics(studentId, dateStr) {
        var offset = getPacificOffsetHours(dateStr);
        var offsetStr = String(offset).padStart(2, '0');
        var endOffsetStr = String(offset - 1).padStart(2, '0');
        var startUtc = dateStr + 'T' + offsetStr + ':00:00.000Z';
        var dt = new Date(dateStr + 'T00:00:00');
        var nextDay = new Date(dt);
        nextDay.setDate(nextDay.getDate() + 1);
        var nextDateStr = nextDay.getFullYear() + '-' + String(nextDay.getMonth() + 1).padStart(2, '0') + '-' + String(nextDay.getDate()).padStart(2, '0');
        var endUtc = nextDateStr + 'T' + endOffsetStr + ':59:59.999Z';
        var resp = await fetch('/_serverFn/src_features_learning-metrics_actions_getActivityMetrics_ts--getActivityMetrics_createServerFn_handler?createServerFn', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                data: { startDate: startUtc, endDate: endUtc, studentId: studentId, timezone: 'America/Los_Angeles' },
                context: {},
            }),
        });
        var data = await resp.json();
        return ((data.result || {}).data) || {};
    }

    function processApiMetrics(studentName, metricsData, dateStr) {
        var facts = ((metricsData.facts || {})[dateStr]) || {};
        var subjects = [];
        var totalXp = 0, totalMinutes = 0, totalCorrect = 0, totalQuestions = 0;
        for (var subjectName in facts) {
            if (!facts.hasOwnProperty(subjectName)) continue;
            var subjectData = facts[subjectName];

            // Log full subject data keys to console for debugging test detection
            var subjectKeys = Object.keys(subjectData);
            if (subjectKeys.length > 2) {
                console.log('[XP Tracker] ' + studentName + ' > ' + subjectName + ' keys:', subjectKeys, subjectData);
            }

            var activity = subjectData.activityMetrics || {};
            var timeData = subjectData.timeSpentMetrics || {};
            var testMetrics = subjectData.testMetrics || subjectData.alphaTestMetrics || subjectData.assessmentMetrics || null;
            var xp = activity.xpEarned || 0;
            var correct = activity.correctQuestions || 0;
            var totalQ = activity.totalQuestions || 0;
            var mastered = activity.masteredUnits || 0;
            var activeSecs = timeData.activeSeconds || 0;
            var minutes = activeSecs ? Math.ceil(activeSecs / 60) : 0;
            var accuracy = totalQ > 0 ? Math.round((correct / totalQ) * 100) : 0;

            // Detect Alpha Test — check multiple possible indicators
            var hasTest = false;
            if (testMetrics) {
                hasTest = true;
            }
            // Check if activityMetrics has test-related fields
            if (activity.alphaTestTaken || activity.testTaken || activity.hasTest) {
                hasTest = true;
            }
            // Check for a dedicated test key at the subject level
            if (subjectData.alphaTest || subjectData.test || subjectData.hasAlphaTest) {
                hasTest = true;
            }
            // Log when we detect something unexpected for investigation
            for (var key in subjectData) {
                if (subjectData.hasOwnProperty(key) && key !== 'activityMetrics' && key !== 'timeSpentMetrics') {
                    console.log('[XP Tracker] Extra key in ' + studentName + ' > ' + subjectName + ': "' + key + '"', subjectData[key]);
                    // If any extra key contains "test" in its name, flag it
                    if (key.toLowerCase().indexOf('test') !== -1) {
                        hasTest = true;
                    }
                }
            }

            totalXp += xp;
            totalMinutes += minutes;
            totalCorrect += correct;
            totalQuestions += totalQ;
            subjects.push({ name: subjectName, xp: Math.round(xp), accuracy: accuracy, minutes: minutes, mastered: mastered, no_data: xp === 0 && minutes === 0 && accuracy === 0, has_test: hasTest });
        }
        return {
            name: studentName,
            total_xp: Math.round(totalXp),
            overall_accuracy: totalQuestions > 0 ? Math.round((totalCorrect / totalQuestions) * 100) : 0,
            total_minutes: totalMinutes,
            subjects: subjects,
            absent: totalXp === 0 && totalMinutes === 0 && subjects.length === 0,
        };
    }

    // === Data fetching ===
    async function fetchDayViaApi(dateStr) {
        var studentList = getStudentsFromStorage();
        var processed = [];
        for (var si = 0; si < studentList.length; si++) {
            var name = studentList[si];
            var sid = await resolveStudentId(name);
            if (!sid) continue;
            try {
                var metrics = await fetchActivityMetrics(sid, dateStr);
                processed.push(processApiMetrics(name, metrics, dateStr));
            } catch (e) {
                console.error('API error for ' + name + ' on ' + dateStr + ':', e);
            }
        }
        return processed;
    }

    function getLocalToday() {
        var now = new Date();
        return now.getFullYear() + '-' + String(now.getMonth() + 1).padStart(2, '0') + '-' + String(now.getDate()).padStart(2, '0');
    }

    async function scrapeSingle(dateStr) {
        var studentList = getStudentsFromStorage();
        if (!studentList.length) return { error: 'no_students', message: 'Add students first.' };
        var today = getLocalToday();
        dateStr = dateStr || today;
        // Use cache only if data was fetched AFTER that day ended
        // This prevents stale mid-day caches (e.g. pulled Friday at 2pm, missing evening work)
        if (dateStr !== today) {
            var cacheEntry = getCachedDay(dateStr);
            if (cacheEntry && isCacheFresh(dateStr, cacheEntry)) {
                return { students: cacheEntry.students, date: dateStr, timestamp: new Date().toLocaleString('en-US', { month: 'long', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' }), from_cache: true };
            }
        }
        var processed = await fetchDayViaApi(dateStr);
        if (!processed.length) return { error: 'no_data', message: 'No data returned. Make sure you are logged into TimeBack.' };
        saveCachedDay(dateStr, processed);
        var result = { students: processed, date: dateStr, timestamp: new Date().toLocaleString('en-US', { month: 'long', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' }) };
        saveLastData(result);
        return result;
    }

    async function scrapeRange(startDate, endDate, weekdaysOnly) {
        var studentList = getStudentsFromStorage();
        if (!studentList.length) return { error: 'no_students', message: 'Add students first.' };
        weekdaysOnly = weekdaysOnly !== false;
        var today = getLocalToday();
        var dates = [];
        var current = new Date(startDate + 'T12:00:00');
        var end = new Date(endDate + 'T12:00:00');
        while (current <= end) {
            var dow = current.getDay();
            if (!weekdaysOnly || (dow >= 1 && dow <= 5)) {
                dates.push(current.getFullYear() + '-' + String(current.getMonth() + 1).padStart(2, '0') + '-' + String(current.getDate()).padStart(2, '0'));
            }
            current.setDate(current.getDate() + 1);
        }
        if (!dates.length) return { error: 'no_dates', message: 'No weekdays in the selected range.' };
        var days = [];
        var datesToFetch = [];
        for (var di = 0; di < dates.length; di++) {
            var ds = dates[di];
            // Use cache only if data was fetched AFTER that day ended
            if (ds !== today) {
                var cacheEntry = getCachedDay(ds);
                if (cacheEntry && isCacheFresh(ds, cacheEntry)) {
                    days.push({ date: ds, day_name: new Date(ds + 'T12:00:00').toLocaleDateString('en-US', { weekday: 'long' }), students: cacheEntry.students });
                    continue;
                }
            }
            datesToFetch.push(ds);
        }
        for (var fi = 0; fi < datesToFetch.length; fi++) {
            var ds2 = datesToFetch[fi];
            var processed = await fetchDayViaApi(ds2);
            if (processed.length) {
                saveCachedDay(ds2, processed);
                days.push({ date: ds2, day_name: new Date(ds2 + 'T12:00:00').toLocaleDateString('en-US', { weekday: 'long' }), students: processed });
            }
        }
        days.sort(function(a, b) { return a.date.localeCompare(b.date); });
        var result = { days: days, start: startDate, end: endDate, cached_count: dates.length - datesToFetch.length, scraped_count: datesToFetch.length, timestamp: new Date().toLocaleString('en-US', { month: 'long', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' }) };
        saveLastData(result);
        return result;
    }

    // === State ===
    var currentData = null;
    var students = [];
    var groups = [];
    var activeGroupIndex = -1;
    var activeDayIndex = 0;
    var weeklyViewMode = 'daily'; // 'daily' or 'subjects'

    var todayDate = new Date();
    var yyyy = function(d) { return d.getFullYear() + '-' + String(d.getMonth()+1).padStart(2,'0') + '-' + String(d.getDate()).padStart(2,'0'); };

    document.getElementById('dateFrom').value = yyyy(todayDate);
    document.getElementById('dateTo').value = yyyy(todayDate);

    // === Presets ===
    function setPreset(type, el) {
        document.querySelectorAll('#tb-dash-overlay .preset-btn').forEach(function(b) { b.classList.remove('active'); });
        if (el) el.classList.add('active');
        var d = new Date();
        var day = d.getDay();
        if (type === 'today') {
            document.getElementById('dateFrom').value = yyyy(d);
            document.getElementById('dateTo').value = yyyy(d);
        } else if (type === 'week') {
            var mon = new Date(d);
            mon.setDate(d.getDate() - (day === 0 ? 6 : day - 1));
            var sun = new Date(mon);
            sun.setDate(mon.getDate() + 6);
            document.getElementById('dateFrom').value = yyyy(mon);
            document.getElementById('dateTo').value = yyyy(sun);
        } else if (type === 'last') {
            var mon2 = new Date(d);
            mon2.setDate(d.getDate() - (day === 0 ? 13 : day + 6));
            var sun2 = new Date(mon2);
            sun2.setDate(mon2.getDate() + 6);
            document.getElementById('dateFrom').value = yyyy(mon2);
            document.getElementById('dateTo').value = yyyy(sun2);
        }
    }

    // === Pull Data ===
    async function pullData() {
        var btn = document.getElementById('btnPull');
        var loading = document.getElementById('loadingOverlay');
        var statusDot = document.getElementById('statusDot');
        btn.disabled = true;
        btn.classList.add('loading');
        loading.classList.add('show');
        statusDot.className = 'status-dot loading';
        var start = document.getElementById('dateFrom').value;
        var end = document.getElementById('dateTo').value;
        try {
            var data;
            if (start === end) {
                data = await scrapeSingle(start);
            } else {
                data = await scrapeRange(start, end, false);
            }
            if (data.error) {
                alert(data.message || 'Error pulling data');
                statusDot.className = 'status-dot offline';
            } else {
                currentData = data;
                activeDayIndex = 0;
                renderDashboard(data);
                statusDot.className = 'status-dot';
                if (data.cached_count !== undefined) {
                    var ts = document.getElementById('timestamp');
                    if (data.cached_count > 0) {
                        ts.textContent = (ts.textContent || '') + ' (' + data.cached_count + ' cached, ' + data.scraped_count + ' scraped)';
                    }
                }
                if (data.from_cache) {
                    var ts2 = document.getElementById('timestamp');
                    ts2.textContent = (ts2.textContent || '') + ' (from cache)';
                }
            }
        } catch (e) {
            alert('Error: ' + e.message);
            statusDot.className = 'status-dot offline';
        } finally {
            btn.disabled = false;
            btn.classList.remove('loading');
            loading.classList.remove('show');
        }
    }

    // === Render Dashboard ===
    function renderDashboard(data) {
        var main = document.getElementById('mainContent');
        document.getElementById('timestamp').textContent = data.timestamp || '';
        if (data.days && data.days.length > 0) {
            renderWeeklyView(main, data);
        } else if (data.students) {
            renderDayView(main, data.students, data.date);
        } else {
            main.innerHTML = '<div class="empty-state"><div class="empty-icon">&#9888;</div><div class="empty-title">No data returned</div></div>';
        }
    }

    function renderWeeklyView(main, data) {
        var filteredDays = data.days.map(function(day) {
            return Object.assign({}, day, { students: getFilteredStudents(day.students) });
        });
        var startLabel = formatDateLabel(data.start || (filteredDays[0] && filteredDays[0].date));
        var endLabel = formatDateLabel(data.end || (filteredDays[filteredDays.length - 1] && filteredDays[filteredDays.length - 1].date));
        var rangeLabel = startLabel + ' \u2013 ' + endLabel;
        var html = '';
        // View toggle buttons
        html += '<div class="view-toggle-bar">' +
            '<button class="view-toggle-btn ' + (weeklyViewMode === 'daily' ? 'active' : '') + '" onclick="switchWeeklyView(\'daily\')">Daily Breakdown</button>' +
            '<button class="view-toggle-btn ' + (weeklyViewMode === 'subjects' ? 'active' : '') + '" onclick="switchWeeklyView(\'subjects\')">Weekly XP by Subject</button>' +
            '</div>';

        if (weeklyViewMode === 'subjects') {
            // Subject totals view
            html += '<div class="section-header">Weekly XP by Subject <span class="section-date">' + rangeLabel + '</span></div>';
            html += renderWeeklySubjectTotals(filteredDays);
            html += '<div class="section-header">Weekly XP Leaderboard <span class="section-date">' + rangeLabel + '</span></div>';
            html += renderWeeklyLeaderboard(filteredDays);
            html += renderWeeklyTrends(filteredDays);
        } else {
            // Daily breakdown view (original)
            html += '<div class="section-header">Daily XP Overview <span class="section-date">' + rangeLabel + '</span></div>';
            var dayXPs = filteredDays.map(function(d) { return d.students.reduce(function(s, st) { return s + st.total_xp; }, 0); });
            var maxXP = Math.max.apply(null, dayXPs.concat([1]));
            html += '<div class="day-tabs">';
            filteredDays.forEach(function(day, i) {
                var totalXP = dayXPs[i];
                var activeStudents = day.students.filter(function(s) { return !(s.absent || (s.total_xp === 0 && s.total_minutes === 0 && (!s.subjects || s.subjects.length === 0))); });
                var dayIsWeekend = isWeekend(day.date);
                var absentCount = dayIsWeekend ? 0 : day.students.length - activeStudents.length;
                var avgAcc = activeStudents.length ? Math.round(activeStudents.reduce(function(s, st) { return s + st.overall_accuracy; }, 0) / activeStudents.length) : 0;
                var barPct = Math.round((totalXP / maxXP) * 100);
                var absentTag = absentCount > 0 ? '<div style="font-size:10px;color:var(--accent-rose);margin-top:2px;">' + absentCount + ' absent</div>' : '';
                html += '<button class="day-tab ' + (i === activeDayIndex ? 'active' : '') + '" onclick="switchDay(' + i + ')">' +
                    '<div class="day-tab-name">' + day.day_name + '</div>' +
                    '<div class="day-tab-xp">' + Math.round(totalXP) + ' XP &middot; ' + avgAcc + '%</div>' +
                    absentTag +
                    '<div class="metric-bar" style="width:100%;margin-top:6px;height:3px;">' +
                    '<div class="metric-bar-fill ' + (avgAcc >= 80 ? 'emerald' : 'rose') + '" style="width:' + barPct + '%"></div>' +
                    '</div></button>';
            });
            html += '</div>';
            html += '<div class="section-header">Weekly XP Leaderboard <span class="section-date">' + rangeLabel + '</span></div>';
            html += renderWeeklyLeaderboard(filteredDays);
            var activeDay = filteredDays[activeDayIndex];
            if (activeDay) {
                var activeDateLabel = formatDateLabel(activeDay.date);
                html += '<div class="section-header">' + activeDay.day_name + ' Summary <span class="section-date">' + activeDateLabel + '</span></div>';
                html += renderSummaryCards(activeDay.students, activeDay.date);
                html += '<div class="section-header">' + activeDay.day_name + ' Student Breakdown <span class="section-date">' + activeDateLabel + '</span></div>';
                html += '<div class="student-grid">';
                var activeDayIsWeekend = isWeekend(activeDay.date);
                activeDay.students.forEach(function(s) { html += renderStudentCard(s, activeDayIsWeekend); });
                html += '</div>';
            }
            html += renderWeeklyTrends(filteredDays);
        }
        main.innerHTML = html;
    }

    function switchWeeklyView(mode) {
        weeklyViewMode = mode;
        if (currentData) renderDashboard(currentData);
    }

    function renderWeeklySubjectTotals(filteredDays) {
        // Aggregate XP per student per subject across all days
        var allSubjects = {};
        var studentData = {};

        filteredDays.forEach(function(day) {
            day.students.forEach(function(s) {
                if (!studentData[s.name]) studentData[s.name] = {};
                s.subjects.forEach(function(subj) {
                    if (subj.no_data) return;
                    allSubjects[subj.name] = true;
                    if (!studentData[s.name][subj.name]) {
                        studentData[s.name][subj.name] = { xp: 0, accuracy: [], minutes: 0 };
                    }
                    studentData[s.name][subj.name].xp += subj.xp;
                    studentData[s.name][subj.name].accuracy.push(subj.accuracy);
                    studentData[s.name][subj.name].minutes += subj.minutes;
                });
            });
        });

        var subjectNames = Object.keys(allSubjects).sort();
        var studentNames = Object.keys(studentData).sort(function(a, b) {
            var totalA = 0, totalB = 0;
            for (var s in studentData[a]) totalA += studentData[a][s].xp;
            for (var s2 in studentData[b]) totalB += studentData[b][s2].xp;
            return totalB - totalA;
        });

        if (!subjectNames.length || !studentNames.length) return '<div style="color:var(--text-muted);text-align:center;padding:20px;">No subject data available</div>';

        // Build table
        var html = '<div class="subject-totals-wrapper"><table class="subject-totals-table">';

        // Header row
        html += '<thead><tr><th>Student</th>';
        subjectNames.forEach(function(subj) {
            html += '<th style="text-align:center;">' + subj + '</th>';
        });
        html += '<th style="text-align:center;">Total XP</th>';
        html += '<th style="text-align:center;">Avg Acc</th>';
        html += '<th style="text-align:center;">Total Min</th>';
        html += '</tr></thead>';

        // Student rows
        html += '<tbody>';
        var subjectColTotals = {};
        subjectNames.forEach(function(s) { subjectColTotals[s] = 0; });
        var grandTotalXP = 0, grandTotalMin = 0;

        studentNames.forEach(function(name) {
            var data = studentData[name];
            var rowTotalXP = 0, rowTotalMin = 0, rowAccs = [];

            html += '<tr><td class="student-name-cell">' + name + '</td>';
            subjectNames.forEach(function(subj) {
                var d = data[subj];
                if (d && d.xp !== 0) {
                    html += '<td class="xp-cell">' + Math.round(d.xp) + '</td>';
                    rowTotalXP += d.xp;
                    rowTotalMin += d.minutes;
                    subjectColTotals[subj] += d.xp;
                    d.accuracy.forEach(function(a) { rowAccs.push(a); });
                } else if (d) {
                    html += '<td class="xp-cell zero">0</td>';
                    rowTotalMin += d.minutes;
                    d.accuracy.forEach(function(a) { rowAccs.push(a); });
                } else {
                    html += '<td class="xp-cell zero">&mdash;</td>';
                }
            });

            var avgAcc = rowAccs.length ? Math.round(rowAccs.reduce(function(a, b) { return a + b; }, 0) / rowAccs.length) : 0;
            var accColor = avgAcc >= 80 ? 'var(--accent-emerald)' : 'var(--accent-rose)';

            html += '<td class="total-cell">' + Math.round(rowTotalXP) + '</td>';
            html += '<td class="xp-cell" style="color:' + accColor + '">' + avgAcc + '%</td>';
            html += '<td class="xp-cell" style="color:var(--accent-purple)">' + rowTotalMin + '</td>';
            html += '</tr>';

            grandTotalXP += rowTotalXP;
            grandTotalMin += rowTotalMin;
        });

        // Totals row
        html += '<tr class="total-row"><td class="student-name-cell">All Students</td>';
        subjectNames.forEach(function(subj) {
            var val = subjectColTotals[subj];
            html += '<td class="total-cell">' + Math.round(val) + '</td>';
        });
        html += '<td class="total-cell" style="font-size:15px;">' + Math.round(grandTotalXP) + '</td>';
        html += '<td class="total-cell">&mdash;</td>';
        html += '<td class="total-cell" style="color:var(--accent-purple)">' + grandTotalMin + '</td>';
        html += '</tr>';

        html += '</tbody></table></div>';
        return html;
    }

    function formatDateLabel(dateStr) {
        if (!dateStr) return '';
        var d = new Date(dateStr + 'T12:00:00');
        return d.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' });
    }

    function renderDayView(main, studentsData, dateStr) {
        var filtered = getFilteredStudents(studentsData);
        var dateLabel = formatDateLabel(dateStr);
        var dayIsWeekend = isWeekend(dateStr);
        var html = '<div class="section-header">Daily Summary <span class="section-date">' + dateLabel + '</span></div>';
        html += renderSummaryCards(filtered, dateStr);
        html += '<div class="section-header">XP Leaderboard <span class="section-date">' + dateLabel + '</span></div>';
        html += renderLeaderboard(filtered);
        html += '<div class="section-header">Individual Student Breakdown <span class="section-date">' + dateLabel + '</span></div>';
        html += '<div class="student-grid">';
        filtered.forEach(function(s) { html += renderStudentCard(s, dayIsWeekend); });
        html += '</div>';
        main.innerHTML = html;
    }

    function renderLeaderboard(studentsData) {
        if (!studentsData.length) return '';
        var sorted = studentsData.slice().sort(function(a,b) { return b.total_xp - a.total_xp; });
        var maxXP = Math.max.apply(null, sorted.map(function(s) { return s.total_xp; }).concat([1]));
        var rows = sorted.map(function(s, i) {
            var pct = Math.round((s.total_xp / maxXP) * 100);
            var accColor = s.overall_accuracy >= 80 ? 'emerald' : 'rose';
            return '<div class="trend-item" style="padding:10px 14px;">' +
                '<div style="display:flex;align-items:center;gap:10px;flex:1;min-width:0;">' +
                '<span style="font-size:12px;color:var(--text-muted);width:18px;text-align:center;font-weight:700;">' + (i+1) + '</span>' +
                '<span class="trend-item-name" style="min-width:120px;">' + s.name + '</span>' +
                '<div class="metric-bar" style="flex:1;height:6px;"><div class="metric-bar-fill ' + accColor + '" style="width:' + pct + '%"></div></div>' +
                '</div>' +
                '<div style="display:flex;gap:16px;align-items:center;">' +
                '<span class="trend-item-value blue">' + Math.round(s.total_xp) + ' XP</span>' +
                '<span class="trend-item-value ' + (s.overall_accuracy >= 80 ? 'good' : 'alert') + '">' + s.overall_accuracy + '%</span>' +
                '<span style="font-size:12px;color:var(--text-muted);">' + s.total_minutes + ' min</span>' +
                '</div></div>';
        }).join('');
        return '<div class="trend-panel" style="margin-bottom:20px;">' +
            '<div class="trend-panel-header" style="background:var(--bg-glass);color:var(--text-primary);">' +
            '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 20V10"/><path d="M12 20V4"/><path d="M6 20v-6"/></svg>' +
            ' Student Leaderboard</div>' +
            '<div class="trend-panel-body" style="padding:12px 16px;">' + rows + '</div></div>';
    }

    function renderWeeklyLeaderboard(days) {
        if (!days || !days.length) return '';
        var totals = {};
        days.forEach(function(day) {
            var dayIsWeekend = isWeekend(day.date);
            day.students.forEach(function(s) {
                if (!totals[s.name]) {
                    totals[s.name] = { name: s.name, xp: 0, minutes: 0, correct: 0, questions: 0, daysActive: 0, daysAbsent: 0 };
                }
                var isNoWork = s.absent || (s.total_xp === 0 && s.total_minutes === 0 && (!s.subjects || s.subjects.length === 0));
                if (isNoWork) {
                    // Only count as absent on weekdays
                    if (!dayIsWeekend) totals[s.name].daysAbsent++;
                } else {
                    totals[s.name].xp += s.total_xp;
                    totals[s.name].minutes += s.total_minutes;
                    totals[s.name].daysActive++;
                    var activeSubs = s.subjects ? s.subjects.filter(function(x) { return !x.no_data; }).length : 0;
                    totals[s.name].correct += s.overall_accuracy * (activeSubs || 1);
                    totals[s.name].questions += (activeSubs || 1);
                }
            });
        });
        var sorted = Object.values(totals).sort(function(a, b) { return b.xp - a.xp; });
        var maxXP = Math.max.apply(null, sorted.map(function(s) { return s.xp; }).concat([1]));
        var rows = sorted.map(function(s, i) {
            var pct = Math.round((s.xp / maxXP) * 100);
            var avgAcc = s.questions > 0 ? Math.round(s.correct / s.questions) : 0;
            var accColor = avgAcc >= 80 ? 'emerald' : 'rose';
            var absentNote = s.daysAbsent > 0 ? '<span style="font-size:10px;color:var(--accent-rose);margin-left:4px;">' + s.daysAbsent + 'd absent</span>' : '';
            return '<div class="trend-item" style="padding:10px 14px;">' +
                '<div style="display:flex;align-items:center;gap:10px;flex:1;min-width:0;">' +
                '<span style="font-size:12px;color:var(--text-muted);width:18px;text-align:center;font-weight:700;">' + (i+1) + '</span>' +
                '<span class="trend-item-name" style="min-width:120px;">' + s.name + absentNote + '</span>' +
                '<div class="metric-bar" style="flex:1;height:6px;"><div class="metric-bar-fill ' + accColor + '" style="width:' + pct + '%"></div></div>' +
                '</div>' +
                '<div style="display:flex;gap:16px;align-items:center;">' +
                '<span class="trend-item-value blue">' + Math.round(s.xp) + ' XP</span>' +
                '<span class="trend-item-value ' + (avgAcc >= 80 ? 'good' : 'alert') + '">' + avgAcc + '%</span>' +
                '<span style="font-size:12px;color:var(--text-muted);">' + s.minutes + ' min</span>' +
                '</div></div>';
        }).join('');
        return '<div class="trend-panel" style="margin-bottom:20px;">' +
            '<div class="trend-panel-header" style="background:var(--bg-glass);color:var(--text-primary);">' +
            '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 20V10"/><path d="M12 20V4"/><path d="M6 20v-6"/></svg>' +
            ' Weekly Leaderboard &mdash; ' + days.length + ' Days</div>' +
            '<div class="trend-panel-body" style="padding:12px 16px;">' + rows + '</div></div>';
    }

    function renderSummaryCards(studentsData, dateStr) {
        var n = studentsData.length;
        var active = studentsData.filter(function(s) { return !(s.absent || (s.total_xp === 0 && s.total_minutes === 0 && (!s.subjects || s.subjects.length === 0))); });
        var dayIsWeekend = dateStr ? isWeekend(dateStr) : false;
        var absentCount = dayIsWeekend ? 0 : n - active.length;
        var totalXP = Math.round(studentsData.reduce(function(s, st) { return s + st.total_xp; }, 0));
        var avgAcc = active.length ? Math.round(active.reduce(function(s, st) { return s + st.overall_accuracy; }, 0) / active.length) : 0;
        var avgMin = active.length ? Math.round(active.reduce(function(s, st) { return s + st.total_minutes; }, 0) / active.length) : 0;
        var totalMin = studentsData.reduce(function(s, st) { return s + st.total_minutes; }, 0);
        var flagged = active.filter(function(s) { return s.overall_accuracy < 80; }).length;
        var absentLabel = absentCount > 0 ? ', ' + absentCount + ' absent' : '';
        return '<div class="summary-row fade-in">' +
            '<div class="summary-card blue"><div class="summary-label">Total XP</div><div class="summary-value">' + totalXP.toLocaleString() + '</div><div class="summary-sub">' + active.length + ' active' + absentLabel + '</div></div>' +
            '<div class="summary-card ' + (avgAcc >= 80 ? 'emerald' : 'amber') + '"><div class="summary-label">Avg Accuracy</div><div class="summary-value">' + avgAcc + '%</div><div class="summary-sub">' + (avgAcc >= 80 ? 'On target' : flagged + ' below 80%') + '</div></div>' +
            '<div class="summary-card amber"><div class="summary-label">Avg Minutes</div><div class="summary-value">' + avgMin + '</div><div class="summary-sub">' + totalMin + ' total across all</div></div>' +
            '<div class="summary-card purple"><div class="summary-label">Students</div><div class="summary-value">' + n + '</div><div class="summary-sub">' + (absentCount > 0 ? absentCount + ' absent, ' : '') + flagged + ' need' + (flagged !== 1 ? '' : 's') + ' attention</div></div>' +
            '</div>';
    }

    function renderStudentCard(student, isWeekendDay) {
        var isNoWork = student.absent || (student.total_xp === 0 && student.total_minutes === 0 && (!student.subjects || student.subjects.length === 0));
        if (isNoWork) {
            var bannerText = isWeekendDay
                ? 'NO WORK COMPLETED'
                : 'NO WORK COMPLETED &mdash; Absent';
            var cardClass = isWeekendDay ? 'student-card' : 'student-card flag-absent';
            return '<div class="' + cardClass + '">' +
                '<div class="student-header"><span class="student-name">' + student.name + '</span>' +
                '<div class="student-badges"><span class="badge badge-xp">0 XP</span><span class="badge badge-acc warn">0%</span><span class="badge badge-min warn">0 min</span></div></div>' +
                '<div class="absent-banner"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg> ' + bannerText + '</div></div>';
        }
        var accClass = student.overall_accuracy >= 80 ? 'good' : 'warn';
        var minClass = student.total_minutes >= 20 ? 'good' : 'warn';
        var flagClass = '';
        if (student.overall_accuracy < 80) flagClass = 'flag-red';
        else if (student.total_minutes < 20) flagClass = 'flag-yellow';
        else if (student.overall_accuracy >= 90) flagClass = 'flag-green';
        var subjectsHtml = '';
        student.subjects.forEach(function(subj) {
            var noData = subj.no_data;
            var accColor = subj.accuracy >= 90 ? 'good' : (subj.accuracy < 80 && !noData ? 'warn' : '');
            var minColor = !noData && subj.minutes < 20 ? 'low-min' : '';
            var accBarColor = subj.accuracy >= 80 ? 'emerald' : (noData ? 'amber' : 'rose');
            var accWidth = Math.min(100, subj.accuracy);
            var testClass = subj.has_test ? ' has-test' : '';
            var testBadge = subj.has_test ? '<span class="test-badge">Test</span>' : '';
            subjectsHtml += '<div class="subject-row' + testClass + (noData ? ' no-data' : '') + '">' +
                '<span class="subject-name">' + subj.name + testBadge + '</span>' +
                '<div class="subject-metrics">' +
                '<div class="metric"><span class="metric-value" style="color: var(--accent-blue)">' + Math.round(subj.xp) + '</span><span class="metric-unit">XP</span></div>' +
                '<div class="metric"><div class="metric-bar"><div class="metric-bar-fill ' + accBarColor + '" style="width:' + accWidth + '%"></div></div><span class="metric-value ' + accColor + '">' + subj.accuracy + '%</span></div>' +
                '<div class="metric"><span class="metric-value" style="color: var(--accent-purple)">' + subj.minutes + '</span><span class="metric-unit">min</span></div>' +
                (subj.mastered !== undefined && subj.mastered > 0 ? '<div class="metric"><span class="metric-value" style="color: var(--accent-cyan)">' + subj.mastered + '</span><span class="metric-unit">mastered</span></div>' : '') +
                '</div></div>';
        });
        return '<div class="student-card ' + flagClass + '">' +
            '<div class="student-header"><span class="student-name">' + student.name + '</span>' +
            '<div class="student-badges"><span class="badge badge-xp">' + Math.round(student.total_xp) + ' XP</span>' +
            '<span class="badge badge-acc ' + accClass + '">' + student.overall_accuracy + '%</span>' +
            '<span class="badge badge-min ' + minClass + '">' + student.total_minutes + ' min</span></div></div>' +
            '<div class="student-subjects">' + subjectsHtml + '</div></div>';
    }

    // === Weekly Trends ===
    function renderWeeklyTrends(days) {
        if (!days || days.length < 2) return '';
        var studentTotals = {};
        var subjectTotals = {};
        days.forEach(function(day) {
            day.students.forEach(function(student) {
                if (!studentTotals[student.name]) {
                    studentTotals[student.name] = { xp: 0, minutes: 0, accuracy: [], days: 0 };
                }
                studentTotals[student.name].xp += student.total_xp;
                studentTotals[student.name].minutes += student.total_minutes;
                studentTotals[student.name].accuracy.push(student.overall_accuracy);
                studentTotals[student.name].days++;
                student.subjects.forEach(function(subj) {
                    if (subj.no_data) return;
                    if (!subjectTotals[subj.name]) {
                        subjectTotals[subj.name] = { xp: 0, minutes: 0, accuracy: [], count: 0 };
                    }
                    subjectTotals[subj.name].xp += subj.xp;
                    subjectTotals[subj.name].minutes += subj.minutes;
                    subjectTotals[subj.name].accuracy.push(subj.accuracy);
                    subjectTotals[subj.name].count++;
                });
            });
        });
        var avg = function(arr) { return arr.length ? Math.round(arr.reduce(function(a,b){return a+b;},0)/arr.length) : 0; };
        var studentList2 = Object.entries(studentTotals).map(function(e) {
            return { name: e[0], xp: e[1].xp, minutes: e[1].minutes, avgAccuracy: avg(e[1].accuracy), days: e[1].days };
        });
        var subjectList = Object.entries(subjectTotals).map(function(e) {
            return { name: e[0], xp: e[1].xp, minutes: e[1].minutes, avgAccuracy: avg(e[1].accuracy), count: e[1].count };
        });
        var lowestAccSubjects = subjectList.slice().sort(function(a,b){return a.avgAccuracy-b.avgAccuracy;}).slice(0,3);
        var lowestMinStudents = studentList2.slice().sort(function(a,b){return a.minutes-b.minutes;}).slice(0,3);
        var lowestXPStudents = studentList2.slice().sort(function(a,b){return a.xp-b.xp;}).slice(0,3);
        var highestXPStudents = studentList2.slice().sort(function(a,b){return b.xp-a.xp;}).slice(0,3);
        var highestAccSubjects = subjectList.slice().sort(function(a,b){return b.avgAccuracy-a.avgAccuracy;}).slice(0,3);
        var highestMinStudents = studentList2.slice().sort(function(a,b){return b.minutes-a.minutes;}).slice(0,3);

        function trendItems(arr, valFn) {
            return arr.map(function(s) { return '<div class="trend-item"><span class="trend-item-name">' + s.name + '</span>' + valFn(s) + '</div>'; }).join('');
        }

        return '<div class="trends-section fade-in">' +
            '<div class="section-title"><span class="section-title-icon" style="background: var(--accent-blue-glow); color: var(--accent-blue);">&#9733;</span> Weekly Trends &middot; ' + days.length + ' days</div>' +
            '<div class="trends-grid">' +
            '<div class="trend-panel alert">' +
            '<div class="trend-panel-header"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg> Needs Attention</div>' +
            '<div class="trend-panel-body">' +
            '<div class="trend-category"><div class="trend-category-title">Lowest Accuracy Subjects</div>' + trendItems(lowestAccSubjects, function(s){ return '<span class="trend-item-value ' + (s.avgAccuracy < 80 ? 'alert' : 'warn') + '">' + s.avgAccuracy + '% avg</span>'; }) + '</div>' +
            '<div class="trend-category"><div class="trend-category-title">Lowest Total Minutes</div>' + trendItems(lowestMinStudents, function(s){ return '<span class="trend-item-value warn">' + s.minutes + ' min</span>'; }) + '</div>' +
            '<div class="trend-category"><div class="trend-category-title">Lowest Total XP</div>' + trendItems(lowestXPStudents, function(s){ return '<span class="trend-item-value warn">' + Math.round(s.xp) + ' XP</span>'; }) + '</div>' +
            '</div></div>' +
            '<div class="trend-panel success">' +
            '<div class="trend-panel-header"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg> Top Performers</div>' +
            '<div class="trend-panel-body">' +
            '<div class="trend-category"><div class="trend-category-title">Most XP Earned</div>' + trendItems(highestXPStudents, function(s){ return '<span class="trend-item-value blue">' + Math.round(s.xp) + ' XP</span>'; }) + '</div>' +
            '<div class="trend-category"><div class="trend-category-title">Highest Accuracy Subjects</div>' + trendItems(highestAccSubjects, function(s){ return '<span class="trend-item-value good">' + s.avgAccuracy + '% avg</span>'; }) + '</div>' +
            '<div class="trend-category"><div class="trend-category-title">Most Active Minutes</div>' + trendItems(highestMinStudents, function(s){ return '<span class="trend-item-value good">' + s.minutes + ' min</span>'; }) + '</div>' +
            '</div></div>' +
            '</div></div>';
    }

    // === Day Switching ===
    function switchDay(index) {
        activeDayIndex = index;
        renderDashboard(currentData);
    }

    // === Student Management ===
    function loadStudents() {
        students = getStudentsFromStorage();
        renderStudentList();
    }

    function renderStudentList() {
        var container = document.getElementById('studentList');
        if (!students.length) {
            container.innerHTML = '<div style="text-align:center;padding:20px;color:var(--text-muted)">No students added yet</div>';
            return;
        }
        container.innerHTML = students.map(function(s, i) {
            return '<div class="student-list-item"><span class="student-list-name">' + s + '</span><button class="btn-remove" onclick="removeStudent(' + i + ')">&times;</button></div>';
        }).join('');
    }

    var searchTimeout = null;
    var searchHighlightIndex = -1;
    var lastSearchResults = [];

    function addStudent() {
        var input = document.getElementById('newStudentInput');
        var name = input.value.trim();
        if (!name) return;
        if (students.indexOf(name) === -1) {
            students.push(name);
        }
        input.value = '';
        hideSearchResults();
        saveStudents();
    }

    function addStudentFromSearch(name, sourcedId) {
        if (students.indexOf(name) !== -1) return;
        students.push(name);
        if (sourcedId) {
            var ids = getStudentIds();
            ids[name] = sourcedId;
            saveStudentIds(ids);
        }
        document.getElementById('newStudentInput').value = '';
        hideSearchResults();
        saveStudents();
    }

    async function searchStudents(query) {
        query = query.trim();
        var resultsEl = document.getElementById('searchResults');
        if (query.length < 2) {
            hideSearchResults();
            return;
        }
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(async function() {
            resultsEl.innerHTML = '<div class="search-loading">Searching TimeBack...</div>';
            resultsEl.classList.add('show');
            try {
                var resp = await fetch('/_serverFn/src_features_learning-metrics_components_fast-student-search_actions_client_ts--fetchUsersByRole_createServerFn_handler?createServerFn', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        data: { roles: ['student'], search: query, limit: { '$undefined': 0 }, orgSourcedIds: [] },
                        context: {},
                    }),
                });
                var data = await resp.json();
                var results = data.result || [];
                lastSearchResults = results.map(function(user) {
                    return {
                        name: ((user.givenName || '') + ' ' + (user.familyName || '')).trim(),
                        sourcedId: user.sourcedId,
                        role: user.role || 'student'
                    };
                });
                searchHighlightIndex = -1;
                if (!lastSearchResults.length) {
                    resultsEl.innerHTML = '<div class="search-loading">No students found for "' + query + '"</div>';
                } else {
                    renderSearchResults();
                }
            } catch (e) {
                resultsEl.innerHTML = '<div class="search-loading">Search failed \u2014 make sure you are logged into TimeBack</div>';
            }
        }, 300);
    }

    function renderSearchResults() {
        var resultsEl = document.getElementById('searchResults');
        resultsEl.innerHTML = lastSearchResults.map(function(r, i) {
            var alreadyAdded = students.indexOf(r.name) !== -1;
            var highlighted = i === searchHighlightIndex ? 'background:rgba(59,130,246,0.15);' : '';
            return '<div class="search-result-item' + (alreadyAdded ? ' already-added' : '') + '" style="' + highlighted + '" onclick="addStudentFromSearch(\'' + r.name.replace(/'/g, "\\'") + '\', \'' + r.sourcedId + '\')">' +
                '<span class="result-name">' + r.name + '</span>' +
                (alreadyAdded ? '' : '<span class="result-role">' + r.role + '</span>') +
                '</div>';
        }).join('');
        resultsEl.classList.add('show');
    }

    function handleSearchKeydown(e) {
        if (!lastSearchResults.length) {
            if (e.key === 'Enter') addStudent();
            return;
        }
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            searchHighlightIndex = Math.min(searchHighlightIndex + 1, lastSearchResults.length - 1);
            renderSearchResults();
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            searchHighlightIndex = Math.max(searchHighlightIndex - 1, -1);
            renderSearchResults();
        } else if (e.key === 'Enter') {
            e.preventDefault();
            if (searchHighlightIndex >= 0 && searchHighlightIndex < lastSearchResults.length) {
                var r = lastSearchResults[searchHighlightIndex];
                addStudentFromSearch(r.name, r.sourcedId);
            } else if (lastSearchResults.length === 1) {
                var r2 = lastSearchResults[0];
                addStudentFromSearch(r2.name, r2.sourcedId);
            } else {
                addStudent();
            }
        } else if (e.key === 'Escape') {
            hideSearchResults();
        }
    }

    function hideSearchResults() {
        document.getElementById('searchResults').classList.remove('show');
        lastSearchResults = [];
        searchHighlightIndex = -1;
    }

    function removeStudent(index) {
        students.splice(index, 1);
        saveStudents();
    }

    function saveStudents() {
        saveStudentsToStorage(students);
        renderStudentList();
    }

    // === Groups ===
    function loadGroups() {
        groups = getGroupsFromStorage();
        renderGroupTabs();
        renderGroupList();
        renderNewGroupStudents();
    }

    function saveGroups() {
        saveGroupsToStorage(groups);
        renderGroupTabs();
        renderGroupList();
    }

    function renderGroupTabs() {
        var bar = document.getElementById('groupTabsBar');
        if (!groups.length) { bar.innerHTML = ''; return; }
        var html = '<button class="group-tab ' + (activeGroupIndex === -1 ? 'active' : '') + '" onclick="switchGroup(-1)">All Students</button>';
        groups.forEach(function(g, i) {
            html += '<button class="group-tab ' + (activeGroupIndex === i ? 'active' : '') + '" onclick="switchGroup(' + i + ')">' + g.name + ' <span style="opacity:0.6;font-size:11px;">(' + g.students.length + ')</span></button>';
        });
        html += '<button class="group-tab-manage" onclick="openModal(); switchModalTab(\'groups\', document.querySelectorAll(\'#tb-dash-overlay .modal-tab\')[1])">+ Group</button>';
        bar.innerHTML = html;
    }

    function switchGroup(index) {
        activeGroupIndex = index;
        renderGroupTabs();
        if (currentData) renderDashboard(currentData);
    }

    function getFilteredStudents(studentsList) {
        if (activeGroupIndex === -1 || !groups[activeGroupIndex]) return studentsList;
        var groupNames = new Set(groups[activeGroupIndex].students.map(function(n) { return n.toLowerCase(); }));
        return studentsList.filter(function(s) { return groupNames.has(s.name.toLowerCase()); });
    }

    function renderGroupList() {
        var container = document.getElementById('groupList');
        if (!groups.length) {
            container.innerHTML = '<div style="text-align:center;padding:16px;color:var(--text-muted)">No groups yet. Create one below.</div>';
            return;
        }
        container.innerHTML = groups.map(function(g, gi) {
            var chips = g.students.map(function(s, si) {
                return '<span class="group-student-chip">' + s + '<span class="chip-remove" onclick="removeFromGroup(' + gi + ',' + si + ')">&times;</span></span>';
            }).join('');
            return '<div class="group-card"><div class="group-card-header"><span class="group-card-name">' + g.name + '</span>' +
                '<div style="display:flex;gap:6px;align-items:center;"><span class="group-card-count">' + g.students.length + ' students</span>' +
                '<button class="btn-remove" onclick="deleteGroup(' + gi + ')" title="Delete group">&times;</button></div></div>' +
                '<div class="group-card-students">' + chips + '</div>' +
                '<div style="margin-top:8px;"><select onchange="addToGroup(' + gi + ', this)" style="background:var(--bg-card);border:1px solid var(--border);color:var(--text-secondary);padding:5px 8px;border-radius:6px;font-size:11px;font-family:inherit;">' +
                '<option value="">+ Add student...</option>' +
                students.filter(function(s) { return !g.students.includes(s); }).map(function(s) { return '<option value="' + s + '">' + s + '</option>'; }).join('') +
                '</select></div></div>';
        }).join('');
    }

    function renderNewGroupStudents() {
        var container = document.getElementById('newGroupStudents');
        container.innerHTML = students.map(function(s) {
            return '<label class="student-checkbox-item"><input type="checkbox" value="' + s + '"> ' + s + '</label>';
        }).join('');
    }

    function createGroup() {
        var nameInput = document.getElementById('newGroupName');
        var name = nameInput.value.trim();
        if (!name) { nameInput.focus(); return; }
        var checked = Array.from(document.querySelectorAll('#newGroupStudents input:checked')).map(function(cb) { return cb.value; });
        if (!checked.length) return;
        groups.push({ name: name, students: checked });
        nameInput.value = '';
        document.querySelectorAll('#newGroupStudents input:checked').forEach(function(cb) { cb.checked = false; });
        saveGroups();
    }

    function deleteGroup(gi) {
        if (activeGroupIndex === gi) activeGroupIndex = -1;
        else if (activeGroupIndex > gi) activeGroupIndex--;
        groups.splice(gi, 1);
        saveGroups();
    }

    function removeFromGroup(gi, si) {
        groups[gi].students.splice(si, 1);
        if (!groups[gi].students.length) {
            groups.splice(gi, 1);
            if (activeGroupIndex === gi) activeGroupIndex = -1;
            else if (activeGroupIndex > gi) activeGroupIndex--;
        }
        saveGroups();
    }

    function addToGroup(gi, selectEl) {
        var name = selectEl.value;
        if (!name) return;
        if (!groups[gi].students.includes(name)) {
            groups[gi].students.push(name);
            saveGroups();
        }
        selectEl.value = '';
    }

    function switchModalTab(tab, btn) {
        document.querySelectorAll('#tb-dash-overlay .modal-tab').forEach(function(t) { t.classList.remove('active'); });
        document.querySelectorAll('#tb-dash-overlay .modal-section').forEach(function(s) { s.classList.remove('active'); });
        if (btn) btn.classList.add('active');
        document.getElementById(tab === 'groups' ? 'modalGroups' : 'modalStudents').classList.add('active');
        if (tab === 'groups') { renderGroupList(); renderNewGroupStudents(); }
    }

    function openModal() {
        loadStudents();
        loadGroups();
        document.getElementById('modalOverlay').classList.add('show');
    }

    function closeModal() {
        document.getElementById('modalOverlay').classList.remove('show');
    }

    function openSettings() { openModal(); }

    // === Chat / Q&A ===
    var chatMessagesList = [];
    var chatOpen = false;

    function toggleChat() {
        chatOpen = !chatOpen;
        document.getElementById('chatPanel').classList.toggle('open', chatOpen);
        document.getElementById('chatFab').classList.toggle('hidden', chatOpen);
        if (chatOpen) document.getElementById('chatInput').focus();
    }

    function sendChat(text) {
        var input = document.getElementById('chatInput');
        var msg = text || input.value.trim();
        if (!msg) return;
        input.value = '';
        chatMessagesList.push({ role: 'user', text: msg });
        var answer = answerQuestion(msg, currentData);
        chatMessagesList.push({ role: 'assistant', text: answer });
        renderChatMessages();
        document.getElementById('chatSuggestions').style.display = 'none';
    }

    function renderChatMessages() {
        var container = document.getElementById('chatMessages');
        container.innerHTML = chatMessagesList.map(function(m) {
            return '<div class="chat-bubble ' + m.role + '">' + escapeHTML(m.text) + '</div>';
        }).join('');
        container.scrollTop = container.scrollHeight;
    }

    function escapeHTML(str) {
        var d = document.createElement('div');
        d.textContent = str;
        return d.innerHTML;
    }

    // === Q&A Engine ===
    function answerQuestion(question, data) {
        if (!data || (!data.students && !data.days)) {
            return 'No data loaded yet. Pull data first using the date controls above, then ask me anything about the results.';
        }
        var q = question.toLowerCase().trim();
        var allStudents2 = getStudentsFromData(data);
        var isWeekly = !!(data.days && data.days.length > 1);
        var matchedStudent = findStudentInQuestion(q, allStudents2);
        var allSubjects = getAllSubjectNames(allStudents2);
        var matchedSubject = findSubjectInQuestion(q, allSubjects);

        if (matchedStudent) {
            var s = matchedStudent;
            if (/lowest.*(accuracy|acc)|worst.*subject/i.test(q)) {
                var subs = s.subjects.filter(function(x){return !x.no_data;}).sort(function(a,b){return a.accuracy-b.accuracy;});
                if (!subs.length) return s.name + ' has no subject data available.';
                return s.name + "'s lowest accuracy subject is " + subs[0].name + ' at ' + subs[0].accuracy + '% (' + subs[0].xp + ' XP, ' + subs[0].minutes + ' min).';
            }
            if (/best.*subject|highest.*(accuracy|acc).*subject|strongest/i.test(q)) {
                var subs2 = s.subjects.filter(function(x){return !x.no_data;}).sort(function(a,b){return b.accuracy-a.accuracy;});
                if (!subs2.length) return s.name + ' has no subject data available.';
                return s.name + "'s best subject is " + subs2[0].name + ' at ' + subs2[0].accuracy + '% accuracy (' + subs2[0].xp + ' XP).';
            }
            if (/how much xp|total xp|xp.*earn/i.test(q)) {
                if (isWeekly) {
                    var weekTotal = getWeeklyStudentXP(data, s.name);
                    return s.name + ' earned ' + s.total_xp + ' XP today and ' + weekTotal + ' XP total this week.';
                }
                return s.name + ' earned ' + s.total_xp + ' XP total.';
            }
            if (/miss|skip|absent|no.?data/i.test(q) && matchedSubject) {
                if (!isWeekly) return 'Weekly data is needed to check missed days. Try selecting a week range.';
                var missed = [];
                data.days.forEach(function(day) {
                    var st = day.students.find(function(x){return x.name.toLowerCase()===s.name.toLowerCase();});
                    if (st) {
                        var subj = st.subjects.find(function(x){return x.name.toLowerCase()===matchedSubject.toLowerCase();});
                        if (subj && subj.no_data) missed.push(day.day_name);
                    }
                });
                if (!missed.length) return s.name + ' did not miss ' + matchedSubject + ' on any day this week.';
                return s.name + ' missed ' + matchedSubject + ' on: ' + missed.join(', ') + '.';
            }
            if (/minutes|time.*spen/i.test(q) && matchedSubject) {
                var subj3 = s.subjects.find(function(x){return x.name.toLowerCase()===matchedSubject.toLowerCase();});
                if (!subj3) return 'Could not find ' + matchedSubject + ' data for ' + s.name + '.';
                return s.name + ' spent ' + subj3.minutes + ' minutes on ' + subj3.name + ' (' + subj3.xp + ' XP, ' + subj3.accuracy + '% accuracy).';
            }
            if (/minutes|time.*spen|how long/i.test(q)) {
                return s.name + ' spent ' + s.total_minutes + ' minutes total across all subjects.';
            }
            if (/improv|trend|progress|getting better/i.test(q)) {
                if (!isWeekly) return 'Need weekly data to check trends. Select a week range and pull data.';
                var dayData = data.days.map(function(day) {
                    var st = day.students.find(function(x){return x.name.toLowerCase()===s.name.toLowerCase();});
                    return st ? { day: day.day_name, xp: st.total_xp, acc: st.overall_accuracy } : null;
                }).filter(Boolean);
                if (dayData.length < 2) return 'Not enough days of data to determine a trend for ' + s.name + '.';
                var first = dayData[0], last = dayData[dayData.length - 1];
                var accTrend = last.acc - first.acc;
                var lines = [s.name + "'s trend across " + dayData.length + ' days:'];
                dayData.forEach(function(d) { lines.push('  ' + d.day + ': ' + d.xp + ' XP, ' + d.acc + '%'); });
                lines.push('Accuracy ' + (accTrend >= 0 ? 'up' : 'down') + ' ' + Math.abs(accTrend) + '% from ' + first.day + ' to ' + last.day + '.');
                return lines.join('\n');
            }
            return s.name + ': ' + s.total_xp + ' XP, ' + s.overall_accuracy + '% accuracy, ' + s.total_minutes + ' min total.\nSubjects: ' + s.subjects.filter(function(x){return !x.no_data;}).map(function(x){return x.name+' ('+x.accuracy+'%, '+x.xp+' XP)';}).join(', ') + '.';
        }

        if (/lowest.*(accuracy|acc)|worst.*(accuracy|acc)/i.test(q) && !matchedSubject) {
            var sorted = allStudents2.slice().sort(function(a,b){return a.overall_accuracy-b.overall_accuracy;});
            return 'Lowest accuracy students:\n' + sorted.slice(0,3).map(function(s,i){return '  '+(i+1)+'. '+s.name+': '+s.overall_accuracy+'%';}).join('\n');
        }
        if (/highest.*(accuracy|acc)|best.*(accuracy|acc)/i.test(q) && !matchedSubject) {
            var sorted2 = allStudents2.slice().sort(function(a,b){return b.overall_accuracy-a.overall_accuracy;});
            return 'Highest accuracy students:\n' + sorted2.slice(0,3).map(function(s,i){return '  '+(i+1)+'. '+s.name+': '+s.overall_accuracy+'%';}).join('\n');
        }
        if (/most xp|highest xp|top xp/i.test(q)) {
            var sorted3 = allStudents2.slice().sort(function(a,b){return b.total_xp-a.total_xp;});
            return 'Most XP:\n' + sorted3.slice(0,3).map(function(s,i){return '  '+(i+1)+'. '+s.name+': '+s.total_xp+' XP';}).join('\n');
        }
        if (/least xp|lowest xp|fewest xp/i.test(q)) {
            var sorted4 = allStudents2.slice().sort(function(a,b){return a.total_xp-b.total_xp;});
            return 'Least XP:\n' + sorted4.slice(0,3).map(function(s,i){return '  '+(i+1)+'. '+s.name+': '+s.total_xp+' XP';}).join('\n');
        }
        if (/who.*(need|attention|help|struggling|behind)/i.test(q)) {
            var flagged2 = allStudents2.filter(function(s){return s.overall_accuracy<80||s.total_minutes<20;});
            if (!flagged2.length) return 'All students are on track -- no one is below 80% accuracy or under 20 minutes.';
            var lines2 = ['Students needing attention:'];
            flagged2.forEach(function(s) {
                var reasons = [];
                if (s.overall_accuracy < 80) reasons.push(s.overall_accuracy + '% accuracy');
                if (s.total_minutes < 20) reasons.push('only ' + s.total_minutes + ' min');
                lines2.push('  - ' + s.name + ': ' + reasons.join(', '));
            });
            return lines2.join('\n');
        }
        if (/best performer|top student|star student|mvp/i.test(q)) {
            var sorted5 = allStudents2.slice().sort(function(a,b){return b.total_xp-a.total_xp;});
            var top = sorted5[0];
            if (!top) return 'No student data available.';
            return 'Top performer: ' + top.name + ' with ' + top.total_xp + ' XP, ' + top.overall_accuracy + '% accuracy, ' + top.total_minutes + ' min.';
        }
        if (/most.*(time|minutes)|spending.*most/i.test(q)) {
            var sorted6 = allStudents2.slice().sort(function(a,b){return b.total_minutes-a.total_minutes;});
            return 'Most time spent:\n' + sorted6.slice(0,3).map(function(s,i){return '  '+(i+1)+'. '+s.name+': '+s.total_minutes+' min';}).join('\n');
        }
        if (/least.*(time|minutes)|spending.*least/i.test(q)) {
            var sorted7 = allStudents2.slice().sort(function(a,b){return a.total_minutes-b.total_minutes;});
            return 'Least time spent:\n' + sorted7.slice(0,3).map(function(s,i){return '  '+(i+1)+'. '+s.name+': '+s.total_minutes+' min';}).join('\n');
        }
        if (matchedSubject) {
            if (/average.*(accuracy|acc)/i.test(q)) {
                var accs = [];
                allStudents2.forEach(function(s) {
                    var subj = s.subjects.find(function(x){return x.name.toLowerCase()===matchedSubject.toLowerCase()&&!x.no_data;});
                    if (subj) accs.push(subj.accuracy);
                });
                if (!accs.length) return 'No data found for ' + matchedSubject + '.';
                var avg2 = Math.round(accs.reduce(function(a,b){return a+b;},0)/accs.length);
                return 'Average accuracy for ' + matchedSubject + ': ' + avg2 + '% across ' + accs.length + ' students.';
            }
            if (/most xp|highest xp/i.test(q)) {
                var total = 0;
                allStudents2.forEach(function(s) {
                    var subj = s.subjects.find(function(x){return x.name.toLowerCase()===matchedSubject.toLowerCase()&&!x.no_data;});
                    if (subj) total += subj.xp;
                });
                return 'Total XP earned in ' + matchedSubject + ': ' + total + ' across all students.';
            }
        }
        if (/lowest.*subject|worst.*subject/i.test(q)) {
            var subjAgg = aggregateSubjects(allStudents2);
            var sorted8 = Object.entries(subjAgg).sort(function(a,b){return a[1].avgAcc-b[1].avgAcc;});
            if (!sorted8.length) return 'No subject data available.';
            return 'Lowest accuracy subjects:\n' + sorted8.slice(0,3).map(function(e,i){return '  '+(i+1)+'. '+e[0]+': '+e[1].avgAcc+'% avg accuracy';}).join('\n');
        }
        if (/which.*subject.*most xp|subject.*highest xp/i.test(q)) {
            var subjAgg2 = aggregateSubjects(allStudents2);
            var sorted9 = Object.entries(subjAgg2).sort(function(a,b){return b[1].totalXP-a[1].totalXP;});
            if (!sorted9.length) return 'No subject data available.';
            return 'Subjects by total XP:\n' + sorted9.slice(0,3).map(function(e,i){return '  '+(i+1)+'. '+e[0]+': '+e[1].totalXP+' XP';}).join('\n');
        }
        if (/weekly summary|how.*week|week.*overview|week.*recap/i.test(q)) {
            if (!isWeekly) {
                var n2 = allStudents2.length;
                var totalXP2 = allStudents2.reduce(function(s,st){return s+st.total_xp;},0);
                var avgAcc2 = n2 ? Math.round(allStudents2.reduce(function(s,st){return s+st.overall_accuracy;},0)/n2) : 0;
                var flagged3 = allStudents2.filter(function(s){return s.overall_accuracy<80;}).length;
                return "Today's summary: " + n2 + ' students, ' + totalXP2 + ' total XP, ' + avgAcc2 + '% avg accuracy. ' + flagged3 + ' student' + (flagged3!==1?'s':'') + ' below 80%.';
            }
            var lines3 = ['Weekly summary (' + data.days.length + ' days):'];
            var weekXP = 0, weekAcc = [];
            data.days.forEach(function(day) {
                var dayXP = day.students.reduce(function(s,st){return s+st.total_xp;},0);
                var dayAcc = day.students.length ? Math.round(day.students.reduce(function(s,st){return s+st.overall_accuracy;},0)/day.students.length) : 0;
                weekXP += dayXP;
                weekAcc.push(dayAcc);
                lines3.push('  ' + day.day_name + ': ' + dayXP + ' XP, ' + dayAcc + '% avg accuracy');
            });
            var bestDay = data.days.reduce(function(best, day) {
                var xp = day.students.reduce(function(s,st){return s+st.total_xp;},0);
                return xp > best.xp ? { name: day.day_name, xp: xp } : best;
            }, { name: '', xp: 0 });
            lines3.push('\nTotal week XP: ' + weekXP);
            lines3.push('Best day: ' + bestDay.name + ' (' + bestDay.xp + ' XP)');
            lines3.push('Avg accuracy across week: ' + Math.round(weekAcc.reduce(function(a,b){return a+b;},0)/weekAcc.length) + '%');
            return lines3.join('\n');
        }
        if (/what day.*highest|best day|highest.*day/i.test(q)) {
            if (!isWeekly) return 'Need weekly data to compare days. Select a week range.';
            var best2 = { name: '', xp: 0 };
            data.days.forEach(function(day) {
                var xp = day.students.reduce(function(s,st){return s+st.total_xp;},0);
                if (xp > best2.xp) best2 = { name: day.day_name, xp: xp };
            });
            return 'Best day: ' + best2.name + ' with ' + best2.xp + ' total XP.';
        }
        if (/what day.*lowest|worst day|lowest.*day/i.test(q)) {
            if (!isWeekly) return 'Need weekly data to compare days. Select a week range.';
            var worst2 = { name: '', xp: Infinity };
            data.days.forEach(function(day) {
                var xp = day.students.reduce(function(s,st){return s+st.total_xp;},0);
                if (xp < worst2.xp) worst2 = { name: day.day_name, xp: xp };
            });
            return 'Worst day: ' + worst2.name + ' with ' + worst2.xp + ' total XP.';
        }
        return 'I can answer questions like:\n  - "Who needs help?" / "Who has the lowest accuracy?"\n  - "Best performer?" / "Who has the most XP?"\n  - "[Name]\'s lowest accuracy subject?"\n  - "[Name]\'s best subject?"\n  - "How much XP did [Name] earn?"\n  - "What days did [Name] miss [subject]?"\n  - "Average accuracy for [subject]?"\n  - "Weekly summary" / "What day had the highest XP?"\n  - "Is [Name] improving?"\nTry asking one of these!';
    }

    // === Q&A Helpers ===
    function getStudentsFromData(data) {
        if (data.students) return data.students;
        if (data.days && data.days.length > 0) {
            return data.days[activeDayIndex] ? data.days[activeDayIndex].students : data.days[0].students;
        }
        return [];
    }

    function getWeeklyStudentXP(data, name) {
        if (!data.days) return 0;
        var total = 0;
        data.days.forEach(function(day) {
            var st = day.students.find(function(s){return s.name.toLowerCase()===name.toLowerCase();});
            if (st) total += st.total_xp;
        });
        return total;
    }

    function findStudentInQuestion(q, studentsArr) {
        var best = null;
        var bestLen = 0;
        studentsArr.forEach(function(s) {
            var nameLower = s.name.toLowerCase();
            if (q.includes(nameLower) && nameLower.length > bestLen) { best = s; bestLen = nameLower.length; }
            var firstName = nameLower.split(' ')[0];
            if (firstName.length > 2 && q.includes(firstName) && firstName.length > bestLen) { best = s; bestLen = firstName.length; }
        });
        return best;
    }

    function getAllSubjectNames(studentsArr) {
        var names = new Set();
        studentsArr.forEach(function(s) { s.subjects.forEach(function(subj) { names.add(subj.name); }); });
        return Array.from(names);
    }

    function findSubjectInQuestion(q, subjectNames) {
        var best = null;
        var bestLen = 0;
        subjectNames.forEach(function(name) {
            var lower = name.toLowerCase();
            if (q.includes(lower) && lower.length > bestLen) { best = name; bestLen = lower.length; }
        });
        return best;
    }

    function aggregateSubjects(studentsArr) {
        var agg = {};
        studentsArr.forEach(function(s) {
            s.subjects.forEach(function(subj) {
                if (subj.no_data) return;
                if (!agg[subj.name]) agg[subj.name] = { accs: [], totalXP: 0 };
                agg[subj.name].accs.push(subj.accuracy);
                agg[subj.name].totalXP += subj.xp;
            });
        });
        Object.keys(agg).forEach(function(name) {
            var a = agg[name];
            a.avgAcc = Math.round(a.accs.reduce(function(x,y){return x+y;},0)/a.accs.length);
        });
        return agg;
    }

    // === Expose functions for inline onclick handlers ===
    window.pullData = pullData;
    window.setPreset = setPreset;
    window.openModal = openModal;
    window.closeModal = closeModal;
    window.openSettings = openSettings;
    window.switchModalTab = switchModalTab;
    window.addStudent = addStudent;
    window.addStudentFromSearch = addStudentFromSearch;
    window.searchStudents = searchStudents;
    window.handleSearchKeydown = handleSearchKeydown;
    window.removeStudent = removeStudent;
    window.createGroup = createGroup;
    window.deleteGroup = deleteGroup;
    window.removeFromGroup = removeFromGroup;
    window.addToGroup = addToGroup;
    window.switchGroup = switchGroup;
    window.switchDay = switchDay;
    window.switchWeeklyView = switchWeeklyView;
    window.toggleChat = toggleChat;
    window.sendChat = sendChat;

    // === Initialize ===
    async function init() {
        students = getStudentsFromStorage();
        groups = getGroupsFromStorage();
        renderGroupTabs();

        var statusDot = document.getElementById('statusDot');
        statusDot.className = 'status-dot';

        if (!students.length) {
            document.getElementById('emptyTitle').textContent = 'Get Started';
            document.getElementById('emptyMessage').innerHTML = 'Add your students to begin tracking their progress.<br><br><button class="btn-pull" onclick="openModal()" style="margin-top:8px;padding:10px 24px;font-size:14px;">Add Students</button>';
            return;
        }

        var lastData = getLastData();
        if (lastData && (lastData.students || lastData.days)) {
            currentData = lastData;
            document.getElementById('timestamp').textContent = lastData.timestamp || '';
            if (lastData.date) {
                document.getElementById('dateFrom').value = lastData.date;
                document.getElementById('dateTo').value = lastData.date;
            } else if (lastData.start && lastData.end) {
                document.getElementById('dateFrom').value = lastData.start;
                document.getElementById('dateTo').value = lastData.end;
            }
            renderDashboard(lastData);
        } else {
            document.getElementById('emptyTitle').textContent = 'Ready to Go';
            document.getElementById('emptyMessage').innerHTML = 'You have ' + students.length + ' student' + (students.length === 1 ? '' : 's') + ' configured.<br>Select a date and click <strong>Pull Data</strong> to get started.';
        }
    }

    init();

    // === API Discovery: find assessment/test data ===
    // Runs automatically, shows results in a toast notification on the dashboard
    (function() {
        var studentList = getStudentsFromStorage();
        var studentIds = getStudentIds();
        var firstStudentName = null;
        var firstStudentId = null;
        for (var i = 0; i < studentList.length; i++) {
            if (studentIds[studentList[i]]) {
                firstStudentName = studentList[i];
                firstStudentId = studentIds[studentList[i]];
                break;
            }
        }
        if (!firstStudentId) return;

        var today = getLocalToday();
        var offset = getPacificOffsetHours(today);
        var offsetStr = String(offset).padStart(2, '0');

        // 1. Check raw activity metrics for extra keys
        fetch('/_serverFn/src_features_learning-metrics_actions_getActivityMetrics_ts--getActivityMetrics_createServerFn_handler?createServerFn', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                data: { startDate: today + 'T' + offsetStr + ':00:00.000Z', endDate: today + 'T' + offsetStr + ':00:00.000Z', studentId: firstStudentId, timezone: 'America/Los_Angeles' },
                context: {},
            }),
        }).then(function(r) { return r.json(); }).then(function(data) {
            var metrics = ((data.result || {}).data) || {};
            var topKeys = Object.keys(metrics);
            console.log('[XP Discovery] Activity metrics top keys:', topKeys);
            var facts = (metrics.facts || {})[today] || {};
            for (var subj in facts) {
                if (!facts.hasOwnProperty(subj)) continue;
                var keys = Object.keys(facts[subj]);
                console.log('[XP Discovery] ' + firstStudentName + ' > ' + subj + ' keys:', keys);
                for (var k in facts[subj]) {
                    if (k !== 'activityMetrics' && k !== 'timeSpentMetrics') {
                        console.log('[XP Discovery] EXTRA: ' + subj + '.' + k + ' =', JSON.stringify(facts[subj][k]).substring(0, 500));
                    }
                }
                // Also log all activityMetrics keys
                var am = facts[subj].activityMetrics || {};
                console.log('[XP Discovery] ' + subj + ' activityMetrics keys:', Object.keys(am));
            }
        }).catch(function(e) { console.log('[XP Discovery] Activity check error:', e); });

        // 2. Probe assessment endpoints
        var endpoints = [
            'src_features_assessment-results_actions_getUserPendingAssessments_ts--getUserPendingAssessments_createServerFn_handler',
            'src_features_assessment-results_actions_getUserAssessmentResults_ts--getUserAssessmentResults_createServerFn_handler',
            'src_features_assessment-results_actions_getAssessmentResults_ts--getAssessmentResults_createServerFn_handler',
            'src_features_assessment-results_actions_getUserAssessments_ts--getUserAssessments_createServerFn_handler',
            'src_features_assessment-results_actions_getStudentAssessmentResults_ts--getStudentAssessmentResults_createServerFn_handler',
        ];

        var payloads = [
            { data: { studentId: firstStudentId }, context: {} },
            { data: { userId: firstStudentId }, context: {} },
            { data: { studentId: firstStudentId, timezone: 'America/Los_Angeles' }, context: {} },
        ];

        var found = false;
        endpoints.forEach(function(ep) {
            payloads.forEach(function(payload) {
                fetch('/_serverFn/' + ep + '?createServerFn', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                }).then(function(resp) {
                    if (resp.ok) {
                        return resp.json().then(function(data) {
                            if (!found) {
                                found = true;
                                var shortName = ep.split('--')[1] ? ep.split('--')[1].split('_')[0] : ep;
                                console.log('%c[XP Discovery] ASSESSMENT ENDPOINT FOUND: ' + shortName, 'color: #22c55e; font-weight: bold; font-size: 14px;');
                                console.log('  Full endpoint:', ep);
                                console.log('  Payload:', JSON.stringify(payload));
                                console.log('  Response:', data);
                                // Store for later use
                                localStorage.setItem('tb-dash-assessment-endpoint', ep);
                                localStorage.setItem('tb-dash-assessment-payload-key', payload.data.studentId ? 'studentId' : 'userId');
                            }
                        });
                    }
                }).catch(function() {});
            });
        });

        // 3. Probe course-progress endpoints (might have activity type breakdown)
        var courseEndpoints = [
            'src_features_course-progress_api_batchClient_ts--batchFetchCourses_createServerFn_handler',
            'src_features_course-progress_api_batchClient_ts--batchFetchCoursesProgress_createServerFn_handler',
            'src_features_course-progress_api_client_ts--fetchCourseProgress_createServerFn_handler',
        ];
        courseEndpoints.forEach(function(ep) {
            payloads.forEach(function(payload) {
                fetch('/_serverFn/' + ep + '?createServerFn', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                }).then(function(resp) {
                    if (resp.ok) {
                        return resp.json().then(function(data) {
                            var shortName = ep.split('--')[1] ? ep.split('--')[1].split('_')[0] : ep;
                            console.log('%c[XP Discovery] COURSE ENDPOINT FOUND: ' + shortName, 'color: #3b82f6; font-weight: bold;');
                            console.log('  Response:', JSON.stringify(data).substring(0, 1000));
                        });
                    }
                }).catch(function() {});
            });
        });
    })();

})();
