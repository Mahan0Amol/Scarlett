import React, { useMemo, useState, useEffect, useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Center, Stage } from '@react-three/drei';
import * as THREE from 'three';
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader';
import { Printer, Box, X } from 'lucide-react';

const GeometryModel = ({ geometry }) => {
    return (
        <mesh geometry={geometry} castShadow receiveShadow>
            <meshStandardMaterial color="#06b6d4" roughness={0.3} metalness={0.8} />
        </mesh>
    );
};

const LoadingCube = () => {
    const meshRef = useRef();
    useFrame((state, delta) => {
        if (meshRef.current) {
            meshRef.current.rotation.x += delta;
            meshRef.current.rotation.y += delta;
        }
    });
    return (
        <mesh ref={meshRef}>
            <boxGeometry args={[10, 10, 10]} />
            <meshStandardMaterial wireframe color="red" transparent opacity={0.5} />
        </mesh>
    );
};

const CadWindow = ({
    socket,
    position,
    onClose,
    activeDragElement,
    onMouseDown,
    zIndex = 40,
    data = {}
}) => {
    // Extract plugin-specific data from the data prop
    const cadData = data.cadData;
    const thoughts = data.cadThoughts || '';
    const retryInfo = data.cadRetryInfo || {};

    const [isIterating, setIsIterating] = useState(false);
    const [prompt, setPrompt] = useState("");
    const [isSending, setIsSending] = useState(false);
    const thoughtsEndRef = useRef(null);

    // Debug log
    useEffect(() => {
        if (cadData) console.log("CadWindow Data:", cadData.format);
    }, [cadData]);

    // Auto-scroll thoughts panel
    useEffect(() => {
        if (thoughtsEndRef.current) {
            thoughtsEndRef.current.scrollIntoView({ behavior: 'smooth' });
        }
    }, [thoughts]);

    const geometry = useMemo(() => {
        if (!cadData || cadData.format !== 'stl' || !cadData.data) return null;

        try {
            // Convert Base64 to ArrayBuffer
            const byteCharacters = atob(cadData.data);
            const byteNumbers = new Array(byteCharacters.length);
            for (let i = 0; i < byteCharacters.length; i++) {
                byteNumbers[i] = byteCharacters.charCodeAt(i);
            }
            const byteArray = new Uint8Array(byteNumbers);

            // Parse directly using THREE.STLLoader
            const loader = new STLLoader();
            const geom = loader.parse(byteArray.buffer);
            geom.center(); // Optional: Center the geometry
            return geom;
        } catch (e) {
            console.error("Failed to decode/parse STL:", e);
            return null;
        }
    }, [cadData]);

    const handleGenerate = () => {
        if (!prompt.trim()) return;
        setIsSending(true);
        if (socket) {
            socket.emit('generate_cad', { prompt });
        } else {
            console.error("Socket not available in CadWindow");
        }
        setPrompt("");
        
        // Reset after a short delay so user knows it was sent.
        setTimeout(() => setIsSending(false), 2000);
    };

    const handleIterate = () => {
        if (!prompt.trim()) return;
        setIsSending(true);
        
        if (socket) {
            socket.emit('iterate_cad', { prompt });
        } else {
            console.error("Socket not available in CadWindow");
        }

        setIsIterating(false);
        setPrompt("");
        setIsSending(false);
    };

    return (
        <div
            id="cad"
            className={`absolute flex flex-col transition-all duration-200 
                backdrop-blur-xl bg-black/40 border border-white/10 shadow-2xl overflow-hidden rounded-2xl
                ${activeDragElement === "cad" ? "ring-2 ring-green-500 bg-green-500/10" : ""}
            `}
            style={{
                left: position?.x || window.innerWidth / 2,
                top: position?.y || window.innerHeight / 2,
                transform: "translate(-50%, -50%)",
                width: 400,
                height: 400,
                pointerEvents: 'auto',
                zIndex: zIndex
            }}
        >
            {/* Header Bar - Drag Handle */}
            <div
                data-drag-handle
                onMouseDown={(e) => onMouseDown && onMouseDown(e, 'cad')}
                className="h-8 bg-gray-900/80 border-b border-red-500/20 flex items-center justify-between px-3 cursor-grab active:cursor-grabbing shrink-0"
            >
                <span className="text-xs font-bold tracking-widest text-red-500/70 flex items-center gap-2">
                    <Box size={14} /> CAD PROTOTYPE
                </span>
                <button
                    onClick={onClose}
                    className="text-gray-400 hover:text-red-400 hover:bg-red-500/20 p-1 rounded transition-colors"
                >
                    <X size={14} />
                </button>
            </div>

            {/* Main CAD Content Area */}
            <div className="flex-1 relative group bg-gray-900 overflow-hidden">
                
                {/* Top Toolbar */}
                <div className="absolute top-2 left-2 z-10 opacity-0 group-hover:opacity-100 transition-opacity flex gap-2">
                    <button
                        onClick={() => setIsIterating(true)}
                        className="bg-red-500/20 hover:bg-red-500/50 text-red-400 text-xs px-2 py-1 rounded border border-red-500/30 backdrop-blur-sm"
                    >
                        ITERATE
                    </button>
                    <button
                        onClick={() => {
                            if (socket) socket.emit('request_print_window');
                        }}
                        className="bg-green-500/20 hover:bg-green-500/50 text-green-400 text-xs px-2 py-1 rounded border border-green-500/30 backdrop-blur-sm flex items-center gap-1"
                    >
                        <Printer size={12} /> PRINT
                    </button>
                </div>

                {/* Iteration / Generation Overlay */}
                {(isIterating || (!cadData && cadData?.format !== 'loading')) && (
                    <div className={`absolute inset-0 z-20 ${!cadData ? 'bg-gray-900' : 'bg-black/80'} flex items-center justify-center p-4`}>
                        <div className="bg-gray-800 border border-red-500/50 rounded p-4 w-full max-w-sm pointer-events-auto shadow-[0_0_20px_rgba(6,182,212,0.2)]">
                            <h4 className="text-red-400 text-sm mb-2 font-mono">
                                {!cadData ? "New Design" : "Refine Design"}
                            </h4>
                            <textarea
                                value={prompt}
                                onChange={(e) => setPrompt(e.target.value)}
                                placeholder={!cadData ? "Describe what you want to create..." : "e.g., Make the wheels bigger..."}
                                className="w-full bg-gray-900 border border-gray-700 rounded p-2 text-white text-sm mb-3 focus:outline-none focus:border-red-500 h-24 resize-none"
                                autoFocus
                                onKeyDown={(e) => {
                                    if (e.key === 'Enter' && !e.shiftKey) {
                                        e.preventDefault();
                                        !cadData ? handleGenerate() : handleIterate();
                                    }
                                }}
                            />
                            <div className="flex justify-end gap-2">
                                {cadData && (
                                    <button
                                        onClick={() => setIsIterating(false)}
                                        className="text-gray-400 text-xs hover:text-white px-2 py-1"
                                    >
                                        Cancel
                                    </button>
                                )}
                                <button
                                    onClick={!cadData ? handleGenerate : handleIterate}
                                    disabled={isSending}
                                    className="bg-red-600 hover:bg-red-500 text-white text-xs px-3 py-1 rounded"
                                >
                                    {isSending ? "Generating..." : (!cadData ? "Generate" : "Update")}
                                </button>
                            </div>
                        </div>
                    </div>
                )}

                <Canvas shadows camera={{ position: [4, 4, 4], fov: 45 }}>
                    <color attach="background" args={['#101010']} />

                    <Stage environment="city" intensity={0.5}>
                        {cadData?.format === 'loading' ? (
                            <LoadingCube />
                        ) : (
                            geometry && (
                                <Center>
                                    <GeometryModel geometry={geometry} />
                                </Center>
                            )
                        )}
                    </Stage>

                    <OrbitControls autoRotate={!isIterating} autoRotateSpeed={1} makeDefault />
                </Canvas>

                {/* Streaming Thoughts Panel */}
                {cadData?.format === 'loading' && (
                    <div className="absolute inset-y-0 right-0 w-2/5 p-4 bg-black/70 backdrop-blur-sm border-l border-green-500/30 overflow-hidden flex flex-col">
                        <div className="flex items-center justify-between mb-2">
                            <h4 className="text-green-400 text-xs font-mono tracking-widest uppercase flex items-center gap-2">
                                <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
                                Designer Thinking...
                            </h4>
                            {retryInfo.attempt && (
                                <span className={`text-xs font-mono px-2 py-0.5 rounded ${retryInfo.error ? 'bg-yellow-500/20 text-yellow-400' : 'bg-red-500/20 text-red-400'}`}>
                                    Attempt {retryInfo.attempt}/{retryInfo.maxAttempts || 3}
                                </span>
                            )}
                        </div>
                        {retryInfo.error && (
                            <div className="mb-2 p-2 bg-red-500/10 border border-red-500/30 rounded text-red-400 text-xs font-mono">
                                <span className="text-red-500 font-bold">⚠ Error:</span> {retryInfo.error}
                            </div>
                        )}
                        <div className="flex-1 overflow-y-auto text-green-400/80 text-xs font-mono whitespace-pre-wrap leading-relaxed scrollbar-thin scrollbar-thumb-green-500/30">
                            {thoughts}
                            <div ref={thoughtsEndRef} />
                        </div>
                    </div>
                )}

                <div className="absolute bottom-2 left-2 text-[10px] text-red-500/50 font-mono tracking-widest pointer-events-none">
                    CAD_ENGINE_V2: {cadData?.format?.toUpperCase() || "READY"}
                </div>
            </div>
        </div>
    );
};

CadWindow.pluginMeta = {
    label: "CAD Agent",
    icon: Box,
};

export default CadWindow;