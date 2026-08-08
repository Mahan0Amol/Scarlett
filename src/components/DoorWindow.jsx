import React, { useState, useEffect } from 'react';
import { X, RefreshCw, Lock, Unlock, DoorOpen } from 'lucide-react';

const DoorWindow = ({
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

        socket.on('door_update', onUpdate);
        return () => socket.off('door_update', onUpdate);
    }, [socket]);

    useEffect(() => {
        if (devices && devices.length > 0) {
            setIsThinking(false);
        }
    }, [devices]);

    const handleDiscover = () => {
        setIsThinking(true);
        socket.emit('discover_door');
        // Reset thinking after 10s if no response (safety)
        setTimeout(() => setIsThinking(false), 10000);
    };

    // A door only has two meaningful states: locked / unlocked.
    // (Previously this copied KasaWindow's on/off + brightness/color
    // controls, which don't make sense for a physical lock.)
    const handleToggleLock = (ip, isLocked) => {
        setLoadingDevices(prev => ({ ...prev, [ip]: true }));
        socket.emit('control_door', {
            ip: ip,
            action: isLocked ? 'unlock' : 'lock'
        });
    };

    return (
        <div
            id="door"
            className={`absolute flex flex-col transition-all duration-200 
                backdrop-blur-xl bg-black/40 border border-white/10 shadow-2xl overflow-hidden rounded-2xl select-none
                ${activeDragElement === "door" ? "ring-2 ring-green-500 bg-green-500/10" : ""}
            `}
            style={{
                left: position?.x || window.innerWidth / 2,
                top: position?.y || window.innerHeight / 2,
                transform: "translate(-50%, -50%)",
                width: 360,
                minHeight: 250,
                pointerEvents: 'auto',
                zIndex: zIndex
            }}
        >
            {/* Header Bar - Drag Handle */}
            <div
                data-drag-handle
                onMouseDown={(e) => onMouseDown && onMouseDown(e, 'door')}
                className="h-8 flex items-center justify-between px-3 border-b border-white/10 mb-2 cursor-grab active:cursor-grabbing shrink-0"
            >
                <span className="text-xs font-bold tracking-widest text-red-500/70 flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full ${devices.length > 0 ? 'bg-green-500 animate-pulse' : 'bg-gray-500'}`} />
                    SMART DOOR CONTROL
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
                            <RefreshCw size={14} /> DISCOVER DOORS
                        </button>
                    </div>
                )}

                {isThinking && (
                    <div className="flex flex-col items-center justify-center p-8 gap-3">
                        <div className="w-6 h-6 border-2 border-red-500 border-t-transparent rounded-full animate-spin" />
                        <span className="text-xs text-red-400 animate-pulse">Scanning Network...</span>
                    </div>
                )}

                {devices.map((dev) => {
                    // Backend may report the lock state as `is_locked`, or
                    // (legacy) as `is_on` where "on" meant "locked". Accept
                    // either so this keeps working regardless of payload shape.
                    const isLocked = dev.is_locked ?? dev.is_on ?? false;
                    const isLoading = loadingDevices[dev.ip];

                    return (
                        <div key={dev.ip} className="mb-3 p-3 bg-white/5 rounded-lg border border-white/10 hover:border-red-500/30 transition-all">
                            <div className="flex items-center justify-between">
                                <div className="flex flex-col">
                                    <span className="font-bold text-sm text-white">{dev.alias}</span>
                                    <span className="text-[10px] text-white/40 font-mono">{dev.ip}</span>
                                    <span className={`text-[10px] font-bold uppercase tracking-wider mt-1 ${isLocked ? 'text-green-400' : 'text-yellow-400'}`}>
                                        {isLocked ? 'Locked' : 'Unlocked'}
                                    </span>
                                </div>
                                <button
                                    onClick={() => handleToggleLock(dev.ip, isLocked)}
                                    disabled={isLoading}
                                    title={isLocked ? 'Unlock door' : 'Lock door'}
                                    className={`p-2 rounded-full transition-all ${isLocked
                                        ? 'bg-green-500/20 text-green-400 shadow-[0_0_10px_rgba(34,197,94,0.3)]'
                                        : 'bg-yellow-500/10 text-yellow-400 hover:text-white'}
                                        ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}
                                    `}
                                >
                                    {isLoading ? (
                                        <div className="w-[18px] h-[18px] border-2 border-current border-t-transparent rounded-full animate-spin" />
                                    ) : isLocked ? (
                                        <Lock size={18} />
                                    ) : (
                                        <Unlock size={18} />
                                    )}
                                </button>
                            </div>
                        </div>
                    );
                })}
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

DoorWindow.pluginMeta = {
    label: "Smart Door",
    icon: DoorOpen,
};

export default DoorWindow;
