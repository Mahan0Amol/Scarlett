import React, { useState, useEffect } from "react";
import { Chessboard } from "react-chessboard";
import { Chess } from "chess.js";
import { X, Gamepad2 } from "lucide-react";

const ChessWindow = ({
    socket,
    position,
    onClose,
    activeDragElement,
    onMouseDown,
    zIndex = 40,
    data = {} 
}) => {
    const [game, setGame] = useState(new Chess());
    const [fen, setFen] = useState("start");
    const [rightClickedSquares, setRightClickedSquares] = useState({});
    const [optionSquares, setOptionSquares] = useState({});

    useEffect(() => {
        if (!socket) return;

        const handlePluginUpdate = (updateData) => {
            if (updateData.plugin === "chess" && updateData.data?.fen) {
                setFen(updateData.data.fen);
                setGame(new Chess(updateData.data.fen));
            }
        };

        // Listen for generic plugin updates
        socket.on("plugin_update", handlePluginUpdate);
        
        // Request initial state using the generic plugin action
        socket.emit("plugin_action", { 
            plugin: "chess", 
            action: "chess_state_request", 
            payload: {} 
        });

        return () => {
            socket.off("plugin_update", handlePluginUpdate);
        };
    }, [socket]);

    const onDrop = (sourceSquare, targetSquare, piece) => {
        setOptionSquares({});
        
        try {
            const move = game.move({
                from: sourceSquare,
                to: targetSquare,
                // Fix: Always default to Queen ('q') for promotion validity
                promotion: piece[1].toLowerCase() === "p" ? "q" : undefined, 
            });

            if (move === null) return false; // Illegal move

            setFen(game.fen());
            
            // Send move to backend using the generic plugin action
            socket.emit("plugin_action", { 
                plugin: "chess", 
                action: "chess_user_move", 
                payload: { move: move.from + move.to + (move.promotion || '') } 
            });
            
            return true;
        } catch (e) {
            return false;
        }
    };
    // Show possible moves on piece click
    const getMoveOptions = (square) => {
        const moves = game.moves({ square, verbose: true });
        if (moves.length === 0) {
            setOptionSquares({});
            return;
        }

        const newSquares = {};
        moves.map((move) => {
            newSquares[move.to] = {
                background: 'rgba(255, 255, 0, 0.4)',
                borderRadius: '50%',
            };
            return move;
        });
        setOptionSquares(newSquares);
    };

    return (
        <div
            id="chess"
            className={`absolute flex flex-col p-4 rounded-xl backdrop-blur-xl bg-black/40 border border-white/10 shadow-2xl overflow-hidden select-none transition-all duration-200
                ${activeDragElement === "chess" ? "ring-2 ring-green-500 bg-green-500/10" : ""}`}
            style={{
                left: position?.x || window.innerWidth / 2,
                top: position?.y || window.innerHeight / 2,
                transform: "translate(-50%, -50%)",
                width: 400,
                pointerEvents: 'auto',
                zIndex: zIndex
            }}
        >
            {/* Header Bar - Drag Handle */}
            <div
                data-drag-handle
                onMouseDown={(e) => onMouseDown && onMouseDown(e, 'chess')}
                className="h-8 flex items-center justify-between px-2 mb-2 border-b border-white/10 cursor-grab active:cursor-grabbing shrink-0"
            >
                <span className="text-xs font-bold tracking-widest text-green-500/70 flex items-center gap-2">
                    <Gamepad2 size={14} /> CHESS MATCH
                </span>
                <button
                    onClick={onClose}
                    className="text-gray-400 hover:text-red-400 hover:bg-red-500/20 p-1 rounded transition-colors"
                >
                    <X size={14} />
                </button>
            </div>

            {/* Board */}
            <div className="w-full aspect-square">
                <Chessboard 
                    position={fen} 
                    onPieceDrop={onDrop} 
                    onSquareClick={getMoveOptions}
                    customSquareStyles={{ ...optionSquares, ...rightClickedSquares }}
                    boardOrientation="white"
                    customDarkSquareStyle={{ backgroundColor: '#2c3e50' }}
                    customLightSquareStyle={{ backgroundColor: '#ecf0f1' }}
                />
            </div>
        </div>
    );
};

export default ChessWindow;