# cmd_agent.py - Fixed Version
import os
import subprocess
import platform
import shlex

class CmdAgent:
    def __init__(self, ai_function=None):
        self.current_dir = os.getcwd()
        self.ai_function = ai_function
        
        # دستورات خطرناک
        self.blocked_patterns = [
            'rm -rf /', 'del /f /s /q C:\\', 'format C:', 'format /',
            'shutdown /s', 'shutdown -h', 'reboot', 'init 0', 'init 6',
            'dd if=/dev/zero', 'mkfs.', ':(){ :|:& };:',
        ]
        
        # دستورات تعاملی که نباید مستقیم اجرا بشن
        self.interactive_commands = [
            'ipython', 'python', 'python3', 'node', 'bash', 'sh', 
            'zsh', 'fish', 'cmd', 'powershell', 'mysql', 'psql',
            'sqlite3', 'redis-cli', 'mongo', 'vim', 'vi', 'nano',
            'emacs', 'top', 'htop', 'less', 'more', 'man'
        ]
        
        # دستورات داخلی
        self.internal_commands = ['cd', 'clear', 'help', 'status']
    
    def is_dangerous(self, command):
        command_lower = command.lower().strip()
        for pattern in self.blocked_patterns:
            if pattern.lower() in command_lower:
                return True
        return False
    
    def is_interactive(self, command):
        """تشخیص دستورات تعاملی"""
        cmd_name = command.strip().split()[0].lower() if command.strip() else ''
        
        # چک کردن با مسیر کامل
        cmd_base = os.path.basename(cmd_name).lower()
        
        if cmd_base in self.interactive_commands:
            # اگه آرگومان داشته باشه (مثل python script.py) تعاملی نیست
            parts = command.strip().split()
            if len(parts) > 1:
                # چک کن آرگومان اول فایل نیست (-i, -c و... هم تعاملی نیستن)
                first_arg = parts[1]
                if first_arg in ['-i', '--interactive']:
                    return True  # تعاملی
                # اگه فایل یا آرگومان داره، غیرتعاملیه
                return False
            # بدون آرگومان = تعاملی
            return True
        
        return False
    
    async def execute_command(self, command):
        command = command.strip()
        if not command:
            return {'output': '', 'current_dir': self._get_display_dir()}
        
        # چک امنیتی
        if self.is_dangerous(command):
            return {'error': '⚠️ DANGEROUS COMMAND BLOCKED!'}
        
        cmd_name = command.split()[0].lower()
        
        # دستورات داخلی
        if cmd_name == 'clear':
            return {'output': '', 'clear': True}
        
        if cmd_name == 'help':
            return self.get_help()
        
        if cmd_name == 'status':
            return await self.get_status()
        
        if cmd_name == 'cd':
            return self._handle_cd(command)
        
        # چک دستورات تعاملی
        if self.is_interactive(command):
            return {'error': f'❌ Interactive command blocked: {cmd_name}\n\n' +
                           f'Interactive shells (python, node, ipython, etc.) cannot run here.\n' +
                           f'Try: {cmd_name} script.py  or  {cmd_name} -c "code"  or  {cmd_name} --version'}
        
        # اجرای دستور
        return await self._execute_command(command)
    
    async def _execute_command(self, command):
        """اجرای دستور با timeout"""
        try:
            if platform.system() == 'Windows':
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    shell=True,
                    cwd=self.current_dir,
                    stdin=subprocess.DEVNULL,  # 👈 این مهمه! ورودی رو می‌بنده
                    env={**os.environ, 'PYTHONUNBUFFERED': '1'}
                )
            else:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    shell=True,
                    executable='/bin/bash',
                    cwd=self.current_dir,
                    stdin=subprocess.DEVNULL,  # 👈 جلوگیری از تعاملی شدن
                    env={**os.environ, 'PYTHONUNBUFFERED': '1', 'TERM': 'dumb'}
                )
            
            output = result.stdout or ''
            if result.stderr:
                output += ('\n' + result.stderr) if output else result.stderr
            
            self.current_dir = os.getcwd()
            
            return {
                'output': output.rstrip() or 'Command ran successfully',
                'current_dir': self._get_display_dir(),
                'exit_code': result.returncode
            }
            
        except subprocess.TimeoutExpired:
            return {'error': f'⏱️ Command timed out (30s): {command[:50]}...'}
        except Exception as e:
            return {'error': f'Error: {str(e)}'}
    
    def _handle_cd(self, command):
        """مدیریت دستور cd با پشتیبانی کامل از ویندوز و لینوکس"""
        try:
            # جدا کردن مسیر از دستور
            # پشتیبانی از: cd /d E:, cd E:, cd "path", cd /path, cd ..
            parts = command.split(maxsplit=1)
            
            if len(parts) < 2:
                # cd بدون آرگومان
                os.chdir(os.path.expanduser('~'))
                self.current_dir = os.getcwd()
                return {
                    'output': '',
                    'current_dir': self._get_display_dir()
                }
            
            path = parts[1].strip()
            
            # حذف کوتیشن‌ها
            if (path.startswith('"') and path.endswith('"')) or \
            (path.startswith("'") and path.endswith("'")):
                path = path[1:-1]
            
            # پشتیبانی از سینتکس CMD ویندوز
            if platform.system() == 'Windows':
                # cd /d E:/path
                if path.lower().startswith('/d'):
                    path = path[2:].strip()
            
            # تبدیل / به \ در ویندوز
            if platform.system() == 'Windows':
                # فقط درایو؟ (مثل E:)
                if len(path) == 2 and path[1] == ':' and path[0].isalpha():
                    path = path + '\\'
                path = path.replace('/', '\\')
            
            # تبدیل ~ به مسیر home
            path = os.path.expanduser(path)
            
            # مسیر نسبی رو مطلق کن
            if not os.path.isabs(path):
                path = os.path.join(self.current_dir, path)
            
            # نرمال‌سازی (حذف .. و . های اضافی)
            path = os.path.normpath(path)
            
            # بررسی وجود مسیر
            if not os.path.exists(path):
                return {'error': f'Directory not found: {path}'}
            if not os.path.isdir(path):
                return {'error': f'Not a directory: {path}'}
            
            # تغییر دایرکتوری
            os.chdir(path)
            self.current_dir = os.getcwd()
            
            return {
                'output': '',
                'current_dir': self._get_display_dir()
            }
            
        except PermissionError:
            return {'error': f'Permission denied: {path if "path" in locals() else "unknown"}'}
        except Exception as e:
            return {'error': f'cd error: {str(e)}'}
    
    def _get_display_dir(self):
        if platform.system() == 'Windows':
            # ویندوز: D:\path\to\folder
            return self.current_dir
        else:
            # لینوکس: ~/path یا /full/path
            home = os.path.expanduser('~')
            if self.current_dir.startswith(home):
                return '~' + self.current_dir[len(home):]
            return self.current_dir
    
    def get_help(self):
        return {'output': """
╔══════════════════════ SCARLETT TERMINAL ═══════════════════════╗
║                                                                ║
║  ✅ All system commands work: ls, dir, cat, echo, git, pip...  ║
║  ❌ Interactive shells blocked: python, node, ipython, vim...  ║
║                                                                ║
║  For Python/Node, pass a script or use -c:                    ║
║    python script.py                                            ║
║    python -c "print('hello')"                                  ║
║    node script.js                                              ║
║    node -e "console.log('hi')"                                 ║
║                                                                ║
║  Special commands:                                             ║
║    cd <dir>     Change directory                               ║
║    clear        Clear screen                                   ║
║    help         This help                                      ║
║    status       System info                                    ║
║                                                                ║
╚══════════════════════════════════════════════════════════════════╝
        """}
    
    async def get_status(self):
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=0.3)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage(self.current_dir)
            
            return {'output': f"""
System: {platform.system()} {platform.release()}
CPU: {cpu}% | Cores: {psutil.cpu_count()}
Memory: {mem.percent}% ({mem.used//(1024**3)}/{mem.total//(1024**3)} GB)
Disk: {disk.percent}% ({disk.free//(1024**3)} GB free)
Python: {platform.python_version()}
Dir: {self.current_dir}
            """.strip()}
        except ImportError:
            return {'output': f"System: {platform.system()} {platform.release()}\\nPython: {platform.python_version()}\\nDir: {self.current_dir}\\n\\n💡 pip install psutil for more info"}
    
    def get_autocomplete(self, partial):
        if not partial:
            return []
        
        suggestions = set()
        
        for cmd in self.internal_commands:
            if cmd.startswith(partial):
                suggestions.add(cmd)
        
        for path in os.environ.get('PATH', '').split(os.pathsep):
            try:
                for file in os.listdir(path):
                    if file.startswith(partial):
                        full = os.path.join(path, file)
                        if os.access(full, os.X_OK) and not os.path.isdir(full):
                            suggestions.add(file)
            except (FileNotFoundError, PermissionError):
                continue
        
        return sorted(suggestions)[:15]