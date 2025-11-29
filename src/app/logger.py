#type: ignore

import logging
import sys
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.text import Text
from rich.columns import Columns
from rich import box
from rich.table import Table
import threading
from typing import Dict, List, Deque
from collections import deque
import re
import time

class RichTradingVisualizer:
    """Визуализатор логов торговли с использованием Rich"""
    
    def __init__(self, exchanges: List[str] = None):
        self.console = Console()
        self.exchanges = exchanges or ['okx', 'bitget', 'kucoin', 'htx']
        self.logs: Dict[str, Deque] = {exchange: deque(maxlen=20) for exchange in self.exchanges}
        self.stats: Dict[str, Dict] = {exchange: {'buys': 0, 'sells': 0, 'errors': 0, 'warnings': 0} for exchange in self.exchanges}
        self.lock = threading.Lock()
        self.is_running = True
        
        # Цвета для бирж
        self.exchange_colors = {
            'okx': 'cyan',
            'bitget': 'green', 
            'kucoin': 'yellow',
            'htx': 'red'
        }
        
        # Цвета для уровней логов
        self.level_colors = {
            'INFO': 'green',
            'BUY': 'bright_green',
            'SELL': 'orange3',
            'SUCCESS': 'bright_green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'bold red',
            'DEBUG': 'blue'
        }
    
    def parse_log_line(self, line: str) -> dict:
        """Парсит строку лога и извлекает информацию"""
        try:
            if not line.strip():
                return None
                
            # Упрощенный парсинг для стандартного формата логов
            pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) - (.*?) - (.*?) - (.*)'
            match = re.match(pattern, line.strip())
            if match:
                timestamp, logger_name, level, message = match.groups()
                
                # Определяем биржу по имени логгера
                exchange = None
                for exch in self.exchanges:
                    if exch in logger_name.lower():
                        exchange = exch
                        break
                
                # Если не нашли в имени логгера, ищем в сообщении
                if not exchange:
                    for exch in self.exchanges:
                        if exch in message.lower():
                            exchange = exch
                            break
                
                # Если все еще не нашли, пробуем по контексту
                if not exchange:
                    if 'okx' in logger_name.lower() or 'okx' in message.lower():
                        exchange = 'okx'
                    elif 'bitget' in logger_name.lower() or 'bitget' in message.lower():
                        exchange = 'bitget'
                    elif 'kucoin' in logger_name.lower() or 'kucoin' in message.lower():
                        exchange = 'kucoin'
                    elif 'htx' in logger_name.lower() or 'htx' in message.lower():
                        exchange = 'htx'
                    else:
                        # Если не можем определить, используем первую биржу
                        exchange = self.exchanges[0]
                
                return {
                    'exchange': exchange,
                    'level': level,
                    'message': message,
                    'timestamp': timestamp,
                    'full_line': line
                }
        except Exception as e:
            self.console.print(f"[red]Error parsing log: {e}[/red]")
        return None
    
    def add_log(self, line: str):
        """Добавляет лог в соответствующую колонку и обновляет статистику"""
        log_data = self.parse_log_line(line)
        if log_data and log_data['exchange'] in self.exchanges:
            with self.lock:
                exchange = log_data['exchange']
                self.logs[exchange].append(log_data)
                
                # Обновляем статистику
                level = log_data['level']
                if level == 'BUY':
                    self.stats[exchange]['buys'] += 1
                elif level == 'SELL':
                    self.stats[exchange]['sells'] += 1
                elif level == 'ERROR':
                    self.stats[exchange]['errors'] += 1
                elif level == 'WARNING':
                    self.stats[exchange]['warnings'] += 1
                elif level == 'CRITICAL':
                    self.stats[exchange]['errors'] += 1
    
    def create_exchange_panel(self, exchange: str) -> Panel:
        """Создает панель для конкретной биржи"""
        # Статистика
        stats = self.stats[exchange]
        stats_text = f"BUY: {stats['buys']} | SELL: {stats['sells']} | ERR: {stats['errors']}"
        
        # Основное содержимое
        content = Text()
        with self.lock:
            logs_list = list(self.logs[exchange])
        
        if not logs_list:
            content.append("Waiting for logs...\n", style="dim italic")
        else:
            for log in logs_list[-15:]:  # Показываем последние 15 записей
                # Время (только часы:минуты:секунды)
                time_str = log['timestamp'][11:19]
                content.append(f"{time_str} ", style="dim")
                
                # Уровень
                level_style = self.level_colors.get(log['level'], 'white')
                level_display = log['level'][:4]  # Короткое название уровня
                content.append(f"{level_display:<4} ", style=level_style)
                
                # Сообщение (обрезаем если слишком длинное)
                message = log['message']
                if len(message) > 35:
                    message = message[:32] + "..."
                content.append(f"{message}\n", style="white")
        
        # Создаем панель
        border_color = self.exchange_colors.get(exchange, 'white')
        return Panel(
            content,
            title=f"[bold {border_color}]{exchange.upper()}[/bold {border_color}]",
            subtitle=f"[dim]{stats_text}[/dim]",
            title_align="center",
            box=box.ROUNDED,
            border_style=border_color,
            height=25
        )
    
    def create_status_table(self) -> Table:
        """Создает таблицу со статусом бирж"""
        table = Table(show_header=True, header_style="bold magenta", box=box.SIMPLE)
        table.add_column("Exchange", width=8)
        table.add_column("Status", width=12)
        table.add_column("Last Activity", width=12)
        table.add_column("Stats", width=20)
        
        with self.lock:
            for exchange in self.exchanges:
                logs_list = list(self.logs[exchange])
                stats = self.stats[exchange]
                
                # Определяем статус
                if any(log['level'] in ['ERROR', 'CRITICAL'] for log in logs_list[-3:]):
                    status = "❌ ERROR"
                    status_style = "red"
                elif any(log['level'] in ['BUY', 'SELL'] for log in logs_list[-3:]):
                    status = "🟢 TRADING"
                    status_style = "green"
                elif logs_list:
                    if any(log['level'] == 'WARNING' for log in logs_list[-3:]):
                        status = "⚠️ WARNING"
                        status_style = "yellow"
                    else:
                        status = "🔵 CONNECTED"
                        status_style = "blue"
                else:
                    status = "⚪ OFFLINE"
                    status_style = "grey70"
                
                # Последняя активность
                last_activity = "Never"
                if logs_list:
                    last_log = logs_list[-1]
                    last_activity = last_log['timestamp'][11:19]
                
                # Статистика
                stats_display = f"B:{stats['buys']} S:{stats['sells']} E:{stats['errors']}"
                
                table.add_row(
                    f"[{self.exchange_colors[exchange]}]{exchange.upper()}[/{self.exchange_colors[exchange]}]",
                    f"[{status_style}]{status}[/{status_style}]",
                    f"[dim]{last_activity}[/dim]",
                    stats_display
                )
        
        return table
    
    def display(self):
        """Основной метод отображения"""
        try:
            # Очищаем консоль и показываем Rich интерфейс
            self.console.clear()
            self.console.print("[bold green]🚀 Trading Monitor Started[/bold green]")
            self.console.print("[dim]Monitoring exchanges in real-time...[/dim]\n")
            
            with Live(refresh_per_second=4, screen=True, console=self.console) as live:
                while self.is_running:
                    try:
                        # Создаем панели для бирж
                        exchange_panels = [self.create_exchange_panel(exchange) for exchange in self.exchanges]
                        
                        # Создаем layout
                        layout = [
                            self.create_status_table(),
                            Columns(exchange_panels, equal=True, expand=True)
                        ]
                        
                        live.update(layout)
                        time.sleep(0.25)
                        
                    except Exception as e:
                        self.console.print(f"[red]Display error: {e}[/red]")
                        break
                        
        except KeyboardInterrupt:
            self.console.print("\n[bold yellow]📊 Trading monitor stopped[/bold yellow]")
        except Exception as e:
            self.console.print(f"[red]Visualizer error: {e}[/red]")
    
    def stop(self):
        """Остановка визуализатора"""
        self.is_running = False

