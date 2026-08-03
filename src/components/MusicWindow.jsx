import React, { useEffect, useState } from "react";
import { X, Music, Disc3, Play, Pause, SkipBack, SkipForward, Volume2 } from "lucide-react";

const formatTime = (seconds = 0) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, "0")}`;
};

const MusicWindow = ({
    socket,
    position,
    onClose,
    activeDragElement,
    onMouseDown,
    zIndex = 40
}) => {
    const [track, setTrack] = useState({
        title: "No Track Selected",
        artist: "Unknown Artist",
        thumb: null
    });

    const [isPlaying, setIsPlaying] = useState(false);
    const [currentTime, setCurrentTime] = useState(0);
    const [duration, setDuration] = useState(0);
    const [volume, setVolume] = useState(80);
    const [isSeeking, setIsSeeking] = useState(false);
    const [localTime, setLocalTime] = useState(0);

    // ====================== دریافت وضعیت از سرور ======================
    useEffect(() => {
        if (!socket) return;

        const handleMusicState = (data) => {
            if (!data) return;

            setTrack({
                title: data.title || "No Track Selected",
                artist: data.artist || "Unknown Artist",
                thumb: data.thumb
            });

            setIsPlaying(!!data.isPlaying);
            setDuration(data.duration || 0);
            setCurrentTime(data.position || 0);

            if (!isSeeking) {
                setLocalTime(data.position || 0);
            }

            if (typeof data.volume === "number") {
                setVolume(data.volume);
            }
        };

        const handleTick = (data) => {
            if (!data || isSeeking) return;

            setCurrentTime(data.position);
            setDuration(data.duration);
            setLocalTime(data.position);
        };

        socket.on("music_state", handleMusicState);
        socket.on("music_tick", handleTick);

        // درخواست وضعیت فعلی هنگام باز شدن پنجره
        socket.emit("music_state_request");

        return () => {
            socket.off("music_state", handleMusicState);
            socket.off("music_tick", handleTick);
        };
    }, [socket, isSeeking]);

    // ====================== کنترل‌های پلیر ======================
    const playPause = () => {
        socket?.emit(isPlaying ? "music_pause" : "music_play");
    };

    const next = () => {
        socket?.emit("music_next");
    };

    const prev = () => {
        socket?.emit("music_prev");
    };

    const stop = () => {
        socket?.emit("music_stop");
        onClose?.(); // بستن پنجره توسط App.jsx
    };

    const seek = (value) => {
        setLocalTime(value);
        setIsSeeking(true);
    };

    const commitSeek = (value) => {
        socket.emit("music_seek", { position: value });
        
        // Wait 800ms before accepting backend tick updates.
        // This gives the backend and VLC player time to settle, 
        // preventing the slider from snapping back.
        setTimeout(() => {
            setIsSeeking(false);
        }, 800);
    };

    const changeVolume = (value) => {
        setVolume(value);
        socket?.emit("music_volume", { volume: value });
    };

    // ====================== رندر کامپوننت ======================
    return (
        <div
            id="music"
            className={`absolute flex flex-col p-4 rounded-xl backdrop-blur-md bg-black/60 border border-purple-500/30 select-none transition-all duration-200
                ${activeDragElement === "music" ? "ring-2 ring-purple-500 shadow-[0_0_30px_rgba(168,85,247,0.3)]" : "shadow-[0_0_20px_rgba(0,0,0,0.45)]"}
            `}
            style={{
                left: position?.x || window.innerWidth / 2,
                top: position?.y || window.innerHeight / 2,
                width: 320,
                height: 430,
                transform: "translate(-50%, -50%)",
                pointerEvents: 'auto',
                zIndex: zIndex
            }}
        >
            {/* HEADER (Drag Handle) */}
            <div
                data-drag-handle
                onMouseDown={(e) => onMouseDown && onMouseDown(e, 'music')} // ارسال رویداد درگ به App.jsx
                className="flex items-center justify-between pb-2 border-b border-white/10 cursor-grab active:cursor-grabbing"
            >
                <div className="flex items-center gap-2">
                    <Music size={14} className="text-purple-400" />
                    <span className="text-purple-300 font-bold text-sm tracking-wider">
                        MUSIC PLAYER
                    </span>
                </div>

                <button
                    onClick={stop}
                    className="text-white/40 hover:text-white transition-colors"
                >
                    <X size={16} />
                </button>
            </div>

            {/* COVER ART */}
            <div className="mt-4 flex flex-col items-center">
                <div
                    className={`
                        w-44 h-44
                        rounded-xl
                        overflow-hidden
                        border border-purple-500/30
                        shadow-[0_0_25px_rgba(168,85,247,0.2)]
                        transition-transform duration-700
                        ${isPlaying ? "scale-[1.02]" : ""}
                    `}
                >
                    {track.thumb ? (
                        <img
                            src={track.thumb}
                            alt={track.title}
                            className="w-full h-full object-cover"
                            onError={(e) => {
                                e.target.style.display = 'none';
                            }}
                        />
                    ) : (
                        <div className="w-full h-full flex items-center justify-center bg-zinc-800">
                            <Disc3 size={80} className="text-zinc-500" />
                        </div>
                    )}
                </div>

                {/* TRACK INFO */}
                <div className="mt-3 text-center">
                    <div className="text-white font-semibold text-sm truncate w-[240px]">
                        {track.title}
                    </div>
                    <div className="text-white/50 text-xs truncate w-[240px]">
                        {track.artist}
                    </div>
                    <div className="text-[11px] text-purple-300 mt-1">
                        {formatTime(currentTime)} / {formatTime(duration)}
                    </div>
                </div>
            </div>

            {/* SEEK BAR */}
            <div className="mt-4 px-1">
                <input
                    type="range"
                    min={0}
                    max={duration || 100}
                    value={localTime}
                    onMouseDown={() => setIsSeeking(true)}
                    onChange={(e) => seek(Number(e.target.value))}
                    onMouseUp={(e) => commitSeek(Number(e.target.value))}
                    className="w-full accent-purple-500 cursor-pointer"
                />
            </div>

            {/* PLAYBACK CONTROLS */}
            <div className="flex items-center justify-center gap-6 mt-5">
                <button onClick={prev} className="text-white/60 hover:text-white hover:scale-110 transition-all">
                    <SkipBack size={22} />
                </button>

                <button
                    onClick={playPause}
                    className="w-14 h-14 flex items-center justify-center rounded-full bg-purple-500/20 hover:bg-purple-500/30 hover:scale-105 transition-all text-purple-300 shadow-[0_0_20px_rgba(168,85,247,0.25)]"
                >
                    {isPlaying ? <Pause size={24} /> : <Play size={24} />}
                </button>

                <button onClick={next} className="text-white/60 hover:text-white hover:scale-110 transition-all">
                    <SkipForward size={22} />
                </button>
            </div>

            {/* VOLUME CONTROL */}
            <div className="mt-auto pt-5">
                <div className="flex items-center gap-3">
                    <Volume2 size={16} className="text-white/50" />
                    <input
                        type="range"
                        min={0}
                        max={100}
                        value={volume}
                        onChange={(e) => changeVolume(Number(e.target.value))}
                        className="w-full accent-purple-500"
                    />
                </div>
            </div>
        </div>
    );
};

export default MusicWindow;