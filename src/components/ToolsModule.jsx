import React from 'react';
import { Mic, MicOff, Settings, Power, Video, VideoOff, Hand } from 'lucide-react';

// Core, always-present system controls. Plugin launcher buttons are appended
// dynamically below based on `toolbarPlugins` - nothing plugin-specific is
// hardcoded here anymore.
const ToolsModule = ({
    isConnected,
    isMuted,
    isVideoOn,
    isHandTrackingEnabled,
    showSettings,
    onTogglePower,
    onToggleMute,
    onToggleVideo,
    onToggleSettings,
    onToggleHand,

    // List of { id, label, icon } for the plugins currently pinned to the
    // toolbar (see pluginRegistry.PLUGIN_META + the picker in SettingsWindow).
    toolbarPlugins = [],
    // Set/array of plugin ids that currently have an open window, so we can
    // highlight their button the same way the fixed buttons highlight.
    openPluginIds = [],
    // (id) => void - toggles that plugin's window open/closed.
    onTogglePlugin,

    activeDragElement,
    position,
    onMouseDown
}) => {
    return (
        <div
            id="tools"
            onMouseDown={onMouseDown}
            className={`absolute px-6 py-3 transition-all duration-200 
                        backdrop-blur-xl bg-black/40 border border-white/10 shadow-2xl rounded-2xl`}
            style={{
                right: position.x,
                bottom: position.y,
                transform: 'translate(-40%, 520%) rotate(90deg)',
                pointerEvents: 'auto'
            }}
        >
            <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-5 pointer-events-none mix-blend-overlay rounded-full"></div>

            <div className="flex justify-center gap-6 relative z-10">
                {/* Power Button */}
                <button
                    onClick={onTogglePower}
                    className={`p-3 rounded-full border-2 transition-all duration-300 ${isConnected
                        ? 'border-green-500 bg-green-500/10 text-green-500 hover:bg-green-500/20 shadow-[0_0_15px_rgba(34,197,94,0.3)]'
                        : 'border-gray-600 bg-gray-600/10 text-gray-500 hover:bg-gray-600/20'
                        } `}
                    style={{ transform: 'rotate(-90deg)' }}
                >
                    <Power size={24} />
                </button>

                {/* Mute Button */}
                <button
                    onClick={onToggleMute}
                    disabled={!isConnected}
                    className={`p-3 rounded-full border-2 transition-all duration-300 ${!isConnected
                        ? 'border-gray-800 text-gray-800 cursor-not-allowed'
                        : isMuted
                            ? 'border-red-500 bg-red-500/10 text-red-500 hover:bg-red-500/20 shadow-[0_0_15px_rgba(239,68,68,0.3)]'
                            : 'border-cyan-500 bg-cyan-500/10 text-cyan-500 hover:bg-cyan-500/20 shadow-[0_0_15px_rgba(6,182,212,0.3)]'
                        } `}
                    style={{ transform: 'rotate(-90deg)' }}
                >
                    {isMuted ? <MicOff size={24} /> : <Mic size={24} />}
                </button>

                {/* Video Button */}
                <button
                    onClick={onToggleVideo}
                    className={`p-3 rounded-full border-2 transition-all duration-300 ${isVideoOn
                        ? 'border-purple-500 bg-purple-500/10 text-purple-500 hover:bg-purple-500/20 shadow-[0_0_15px_rgba(168,85,247,0.3)]'
                        : 'border-cyan-900 text-cyan-700 hover:border-cyan-500 hover:text-cyan-500'
                        } `}
                    style={{ transform: 'rotate(-90deg)' }}
                >
                    {isVideoOn ? <Video size={24} /> : <VideoOff size={24} />}
                </button>

                {/* Settings Button */}
                <button
                    onClick={onToggleSettings}
                    className={`p-3 rounded-full border-2 transition-all ${showSettings ? 'border-cyan-400 text-cyan-400 bg-cyan-900/20' : 'border-cyan-900 text-cyan-700 hover:border-cyan-500 hover:text-cyan-500'
                        } `}
                    style={{ transform: 'rotate(-90deg)' }}
                >
                    <Settings size={24} />
                </button>

                {/* Hand Tracking Toggle */}
                <button
                    onClick={onToggleHand}
                    className={`p-3 rounded-full border-2 transition-all duration-300 ${isHandTrackingEnabled
                        ? 'border-orange-500 bg-orange-500/10 text-orange-500 hover:bg-orange-500/20 shadow-[0_0_15px_rgba(249,115,22,0.3)]'
                        : 'border-cyan-900 text-cyan-700 hover:border-cyan-500 hover:text-cyan-500'
                        } `}
                    style={{ transform: 'rotate(-90deg)' }}
                >
                    <Hand size={24} />
                </button>

                {/* Plugin launcher buttons - fully data-driven. Each plugin
                    supplies its own icon/label via `pluginMeta` on the
                    component (see pluginRegistry.jsx); this list is just
                    whichever ones the user pinned (max MAX_TOOLBAR_PLUGINS,
                    see SettingsWindow's toolbar picker). */}
                {toolbarPlugins.map(({ id, label, icon: Icon }) => {
                    if (!Icon) return null;
                    const isOpen = openPluginIds.includes(id);
                    return (
                        <button
                            key={id}
                            onClick={() => onTogglePlugin && onTogglePlugin(id)}
                            title={label}
                            className={`p-3 rounded-full border-2 transition-all duration-300 ${isOpen
                                ? 'border-cyan-400 bg-cyan-400/10 text-cyan-400 hover:bg-cyan-400/20 shadow-[0_0_15px_rgba(34,211,238,0.3)]'
                                : 'border-cyan-900 text-cyan-700 hover:border-cyan-500 hover:text-cyan-500'
                                } `}
                            style={{ transform: 'rotate(-90deg)' }}
                        >
                            <Icon size={24} />
                        </button>
                    );
                })}
            </div>
        </div>
    );
};

export default ToolsModule;