class TradingLogger(logging.Logger):
    """Кастомный логгер для торговых операций"""
    
    BUY = 24
    SELL = 25
    SUCCESS_LEVEL = 35
    
    def __init__(self, name):
        super().__init__(name)
        
        logging.addLevelName(self.BUY, "BUY")
        logging.addLevelName(self.SELL, "SELL")
        logging.addLevelName(self.SUCCESS_LEVEL, "SUCCESS")
    
    def buy(self, symbol, price, quantity, exchange="", *args, **kwargs):
        message = f"BUY ORDER: {symbol} | Price: {price} | Quantity: {quantity}"
        if exchange:
            message = f"[{exchange.upper()}] {message}"
        if self.isEnabledFor(self.BUY):
            self._log(self.BUY, message, args, **kwargs)
    
    def sell(self, symbol, price, quantity, exchange="", *args, **kwargs):
        message = f"SELL ORDER: {symbol} | Price: {price} | Quantity: {quantity}"
        if exchange:
            message = f"[{exchange.upper()}] {message}"
        if self.isEnabledFor(self.SELL):
            self._log(self.SELL, message, args, **kwargs)
    
    def success(self, message, exchange="", *args, **kwargs):
        if exchange:
            message = f"[{exchange.upper()}] {message}"
        if self.isEnabledFor(self.SUCCESS_LEVEL):
            self._log(self.SUCCESS_LEVEL, message, args, **kwargs)

