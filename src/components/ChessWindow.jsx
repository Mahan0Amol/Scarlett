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
    const [optionSquares, setOptionSquares] = useState({});

    // Extract theme from data prop, fallback to defaults
    const theme = data.theme || { dark: "#2c3e50", light: "#ecf0f1", glow: "none" };

    useEffect(() => {
        if (!socket) return;

        const handlePluginUpdate = (updateData) => {
            if (updateData.plugin === "chess" && updateData.data?.fen) {
                setFen(updateData.data.fen);
                setGame(new Chess(updateData.data.fen));
            }
        };

        socket.on("plugin_update", handlePluginUpdate);
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
                promotion: piece[1].toLowerCase() === "p" ? "q" : undefined,
            });

            if (move === null) return false;

            setFen(game.fen());
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

    const getMoveOptions = (square) => {
        const moves = game.moves({ square, verbose: true });
        if (moves.length === 0) {
            setOptionSquares({});
            return;
        }
        const newSquares = {};
        moves.map((move) => {
            newSquares[move.to] = {
                // If glow is set, use it for move highlights too!
                background: theme.glow !== "none" ? `${theme.glow}44` : 'rgba(255, 255, 0, 0.4)',
                borderRadius: '50%',
            };
            return move;
        });
        setOptionSquares(newSquares);
    };

    // CSS filter for piece glow
    const pieceFilter = theme.glow && theme.glow !== "none" ? `drop-shadow(0 0 5px ${theme.glow}) drop-shadow(0 0 8px ${theme.glow})` : 'none';

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
                <span className="text-xs font-bold tracking-widest text-green-500/70 flex items-center gap-2 uppercase">
                    <Gamepad2 size={14} /> CHESS MATCH
                </span>
                <button
                    onClick={onClose}
                    className="text-gray-400 hover:text-red-400 hover:bg-red-500/20 p-1 rounded transition-colors"
                >
                    <X size={14} />
                </button>
            </div>

            {/* Board Container */}
            <div className="w-full aspect-square">
                <Chessboard 
                    position={fen} 
                    onPieceDrop={onDrop} 
                    onSquareClick={getMoveOptions}
                    customSquareStyles={{ ...optionSquares }}
                    boardOrientation="white"
                    customDarkSquareStyle={{ backgroundColor: theme.dark, transition: 'background-color 0.5s' }}
                    customLightSquareStyle={{ backgroundColor: theme.light, transition: 'background-color 0.5s' }}
                    customPieces={(piece) => (
                        <div
                            style={{
                                width: '100%',
                                height: '100%',
                                display: 'flex',
                                justifyContent: 'center',
                                alignItems: 'center',
                                fontSize: '40px',
                                filter: pieceFilter,
                                transition: 'filter 0.5s'
                            }}
                        >
                            {piece === 'wP' && '♙'}
                            {piece === 'wN' && '♘'}
                            {piece === 'wB' && '♗'}
                            {piece === 'wR' && '♖'}
                            {piece === 'wQ' && '♕'}
                            {piece === 'wK' && '♔'}
                            {piece === 'bP' && '♟'}
                            {piece === 'bN' && '♞'}
                            {piece === 'bB' && '♝'}
                            {piece === 'bR' && '♜'}
                            {piece === 'bQ' && '♛'}
                            {piece === 'bK' && '♚'}
                        </div>
                    )}
                />
            </div>
        </div>
    );
};

export default ChessWindow;