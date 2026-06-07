import React from 'react';
import { X, Play, Pause, SkipBack, SkipForward, Music } from 'lucide-react';

const MusicWindow = ({
    socket,
    position,
    onClose,
    activeDragElement,
    onMouseDown,
    zIndex = 40,
    currentTrack,
    isPlaying,
}) => {

    const playPause = () => {
        socket?.emit(isPlaying ? 'music_pause' : 'music_play');
    };

    const next = () => socket?.emit('music_next');
    const prev = () => socket?.emit('music_prev');

    return (
        <div
            id="music"
            onMouseDown={onMouseDown}
            className={`absolute flex flex-col p-4 rounded-xl backdrop-blur-md bg-black/60 border border-purple-500/30 select-none
            ${activeDragElement === 'music'
                ? 'ring-2 ring-purple-500 shadow-[0_0_30px_rgba(168,85,247,0.3)]'
                : 'shadow-[0_0_20px_rgba(0,0,0,0.4)]'
            }`}
            style={{
                left: position.x,
                top: position.y,
                width: '320px',
                minHeight: '420px',
                transform: 'translate(-50%, -50%)',
                zIndex
            }}
        >

            {/* Header */}
            <div data-drag-handle className="flex items-center justify-between pb-2 border-b border-white/10 cursor-grab active:cursor-grabbing">
                <div className="flex items-center gap-2">
                    <Music size={14} className="text-purple-400" />
                    <h3 className="text-purple-300 font-bold text-sm tracking-wider">
                        MUSIC PLAYER
                    </h3>
                </div>

                <button onClick={onClose} className="text-white/40 hover:text-white">
                    <X size={16} />
                </button>
            </div>

            {/* COVER / THUMB */}
            <div className="mt-4 flex flex-col items-center">
                <div className="w-[220px] h-[220px] rounded-xl overflow-hidden border border-purple-500/30 shadow-[0_0_25px_rgba(168,85,247,0.2)]">
                    <img
                        src={currentTrack?.thumb || 'https://via.placeholder.com/300'}
                        className="w-full h-full object-cover"
                    />
                </div>

                {/* Track info */}
                <div className="mt-3 text-center">
                    <div className="text-white font-semibold text-sm truncate w-[260px]">
                        {currentTrack?.title || 'No Track Selected'}
                    </div>
                    <div className="text-white/40 text-[11px]">
                        {currentTrack?.artist || 'Unknown Artist'}
                    </div>
                </div>
            </div>

            {/* CONTROLS */}
            <div className="flex items-center justify-center gap-6 mt-6">

                <button onClick={prev} className="text-white/60 hover:text-white">
                    <SkipBack size={22} />
                </button>

                <button
                    onClick={playPause}
                    className="w-14 h-14 flex items-center justify-center rounded-full bg-purple-500/20 hover:bg-purple-500/30 text-purple-300 shadow-[0_0_20px_rgba(168,85,247,0.25)]"
                >
                    {isPlaying ? <Pause size={24} /> : <Play size={24} />}
                </button>

                <button onClick={next} className="text-white/60 hover:text-white">
                    <SkipForward size={22} />
                </button>
            </div>

        </div>
    );
};

export default MusicWindow;