# Устанавливаем кастомный логгер
logging.setLoggerClass(TradingLogger)

class RichLogHandler(logging.Handler):
    """Обработчик логов для Rich визуализатора"""
    
    def __init__(self, visualizer):
        super().__init__()
        self.visualizer = visualizer
    
    def emit(self, record):
        try:
            formatter = self.formatter or logging.Formatter(
                fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            log_line = formatter.format(record)
            self.visualizer.add_log(log_line)
        except Exception:
            self.handleError(record)

def setup_trading_logging(visualizer=None):
    """Настройка логирования"""
    root_logger = logging.getLogger()
    
    # Очищаем существующие обработчики
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Форматтер с цветами
    class TradingFormatter(logging.Formatter):
        LEVEL_COLORS = {
            logging.DEBUG: "\033[38;5;51m",
            logging.INFO: "\033[38;5;46m",
            TradingLogger.BUY: "\033[38;5;42m",
            TradingLogger.SELL: "\033[38;5;208m",
            logging.WARNING: "\033[38;5;226m",
            TradingLogger.SUCCESS_LEVEL: "\033[38;5;82m",
            logging.ERROR: "\033[38;5;196m",
            logging.CRITICAL: "\033[38;5;201m",
        }
        RESET = "\033[0m"
        
        def format(self, record):
            level_color = self.LEVEL_COLORS.get(record.levelno, self.RESET)
            time_part = f"\033[38;5;245m{self.formatTime(record, self.datefmt)}{self.RESET}"
            name_part = f"\033[38;5;39m{record.name}{self.RESET}"
            level_part = f"{level_color}{record.levelname}{self.RESET}"
            message_part = f"\033[97m{record.getMessage()}{self.RESET}"
            return f"{time_part} - {name_part} - {level_part} - {message_part}"
    
    # Обычный обработчик для консоли
    console_handler = logging.StreamHandler(sys.stdout)
    formatter = TradingFormatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Rich обработчик если передан визуализатор
    if visualizer:
        rich_handler = RichLogHandler(visualizer)
        rich_handler.setFormatter(formatter)
        root_logger.addHandler(rich_handler)
    
    root_logger.setLevel(logging.INFO)

def start_trading_monitor():
    """Запуск монитора торговли"""
    # Создаем визуализатор
    visualizer = RichTradingVisualizer()
    
    # Настраиваем логирование с Rich обработчиком
    setup_trading_logging(visualizer)
    
    # Запускаем отображение в отдельном потоке
    display_thread = threading.Thread(target=visualizer.display, daemon=True)
    display_thread.start()
    
    # Даем время для инициализации Rich
    time.sleep(1)
    
    return visualizer

