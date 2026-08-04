import MusicWindow from './components/MusicWindow';
import CadWindow from './components/CadWindow';
import KasaWindow from './components/KasaWindow';
import DoorWindow from './components/DoorWindow';
import PrinterWindow from './components/PrinterWindow';
import BrowserWindow from './components/BrowserWindow';
import ChessWindow from './components/ChessWindow';

// Registry of all available UI plugins
export const UI_PLUGINS = {
    music: MusicWindow,
    cad: CadWindow,
    kasa: KasaWindow,
    door: DoorWindow,
    printer: PrinterWindow,
    browser: BrowserWindow,
    chess: ChessWindow,
    // Add new plugins here...
};