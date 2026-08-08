import React, { useState, useRef, useEffect } from 'react';
import { Terminal, X, Folder, ChevronRight } from 'lucide-react';

// Command output is rendered as raw HTML when the backend marks it
// `isHtml: true`. This app runs in Electron with the renderer able to
// `window.require('electron')`, so unsanitized HTML in that path is a real
// remote-code-execution risk if any command output ever contains untrusted
// content (a fetched web page, a file's contents, etc). This strips the
// dangerous bits (script tags, inline event handlers, javascript:/data:
// URLs) before they ever reach dangerouslySetInnerHTML.
//
// This is a stop-gap, not a substitute for a real sanitizer - prefer
// swapping this out for DOMPurify (`npm install dompurify`) when the
// project has network access to install it.
const sanitizeHtml = (html) => {
    if (typeof html !== 'string') return '';
    const template = document.createElement('template');
    template.innerHTML = html;

    const walk = (node) => {
        // Snapshot children first - we may remove/mutate nodes as we go.
        Array.from(node.childNodes).forEach((child) => {
            if (child.nodeType === Node.ELEMENT_NODE) {
                const tag = child.tagName.toLowerCase();
                if (tag === 'script' || tag === 'iframe' || tag === 'object' || tag === 'embed' || tag === 'link' || tag === 'style') {
                    child.remove();
                    return;
                }
                Array.from(child.attributes).forEach((attr) => {
                    const name = attr.name.toLowerCase();
                    const value = attr.value.trim().toLowerCase();
                    if (name.startsWith('on')) {
                        child.removeAttribute(attr.name);
                    } else if ((name === 'href' || name === 'src') && (value.startsWith('javascript:') || value.startsWith('data:text/html'))) {
                        child.removeAttribute(attr.name);
                    }
                });
                walk(child);
            }
        });
    };
    walk(template.content);
    return template.innerHTML;
};

