import React, { useState, useEffect } from 'react';
import { X, ExternalLink } from 'lucide-react';
import { PLUGIN_META, MAX_TOOLBAR_PLUGINS } from '../pluginRegistry';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';

const SettingsWindow = ({
    socket,
    micDevices,
    speakerDevices,
    webcamDevices,
    selectedMicId,
    setSelectedMicId,
    selectedSpeakerId,
    setSelectedSpeakerId,
    selectedWebcamId,
    setSelectedWebcamId,
    cursorSensitivity,
    setCursorSensitivity,
    isCameraFlipped,
    setIsCameraFlipped,
    handleFileUpload,
    toolbarPluginIds = [],
    setToolbarPluginIds,
    onClose
}) => {
    const [permissions, setPermissions] = useState({});
    const [faceAuthEnabled, setFaceAuthEnabled] = useState(false);
    const [tools, setTools] = useState([]);

    useEffect(() => {
        // Fetched fresh from the backend's live plugin registry, so any
        // installed plugin's tools show up automatically - nothing here
        // needs to be hardcoded or updated when a plugin is added/removed.
        fetch(`${BACKEND_URL}/api/tools/list`)
            .then(res => res.json())
            .then(setTools)
            .catch(err => console.error('Failed to load tools list:', err));
    }, []);

    const toggleToolbarPlugin = (id) => {
        if (!setToolbarPluginIds) return;
        const isSelected = toolbarPluginIds.includes(id);
        if (isSelected) {
            setToolbarPluginIds(toolbarPluginIds.filter(p => p !== id));
        } else if (toolbarPluginIds.length < MAX_TOOLBAR_PLUGINS) {
            setToolbarPluginIds([...toolbarPluginIds, id]);
        }
    };

    useEffect(() => {
        socket.emit('get_settings');

        const handleSettings = (settings) => {
            console.log("Received settings:", settings);
            if (settings) {
                if (settings.tool_permissions) setPermissions(settings.tool_permissions);
                if (typeof settings.face_auth_enabled !== 'undefined') {
                    setFaceAuthEnabled(settings.face_auth_enabled);
                    localStorage.setItem('face_auth_enabled', settings.face_auth_enabled);
                }
            }
        };

        socket.on('settings', handleSettings);

        return () => {
            socket.off('settings', handleSettings);
        };
    }, [socket]);

    const togglePermission = (toolId) => {
        const currentVal = permissions[toolId] !== false;
        const nextVal = !currentVal;
        socket.emit('update_settings', { tool_permissions: { [toolId]: nextVal } });
    };

    const toggleFaceAuth = () => {
        const newVal = !faceAuthEnabled;
        setFaceAuthEnabled(newVal);
        localStorage.setItem('face_auth_enabled', newVal);
        socket.emit('update_settings', { face_auth_enabled: newVal });
    };

    const toggleCameraFlip = () => {
        const newVal = !isCameraFlipped;
        setIsCameraFlipped(newVal);
        socket.emit('update_settings', { camera_flipped: newVal });
    };

    // Function to open the web dashboard in default browser
    const openFullSettings = () => {
        const { shell } = window.require('electron');
        shell.openExternal(`${BACKEND_URL}/full-settings`);
    };

    return (
        <div className="absolute top-20 right-10 bg-black/90 border border-red-500/50 p-4 rounded-lg z-50 w-80 backdrop-blur-xl shadow-[0_0_30px_rgba(6,182,212,0.2)]" style={{ transform: 'translate(0%, -10%) scale(0.85)'}}>
            <div className="flex justify-between items-center mb-4 border-b border-red-900/50 pb-2">
                <h2 className="text-red-400 font-bold text-sm uppercase tracking-wider">Settings</h2>
                <button onClick={onClose} className="text-red-600 hover:text-red-400">
                    <X size={16} />
                </button>
            </div>

            {/* Authentication Section */}
            <div className="mb-6">
                <h3 className="text-red-400 font-bold mb-3 text-xs uppercase tracking-wider opacity-80">Security</h3>
                <div className="flex items-center justify-between text-xs bg-gray-900/50 p-2 rounded border border-red-900/30">
                    <span className="text-red-100/80">Face Authentication</span>
                    <button
                        onClick={toggleFaceAuth}
                        className={`relative w-8 h-4 rounded-full transition-colors duration-200 ${faceAuthEnabled ? 'bg-red-500/80' : 'bg-gray-700'}`}
                    >
                        <div
                            className={`absolute top-0.5 left-0.5 w-3 h-3 bg-white rounded-full transition-transform duration-200 ${faceAuthEnabled ? 'translate-x-4' : 'translate-x-0'}`}
                        />
                    </button>
                </div>
            </div>

            {/* Microphone Section */}
            <div className="mb-4">
                <h3 className="text-red-400 font-bold mb-2 text-xs uppercase tracking-wider opacity-80">Microphone</h3>
                <select
                    value={selectedMicId}
                    onChange={(e) => setSelectedMicId(e.target.value)}
                    className="w-full bg-gray-900 border border-red-800 rounded p-2 text-xs text-red-100 focus:border-red-400 outline-none"
                >
                    {micDevices.map((device, i) => (
                        <option key={device.deviceId} value={device.deviceId}>
                            {device.label || `Microphone ${i + 1}`}
                        </option>
                    ))}
                </select>
            </div>

            {/* Speaker Section */}
            <div className="mb-4">
                <h3 className="text-red-400 font-bold mb-2 text-xs uppercase tracking-wider opacity-80">Speaker</h3>
                <select
                    value={selectedSpeakerId}
                    onChange={(e) => setSelectedSpeakerId(e.target.value)}
                    className="w-full bg-gray-900 border border-red-800 rounded p-2 text-xs text-red-100 focus:border-red-400 outline-none"
                >
                    {speakerDevices.map((device, i) => (
                        <option key={device.deviceId} value={device.deviceId}>
                            {device.label || `Speaker ${i + 1}`}
                        </option>
                    ))}
                </select>
            </div>

            {/* Webcam Section */}
            <div className="mb-6">
                <h3 className="text-red-400 font-bold mb-2 text-xs uppercase tracking-wider opacity-80">Webcam</h3>
                <select
                    value={selectedWebcamId}
                    onChange={(e) => setSelectedWebcamId(e.target.value)}
                    className="w-full bg-gray-900 border border-red-800 rounded p-2 text-xs text-red-100 focus:border-red-400 outline-none"
                >
                    {webcamDevices.map((device, i) => (
                        <option key={device.deviceId} value={device.deviceId}>
                            {device.label || `Camera ${i + 1}`}
                        </option>
                    ))}
                </select>
            </div>

            {/* Cursor Section */}
            <div className="mb-6">
                <div className="flex justify-between mb-2">
                    <h3 className="text-red-400 font-bold text-xs uppercase tracking-wider opacity-80">Cursor Sensitivity</h3>
                    <span className="text-xs text-red-500">{cursorSensitivity}x</span>
                </div>
                <input
                    type="range"
                    min="1.0"
                    max="5.0"
                    step="0.1"
                    value={cursorSensitivity}
                    onChange={(e) => setCursorSensitivity(parseFloat(e.target.value))}
                    className="w-full accent-red-400 cursor-pointer h-1 bg-gray-800 rounded-lg appearance-none"
                />
            </div>

            {/* Gesture Control Section */}
            <div className="mb-6">
                <h3 className="text-red-400 font-bold mb-3 text-xs uppercase tracking-wider opacity-80">Gesture Control</h3>
                <div className="flex items-center justify-between text-xs bg-gray-900/50 p-2 rounded border border-red-900/30">
                    <span className="text-red-100/80">Flip Camera Horizontal</span>
                    <button
                        onClick={toggleCameraFlip}
                        className={`relative w-8 h-4 rounded-full transition-colors duration-200 ${isCameraFlipped ? 'bg-red-500/80' : 'bg-gray-700'}`}
                    >
                        <div
                            className={`absolute top-0.5 left-0.5 w-3 h-3 bg-white rounded-full transition-transform duration-200 ${isCameraFlipped ? 'translate-x-4' : 'translate-x-0'}`}
                        />
                    </button>
                </div>
            </div>

            {/* Toolbar Shortcuts Section */}
            <div className="mb-6">
                <h3 className="text-red-400 font-bold mb-1 text-xs uppercase tracking-wider opacity-80">
                    Toolbar Shortcuts ({toolbarPluginIds.length}/{MAX_TOOLBAR_PLUGINS})
                </h3>
                <p className="text-[10px] text-gray-500 mb-2">
                    Pick up to {MAX_TOOLBAR_PLUGINS} plugins to pin in the toolbar. Unpinned plugins can still be opened by the AI, just not from a toolbar button.
                </p>
                <div className="flex flex-col gap-1.5 max-h-48 overflow-y-auto pr-1">
                    {PLUGIN_META.map(({ id, label, icon: Icon }) => {
                        const isSelected = toolbarPluginIds.includes(id);
                        const isDisabled = !isSelected && toolbarPluginIds.length >= MAX_TOOLBAR_PLUGINS;
                        return (
                            <label
                                key={id}
                                className={`flex items-center justify-between text-xs bg-gray-900/50 p-2 rounded border border-red-900/30 ${isDisabled ? 'opacity-40' : 'cursor-pointer'}`}
                            >
                                <span className="flex items-center gap-2 text-red-100/80">
                                    {Icon && <Icon size={14} className="text-red-400 shrink-0" />}
                                    {label}
                                </span>
                                <input
                                    type="checkbox"
                                    checked={isSelected}
                                    disabled={isDisabled}
                                    onChange={() => toggleToolbarPlugin(id)}
                                    className="accent-red-500"
                                />
                            </label>
                        );
                    })}
                </div>
            </div>

            {/* Tool Permissions Section */}
            <div className="mb-6">
                <h3 className="text-red-400 font-bold mb-2 text-xs uppercase tracking-wider opacity-80">
                    Tool Permissions ({tools.length})
                </h3>
                <div className="flex flex-col gap-1.5 max-h-48 overflow-y-auto pr-1">
                    {tools.length === 0 && (
                        <p className="text-[10px] text-gray-500 italic">Loading tools...</p>
                    )}
                    {tools.map((tool) => {
                        const enabled = permissions[tool.name] !== false; // default: allowed
                        const label = tool.name
                            .split('_')
                            .map(w => w.charAt(0).toUpperCase() + w.slice(1))
                            .join(' ');
                        return (
                            <div
                                key={tool.name}
                                title={tool.description}
                                className="flex items-center justify-between text-xs bg-gray-900/50 p-2 rounded border border-red-900/30"
                            >
                                <span className="text-red-100/80 truncate pr-2">{label}</span>
                                <button
                                    onClick={() => togglePermission(tool.name)}
                                    className={`relative w-8 h-4 rounded-full transition-colors duration-200 shrink-0 ${enabled ? 'bg-red-500/80' : 'bg-gray-700'}`}
                                >
                                    <div
                                        className={`absolute top-0.5 left-0.5 w-3 h-3 bg-white rounded-full transition-transform duration-200 ${enabled ? 'translate-x-4' : 'translate-x-0'}`}
                                    />
                                </button>
                            </div>
                        );
                    })}
                </div>
            </div>

            {/* Memory Section */}
            <div className="mb-6">
                <h3 className="text-red-400 font-bold mb-2 text-xs uppercase tracking-wider opacity-80">Memory Data</h3>
                <div className="flex flex-col gap-2">
                    <label className="text-[10px] text-red-500/60 uppercase">Upload Memory For Chat</label>
                    <input
                        type="file"
                        accept=".txt"
                        onChange={handleFileUpload}
                        className="text-xs text-red-100 bg-gray-900 border border-red-800 rounded p-2 file:mr-2 file:py-1 file:px-2 file:rounded-full file:border-0 file:text-[10px] file:font-semibold file:bg-red-900 file:text-red-400 hover:file:bg-red-800 cursor-pointer"
                    />
                </div>
            </div>

            {/* Full Settings Web Dashboard Button */}
            <div className="pt-4 mt-2 border-t border-red-900/30">
                <button 
                    onClick={openFullSettings}
                    className="w-full flex items-center justify-center gap-2 bg-red-900/30 hover:bg-red-800/50 border border-red-500/40 text-red-300 font-bold py-2 text-xs rounded transition-all"
                >
                    <ExternalLink size={14} />
                    Open Full Settings in Browser
                </button>
                <p className="text-[10px] text-gray-500 text-center mt-2">
                    Opens the advanced configuration panel.
                </p>
            </div>
        </div>
    );
};

export default SettingsWindow;