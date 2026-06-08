import React, { useEffect, useState } from "react";
import {X, Music, Play, Pause, SkipBack, SkipForward, Volume2 } from "lucide-react";

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

    useEffect(() => {
        if (!socket) return;

        const handleMusicState = (data) => {
            setTrack({
                title: data.title,
                artist: data.artist,
                thumb: data.thumb
            });

            setIsPlaying(data.isPlaying);
            setDuration(data.duration || 0);

            if (!isSeeking) {
                setCurrentTime(data.position || 0);
            }
        };

        socket.on("music_state", handleMusicState);

        return () => {
            socket.off("music_state", handleMusicState);
        };
    }, [socket, isSeeking]);

    const playPause = () => {
        socket?.emit(isPlaying ? "music_pause": "music_play");
    };

    const next = () => {
        socket?.emit("music_next");
    };

    const prev = () => {
        socket?.emit("music_prev");
    };

    const stop = () => {
        socket?.emit("music_stop");
    };

    const seek = (value) => {
        setCurrentTime(value);
    };

    const commitSeek = (value) => {
        setIsSeeking(false);

        socket?.emit("music_seek", {
            position: value
        });
    };

    const changeVolume = (value) => {
        setVolume(value);

        socket?.emit("music_volume", {
            volume: value
        });
    };

    return (
        <div
            id="music"
            className={`absolute flex flex-col p-4 rounded-xl backdrop-blur-md bg-black/60 border border-purple-500/30 select-none
            ${
                activeDragElement === "music"
                    ? "ring-2 ring-purple-500 shadow-[0_0_30px_rgba(168,85,247,0.3)]"
                    : "shadow-[0_0_20px_rgba(0,0,0,0.45)]"
            }`}
            style={{
                left: position.x,
                top: position.y,
                width: 320,
                height: 430,
                transform: "translate(-50%, -50%)",
                zIndex
            }}
        >
            {/* HEADER */}

            <div
                data-drag-handle
                onMouseDown={onMouseDown}
                className="flex items-center justify-between pb-2 border-b border-white/10 cursor-grab active:cursor-grabbing"
            >
                <div className="flex items-center gap-2">
                    <Music
                        size={14}
                        className="text-purple-400"
                    />

                    <span className="text-purple-300 font-bold text-sm tracking-wider">
                        MUSIC PLAYER
                    </span>
                </div>

                <button
                    onClick={() => {
                        stop();
                        onClose?.();
                    }}
                    className="text-white/40 hover:text-white transition-colors"
                    aria-label="Close Music Player"
                >
                    <X size={16} />
                </button>
            </div>

            {/* COVER */}

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
                    <img
                        src={
                            track.thumb ||
                            "https://via.placeholder.com/300"
                        }
                        alt={track.title}
                        className="w-full h-full object-cover"
                    />
                </div>

                {/* INFO */}

                <div className="mt-3 text-center">
                    <div
                        title={track.title}
                        className="text-white font-semibold text-sm truncate w-[240px]"
                    >
                        {track.title}
                    </div>

                    <div
                        title={track.artist}
                        className="text-white/50 text-xs truncate w-[240px]"
                    >
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
                    value={currentTime}
                    onMouseDown={() => setIsSeeking(true)}
                    onChange={(e) =>
                        seek(Number(e.target.value))
                    }
                    onMouseUp={(e) =>
                        commitSeek(
                            Number(e.target.value)
                        )
                    }
                    className="w-full accent-purple-500 cursor-pointer"
                />
            </div>

            {/* CONTROLS */}

            <div className="flex items-center justify-center gap-6 mt-5">
                <button
                    onClick={prev}
                    className="text-white/60 hover:text-white hover:scale-110 transition-all"
                    aria-label="Previous Track"
                >
                    <SkipBack size={22} />
                </button>

                <button
                    onClick={playPause}
                    className="
                        w-14 h-14
                        flex items-center justify-center
                        rounded-full
                        bg-purple-500/20
                        hover:bg-purple-500/30
                        hover:scale-105
                        transition-all
                        text-purple-300
                        shadow-[0_0_20px_rgba(168,85,247,0.25)]
                    "
                    aria-label="Play Pause"
                >
                    {isPlaying
                        ? <Pause size={24} />
                        : <Play size={24} />}
                </button>

                <button
                    onClick={next}
                    className="text-white/60 hover:text-white hover:scale-110 transition-all"
                    aria-label="Next Track"
                >
                    <SkipForward size={22} />
                </button>
            </div>

            {/* VOLUME */}

            <div className="mt-auto pt-5">
                <div className="flex items-center gap-3">
                    <Volume2
                        size={16}
                        className="text-white/50"
                    />

                    <input
                        type="range"
                        min={0}
                        max={100}
                        value={volume}
                        onChange={(e) =>
                            changeVolume(
                                Number(e.target.value)
                            )
                        }
                        className="w-full accent-purple-500"
                    />
                </div>
            </div>
        </div>
    );
};

export default MusicWindow;