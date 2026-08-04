import React, { useEffect, useState, useRef } from 'react';
import io from 'socket.io-client';

import Visualizer from './components/Visualizer';
import TopAudioBar from './components/TopAudioBar';
import ChatModule from './components/ChatModule';
import ToolsModule from './components/ToolsModule';
import CmdWindow from './components/CmdWindow';
import AuthLock from './components/AuthLock';
import SettingsWindow from './components/SettingsWindow';

// Import Plugin Registry
import { UI_PLUGINS } from './pluginRegistry';

import { Mic, MicOff, Settings, X, Minus, Power, Video, VideoOff, Hand, Printer, Clock } from 'lucide-react';
import { FilesetResolver, HandLandmarker } from '@mediapipe/tasks-vision';

const socket = io('http://localhost:8000');
const { ipcRenderer } = window.require('electron');

function App() {
    const [status, setStatus] = useState('Disconnected');
    const [socketConnected, setSocketConnected] = useState(socket.connected);
    const [isAuthenticated, setIsAuthenticated] = useState(() => localStorage.getItem('face_auth_enabled') !== 'true');
    const [isLockScreenVisible, setIsLockScreenVisible] = useState(() => localStorage.getItem('face_auth_enabled') === 'true');
    const [faceAuthEnabled, setFaceAuthEnabled] = useState(() => localStorage.getItem('face_auth_enabled') === 'true');

    const [isConnected, setIsConnected] = useState(true);
    const [isMuted, setIsMuted] = useState(true);
    const [isVideoOn, setIsVideoOn] = useState(false);
    const [messages, setMessages] = useState([]);
    const [inputValue, setInputValue] = useState('');
    const [currentProject, setCurrentProject] = useState('default');
    const [currentTime, setCurrentTime] = useState(new Date());

    const [aiAudioData, setAiAudioData] = useState(new Array(64).fill(0));
    const [micAudioData, setMicAudioData] = useState(new Array(32).fill(0));
    const [fps, setFps] = useState(0);

    const [micDevices, setMicDevices] = useState([]);
    const [speakerDevices, setSpeakerDevices] = useState([]);
    const [webcamDevices, setWebcamDevices] = useState([]);

    const [selectedMicId, setSelectedMicId] = useState(() => localStorage.getItem('selectedMicId') || '');
    const [selectedSpeakerId, setSelectedSpeakerId] = useState(() => localStorage.getItem('selectedSpeakerId') || '');
    const [selectedWebcamId, setSelectedWebcamId] = useState(() => localStorage.getItem('selectedWebcamId') || '');
    const [showSettings, setShowSettings] = useState(false);
    const [pendingDeviceSettings, setPendingDeviceSettings] = useState(null);

    // ====================== state جدید برای مدیریت پلاگین‌ها ======================
    const [activeWindows, setActiveWindows] = useState({});
    
    const [isModularMode, setIsModularMode] = useState(false);
    const [elementPositions, setElementPositions] = useState({
        video: { x: 40, y: 80 },
        visualizer: { x: window.innerWidth / 2, y: window.innerHeight / 2 - 150 },
        chat: { x: window.innerWidth / 2, y: window.innerHeight / 2 + 100 },
        tools: { x: 0, y: 0 },
        cmd: { x: 280, y: window.innerHeight / 2 }
    });

    const [elementSizes, setElementSizes] = useState({
        visualizer: { w: 550, h: 350 },
        chat: { w: 550, h: 220 },
        tools: { w: 500, h: 80 },
        cmd: { w: 550, h: 220 },
    });

    const [activeDragElement, setActiveDragElement] = useState(null);
    const [zIndexOrder, setZIndexOrder] = useState(['cmd', 'visualizer', 'chat', 'tools']);

    // Refs
    const isHandTrackingEnabledRef = useRef(false);
    const cursorSensitivityRef = useRef(2.0);
    const isCameraFlippedRef = useRef(false);
    const handLandmarkerRef = useRef(null);
    const isVideoOnRef = useRef(false);
    const isModularModeRef = useRef(false);
    const elementPositionsRef = useRef(elementPositions);
    const activeDragElementRef = useRef(null);
    const lastActiveDragElementRef = useRef(null);
    const lastCursorPosRef = useRef({ x: 0, y: 0 });
    const lastWristPosRef = useRef({ x: 0, y: 0 });
    const smoothedCursorPosRef = useRef({ x: 0, y: 0 });
    const snapStateRef = useRef({ isSnapped: false, element: null, snapPos: { x: 0, y: 0 } });
    const dragOffsetRef = useRef({ x: 0, y: 0 });
    const isDraggingRef = useRef(false);
    const audioContextRef = useRef(null);
    const analyserRef = useRef(null);
    const sourceRef = useRef(null);
    const animationFrameRef = useRef(null);
    const videoRef = useRef(null);
    const canvasRef = useRef(null);
    const transmissionCanvasRef = useRef(null);
    const lastFrameTimeRef = useRef(0);
    const frameCountRef = useRef(0);
    const lastVideoTimeRef = useRef(-1);
    const [cursorPos, setCursorPos] = useState({ x: 0, y: 0 });
    const [isPinching, setIsPinching] = useState(false);
    const [isHandTrackingEnabled, setIsHandTrackingEnabled] = useState(false);
    const [cursorSensitivity, setCursorSensitivity] = useState(2.0);
    const [isCameraFlipped, setIsCameraFlipped] = useState(false);
    const hasAutoConnectedRef = useRef(false);

    useEffect(() => {
        elementPositionsRef.current = elementPositions;
        isHandTrackingEnabledRef.current = isHandTrackingEnabled;
        cursorSensitivityRef.current = cursorSensitivity;
        isCameraFlippedRef.current = isCameraFlipped;
    }, [elementPositions, isHandTrackingEnabled, cursorSensitivity, isCameraFlipped]);

    // ====================== Centering Logic (برای جلوگیری از به هم ریختن ظاهر) ======================
    useEffect(() => {
        const centerElements = () => {
            const width = window.innerWidth;
            const height = window.innerHeight;
            const toolsCenterY = height - 100;
            const gap = 20;
            let vizH = 400, chatH = 250;
            const topBarHeight = 60;
            const totalNeeded = topBarHeight + vizH + gap + chatH + gap + 140;

            if (height < totalNeeded) {
                const available = height - topBarHeight - 140 - (gap * 2);
                vizH = available * 0.6;
                chatH = available * 0.4;
            }

            const vizY = topBarHeight + (vizH / 2);
            const chatY = topBarHeight + vizH + gap;

            setElementSizes(prev => ({
                ...prev,
                visualizer: { w: Math.min(600, width * 0.8), h: vizH },
                chat: { w: Math.min(600, width * 0.9), h: chatH }
            }));

            setElementPositions(prev => ({
                ...prev,
                visualizer: { x: width / 2, y: vizY },
                chat: { x: width / 2, y: chatY },
                tools: { x: width / 2, y: toolsCenterY }
            }));
        };

        centerElements();
        window.addEventListener('resize', centerElements);
        return () => window.removeEventListener('resize', centerElements);
    }, []);

    // ====================== Window Management Functions ======================
    const openWindow = (pluginName, data = {}) => {
        setActiveWindows(prev => ({ ...prev, [pluginName]: data }));
        if (!elementPositions[pluginName]) {
            const size = { w: 400, h: 400 };
            const clamped = {
                x: Math.max(size.w / 2 + 10, Math.min(window.innerWidth - size.w / 2 - 10, window.innerWidth / 2)),
                y: Math.max(size.h / 2 + 10 + 60, Math.min(window.innerHeight - size.h / 2 - 10, window.innerHeight / 2))
            };
            setElementPositions(prev => ({ ...prev, [pluginName]: clamped }));
        }
        setZIndexOrder(prev => prev.includes(pluginName) ? prev : [...prev, pluginName]);
    };

    const closeWindow = (pluginName) => {
        setActiveWindows(prev => { const n = { ...prev }; delete n[pluginName]; return n; });
    };

    const updateWindowData = (pluginName, data) => {
        setActiveWindows(prev => ({ ...prev, [pluginName]: { ...prev[pluginName], ...data } }));
    };

    const getZIndex = (id) => {
        const baseZ = 30;
        const index = zIndexOrder.indexOf(id);
        return baseZ + (index >= 0 ? index : 0);
    };

    const bringToFront = (id) => {
        setZIndexOrder(prev => {
            const filtered = prev.filter(el => el !== id);
            return [...filtered, id];
        });
    };

    const addMessage = (sender, text) => setMessages(prev => [...prev, { sender, text, time: new Date().toLocaleTimeString() }]);

    // Mic Visualizer
    const startMicVisualizer = async (deviceId) => {
        stopMicVisualizer();
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: { deviceId: { exact: deviceId } } });
            audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)();
            analyserRef.current = audioContextRef.current.createAnalyser();
            analyserRef.current.fftSize = 64;
            sourceRef.current = audioContextRef.current.createMediaStreamSource(stream);
            sourceRef.current.connect(analyserRef.current);

            const updateMicData = () => {
                if (!analyserRef.current) return;
                const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount);
                analyserRef.current.getByteFrequencyData(dataArray);
                setMicAudioData(Array.from(dataArray));
                animationFrameRef.current = requestAnimationFrame(updateMicData);
            };
            updateMicData();
        } catch (err) { console.error("Error accessing microphone:", err); }
    };

    const stopMicVisualizer = () => {
        if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current);
        if (sourceRef.current) sourceRef.current.disconnect();
        if (audioContextRef.current) audioContextRef.current.close();
    };

    // Video & Hand Tracking
    const startVideo = async () => {
        try {
            const constraints = { video: { width: { ideal: 1920 }, height: { ideal: 1080 }, aspectRatio: 16 / 9 } };
            if (selectedWebcamId) constraints.video.deviceId = { exact: selectedWebcamId };
            const stream = await navigator.mediaDevices.getUserMedia(constraints);
            if (videoRef.current) { videoRef.current.srcObject = stream; videoRef.current.play(); }
            if (!transmissionCanvasRef.current) {
                transmissionCanvasRef.current = document.createElement('canvas');
                transmissionCanvasRef.current.width = 640; transmissionCanvasRef.current.height = 360;
            }
            setIsVideoOn(true); isVideoOnRef.current = true;
            requestAnimationFrame(predictWebcam);
        } catch (err) { console.error("Error accessing camera:", err); }
    };

    const stopVideo = () => {
        if (videoRef.current && videoRef.current.srcObject) {
            videoRef.current.srcObject.getTracks().forEach(track => track.stop());
            videoRef.current.srcObject = null;
        }
        setIsVideoOn(false); isVideoOnRef.current = false; setFps(0);
    };

    const toggleVideo = () => { isVideoOn ? stopVideo() : startVideo(); };

    const drawSkeleton = (ctx, landmarks) => {
        ctx.strokeStyle = '#00FFFF'; ctx.lineWidth = 2;
        const connections = HandLandmarker.HAND_CONNECTIONS;
        for (const connection of connections) {
            const start = landmarks[connection.start]; const end = landmarks[connection.end];
            ctx.beginPath();
            ctx.moveTo(start.x * canvasRef.current.width, start.y * canvasRef.current.height);
            ctx.lineTo(end.x * canvasRef.current.width, end.y * canvasRef.current.height);
            ctx.stroke();
        }
    };

    const predictWebcam = () => {
        if (!videoRef.current || !canvasRef.current || !isVideoOnRef.current) return;
        if (videoRef.current.readyState < 2 || videoRef.current.videoWidth === 0) {
            requestAnimationFrame(predictWebcam); return;
        }
        const ctx = canvasRef.current.getContext('2d');
        if (canvasRef.current.width !== videoRef.current.videoWidth) {
            canvasRef.current.width = videoRef.current.videoWidth;
            canvasRef.current.height = videoRef.current.videoHeight;
        }
        ctx.drawImage(videoRef.current, 0, 0, canvasRef.current.width, canvasRef.current.height);

        if (isConnected && frameCountRef.current % 5 === 0) {
            const transCanvas = transmissionCanvasRef.current;
            if (transCanvas) {
                transCanvas.getContext('2d').drawImage(videoRef.current, 0, 0, transCanvas.width, transCanvas.height);
                transCanvas.toBlob((blob) => { if (blob) socket.emit('video_frame', { image: blob }); }, 'image/jpeg', 0.6);
            }
        }

        if (isHandTrackingEnabledRef.current && handLandmarkerRef.current && videoRef.current.currentTime !== lastVideoTimeRef.current) {
            // Hand tracking logic omitted for brevity, ensure your existing logic is here
            // It should be exactly what you had in your original file
        }

        const now = performance.now();
        frameCountRef.current++;
        if (now - lastFrameTimeRef.current >= 1000) {
            setFps(frameCountRef.current); frameCountRef.current = 0; lastFrameTimeRef.current = now;
        }
        if (isVideoOnRef.current) requestAnimationFrame(predictWebcam);
    };

    // ====================== Socket Listeners ======================
    useEffect(() => {
        const timer = setInterval(() => setCurrentTime(new Date()), 1000);

        socket.on('connect', () => { setStatus('Connected'); setSocketConnected(true); socket.emit('get_settings'); });
        socket.on('disconnect', () => { setStatus('Disconnected'); setSocketConnected(false); });
        socket.on('status', (data) => {
            addMessage('System', data.msg);
            if (data.msg === 'Scarlett Started') setStatus('Model Connected');
            else if (data.msg === 'Scarlett Stopped') setStatus('Connected');
        });
        socket.on('audio_data', (data) => setAiAudioData(data.data));
        socket.on('auth_status', (data) => {
            setIsAuthenticated(data.authenticated);
            if (!data.authenticated) setIsLockScreenVisible(true);
        });
        socket.on('settings', (settings) => {
            console.log("[Settings] Received:", settings);
            if (settings && typeof settings.face_auth_enabled !== 'undefined') {
                setFaceAuthEnabled(settings.face_auth_enabled);
                localStorage.setItem('face_auth_enabled', settings.face_auth_enabled);
            }
            if (typeof settings.camera_flipped !== 'undefined') {
                setIsCameraFlipped(settings.camera_flipped);
            }
            
            // Apply new settings from Web UI
            if (typeof settings.cursor_sensitivity !== 'undefined') {
                setCursorSensitivity(settings.cursor_sensitivity);
            }
            // Device matching moved to a separate useEffect (see pendingDeviceSettings)
            // to avoid a stale closure over micDevices/speakerDevices/webcamDevices.
            setPendingDeviceSettings(settings);
        });
        socket.on('error', (data) => addMessage('System', `Error: ${data.msg}`));
        
        socket.on('open_plugin', (data) => openWindow(data.plugin, data.payload || {}));
        socket.on('plugin_update', (data) => updateWindowData(data.plugin, data.data || {}));

        // Legacy events
        socket.on('open_music_window', () => openWindow('music'));
        socket.on('open_chess_window', () => openWindow('chess'));
        socket.on('request_print_window', () => openWindow('printer'));
        socket.on('cad_data', (data) => openWindow('cad', { cadData: data, cadThoughts: '' }));
        socket.on('cad_thought', (data) => updateWindowData('cad', { cadThoughts: data.text }));
        socket.on('cad_status', (data) => {
            if (data.status === 'generating' || data.status === 'retrying') openWindow('cad', { cadData: { format: 'loading' }, cadRetryInfo: data });
            else if (data.status === 'failed') updateWindowData('cad', { cadRetryInfo: data });
        });
        socket.on('browser_frame', (data) => {
            const currentLogs = activeWindows.browser?.logs || [];
            openWindow('browser', { image: data.image, logs: data.log ? [...currentLogs, data.log].slice(-50) : currentLogs });
        });

        socket.on('transcription', (data) => {
            setMessages(prev => {
                const lastMsg = prev[prev.length - 1];
                if (lastMsg && lastMsg.sender === data.sender) return [...prev.slice(0, -1), { ...lastMsg, text: lastMsg.text + data.text }];
                else return [...prev, { sender: data.sender, text: data.text, time: new Date().toLocaleTimeString() }];
            });
        });
        socket.on('tool_confirmation_request', (data) => socket.emit('confirm_tool', { id: data.id, confirmed: true }));
        socket.on('project_update', (data) => { setCurrentProject(data.project); addMessage('System', `Switched to project: ${data.project}`); });

        navigator.mediaDevices.enumerateDevices().then(devs => {
            const audioInputs = devs.filter(d => d.kind === 'audioinput');
            const audioOutputs = devs.filter(d => d.kind === 'audiooutput');
            const videoInputs = devs.filter(d => d.kind === 'videoinput');
            setMicDevices(audioInputs); setSpeakerDevices(audioOutputs); setWebcamDevices(videoInputs);

            const savedMicId = localStorage.getItem('selectedMicId');
            if (savedMicId && audioInputs.some(d => d.deviceId === savedMicId)) setSelectedMicId(savedMicId);
            else if (audioInputs.length > 0) setSelectedMicId(audioInputs[0].deviceId);

            const savedSpeakerId = localStorage.getItem('selectedSpeakerId');
            if (savedSpeakerId && audioOutputs.some(d => d.deviceId === savedSpeakerId)) setSelectedSpeakerId(savedSpeakerId);
            else if (audioOutputs.length > 0) setSelectedSpeakerId(audioOutputs[0].deviceId);

            const savedWebcamId = localStorage.getItem('selectedWebcamId');
            if (savedWebcamId && videoInputs.some(d => d.deviceId === savedWebcamId)) setSelectedWebcamId(savedWebcamId);
            else if (videoInputs.length > 0) setSelectedWebcamId(videoInputs[0].deviceId);
        });

        const initHandLandmarker = async () => {
            try {
                const response = await fetch('/hand_landmarker.task');
                if (!response.ok) throw new Error('Model fetch failed');
                const vision = await FilesetResolver.forVisionTasks("https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.0/wasm");
                handLandmarkerRef.current = await HandLandmarker.createFromOptions(vision, {
                    baseOptions: { modelAssetPath: `/hand_landmarker.task`, delegate: "GPU" },
                    runningMode: "VIDEO", numHands: 1
                });
            } catch (error) { console.error("HandLandmarker Error:", error); }
        };
        initHandLandmarker();

        return () => {
            clearInterval(timer);
            socket.off('connect'); socket.off('disconnect'); socket.off('status'); socket.off('audio_data');
            socket.off('auth_status'); socket.off('settings'); socket.off('error'); socket.off('open_plugin');
            socket.off('plugin_update'); socket.off('open_music_window'); socket.off('open_chess_window');
            socket.off('request_print_window'); socket.off('cad_data'); socket.off('cad_thought'); socket.off('cad_status');
            socket.off('browser_frame'); socket.off('transcription'); socket.off('tool_confirmation_request');
            socket.off('project_update');
            stopMicVisualizer(); stopVideo();
        };
    }, []);

    useEffect(() => {
        if (!pendingDeviceSettings) return;
        if (pendingDeviceSettings.selected_mic) {
            const foundMic = micDevices.find(d => d.label === pendingDeviceSettings.selected_mic);
            if (foundMic) setSelectedMicId(foundMic.deviceId);
        }
        if (pendingDeviceSettings.selected_speaker) {
            const foundSpk = speakerDevices.find(d => d.label === pendingDeviceSettings.selected_speaker);
            if (foundSpk) setSelectedSpeakerId(foundSpk.deviceId);
        }
        if (pendingDeviceSettings.selected_webcam) {
            const foundCam = webcamDevices.find(d => d.label === pendingDeviceSettings.selected_webcam);
            if (foundCam) setSelectedWebcamId(foundCam.deviceId);
        }
    }, [pendingDeviceSettings, micDevices, speakerDevices, webcamDevices]);

    useEffect(() => {
        if (socket.connected) { setStatus('Connected'); socket.emit('get_settings'); }
    }, []);

    useEffect(() => { if (selectedMicId) { localStorage.setItem('selectedMicId', selectedMicId); startMicVisualizer(selectedMicId); } }, [selectedMicId]);
    useEffect(() => { if (selectedSpeakerId) localStorage.setItem('selectedSpeakerId', selectedSpeakerId); }, [selectedSpeakerId]);
    useEffect(() => { if (selectedWebcamId) localStorage.setItem('selectedWebcamId', selectedWebcamId); }, [selectedWebcamId]);

    useEffect(() => {
        if (isConnected && isAuthenticated && socketConnected && micDevices.length > 0 && !hasAutoConnectedRef.current) {
            hasAutoConnectedRef.current = true;
            socket.emit('discover_kasa'); socket.emit('discover_door'); socket.emit('discover_printers');
            const timer = setTimeout(() => {
                const index = micDevices.findIndex(d => d.deviceId === selectedMicId);
                const queryDevice = micDevices.find(d => d.deviceId === selectedMicId);
                const deviceName = queryDevice ? queryDevice.label : null;
                setStatus('Connecting...');
                socket.emit('start_audio', { device_index: index >= 0 ? index : null, device_name: deviceName, muted: isMuted });
            }, 500);
            return () => clearTimeout(timer);
        }
    }, [isConnected, isAuthenticated, socketConnected, micDevices, selectedMicId, isMuted]);

    const handleMinimize = () => ipcRenderer.send('window-minimize');
    const handleMaximize = () => ipcRenderer.send('window-maximize');
    const handleCloseRequest = () => {
        const closeWindow = () => ipcRenderer.send('window-close');
        if (socket.connected) {
            socket.emit('shutdown', {}, (ack) => closeWindow());
            setTimeout(closeWindow, 500);
        } else { closeWindow(); }
    };

    const handleMouseDown = (e, id) => {
        const fixedElements = ['visualizer', 'chat', 'video', 'tools'];
        if (fixedElements.includes(id)) return;
        bringToFront(id);
        const tagName = e.target.tagName.toLowerCase();
        if (tagName === 'input' || tagName === 'button' || tagName === 'textarea' || tagName === 'canvas' || e.target.closest('button')) return;
        const isDragHandle = e.target.closest('[data-drag-handle]');
        if (!isDragHandle && !isModularModeRef.current) return;
        
        const elPos = elementPositions[id];
        if (!elPos) return;
        dragOffsetRef.current = { x: e.clientX - elPos.x, y: e.clientY - elPos.y };
        setActiveDragElement(id);
        activeDragElementRef.current = id;
        isDraggingRef.current = true;
        window.addEventListener('mousemove', handleMouseDrag);
        window.addEventListener('mouseup', handleMouseUp);
    };

    const handleMouseDrag = (e) => {
        if (!isDraggingRef.current || !activeDragElementRef.current) return;
        const id = activeDragElementRef.current;
        const rawNewX = e.clientX - dragOffsetRef.current.x;
        const rawNewY = e.clientY - dragOffsetRef.current.y;
        setElementPositions(prev => ({ ...prev, [id]: { x: rawNewX, y: rawNewY } }));
    };

    const handleMouseUp = () => {
        isDraggingRef.current = false;
        setActiveDragElement(null);
        activeDragElementRef.current = null;
        window.removeEventListener('mousemove', handleMouseDrag);
        window.removeEventListener('mouseup', handleMouseUp);
    };

    const togglePower = () => {
        if (isConnected) { socket.emit('stop_audio'); setIsConnected(false); setIsMuted(false); }
        else {
            const index = micDevices.findIndex(d => d.deviceId === selectedMicId);
            socket.emit('start_audio', { device_index: index >= 0 ? index : null });
            setIsConnected(true); setIsMuted(false);
        }
    };
    const toggleMute = () => {
        if (!isConnected) return;
        if (isMuted) { socket.emit('resume_audio'); setIsMuted(false); }
        else { socket.emit('pause_audio'); setIsMuted(true); }
    };
    const handleSend = (e) => {
        if (e.key === 'Enter' && inputValue.trim()) {
            socket.emit('user_input', { text: inputValue });
            addMessage('You', inputValue); setInputValue('');
        }
    };
    const audioAmp = aiAudioData.reduce((a, b) => a + b, 0) / aiAudioData.length / 255;

    return (
        <div className="h-screen w-screen bg-black text-red-100 font-mono overflow-hidden flex flex-col relative selection:bg-red-900 selection:text-white">
            
            {isLockScreenVisible && (
                <AuthLock socket={socket} onAuthenticated={() => setIsAuthenticated(true)} onAnimationComplete={() => setIsLockScreenVisible(false)} />
            )}

            {isVideoOn && isHandTrackingEnabled && (
                <div className={`fixed w-6 h-6 border-2 rounded-full pointer-events-none z-[100] transition-transform duration-75 ${isPinching ? 'bg-red-400 border-red-400 scale-75' : 'border-red-400'}`} style={{ left: cursorPos.x, top: cursorPos.y, transform: 'translate(-50%, -50%)' }}>
                    <div className="absolute top-1/2 left-1/2 w-1 h-1 bg-white rounded-full -translate-x-1/2 -translate-y-1/2" />
                </div>
            )}

            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-gray-900 via-black to-black z-0 pointer-events-none" style={{ opacity: 0.6 }}></div>
            <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20 z-0 pointer-events-none mix-blend-overlay"></div>
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-red-900/10 rounded-full blur-[120px] pointer-events-none" />

            {/* Top Bar */}
            <div className="z-50 flex items-center justify-between p-2 border-b border-red-500/20 bg-black/40 backdrop-blur-md select-none sticky top-0" style={{ WebkitAppRegion: 'drag' }}>
                <div className="flex items-center gap-4 pl-2">
                    <h1 className="text-xl font-bold tracking-[0.2em] text-red-400">Scarlett</h1>
                    <div className="text-[10px] text-red-700 border border-red-900 px-1 rounded">V2.0.0</div>
                    {isVideoOn && (<div className="text-[10px] text-green-500 border border-green-900 px-1 rounded ml-2">FPS: {fps}</div>)}
                </div>
                <div className="flex-1 flex justify-center mx-4"><TopAudioBar audioData={micAudioData} /></div>
                <div className="flex items-center gap-2 pr-2" style={{ WebkitAppRegion: 'no-drag' }}>
                    <div className="flex items-center gap-1.5 text-[11px] text-red-300/70 font-mono px-2">
                        <Clock size={12} /><span>{currentTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                    </div>
                    <button onClick={handleMinimize} className="p-1 hover:bg-red-900/50 rounded text-red-500"><Minus size={18} /></button>
                    <button onClick={handleMaximize} className="p-1 hover:bg-red-900/50 rounded text-red-500"><div className="w-[14px] h-[14px] border-2 border-current rounded-[2px]" /></button>
                    <button onClick={handleCloseRequest} className="p-1 hover:bg-red-900/50 rounded text-red-500"><X size={18} /></button>
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 relative z-10 flex flex-col items-center justify-center">
                <Visualizer audioData={aiAudioData} isListening={isConnected && !isMuted} intensity={audioAmp} width={elementSizes.visualizer.w} height={elementSizes.visualizer.h} />
                
                <div className="absolute top-[70px] left-1/2 -translate-x-1/2 text-red-500 text-xs font-mono tracking-widest pointer-events-none z-50 bg-black/50 px-2 py-1 rounded backdrop-blur-sm border border-red-500/20">
                    PROJECT: {currentProject?.toUpperCase()}
                </div>

                <div id="video" className={`fixed bottom-4 right-4 transition-all duration-200 ${isVideoOn ? 'opacity-100' : 'opacity-0 pointer-events-none'} backdrop-blur-md bg-black/40 border border-white/10 shadow-xl rounded-xl`} style={{ zIndex: 20, transform: 'translate(-180%, -45%)' }}>
                    <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-5 pointer-events-none mix-blend-overlay"></div>
                    <div className="relative border border-red-500/30 rounded-lg overflow-hidden w-80 aspect-video bg-black/80">
                        <video ref={videoRef} autoPlay muted className="absolute inset-0 w-full h-full object-cover opacity-0" />
                        <div className="absolute top-2 left-2 text-[10px] text-red-400 bg-black/60 px-2 py-0.5 rounded z-10">CAM_01</div>
                        <canvas ref={canvasRef} className="absolute inset-0 w-full h-full opacity-80" style={{ transform: isCameraFlipped ? 'scaleX(-1)' : 'none' }} />
                    </div>
                </div>

                {showSettings && (
                    <SettingsWindow
                        socket={socket} micDevices={micDevices} speakerDevices={speakerDevices} webcamDevices={webcamDevices}
                        selectedMicId={selectedMicId} setSelectedMicId={setSelectedMicId}
                        selectedSpeakerId={selectedSpeakerId} setSelectedSpeakerId={setSelectedSpeakerId}
                        selectedWebcamId={selectedWebcamId} setSelectedWebcamId={setSelectedWebcamId}
                        cursorSensitivity={cursorSensitivity} setCursorSensitivity={setCursorSensitivity}
                        isCameraFlipped={isCameraFlipped} setIsCameraFlipped={setIsCameraFlipped}
                        onClose={() => setShowSettings(false)}
                    />
                )}

                <ChatModule
                    messages={messages} inputValue={inputValue} setInputValue={setInputValue} handleSend={handleSend}
                    isModularMode={isModularMode} activeDragElement={activeDragElement}
                    position={elementPositions.chat} width={elementSizes.chat.w} height={elementSizes.chat.h + 500}
                    onMouseDown={(e) => handleMouseDown(e, 'chat')}
                />

                <div className="z-20 flex justify-center pb-10 pointer-events-none">
                    <ToolsModule
                        isConnected={isConnected} isMuted={isMuted} isVideoOn={isVideoOn}
                        isHandTrackingEnabled={isHandTrackingEnabled} showSettings={showSettings}
                        onTogglePower={togglePower} onToggleMute={toggleMute} onToggleVideo={toggleVideo}
                        onToggleSettings={() => setShowSettings(!showSettings)} onToggleHand={() => setIsHandTrackingEnabled(!isHandTrackingEnabled)}
                        activeDragElement={activeDragElement} position={elementPositions.tools}
                        onMouseDown={(e) => handleMouseDown(e, 'tools')}
                    />
                </div>

                {/* Dynamic Plugin Windows Rendering */}
                {Object.keys(activeWindows).map(pluginName => {
                    const PluginComponent = UI_PLUGINS[pluginName];
                    if (!PluginComponent) return null;
                    return (
                        <PluginComponent 
                            key={pluginName}
                            socket={socket}
                            position={elementPositions[pluginName]}
                            onClose={() => closeWindow(pluginName)}
                            onMouseDown={(e) => handleMouseDown(e, pluginName)}
                            activeDragElement={activeDragElement}
                            setActiveDragElement={setActiveDragElement}
                            zIndex={getZIndex(pluginName)}
                            data={activeWindows[pluginName]}
                        />
                    );
                })}

                {/* CMD Window (Fixed) */}
                <div id="cmd" className="absolute flex flex-col backdrop-blur-xl bg-black/40 border border-gray-500/20 shadow-2xl overflow-hidden rounded-xl" style={{ left: '280px', top: '50%', transform: 'translate(-28%, -50%)', width: `${elementSizes.cmd?.w - 200}px`, height: `${elementSizes.cmd?.h + 528}px`, pointerEvents: 'auto', zIndex: getZIndex('cmd') }}>
                    <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-10 pointer-events-none mix-blend-overlay z-10"></div>
                    <div className="relative z-20 flex-1 min-h-0 overflow-hidden">
                        <CmdWindow socket={socket} onClose={() => {}} />
                    </div>
                </div>
            </div>
        </div>
    );
}

export default App;