import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
    LineChart, Line, AreaChart, Area, XAxis, YAxis, CartesianGrid,
    Tooltip, ResponsiveContainer, Legend
} from 'recharts';
import {
    Droplet, Activity, AlertTriangle, MapPin, Radio,
    Settings, ShieldAlert, Cpu, Gauge, BarChart3,
    Clock, History, Download, TrendingUp, DollarSign, LogOut, ImagePlus, Bot, Send
} from 'lucide-react';
import { MapContainer, TileLayer, Marker, Popup, Polyline } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import Login from './Login';

// Fix Leaflet marker icon issue
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
    iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
    iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

const Dashboard = () => {
    const [theme, setTheme] = useState(() => localStorage.getItem('theme') || 'dark');
    const [isLoggedIn, setIsLoggedIn] = useState(!!localStorage.getItem('token'));
    const [telemetry, setTelemetry] = useState([]);
    const [alerts, setAlerts] = useState([]);
    const [currentMode, setCurrentMode] = useState('normal');
    const [stats, setStats] = useState({
        pressure: 5.0,
        flow: 100.0,
        severity: 'Minor',
        score: 0
    });
    const [activeTab, setActiveTab] = useState('dashboard');
    const [analytics, setAnalytics] = useState(null);
    const [trends, setTrends] = useState([]);
    const [geoJson, setGeoJson] = useState(null);
    const [tickets, setTickets] = useState([]);
    const [riskData, setRiskData] = useState(null);
    const [viewMode, setViewMode] = useState('live'); // live or risk
    const [imageDetectionResult, setImageDetectionResult] = useState(null);
    const [imageHistory, setImageHistory] = useState([]);
    const [imageUploadLoading, setImageUploadLoading] = useState(false);
    const [imageUploadError, setImageUploadError] = useState('');
    const [waterQualityLive, setWaterQualityLive] = useState(null);
    const [waterQualityTrend, setWaterQualityTrend] = useState([]);
    const [qualityAlerts, setQualityAlerts] = useState([]);
    const [currentWaterMode, setCurrentWaterMode] = useState('normal');
    const [infraHealth, setInfraHealth] = useState(null);
    const [chatOpen, setChatOpen] = useState(false);
    const [chatInput, setChatInput] = useState('');
    const [chatLoading, setChatLoading] = useState(false);
    const [chatMessages, setChatMessages] = useState([
        {
            role: 'bot',
            text: 'Hi, I am your Ops Assistant. Ask me about leaks, water safety, image detection, or system health.'
        }
    ]);

    const ws = useRef(null);
    const qualityWs = useRef(null);

    useEffect(() => {
        document.body.classList.remove('light-theme', 'dark-theme');
        document.body.classList.add(theme === 'light' ? 'light-theme' : 'dark-theme');
        localStorage.setItem('theme', theme);
    }, [theme]);

    useEffect(() => {
        // Poll single data points for graphs
        const interval = setInterval(async () => {
            try {
                const res = await fetch('/api/v1/simulation/data');
                if (!res.ok) throw new Error("Simulation data fetch failed");
                const data = await res.json();

                let timestamp = new Date();
                if (data.timestamp) {
                    const parsed = new Date(data.timestamp);
                    if (!isNaN(parsed)) timestamp = parsed;
                }

                setTelemetry(prev => [...prev.slice(-29), {
                    ...data,
                    time: timestamp.toLocaleTimeString([], { hour12: false, minute: '2-digit', second: '2-digit' })
                }]);
                setStats({
                    pressure: data.pressure || 0,
                    flow: data.flow_rate || 0,
                    mode: data.mode || 'normal'
                });
            } catch (e) {
                console.error("Failed to fetch simulation data", e);
            }
        }, 1000);

        // Initial Analytics fetch
        const fetchAnalytics = async () => {
            try {
                const endpoints = [
                    '/api/v1/analytics/summary',
                    '/api/v1/analytics/trends',
                    '/api/v1/localization/geo-json',
                    '/api/v1/maintenance/',
                    '/api/v1/analytics/risk-assessment',
                    '/api/v1/leak-image-history'
                ];

                const responses = await Promise.all(endpoints.map(e => fetch(e).catch(err => ({ ok: false, json: () => null }))));

                const [sum, trend, geo, tick, risk, imgHistory] = await Promise.all(responses.map(r => r.ok ? r.json().catch(() => null) : null));

                if (sum) setAnalytics(sum);
                if (trend) setTrends(Array.isArray(trend) ? trend : []);
                if (geo) setGeoJson(geo);
                if (tick) setTickets(Array.isArray(tick) ? tick : []);
                if (risk) setRiskData(risk);
                if (imgHistory) setImageHistory(Array.isArray(imgHistory) ? imgHistory : []);
            } catch (e) {
                console.error("Failed to fetch analytical data", e);
            }
        };

        const fetchUnifiedInfrastructureHealth = async () => {
            try {
                const res = await fetch('/api/v1/infrastructure/health');
                if (!res.ok) return;
                const payload = await res.json();
                setInfraHealth(payload);
            } catch (e) {
                console.error("Failed to fetch unified infrastructure health", e);
            }
        };

        const fetchWaterQualityBootstrap = async () => {
            try {
                const statusRes = await fetch('/api/v1/water-quality/status');
                if (statusRes.ok) {
                    const statusData = await statusRes.json();
                    if (statusData?.current_mode) setCurrentWaterMode(statusData.current_mode);
                }

                const res = await fetch('/api/v1/water-quality/history?limit=20');
                if (!res.ok) return;
                const rows = await res.json();
                if (!Array.isArray(rows)) return;

                const trendRows = rows
                    .slice()
                    .reverse()
                    .map((row) => {
                        const ts = row.timestamp ? new Date(row.timestamp) : new Date();
                        return {
                            time: ts.toLocaleTimeString([], { hour12: false, minute: '2-digit', second: '2-digit' }),
                            ph: row.sensor_values?.ph ?? 0,
                            turbidity: row.sensor_values?.turbidity ?? 0,
                            tds: row.sensor_values?.tds ?? 0,
                            wqi: row.wqi_score ?? 0,
                        };
                    });

                setWaterQualityTrend(trendRows);
                if (rows.length > 0) setWaterQualityLive(rows[0]);
            } catch (e) {
                console.error("Failed to bootstrap water quality data", e);
            }
        };

        // Setup WebSocket for real-time alerts
        const connectWS = () => {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsBase = import.meta.env.VITE_BACKEND_WS_BASE || `${protocol}//${window.location.hostname}:8000`;
            const socket = new WebSocket(`${wsBase}/api/v1/alerts/ws/alerts`);

            socket.onmessage = (event) => {
                try {
                    const alert = JSON.parse(event.data);
                    if (alert) {
                        if (alert.event === 'WATER_QUALITY_ALERT') {
                            setQualityAlerts(prev => [alert, ...prev.slice(0, 7)]);
                        } else {
                            setAlerts(prev => [alert, ...prev.slice(0, 9)]);
                        }
                        fetchAnalytics();
                    }
                } catch (e) {
                    console.error("WebSocket message error", e);
                }
            };

            socket.onclose = () => {
                setTimeout(connectWS, 3000);
            };

            ws.current = socket;
        };

        const connectQualityWS = () => {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsBase = import.meta.env.VITE_BACKEND_WS_BASE || `${protocol}//${window.location.hostname}:8000`;
            const socket = new WebSocket(`${wsBase}/api/v1/water-quality/ws/live`);

            socket.onmessage = (event) => {
                try {
                    const payload = JSON.parse(event.data);
                    if (!payload) return;

                    setWaterQualityLive(payload);
                    const ts = payload.timestamp ? new Date(payload.timestamp) : new Date();
                    setWaterQualityTrend(prev => [
                        ...prev.slice(-29),
                        {
                            time: ts.toLocaleTimeString([], { hour12: false, minute: '2-digit', second: '2-digit' }),
                            ph: payload.sensor_values?.ph ?? 0,
                            turbidity: payload.sensor_values?.turbidity ?? 0,
                            tds: payload.sensor_values?.tds ?? 0,
                            wqi: payload.wqi_score ?? 0,
                        }
                    ]);

                    const isContaminatedNow =
                        payload.ai_prediction === 'CONTAMINATED' ||
                        payload.ai_prediction === 'DANGEROUS' ||
                        payload.risk_level === 'HIGH' ||
                        payload.risk_level === 'CRITICAL' ||
                        Number(payload.wqi_score || 0) < 70;

                    if (isContaminatedNow) {
                        setQualityAlerts(prev => {
                            if (prev[0]?.timestamp === payload.timestamp) return prev;
                            return [
                                {
                                    event: 'WATER_QUALITY_ALERT',
                                    severity: payload.ai_prediction === 'DANGEROUS' ? 'Critical' : 'Warning',
                                    analysis: (payload.alert_reasons || []).join(' | ') || 'Water contamination risk detected.',
                                    timestamp: payload.timestamp,
                                    location: payload.pipeline_id,
                                    wqi_score: payload.wqi_score
                                },
                                ...prev.slice(0, 7)
                            ];
                        });
                    }
                } catch (e) {
                    console.error("Water quality WebSocket message error", e);
                }
            };

            socket.onclose = () => {
                setTimeout(connectQualityWS, 3000);
            };

            qualityWs.current = socket;
        };

        fetchAnalytics();
        fetchWaterQualityBootstrap();
        fetchUnifiedInfrastructureHealth();
        connectWS();
        connectQualityWS();
        fetchAnalytics();
        const infraInterval = setInterval(fetchUnifiedInfrastructureHealth, 5000);

        return () => {
            clearInterval(interval);
            clearInterval(infraInterval);
            if (ws.current) ws.current.close();
            if (qualityWs.current) qualityWs.current.close();
        };
    }, [isLoggedIn]);

    const handleLogout = () => {
        localStorage.removeItem('token');
        setIsLoggedIn(false);
    };

    if (!isLoggedIn) {
        return <Login onLogin={() => setIsLoggedIn(true)} />;
    }

    const changeMode = async (mode) => {
        await fetch(`/api/v1/simulation/mode/${mode}`, { method: 'POST' });
        setCurrentMode(mode);
    };

    const handleLeakImageUpload = async (event) => {
        const selectedFile = event.target.files?.[0];
        if (!selectedFile) return;

        setImageUploadLoading(true);
        setImageUploadError('');

        try {
            const formData = new FormData();
            formData.append('file', selectedFile);

            const res = await fetch('/api/v1/upload-leak-image', {
                method: 'POST',
                body: formData
            });

            if (!res.ok) {
                const errBody = await res.json().catch(() => ({}));
                throw new Error(errBody.detail || 'Image detection request failed');
            }

            const data = await res.json();
            setImageDetectionResult(data);

            const historyRes = await fetch('/api/v1/leak-image-history');
            if (historyRes.ok) {
                const historyData = await historyRes.json();
                setImageHistory(Array.isArray(historyData) ? historyData : []);
            }
        } catch (error) {
            setImageUploadError(error.message || 'Failed to process image');
        } finally {
            setImageUploadLoading(false);
            event.target.value = '';
        }
    };

    const changeWaterQualityMode = async (mode) => {
        try {
            const res = await fetch(`/api/v1/water-quality/mode/${mode}`, { method: 'POST' });
            if (res.ok) setCurrentWaterMode(mode);
        } catch (e) {
            console.error("Failed to change water quality mode", e);
        }
    };

    const sendChatMessage = async (customMessage = null) => {
        const messageToSend = (customMessage ?? chatInput).trim();
        if (!messageToSend || chatLoading) return;

        setChatMessages(prev => [...prev, { role: 'user', text: messageToSend }]);
        setChatInput('');
        setChatLoading(true);

        try {
            const res = await fetch('/api/v1/chatbot/message', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: messageToSend })
            });
            if (!res.ok) throw new Error('Chat request failed');
            const data = await res.json();
            setChatMessages(prev => [
                ...prev,
                {
                    role: 'bot',
                    text: data.answer || 'I could not generate a response.',
                    suggestions: Array.isArray(data.suggestions) ? data.suggestions.slice(0, 3) : []
                }
            ]);
        } catch (e) {
            setChatMessages(prev => [
                ...prev,
                { role: 'bot', text: 'Chatbot is temporarily unavailable. Please try again.' }
            ]);
        } finally {
            setChatLoading(false);
        }
    };

    const downloadFromEndpoint = async (url, fallbackFilename) => {
        try {
            const res = await fetch(url);
            if (!res.ok) throw new Error('Download failed');

            const blob = await res.blob();
            const disposition = res.headers.get('content-disposition') || '';
            const filenameMatch = disposition.match(/filename="?([^"]+)"?/i);
            const filename = filenameMatch?.[1] || fallbackFilename;

            const objectUrl = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = objectUrl;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(objectUrl);
        } catch (e) {
            console.error('Download error', e);
        }
    };

    const currentWQ = waterQualityLive?.sensor_values || {};
    const currentWqi = Number(waterQualityLive?.wqi_score || 0);
    const currentPrediction = waterQualityLive?.ai_prediction || 'SAFE';
    const currentRisk = waterQualityLive?.risk_level || 'LOW';
    const isSafeToDrink = currentPrediction === 'SAFE' && currentWqi >= 70;
    const isContaminated =
        currentPrediction === 'CONTAMINATED' ||
        currentPrediction === 'DANGEROUS' ||
        currentRisk === 'HIGH' ||
        currentRisk === 'CRITICAL' ||
        currentWqi < 70;
    const phGaugePercent = Math.max(0, Math.min(100, ((Number(currentWQ.ph || 0) / 14) * 100)));
    const wqiPercent = Math.max(0, Math.min(100, currentWqi));

    const riskTone = {
        LOW: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
        MEDIUM: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
        HIGH: 'text-orange-400 bg-orange-500/10 border-orange-500/20',
        CRITICAL: 'text-red-500 bg-red-500/10 border-red-500/20'
    };

    const predictionTone = {
        SAFE: 'text-emerald-400',
        MODERATE: 'text-amber-400',
        CONTAMINATED: 'text-orange-400',
        DANGEROUS: 'text-red-500'
    };

    const infraStatusTone = {
        HEALTHY: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
        WATCH: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
        DEGRADED: 'text-orange-400 bg-orange-500/10 border-orange-500/20',
        ALERT: 'text-orange-400 bg-orange-500/10 border-orange-500/20',
        CRITICAL: 'text-red-500 bg-red-500/10 border-red-500/20',
        MONITORING: 'text-blue-400 bg-blue-500/10 border-blue-500/20'
    };

    const leakModule = infraHealth?.modules?.leak_detection;
    const imageModule = infraHealth?.modules?.image_detection;
    const waterModule = infraHealth?.modules?.water_quality_prediction;

    return (
        <div className={`min-h-screen p-3 sm:p-4 md:p-6 space-y-4 md:space-y-6 overflow-x-hidden ${theme === 'dark' ? 'bg-[#020617] text-slate-200' : 'bg-slate-100 text-slate-800'}`}>
            {/* Header */}
            <header className="flex flex-col xl:flex-row xl:items-center xl:justify-between pb-4 border-b border-white/5 gap-4">
                <div className="flex items-center gap-3">
                    <div className="p-2.5 rounded-xl bg-brand-500/10 border border-brand-500/20 text-brand-400">
                        <Droplet size={28} />
                    </div>
                    <div>
                        <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-white">LeakWatch AI</h1>
                        <p className="text-xs sm:text-sm text-slate-400 font-medium">Infrastructure Intelligence Dashboard</p>
                    </div>
                </div>

                <div className="flex flex-wrap gap-2">
                    <button
                        onClick={() => setActiveTab('dashboard')}
                        className={`px-3 sm:px-4 py-2 rounded-lg text-xs sm:text-sm font-semibold transition-all ${activeTab === 'dashboard' ? 'bg-brand-500/10 text-brand-400' : 'text-slate-400'}`}
                    >
                        Live Dashboard
                    </button>
                    <button
                        onClick={() => setActiveTab('reports')}
                        className={`px-3 sm:px-4 py-2 rounded-lg text-xs sm:text-sm font-semibold transition-all ${activeTab === 'reports' ? 'bg-brand-500/10 text-brand-400' : 'text-slate-400'}`}
                    >
                        Intelligence Reports
                    </button>
                    <div className="hidden sm:block w-[1px] h-8 bg-white/5 mx-2" />
                    {['normal', 'small_leak', 'major_burst', 'intermittent', 'valve_fault'].map(mode => (
                        <button
                            key={mode}
                            onClick={() => changeMode(mode)}
                            className={`px-3 sm:px-4 py-2 rounded-lg text-[11px] sm:text-sm font-semibold transition-all ${currentMode === mode
                                ? 'bg-brand-600 text-white shadow-lg shadow-brand-500/20'
                                : 'bg-slate-800/50 text-slate-400 hover:bg-slate-800'
                                }`}
                        >
                            {mode.replace('_', ' ').toUpperCase()}
                        </button>
                    ))}
                </div>

                <div className="flex items-center gap-2 sm:gap-4 self-end xl:self-auto">
                    <button
                        onClick={() => setTheme(prev => (prev === 'dark' ? 'light' : 'dark'))}
                        className={`px-2 sm:px-3 py-2 rounded-lg text-[10px] sm:text-xs font-bold border transition-all ${theme === 'dark' ? 'bg-white/5 hover:bg-white/10 border-white/10 text-slate-300' : 'bg-slate-200 hover:bg-slate-300 border-slate-300 text-slate-700'}`}
                        title="Toggle Theme"
                    >
                        {theme === 'dark' ? 'Switch to Light' : 'Switch to Dark'}
                    </button>
                    <button
                        onClick={handleLogout}
                        className="p-2 rounded-lg bg-white/5 hover:bg-red-500/10 text-slate-400 hover:text-red-500 border border-white/5 transition-all"
                        title="Sign Out"
                    >
                        <LogOut size={18} />
                    </button>
                    <div className="w-10 h-10 rounded-full bg-brand-500/10 border border-brand-500/20 flex items-center justify-center text-brand-400 font-black">
                        AD
                    </div>
                </div>
            </header>

            {activeTab === 'dashboard' ? (
                <>
                    {/* Top Stats */}
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                        {[
                            { label: 'System Pressure', val: `${stats.pressure} bar`, icon: Gauge, color: 'text-blue-400' },
                            { label: 'Flow Rate', val: `${stats.flow} L/min`, icon: Activity, color: 'text-emerald-400' },
                            { label: 'Anomaly Status', val: alerts[0]?.severity || 'Healthy', icon: ShieldAlert, color: alerts[0]?.severity === 'Critical' ? 'text-red-500' : 'text-slate-400' },
                            { label: 'Infrastructure Health', val: infraHealth ? `${infraHealth.overall_health_score}%` : 'Loading...', icon: Cpu, color: infraHealth?.overall_status === 'CRITICAL' ? 'text-red-500' : infraHealth?.overall_status === 'DEGRADED' ? 'text-orange-400' : 'text-purple-400' },
                        ].map((item, idx) => (
                            <div key={idx} className="glass p-5 rounded-2xl flex items-center justify-between group hover:border-white/20 transition-colors">
                                <div>
                                    <p className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-1">{item.label}</p>
                                    <h3 className={`text-2xl font-bold ${item.color}`}>{item.val}</h3>
                                </div>
                                <div className={`p-3 rounded-xl bg-slate-950/50 ${item.color}`}>
                                    <item.icon size={20} />
                                </div>
                            </div>
                        ))}
                    </div>

                    <div className="glass rounded-2xl p-6 space-y-5">
                        <div className="flex items-center justify-between">
                            <h3 className="text-lg font-bold flex items-center gap-2">
                                <BarChart3 size={18} className="text-brand-400" />
                                Unified Infrastructure Health
                            </h3>
                            <div className={`px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-widest border ${infraStatusTone[infraHealth?.overall_status] || infraStatusTone.HEALTHY}`}>
                                {infraHealth?.overall_status || 'HEALTHY'}
                            </div>
                        </div>

                        <div className="h-2 rounded-full bg-slate-800 overflow-hidden">
                            <div
                                className={`${(infraHealth?.overall_health_score || 0) >= 85 ? 'bg-emerald-500' : (infraHealth?.overall_health_score || 0) >= 65 ? 'bg-blue-500' : (infraHealth?.overall_health_score || 0) >= 40 ? 'bg-orange-500' : 'bg-red-500'} h-full`}
                                style={{ width: `${Math.max(0, Math.min(100, Number(infraHealth?.overall_health_score || 0)))}%` }}
                            />
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                            <div className="rounded-xl border border-white/10 bg-slate-900/40 p-4 space-y-2">
                                <div className="flex items-center justify-between">
                                    <p className="text-xs font-bold uppercase tracking-widest text-slate-500">Leak Detection</p>
                                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${infraStatusTone[leakModule?.status] || infraStatusTone.HEALTHY}`}>
                                        {leakModule?.status || 'HEALTHY'}
                                    </span>
                                </div>
                                <p className="text-2xl font-bold text-white">{Math.round(Number(leakModule?.health_score || 0))}%</p>
                                <p className="text-xs text-slate-400 leading-relaxed">{leakModule?.details || 'Leak monitoring active with simulated telemetry feed.'}</p>
                            </div>

                            <div className="rounded-xl border border-white/10 bg-slate-900/40 p-4 space-y-2">
                                <div className="flex items-center justify-between">
                                    <p className="text-xs font-bold uppercase tracking-widest text-slate-500">Image Detection</p>
                                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${infraStatusTone[imageModule?.status] || infraStatusTone.MONITORING}`}>
                                        {imageModule?.status || 'MONITORING'}
                                    </span>
                                </div>
                                <p className="text-2xl font-bold text-white">{Math.round(Number(imageModule?.health_score || 0))}%</p>
                                <p className="text-xs text-slate-400 leading-relaxed">{imageModule?.details || 'Image AI pipeline online. Awaiting latest simulated/uploaded evidence.'}</p>
                            </div>

                            <div className="rounded-xl border border-white/10 bg-slate-900/40 p-4 space-y-2">
                                <div className="flex items-center justify-between">
                                    <p className="text-xs font-bold uppercase tracking-widest text-slate-500">Water Quality Prediction</p>
                                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${infraStatusTone[waterModule?.status] || infraStatusTone.HEALTHY}`}>
                                        {waterModule?.status || 'HEALTHY'}
                                    </span>
                                </div>
                                <p className="text-2xl font-bold text-white">{Math.round(Number(waterModule?.health_score || 0))}%</p>
                                <p className="text-xs text-slate-400 leading-relaxed">
                                    AI: <span className="font-bold text-slate-300">{waterModule?.ai_prediction || 'SAFE'}</span> | WQI: <span className="font-bold text-slate-300">{Number(waterModule?.wqi_score || 0).toFixed(1)}</span>
                                </p>
                            </div>
                        </div>

                        <p className="text-[11px] text-slate-500 uppercase tracking-widest font-bold">
                            Data Source: {infraHealth?.data_source || 'simulated'} | Hardware Sensors Required: {infraHealth?.hardware_required === false ? 'No' : 'Yes'}
                        </p>
                    </div>

                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                        <div className="lg:col-span-2 glass rounded-2xl p-6">
                            <div className="flex items-center justify-between mb-4">
                                <h3 className="text-lg font-bold flex items-center gap-2">
                                    <ImagePlus size={18} className="text-brand-400" />
                                    Image Leak Detection
                                </h3>
                                <label className="px-4 py-2 rounded-lg bg-brand-600 text-white text-xs font-bold cursor-pointer hover:bg-brand-500 transition-colors">
                                    {imageUploadLoading ? 'Processing...' : 'Upload Image'}
                                    <input
                                        type="file"
                                        accept="image/*"
                                        onChange={handleLeakImageUpload}
                                        disabled={imageUploadLoading}
                                        className="hidden"
                                    />
                                </label>
                            </div>

                            {imageUploadError ? (
                                <p className="text-sm text-red-400 mb-4">{imageUploadError}</p>
                            ) : null}

                            {imageDetectionResult ? (
                                <div className="space-y-4">
                                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                                        <div className="p-3 rounded-lg bg-slate-900/60 border border-white/5">
                                            <p className="text-slate-500 uppercase tracking-wide">Leak Type</p>
                                            <p className="text-white font-bold mt-1">{imageDetectionResult.leak_type}</p>
                                        </div>
                                        <div className="p-3 rounded-lg bg-slate-900/60 border border-white/5">
                                            <p className="text-slate-500 uppercase tracking-wide">Severity</p>
                                            <p className="text-white font-bold mt-1">{imageDetectionResult.severity_level}</p>
                                        </div>
                                        <div className="p-3 rounded-lg bg-slate-900/60 border border-white/5">
                                            <p className="text-slate-500 uppercase tracking-wide">Confidence</p>
                                            <p className="text-white font-bold mt-1">{(imageDetectionResult.confidence_score * 100).toFixed(2)}%</p>
                                        </div>
                                        <div className="p-3 rounded-lg bg-slate-900/60 border border-white/5">
                                            <p className="text-slate-500 uppercase tracking-wide">Detections</p>
                                            <p className="text-white font-bold mt-1">{imageDetectionResult.detections?.length || 0}</p>
                                        </div>
                                    </div>

                                    <p className="text-xs text-slate-300 bg-slate-900/60 border border-white/5 rounded-lg p-3">
                                        {imageDetectionResult.recommended_solution}
                                    </p>

                                    <div className="rounded-xl overflow-hidden border border-white/10">
                                        <img
                                            src={`data:image/jpeg;base64,${imageDetectionResult.annotated_image_base64}`}
                                            alt="Leak detection annotated result"
                                            className="w-full h-auto"
                                        />
                                    </div>
                                </div>
                            ) : (
                                <div className="h-[240px] rounded-xl border border-dashed border-white/10 bg-slate-900/40 flex items-center justify-center text-slate-500 text-sm">
                                    Upload an infrastructure image to run YOLOv8 leak detection.
                                </div>
                            )}
                        </div>

                        <div className="glass rounded-2xl p-6">
                            <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
                                <History size={18} className="text-brand-400" />
                                Image Prediction History
                            </h3>
                            <div className="space-y-3 max-h-[420px] overflow-y-auto pr-1 custom-scrollbar">
                                {imageHistory.length === 0 ? (
                                    <p className="text-sm text-slate-500">No image predictions yet.</p>
                                ) : imageHistory.map((item) => (
                                    <div key={item.id} className="rounded-xl border border-white/10 bg-slate-900/50 p-3 space-y-1">
                                        <p className="text-xs font-bold text-white">{item.leak_type}</p>
                                        <p className="text-[11px] text-slate-400">{item.filename}</p>
                                        <p className="text-[11px] text-slate-500">
                                            {new Date(item.timestamp).toLocaleString()} | {item.severity_level} | {(item.confidence_score * 100).toFixed(2)}%
                                        </p>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>

                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                        <div className="lg:col-span-2 glass rounded-2xl p-6">
                            <div className="flex items-center justify-between mb-6">
                                <h3 className="text-lg font-bold flex items-center gap-2">
                                    <Droplet size={18} className="text-cyan-400" />
                                    Water Quality Panel
                                </h3>
                                <div className={`px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-widest border ${riskTone[currentRisk] || riskTone.LOW}`}>
                                    Risk: {currentRisk}
                                </div>
                            </div>

                            <div className="flex flex-wrap gap-2 mb-4">
                                {['normal', 'chemical_contamination', 'dirty_water', 'industrial_pollution'].map(mode => (
                                    <button
                                        key={mode}
                                        onClick={() => changeWaterQualityMode(mode)}
                                        className={`px-3 py-1.5 rounded-lg text-[10px] font-black uppercase tracking-widest transition-all border ${currentWaterMode === mode ? 'bg-cyan-600 text-white border-cyan-500/60' : 'bg-slate-900/50 text-slate-400 border-white/10 hover:bg-slate-800'}`}
                                    >
                                        {mode.replace(/_/g, ' ')}
                                    </button>
                                ))}
                            </div>

                            {isContaminated ? (
                                <div className="mb-4 rounded-xl border border-red-500/30 bg-red-500/10 p-3">
                                    <p className="text-xs font-black uppercase tracking-wider text-red-400">Contamination Alert Active</p>
                                    <p className="text-xs text-red-200 mt-1">
                                        Current water condition indicates contamination risk. Avoid drinking this water until values normalize.
                                    </p>
                                </div>
                            ) : (
                                <div className="mb-4 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3">
                                    <p className="text-xs font-black uppercase tracking-wider text-emerald-400">Water Status Stable</p>
                                    <p className="text-xs text-emerald-200 mt-1">
                                        Current live metrics indicate the water is safe for consumption.
                                    </p>
                                </div>
                            )}

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                                <div className="rounded-xl border border-white/10 bg-slate-900/50 p-4 space-y-3">
                                    <div className="flex items-center justify-between">
                                        <p className="text-xs uppercase tracking-widest text-slate-500 font-bold">Live pH Gauge</p>
                                        <span className="text-sm font-bold text-white">{Number(currentWQ.ph || 0).toFixed(2)}</span>
                                    </div>
                                    <div className="h-3 rounded-full bg-slate-800 overflow-hidden">
                                        <div className={`h-full ${Number(currentWQ.ph || 0) < 6 || Number(currentWQ.ph || 0) > 8.5 ? 'bg-red-500' : 'bg-emerald-500'}`} style={{ width: `${phGaugePercent}%` }} />
                                    </div>
                                    <div className="flex justify-between text-[10px] text-slate-500 font-semibold">
                                        <span>0</span>
                                        <span>Ideal 6.5-8.5</span>
                                        <span>14</span>
                                    </div>
                                </div>

                                <div className="rounded-xl border border-white/10 bg-slate-900/50 p-4 space-y-3">
                                    <div className="flex items-center justify-between">
                                        <p className="text-xs uppercase tracking-widest text-slate-500 font-bold">WQI Meter</p>
                                        <span className="text-sm font-bold text-white">{currentWqi.toFixed(1)}</span>
                                    </div>
                                    <div className="h-3 rounded-full bg-slate-800 overflow-hidden">
                                        <div className={`h-full ${currentWqi >= 90 ? 'bg-emerald-500' : currentWqi >= 70 ? 'bg-blue-500' : currentWqi >= 50 ? 'bg-amber-500' : 'bg-red-500'}`} style={{ width: `${wqiPercent}%` }} />
                                    </div>
                                    <p className="text-xs text-slate-400 flex items-center justify-between">
                                        <span>
                                        Water Quality Status:
                                        <span className={`font-bold ml-2 ${predictionTone[currentPrediction] || predictionTone.SAFE}`}>
                                            {currentPrediction}
                                        </span>
                                        </span>
                                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${isSafeToDrink ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20' : 'text-red-500 bg-red-500/10 border-red-500/20'}`}>
                                            {isSafeToDrink ? 'Safe to Drink' : 'Not Safe to Drink'}
                                        </span>
                                    </p>
                                </div>
                            </div>

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div className="rounded-xl border border-white/10 bg-slate-900/40 p-4">
                                    <p className="text-xs uppercase tracking-widest text-slate-500 font-bold mb-3">TDS Graph</p>
                                    <div className="h-[200px]">
                                        <ResponsiveContainer width="100%" height="100%">
                                            <LineChart data={waterQualityTrend}>
                                                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                                                <XAxis dataKey="time" stroke="#64748b" fontSize={10} axisLine={false} tickLine={false} />
                                                <YAxis stroke="#64748b" fontSize={10} axisLine={false} tickLine={false} />
                                                <Tooltip contentStyle={{ backgroundColor: '#0f172a', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '12px' }} />
                                                <Line type="monotone" dataKey="tds" stroke="#f97316" strokeWidth={2.5} dot={false} />
                                            </LineChart>
                                        </ResponsiveContainer>
                                    </div>
                                </div>
                                <div className="rounded-xl border border-white/10 bg-slate-900/40 p-4">
                                    <p className="text-xs uppercase tracking-widest text-slate-500 font-bold mb-3">Turbidity Trend</p>
                                    <div className="h-[200px]">
                                        <ResponsiveContainer width="100%" height="100%">
                                            <LineChart data={waterQualityTrend}>
                                                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                                                <XAxis dataKey="time" stroke="#64748b" fontSize={10} axisLine={false} tickLine={false} />
                                                <YAxis stroke="#64748b" fontSize={10} axisLine={false} tickLine={false} />
                                                <Tooltip contentStyle={{ backgroundColor: '#0f172a', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '12px' }} />
                                                <Line type="monotone" dataKey="turbidity" stroke="#22d3ee" strokeWidth={2.5} dot={false} />
                                            </LineChart>
                                        </ResponsiveContainer>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div className="glass rounded-2xl p-6">
                            <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
                                <AlertTriangle size={18} className="text-orange-400" />
                                Contamination Alerts
                            </h3>
                            <div className="space-y-3 max-h-[420px] overflow-y-auto pr-1 custom-scrollbar">
                                {qualityAlerts.length === 0 ? (
                                    <p className="text-sm text-slate-500">No contamination alerts in live stream.</p>
                                ) : qualityAlerts.map((alert, idx) => (
                                    <div key={`${alert.timestamp}-${idx}`} className={`rounded-xl border p-3 ${alert.severity === 'Critical' ? 'border-red-500/30 bg-red-500/5' : 'border-orange-500/30 bg-orange-500/5'}`}>
                                        <div className="flex justify-between items-center mb-2">
                                            <span className="text-xs font-bold text-white">{alert.severity} Alert</span>
                                            <span className="text-[10px] text-slate-500">{alert.timestamp ? new Date(alert.timestamp).toLocaleTimeString() : ''}</span>
                                        </div>
                                        <p className="text-[11px] text-slate-300 leading-relaxed">{alert.analysis}</p>
                                        <div className="mt-2 flex items-center justify-between text-[10px] font-bold">
                                            <span className="text-slate-400">Pipeline: {alert.location || 'Unknown'}</span>
                                            <span className="text-brand-400">WQI: {Number(alert.wqi_score || 0).toFixed(1)}</span>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>

                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                        {/* Pressure Chart */}
                        <div className="lg:col-span-2 glass rounded-2xl p-6 relative overflow-hidden">
                            <div className="flex items-center justify-between mb-8">
                                <h3 className="text-lg font-bold flex items-center gap-2">
                                    <Activity size={18} className="text-brand-400" />
                                    Live Telemetry Analysis
                                </h3>
                                <div className="flex gap-4">
                                    <div className="flex items-center gap-2 text-xs font-medium text-slate-400">
                                        <span className="w-2 h-2 rounded-full bg-blue-500"></span> Pressure
                                    </div>
                                    <div className="flex items-center gap-2 text-xs font-medium text-slate-400">
                                        <span className="w-2 h-2 rounded-full bg-emerald-500"></span> Flow
                                    </div>
                                </div>
                            </div>

                            <div className="h-[350px] w-full">
                                <ResponsiveContainer width="100%" height="100%">
                                    <AreaChart data={telemetry}>
                                        <defs>
                                            <linearGradient id="colorPressure" x1="0" y1="0" x2="0" y2="1">
                                                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                                                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                                            </linearGradient>
                                            <linearGradient id="colorFlow" x1="0" y1="0" x2="0" y2="1">
                                                <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                                                <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                                            </linearGradient>
                                        </defs>
                                        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                                        <XAxis dataKey="time" stroke="#64748b" fontSize={10} axisLine={false} tickLine={false} />
                                        <YAxis stroke="#64748b" fontSize={10} axisLine={false} tickLine={false} />
                                        <Tooltip
                                            contentStyle={{ backgroundColor: '#0f172a', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '12px' }}
                                            itemStyle={{ fontSize: '12px', fontWeight: 'bold' }}
                                        />
                                        <Area type="monotone" dataKey="pressure" stroke="#3b82f6" strokeWidth={3} fillOpacity={1} fill="url(#colorPressure)" />
                                        <Area type="monotone" dataKey="flow_rate" stroke="#10b981" strokeWidth={3} fillOpacity={1} fill="url(#colorFlow)" />
                                    </AreaChart>
                                </ResponsiveContainer>
                            </div>
                        </div>

                        {/* Alerts & Localization */}
                        <div className="space-y-6">
                            <div className="glass rounded-2xl p-6 min-h-[440px] flex flex-col">
                                <div className="flex items-center justify-between mb-6">
                                    <h3 className="text-lg font-bold flex items-center gap-2">
                                        <Radio size={18} className="text-red-500 animate-pulse" />
                                        Incident Log
                                    </h3>
                                    <span className="text-[10px] bg-red-500/10 text-red-500 px-2 py-0.5 rounded-full font-bold uppercase tracking-wider underline">Live Feed</span>
                                </div>

                                <div className="space-y-3 flex-1 overflow-y-auto pr-2 custom-scrollbar">
                                    {alerts.length === 0 ? (
                                        <div className="h-full flex flex-col items-center justify-center text-slate-500 gap-3 opacity-50">
                                            <ShieldAlert size={40} strokeWidth={1} />
                                            <p className="text-sm font-medium">No active leaks detected</p>
                                        </div>
                                    ) : (
                                        alerts.map((alert, idx) => {
                                            const ticket = tickets.find(t => t.alert_id === alert.id);
                                            return (
                                                <div key={idx} className={`p-4 rounded-xl border space-y-3 transition-all ${alert.severity === 'Critical' ? 'bg-red-500/5 border-red-500/20' : 'bg-orange-500/5 border-orange-500/20'}`}>
                                                    <div className="flex gap-3 sm:gap-4">
                                                        <div className={`p-2 rounded-lg self-start ${alert.severity === 'Critical' ? 'bg-red-500/10 text-red-500' : 'bg-orange-500/10 text-orange-500'}`}>
                                                            <AlertTriangle size={20} />
                                                        </div>
                                                        <div className="space-y-1 flex-1">
                                                            <div className="flex items-start justify-between gap-2 flex-wrap">
                                                                <div className="flex items-center gap-2 flex-wrap">
                                                                    <span className="text-sm font-bold text-white">{alert.severity || 'Unknown'} Incident</span>
                                                                    <span className="text-[10px] text-slate-500 font-mono italic">
                                                                        {alert.timestamp ? new Date(alert.timestamp).toLocaleTimeString() : 'N/A'}
                                                                    </span>
                                                                </div>
                                                                {ticket ? (
                                                                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${ticket.status === 'Resolved' ? 'bg-emerald-500/20 text-emerald-400' :
                                                                        ticket.status === 'In Progress' ? 'bg-blue-500/20 text-blue-400' : 'bg-slate-500/20 text-slate-400'
                                                                        }`}>
                                                                        {ticket.status}
                                                                    </span>
                                                                ) : null}
                                                            </div>
                                                            <p className="text-xs text-slate-400 font-medium leading-relaxed">{alert.analysis}</p>
                                                            <div className="flex items-center gap-2 sm:gap-4 pt-1 flex-wrap">
                                                                <span className="flex items-center gap-1 text-[10px] font-bold text-slate-500 bg-slate-800 px-2 py-0.5 rounded uppercase break-all">
                                                                    <MapPin size={10} /> Seg: {JSON.stringify(alert.location)}
                                                                </span>
                                                                <span className="text-[10px] font-bold text-brand-400">Score: {Math.round(alert.severity_score)}%</span>
                                                            </div>
                                                        </div>
                                                    </div>

                                                    {ticket && ticket.status !== 'Resolved' && (
                                                        <div className="flex gap-2">
                                                            <button
                                                                onClick={async () => {
                                                                    await fetch(`/api/v1/maintenance/${ticket.id}`, {
                                                                        method: 'PATCH',
                                                                        headers: { 'Content-Type': 'application/json' },
                                                                        body: JSON.stringify({ status: 'In Progress' })
                                                                    });
                                                                    const freshTickets = await (await fetch('/api/v1/maintenance/')).json();
                                                                    setTickets(freshTickets);
                                                                }}
                                                                className="flex-1 py-2 bg-blue-500/10 hover:bg-blue-500/20 border border-blue-500/20 rounded-lg text-[10px] font-bold text-blue-400 transition-all"
                                                            >
                                                                Dispatch
                                                            </button>
                                                        </div>
                                                    )}
                                                </div>
                                            );
                                        })
                                    )}
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                        {/* Network Diagram Placeholder */}
                        <div className="glass rounded-2xl p-6 md:col-span-2 min-h-[400px]">
                            <div className="flex items-center justify-between mb-6">
                                <h3 className="text-lg font-bold flex items-center gap-2">
                                    <MapPin size={18} className="text-brand-400" />
                                    {viewMode === 'live' ? 'Geospatial Infrastructure Map' : 'Infrastructure Risk Heatmap'}
                                </h3>
                                <div className="flex bg-slate-950/50 p-1 rounded-lg border border-white/5">
                                    <button
                                        onClick={() => setViewMode('live')}
                                        className={`px-3 py-1 rounded-md text-[10px] font-black uppercase tracking-widest transition-all ${viewMode === 'live' ? 'bg-brand-500 text-white shadow-lg' : 'text-slate-500 hover:text-slate-300'}`}
                                    >
                                        Live
                                    </button>
                                    <button
                                        onClick={() => setViewMode('risk')}
                                        className={`px-3 py-1 rounded-md text-[10px] font-black uppercase tracking-widest transition-all ${viewMode === 'risk' ? 'bg-orange-600 text-white shadow-lg' : 'text-slate-500 hover:text-slate-300'}`}
                                    >
                                        Risk
                                    </button>
                                </div>
                            </div>
                            <div className="h-[320px] rounded-xl overflow-hidden border border-white/5 relative bg-slate-900 shadow-inner">
                                {geoJson && geoJson.features && (
                                    <MapContainer center={[18.5204, 73.8567]} zoom={16} scrollWheelZoom={false} style={{ height: '100%', width: '100%', borderRadius: '12px' }}>
                                        <TileLayer
                                            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
                                            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
                                        />
                                        {geoJson.features.map((f, i) => {
                                            const key = `feat-${i}`;
                                            if (f.geometry.type === 'Point') {
                                                const id = f.properties?.id;
                                                const loc = alerts[0]?.location;
                                                const isLeakingNode = typeof loc === 'string' && loc.split('-').includes(id);
                                                return (
                                                    <Marker
                                                        key={key}
                                                        position={[f.geometry.coordinates[1], f.geometry.coordinates[0]]}
                                                    >
                                                        <Popup>
                                                            <div className="text-slate-900 p-1">
                                                                <strong>Node: {id}</strong><br />
                                                                Status: {isLeakingNode ? 'ALERT' : 'Normal'}
                                                            </div>
                                                        </Popup>
                                                    </Marker>
                                                );
                                            }

                                            if (f.geometry.type === 'LineString') {
                                                const segment = f.properties?.segment;
                                                const isLeakingSegment = alerts[0]?.location === segment;
                                                const risk = riskData?.[segment];
                                                const riskColor = risk?.status === 'Critical' ? '#ef4444' : risk?.status === 'Warning' ? '#f97316' : '#10b981';

                                                return (
                                                    <Polyline
                                                        key={key}
                                                        positions={f.geometry.coordinates.map(c => [c[1], c[0]])}
                                                        pathOptions={{
                                                            color: viewMode === 'live' ? (isLeakingSegment ? '#ef4444' : '#3b82f6') : riskColor,
                                                            weight: (viewMode === 'live' && isLeakingSegment) ? 10 : 6,
                                                            opacity: 0.8,
                                                            dashArray: (viewMode === 'live' && isLeakingSegment) ? '10, 15' : null
                                                        }}
                                                    >
                                                        <Popup>
                                                            <div className="text-slate-900 p-1">
                                                                <strong>Segment: {segment}</strong><br />
                                                                Status: {isLeakingSegment ? 'LEAK DETECTED' : 'Normal'}
                                                            </div>
                                                        </Popup>
                                                    </Polyline>
                                                );
                                            }
                                            return null;
                                        })}
                                    </MapContainer>
                                )}
                            </div>
                        </div>

                        {/* Training Status */}
                        <div className="glass rounded-2xl p-6 bg-brand-500/5">
                            <h3 className="text-lg font-bold flex items-center gap-2 mb-4">
                                <Settings size={18} className="text-brand-400" />
                                System Calibration
                            </h3>
                            <p className="text-xs text-slate-400 mb-6 leading-relaxed">The Isolation Forest model is optimized for the current network load. Calibrate to refresh baselines.</p>
                            <button
                                onClick={() => fetch('/api/v1/detection/train-simulated', { method: 'POST' })}
                                className="w-full py-3 bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl text-sm font-bold transition-all"
                            >
                                Calibrate AI Model
                            </button>
                            <div className="mt-6 p-4 rounded-xl bg-slate-950/50 space-y-3">
                                <div className="flex justify-between text-[10px] font-bold uppercase tracking-widest text-slate-500">
                                    <span>Model Status</span>
                                    <span className="text-emerald-500">Optimal</span>
                                </div>
                                <div className="h-1 bg-slate-800 rounded-full overflow-hidden">
                                    <div className="h-full bg-brand-500 w-[95%]"></div>
                                </div>
                            </div>
                        </div>
                    </div>
                </>
            ) : (
                <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                        {[
                            { label: 'Total Incidents (30d)', val: analytics?.summary?.total_incidents || 0, icon: History, color: 'text-blue-400' },
                            { label: 'Critical Events', val: analytics?.summary?.critical_incidents || 0, icon: ShieldAlert, color: 'text-red-400' },
                            { label: 'Est. Water Loss', val: `${analytics?.summary?.total_water_loss_liters || 0} L`, icon: Droplet, color: 'text-cyan-400' },
                            { label: 'Financial Impact', val: `$${analytics?.summary?.total_financial_loss_usd || 0}`, icon: DollarSign, color: 'text-emerald-400' },
                        ].map((item, idx) => (
                            <div key={idx} className="glass p-5 rounded-2xl flex items-center justify-between">
                                <div>
                                    <p className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-1">{item.label}</p>
                                    <h3 className={`text-2xl font-bold ${item.color}`}>{item.val}</h3>
                                </div>
                                <div className={`p-3 rounded-xl bg-slate-950/50 ${item.color}`}>
                                    <item.icon size={20} />
                                </div>
                            </div>
                        ))}
                    </div>

                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                        <div className="lg:col-span-2 glass rounded-2xl p-6">
                            <h3 className="text-lg font-bold mb-8 flex items-center gap-2">
                                <TrendingUp size={18} className="text-brand-400" />
                                Incident Trends (Last 7 Days)
                            </h3>
                            <div className="h-[300px]">
                                <ResponsiveContainer width="100%" height="100%">
                                    <LineChart data={trends}>
                                        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                                        <XAxis dataKey="timestamp" stroke="#64748b" fontSize={10} />
                                        <YAxis stroke="#64748b" fontSize={10} />
                                        <Tooltip
                                            contentStyle={{ backgroundColor: '#0f172a', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '12px' }}
                                        />
                                        <Line type="monotone" dataKey="incidents" stroke="#3b82f6" strokeWidth={3} dot={{ r: 4, fill: '#3b82f6' }} />
                                    </LineChart>
                                </ResponsiveContainer>
                            </div>
                        </div>

                        <div className="glass rounded-2xl p-6">
                            <h3 className="text-lg font-bold mb-6 flex items-center gap-2">
                                <Download size={18} className="text-brand-400" />
                                Export Reports
                            </h3>
                            <div className="space-y-4">
                                <button
                                    onClick={() => downloadFromEndpoint('/api/v1/analytics/export/monthly-summary?format=csv', 'monthly_summary.csv')}
                                    className="w-full p-4 rounded-xl bg-white/5 border border-white/10 hover:bg-white/10 transition-all flex items-center justify-between group"
                                >
                                    <div className="text-left">
                                        <p className="text-sm font-bold">Monthly Summary</p>
                                        <p className="text-[10px] text-slate-500">Analytics, Loss, & Maintenance</p>
                                    </div>
                                    <Download size={18} className="text-slate-500 group-hover:text-white" />
                                </button>
                                <button
                                    onClick={() => downloadFromEndpoint('/api/v1/analytics/export/telemetry?format=csv&days=30', 'telemetry_30d.csv')}
                                    className="w-full p-4 rounded-xl bg-white/5 border border-white/10 hover:bg-white/10 transition-all flex items-center justify-between group"
                                >
                                    <div className="text-left">
                                        <p className="text-sm font-bold">Raw Telemetry Data</p>
                                        <p className="text-[10px] text-slate-500">CSV/JSON Export</p>
                                    </div>
                                    <Download size={18} className="text-slate-500 group-hover:text-white" />
                                </button>
                            </div>

                            <div className="mt-8 p-4 rounded-xl bg-brand-500/10 border border-brand-500/20">
                                <p className="text-xs font-bold text-brand-400 mb-2 uppercase tracking-wider">AI Insight</p>
                                <p className="text-xs text-slate-400 leading-relaxed italic">
                                    "System efficiency has increased by 12% compared to last month. Major Burst events are being detected 45 seconds faster on average."
                                </p>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            <div className="fixed bottom-3 right-3 sm:bottom-6 sm:right-6 z-50">
                {!chatOpen ? (
                    <button
                        onClick={() => setChatOpen(true)}
                        className="h-14 w-14 rounded-full bg-cyan-600 hover:bg-cyan-500 text-white shadow-xl border border-cyan-400/40 flex items-center justify-center"
                        title="Open chatbot"
                    >
                        <Bot size={22} />
                    </button>
                ) : (
                    <div className="w-[calc(100vw-1.5rem)] sm:w-[340px] h-[70vh] sm:h-[460px] rounded-2xl border border-white/10 bg-slate-950/95 shadow-2xl flex flex-col overflow-hidden max-w-[340px]">
                        <div className="px-4 py-3 border-b border-white/10 flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                <Bot size={16} className="text-cyan-400" />
                                <p className="text-sm font-bold text-white">Ops Chatbot</p>
                            </div>
                            <button
                                onClick={() => setChatOpen(false)}
                                className="text-xs text-slate-400 hover:text-white"
                            >
                                Close
                            </button>
                        </div>

                        <div className="flex-1 overflow-y-auto p-3 space-y-3">
                            {chatMessages.map((m, i) => (
                                <div key={i} className={`max-w-[90%] rounded-xl px-3 py-2 text-xs leading-relaxed ${m.role === 'user' ? 'ml-auto bg-cyan-600/20 border border-cyan-500/30 text-cyan-100' : 'bg-slate-800/80 border border-white/10 text-slate-200'}`}>
                                    {m.text}
                                    {m.role === 'bot' && Array.isArray(m.suggestions) && m.suggestions.length > 0 ? (
                                        <div className="mt-2 flex flex-wrap gap-1">
                                            {m.suggestions.map((s, idx) => (
                                                <button
                                                    key={`${s}-${idx}`}
                                                    onClick={() => sendChatMessage(s)}
                                                    className="text-[10px] px-2 py-1 rounded-md bg-white/5 border border-white/10 hover:bg-white/10 text-slate-300"
                                                >
                                                    {s}
                                                </button>
                                            ))}
                                        </div>
                                    ) : null}
                                </div>
                            ))}
                            {chatLoading ? (
                                <p className="text-[11px] text-slate-500">Assistant is typing...</p>
                            ) : null}
                        </div>

                        <div className="p-3 border-t border-white/10 flex gap-2">
                            <input
                                value={chatInput}
                                onChange={(e) => setChatInput(e.target.value)}
                                onKeyDown={(e) => {
                                    if (e.key === 'Enter') sendChatMessage();
                                }}
                                placeholder="Ask about leaks, water safety..."
                                className="flex-1 bg-slate-900 border border-white/10 rounded-lg px-3 py-2 text-xs text-slate-200 placeholder:text-slate-500 outline-none focus:border-cyan-500/60"
                            />
                            <button
                                onClick={() => sendChatMessage()}
                                disabled={chatLoading}
                                className="w-10 h-10 rounded-lg bg-cyan-600 hover:bg-cyan-500 disabled:bg-slate-700 text-white flex items-center justify-center"
                            >
                                <Send size={14} />
                            </button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default Dashboard;