const CmdWindow = ({ socket, onClose }) => {
    const [input, setInput] = useState('');
    const [history, setHistory] = useState([]);
    const [isProcessing, setIsProcessing] = useState(false);
    const [currentDir, setCurrentDir] = useState('~');
    const [commandHistory, setCommandHistory] = useState([]);
    const [historyIndex, setHistoryIndex] = useState(-1);
    const inputRef = useRef(null);
    const historyEndRef = useRef(null);

    useEffect(() => {
        if (!socket) return;
        
        socket.on('cmd_output', (data) => {
            setHistory(prev => [...prev, { 
                type: 'output', 
                text: data.output,
                isHtml: data.isHtml || false,
                time: new Date().toLocaleTimeString() 
            }]);
            setIsProcessing(false);
            
            if (data.current_dir) {
                setCurrentDir(data.current_dir);
            }
        });

        socket.on('cmd_error', (data) => {
            setHistory(prev => [...prev, { 
                type: 'error', 
                text: data.error, 
                time: new Date().toLocaleTimeString() 
            }]);
            setIsProcessing(false);
        });

        socket.emit('get_cmd_status');

        return () => {
            socket.off('cmd_output');
            socket.off('cmd_error');
        };
    }, [socket]);

    useEffect(() => {
        historyEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [history]);

    useEffect(() => {
        inputRef.current?.focus();
    }, []);

    const executeCommand = (cmd) => {
        if (!cmd.trim() || isProcessing) return;
        
        if (cmd.trim().toLowerCase() === 'clear') {
            setHistory([]);
            setInput('');
            return; 
        }
        
        setCommandHistory(prev => [...prev, cmd]);
        setHistoryIndex(-1);
        
        setHistory(prev => [...prev, { 
            type: 'command', 
            text: `${currentDir} ❯ ${cmd}`, 
            time: new Date().toLocaleTimeString() 
        }]);
        
        setIsProcessing(true);
        socket.emit('execute_cmd', { command: cmd });
        setInput('');
    };

    const handleExecute = (e) => {
        if (e.key === 'Enter') {
            executeCommand(input);
        }
    };

    const handleKeyDown = (e) => {
        if (e.key === 'ArrowUp') {
            e.preventDefault();
            if (commandHistory.length > 0) {
                const newIndex = historyIndex === -1 
                    ? commandHistory.length - 1 
                    : Math.max(0, historyIndex - 1);
                setHistoryIndex(newIndex);
                setInput(commandHistory[newIndex]);
            }
        } else if (e.key === 'ArrowDown') {
            e.preventDefault();
            if (historyIndex >= 0) {
                const newIndex = historyIndex + 1;
                if (newIndex >= commandHistory.length) {
                    setHistoryIndex(-1);
                    setInput('');
                } else {
                    setHistoryIndex(newIndex);
                    setInput(commandHistory[newIndex]);
                }
            }
        } else if (e.key === 'Tab') {
            e.preventDefault();
            if (input.trim()) {
                socket.emit('autocomplete_cmd', { partial: input });
            }
        }
    };

    const clearTerminal = () => {
        setHistory([]);
    };

    const quickCommands = [
        { cmd: 'help', label: 'Help' },
        { cmd: 'ls', label: 'List Files' },
        { cmd: 'pwd', label: 'Current Dir' },
        { cmd: 'clear', label: 'Clear' },
        { cmd: 'status', label: 'Status' },
    ];

    return (
        <div className="flex flex-col h-full w-full bg-[#0a0a0f] text-red-400 font-mono overflow-hidden">
            {/* Header - Fixed height */}
            <div className="h-10 bg-gray-900/90 border-b border-red-500/20 flex items-center justify-between px-4 shrink-0">
                <div className="flex items-center gap-3 min-w-0">
                    <Terminal size={16} className="text-red-400 shrink-0" />
                    <span className="text-xs font-bold tracking-[0.2em] text-red-400/80 shrink-0">
                        AI TERMINAL
                    </span>
                    <span className="text-[10px] text-gray-600 truncate">
                        {currentDir}
                    </span>
                    {isProcessing && (
                        <span className="text-[10px] text-purple-400 animate-pulse shrink-0">
                            ⏳
                        </span>
                    )}
                </div>
                <div className="flex items-center gap-2 shrink-0">
                    <button
                        onClick={clearTerminal}
                        className="text-gray-600 hover:text-red-400 text-xs px-2 py-1 rounded hover:bg-red-500/10 transition-all"
                        title="Clear terminal"
                    >
                        Clear
                    </button>
                </div>
            </div>
            
            {/* Quick Command Buttons - Fixed height */}
            <div className="flex gap-1 px-3 py-2 bg-black/30 border-b border-red-500/10 overflow-x-auto shrink-0">
                {quickCommands.map((qc, i) => (
                    <button
                        key={i}
                        onClick={() => qc.cmd === 'clear' ? clearTerminal() : executeCommand(qc.cmd)}
                        disabled={isProcessing}
                        className="text-[10px] px-2 py-1 rounded border border-red-500/20 
                        text-red-400/60 hover:text-red-300 hover:border-red-500/40 
                        hover:bg-red-500/10 transition-all disabled:opacity-30 whitespace-nowrap shrink-0"
                    >
                        {qc.label}
                    </button>
                ))}
            </div>
            
            {/* Terminal History - Takes remaining space, scrolls */}
            <div 
                className="flex-1 overflow-y-auto overflow-x-hidden p-4 space-y-1 min-h-0 font-mono text-sm scrollbar-hide"
                onClick={() => inputRef.current?.focus()}
            >
                {/* Welcome Message */}
                <div className="text-xs text-gray-600 mb-3 pb-2 border-b border-gray-800/50">
                    <div className="flex items-center gap-2">
                        <Terminal size={12} className="text-red-600 shrink-0" />
                        <span className="text-red-600/70 shrink-0">Scarlett AI Terminal v2.0</span>
                    </div>
                    <div className="mt-1 text-gray-700">
                        Connected to AI system • Type <span className="text-red-500">help</span> for commands
                    </div>
                    <div className="text-gray-700 truncate">
                        Directory: <span className="text-red-500">{currentDir}</span>
                    </div>
                </div>

                {history.map((entry, i) => (
                    <div key={i} className="space-y-0.5 w-full overflow-hidden">
                        {entry.type === 'command' ? (
                            <div className="flex items-center gap-2 text-purple-400/80 py-0.5">
                                <ChevronRight size={12} className="text-red-600 shrink-0" />
                                <span className="text-xs text-gray-500 shrink-0">{entry.time}</span>
                                <span className="font-bold truncate">{entry.text}</span>
                            </div>
                        ) : entry.type === 'error' ? (
                            <div className="pl-4 text-red-400 py-0.5 border-l-2 border-red-500/30 ml-2">
                                <span className="text-red-500 font-bold mr-2 shrink-0">✗</span>
                                <pre className="inline font-mono whitespace-pre-wrap break-all overflow-hidden">
                                    {entry.text}
                                </pre>
                            </div>
                        ) : (
                            <div className="pl-4 text-red-300/80 py-0.5 border-l-2 border-red-500/20 ml-2">
                                {entry.isHtml ? (
                                    <div 
                                        className="break-words overflow-hidden"
                                        dangerouslySetInnerHTML={{ __html: sanitizeHtml(entry.text) }} 
                                    />
                                ) : (
                                    <pre className="font-mono whitespace-pre-wrap break-all overflow-hidden">
                                        {entry.text}
                                    </pre>
                                )}
                            </div>
                        )}
                    </div>
                ))}

                {isProcessing && (
                    <div className="flex items-center gap-2 text-purple-400 animate-pulse pl-4 py-1">
                        <span className="inline-block w-2 h-2 bg-purple-500 rounded-full animate-ping shrink-0"></span>
                        <span className="text-xs">Executing...</span>
                    </div>
                )}

                <div ref={historyEndRef} />
            </div>
            
            {/* Input Area - Fixed height */}
            <div className="p-3 border-t border-red-500/20 bg-black/40 shrink-0">
                <div className="flex items-center gap-2 bg-black/50 rounded-lg border border-red-500/20 px-3 py-2 focus-within:border-red-500/50 transition-all min-w-0">
                    <Folder size={14} className="text-red-600 shrink-0" />
                    <span className="text-xs text-red-500/70 shrink-0 truncate max-w-[120px]">{currentDir}</span>
                    <span className="text-red-600 font-bold shrink-0">❯</span>
                    <input
                        ref={inputRef}
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => {
                            handleKeyDown(e);
                            if (e.key === 'Enter') handleExecute(e);
                        }}
                        className="flex-1 bg-transparent text-red-300 text-sm outline-none border-none placeholder-gray-700 font-mono min-w-0"
                        placeholder="Type a command..."
                        disabled={isProcessing}
                        spellCheck={false}
                        autoComplete="off"
                    />
                </div>
            </div>
        </div>
    );
};

export default CmdWindow;