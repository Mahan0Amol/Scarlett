import React, { useState, useEffect, useCallback } from "react";
import { Chessboard } from "react-chessboard";
import { X, Gamepad2 } from "lucide-react";
import { Chess } from "chess.js";

const ChessWindow = ({ socket, onClose, position, activeDragElement, onMouseDown, zIndex = 40 }) => {
    const [game, setGame] = useState(new Chess());
    const [fen, setFen] = useState("start");
    const [rightClickedSquares, setRightClickedSquares] = useState({});
    const [optionSquares, setOptionSquares] = useState({});

    useEffect(() => {
        if (!socket) return;

        const handleState = (data) => {
            if (data.fen) {
                setFen(data.fen);
                setGame(new Chess(data.fen));
            }
        };

        socket.on("chess_state", handleState);
        socket.emit("chess_state_request");

        return () => {
            socket.off("chess_state", handleState);
        };
    }, [socket]);

    const onDrop = (sourceSquare, targetSquare, piece) => {
        setOptionSquares({});
        
        try {
            const move = game.move({
                from: sourceSquare,
                to: targetSquare,
                promotion: piece[1].toLowerCase() ?? "q",
            });

            if (move === null) return false; // Illegal move

            setFen(game.fen());
            socket.emit("chess_user_move", { move: move.from + move.to + (move.promotion || '') });
            
            return true;
        } catch (e) {
            return false;
        }
    };

    // نمایش حرکات ممکن با کلیک روی مهره
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
            className={`absolute flex flex-col p-4 rounded-xl backdrop-blur-md bg-black/60 border border-green-500/30 select-none
            ${activeDragElement === "chess" ? "ring-2 ring-green-500 shadow-[0_0_30px_rgba(34,197,94,0.3)]" : "shadow-[0_0_20px_rgba(0,0,0,0.45)]"}`}
            style={{
                left: position.x,
                top: position.y,
                width: 400,
                transform: "translate(-50%, -50%)",
                zIndex
            }}
        >
            {/* HEADER */}
            <div
                data-drag-handle
                onMouseDown={onMouseDown}
                className="flex items-center justify-between pb-2 mb-2 border-b border-white/10 cursor-grab active:cursor-grabbing"
            >
                <div className="flex items-center gap-2">
                    <Gamepad2 size={16} className="text-green-400" />
                    <span className="text-green-300 font-bold text-sm tracking-wider">CHESS MATCH</span>
                </div>
                <button onClick={onClose} className="text-white/40 hover:text-white transition-colors">
                    <X size={16} />
                </button>
            </div>

            {/* BOARD */}
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