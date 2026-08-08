import React, { useState, useEffect } from 'react';
import { X, RefreshCw, Power, Sun, Palette, Lightbulb } from 'lucide-react';

const KasaWindow = ({
    socket,
    position,
    onClose,
    activeDragElement,
    onMouseDown,
    zIndex = 40,
    data = {}
}) => {
    // Extract plugin-specific data from the data prop
    const devices = data.devices || [];

    const [isThinking, setIsThinking] = useState(false);
    const [loadingDevices, setLoadingDevices] = useState({}); // { ip: true/false }

    useEffect(() => {
        if (!socket) return;

        // Listen for individual updates to clear loading state
        const onUpdate = (updateData) => {
            if (updateData && updateData.ip) {
                setLoadingDevices(prev => {
                    const next = { ...prev };
                    delete next[updateData.ip];
                    return next;
                });
            }
        };

        socket.on('kasa_update', onUpdate);
        return () => socket.off('kasa_update', onUpdate);
    }, [socket]);

    useEffect(() => {
        if (devices && devices.length > 0) {
            setIsThinking(false);
        }
    }, [devices]);

    const handleDiscover = () => {
        setIsThinking(true);
        socket.emit('discover_kasa');
        // Reset thinking after 10s if no response (safety)
        setTimeout(() => setIsThinking(false), 10000);
    };

    const handleToggle = (ip, currentState) => {
        setLoadingDevices(prev => ({ ...prev, [ip]: true }));
        socket.emit('control_kasa', {
            ip: ip,
            action: currentState ? 'off' : 'on'
        });
    };

    const handleBrightness = (ip, val) => {
        socket.emit('control_kasa', {
            ip: ip,
            action: 'brightness',
            value: parseInt(val)
        });
    };

    const handleColor = (ip, hue) => {
        socket.emit('control_kasa', {
            ip: ip,
            action: 'color',
            value: { h: parseInt(hue), s: 100, v: 100 }
        });
    };

    return (
        <div
            id="kasa"
            className={`absolute flex flex-col transition-all duration-200 
                backdrop-blur-xl bg-black/40 border border-white/10 shadow-2xl overflow-hidden rounded-2xl select-none
                ${activeDragElement === "kasa" ? "ring-2 ring-green-500 bg-green-500/10" : ""}
            `}
            style={{
                left: position?.x || window.innerWidth / 2,
                top: position?.y || window.innerHeight / 2,
                transform: "translate(-50%, -50%)",
                width: 320,
                minHeight: 200,
                pointerEvents: 'auto',
                zIndex: zIndex
            }}
        >
            {/* Header Bar - Drag Handle */}
            <div
                data-drag-handle
                onMouseDown={(e) => onMouseDown && onMouseDown(e, 'kasa')}
                className="h-8 flex items-center justify-between px-3 border-b border-white/10 mb-2 cursor-grab active:cursor-grabbing shrink-0"
            >
                <span className="text-xs font-bold tracking-widest text-red-500/70 flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full ${devices.length > 0 ? 'bg-green-500 animate-pulse' : 'bg-gray-500'}`} />
                    SMART LIGHT CONTROL
                </span>
                <button
                    onClick={onClose}
                    className="text-gray-400 hover:text-red-400 hover:bg-red-500/20 p-1 rounded transition-colors"
                >
                    <X size={14} />
                </button>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto max-h-[400px] p-4 scrollbar-hide">
                {devices.length === 0 && !isThinking && (
                    <div className="flex flex-col items-center justify-center p-8 text-center opacity-50">
                        <p className="text-xs mb-4">No devices found. Ensure they are on the same network.</p>
                        <button
                            onClick={handleDiscover}
                            className="flex items-center gap-2 px-4 py-2 bg-red-900/30 border border-red-500/30 rounded-lg hover:bg-red-500/20 hover:border-red-500 transition-all text-xs font-mono text-red-300"
                        >
                            <RefreshCw size={14} /> DISCOVER LIGHTS
                        </button>
                    </div>
                )}

                {isThinking && (
                    <div className="flex flex-col items-center justify-center p-8 gap-3">
                        <div className="w-6 h-6 border-2 border-red-500 border-t-transparent rounded-full animate-spin" />
                        <span className="text-xs text-red-400 animate-pulse">Scanning Network...</span>
                    </div>
                )}

                {devices.map((dev) => (
                    <div key={dev.ip} className="mb-3 p-3 bg-white/5 rounded-lg border border-white/10 hover:border-red-500/30 transition-all">
                        <div className="flex items-center justify-between mb-2">
                            <div className="flex flex-col">
                                <span className="font-bold text-sm text-white">{dev.alias}</span>
                                <span className="text-[10px] text-white/40 font-mono">{dev.ip}</span>
                            </div>
                            <button
                                onClick={() => handleToggle(dev.ip, dev.is_on)}
                                disabled={loadingDevices[dev.ip]}
                                className={`p-2 rounded-full transition-all ${dev.is_on
                                    ? 'bg-green-500/20 text-green-400 shadow-[0_0_10px_rgba(34,197,94,0.3)]'
                                    : 'bg-white/5 text-gray-500 hover:text-white'}
                                    ${loadingDevices[dev.ip] ? 'opacity-50 cursor-not-allowed' : ''}
                                `}
                            >
                                {loadingDevices[dev.ip] ? (
                                    <div className="w-[18px] h-[18px] border-2 border-current border-t-transparent rounded-full animate-spin" />
                                ) : (
                                    <Power size={18} />
                                )}
                            </button>
                        </div>

                        {/* Brightness Control */}
                        {dev.has_brightness && dev.is_on && (
                            <div className="flex items-center gap-2 mt-2">
                                <Sun size={14} className="text-yellow-500/70" />
                                <input
                                    type="range"
                                    min="0"
                                    max="100"
                                    defaultValue={dev.brightness || 100}
                                    onChange={(e) => handleBrightness(dev.ip, e.target.value)}
                                    className="w-full h-1 bg-white/10 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-red-400"
                                />
                            </div>
                        )}

                        {/* Color Control */}
                        {dev.has_color && dev.is_on && (
                            <div className="flex items-center gap-2 mt-2">
                                <Palette size={14} className="text-purple-500/70" />
                                <input
                                    type="range"
                                    min="0"
                                    max="360"
                                    defaultValue={(dev.hsv && dev.hsv.h) || 0}
                                    onChange={(e) => handleColor(dev.ip, e.target.value)}
                                    className="w-full h-1 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-white"
                                    style={{
                                        background: 'linear-gradient(to right, red, yellow, lime, red, blue, magenta, red)'
                                    }}
                                />
                            </div>
                        )}
                    </div>
                ))}
            </div>

            {/* Bottom Discover (if devices exist) */}
            {devices.length > 0 && (
                <div className="p-2 border-t border-white/10 mt-2 flex justify-end">
                    <button
                        onClick={handleDiscover}
                        className="p-1 text-white/30 hover:text-red-400 transition-colors"
                        title="Rescan"
                    >
                        <RefreshCw size={14} />
                    </button>
                </div>
            )}
        </div>
    );
};

KasaWindow.pluginMeta = {
    label: "Smart Lights",
    icon: Lightbulb,
};

export default KasaWindow;