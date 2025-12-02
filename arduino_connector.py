# arduino_connector.py - исправленная версия
import serial
import time
import json
import threading

class ArduinoConnector:
    def __init__(self, port='COM3', baudrate=9600):
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.connected = False
        self.room_states = {
            'living_room': False,
            'kitchen': False,
            'bedroom': False,
            'bathroom': False,
            'hallway': False
        }
        self.callbacks = []
        
    def connect(self):
        """Подключиться к Arduino"""
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            time.sleep(2)  # Ждем инициализации Arduino
            self.connected = True
            print(f"✅ Подключено к Arduino на порту {self.port}")
            
            # Запускаем поток для чтения данных
            self.read_thread = threading.Thread(target=self._read_serial, daemon=True)
            self.read_thread.start()
            
            # Отправляем тестовый пинг
            self.send_ping()
            time.sleep(1)
            
            # Запрашиваем текущий статус
            self.get_status()
            
            return True
        except Exception as e:
            print(f"❌ Ошибка подключения: {e}")
            self.connected = False
            return False
    
    def disconnect(self):
        """Отключиться от Arduino"""
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.connected = False
    
    def send_command(self, command):
        """Отправить команду на Arduino"""
        if not self.connected or not self.ser:
            print(f"❌ Не подключено к Arduino")
            return False
        
        try:
            # Arduino ожидает текстовые команды, а не JSON
            cmd_str = str(command) + '\n'
            self.ser.write(cmd_str.encode())
            print(f"📤 Отправлено: {cmd_str.strip()}")
            return True
        except Exception as e:
            print(f"❌ Ошибка отправки: {e}")
            self.connected = False
            return False
    
    def send_ping(self):
        """Отправить ping на Arduino"""
        self.send_command("PING")
    
    def turn_on_room(self, room_name):
        """Включить комнату"""
        # Преобразуем имя комнаты в формат команды Arduino
        room_upper = room_name.upper().replace(" ", "_")
        cmd = f"{room_upper}_ON"
        
        if self.send_command(cmd):
            self.room_states[room_name] = True
            self._notify_callbacks('room_changed', room_name, True)
            return True
        return False
    
    def turn_off_room(self, room_name):
        """Выключить комнату"""
        room_upper = room_name.upper().replace(" ", "_")
        cmd = f"{room_upper}_OFF"
        
        if self.send_command(cmd):
            self.room_states[room_name] = False
            self._notify_callbacks('room_changed', room_name, False)
            return True
        return False
    
    def toggle_room(self, room_name):
        """Переключить комнату"""
        if self.room_states[room_name]:
            return self.turn_off_room(room_name)
        else:
            return self.turn_on_room(room_name)
    
    def all_on(self):
        """Включить все комнаты"""
        if self.send_command("ALL_ON"):
            for room in self.room_states:
                self.room_states[room] = True
            self._notify_callbacks('all_changed', True)
            return True
        return False
    
    def all_off(self):
        """Выключить все комнаты"""
        if self.send_command("ALL_OFF"):
            for room in self.room_states:
                self.room_states[room] = False
            self._notify_callbacks('all_changed', False)
            return True
        return False
    
    def get_status(self):
        """Запросить статус всех комнат"""
        return self.send_command("STATUS")
    
    def get_stats(self):
        """Запросить статистику потребления"""
        return self.send_command("STATS")
    
    def _read_serial(self):
        """Чтение данных из Serial порта"""
        buffer = ""
        while self.connected and self.ser and self.ser.is_open:
            try:
                if self.ser.in_waiting:
                    data = self.ser.read(self.ser.in_waiting).decode('utf-8', errors='ignore')
                    buffer += data
                    
                    # Обработка полных строк
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        line = line.strip()
                        if line:
                            self._process_received_data(line)
                
                time.sleep(0.01)
            except Exception as e:
                print(f"❌ Ошибка чтения: {e}")
                self.connected = False
                break
    
    def _process_received_data(self, data):
        """Обработка полученных данных"""
        print(f"📥 Получено от Arduino: {data}")
        
        # Обработка ответов от Arduino
        if data == "PONG":
            print("✅ Arduino отвечает на ping")
            self._notify_callbacks('ping_received')
            
        elif data.startswith("STATUS:"):
            self._parse_status(data)
            
        elif data.startswith("STATS:"):
            print(f"📊 Статистика: {data}")
            self._notify_callbacks('stats_updated', data)
            
        elif data.startswith("QUICK:"):
            print(f"⚡ Быстрая статистика: {data}")
            self._notify_callbacks('quick_stats', data)
            
        elif "ERROR" in data:
            print(f"⚠ Ошибка Arduino: {data}")
            self._notify_callbacks('error', data)
            
        elif data == "ARDUINO READY":
            print("✅ Arduino готов к работе")
            
        elif data in ["ALL_ROOMS_ON", "ALL_ROOMS_OFF"]:
            state = (data == "ALL_ROOMS_ON")
            for room in self.room_states:
                self.room_states[room] = state
            self._notify_callbacks('all_changed', state)
            
        elif ":ON" in data or ":OFF" in data:
            # Пример: "LIVING_ROOM:ON"
            try:
                room, state = data.split(":")
                room_lower = room.lower().replace("_", " ")
                
                # Маппинг названий комнат
                room_mapping = {
                    'living room': 'living_room',
                    'kitchen': 'kitchen',
                    'bedroom': 'bedroom',
                    'bathroom': 'bathroom',
                    'hallway': 'hallway'
                }
                
                if room_lower in room_mapping:
                    room_key = room_mapping[room_lower]
                    self.room_states[room_key] = (state == "ON")
                    self._notify_callbacks('room_changed', room_key, state == "ON")
            except:
                pass
    
    def _parse_status(self, status_str):
        """Разбор строки статуса"""
        try:
            # Пример: STATUS:LIVING_ROOM:1,KITCHEN:0,...
            status_data = status_str[7:]  # Убираем "STATUS:"
            parts = status_data.split(',')
            
            for part in parts:
                if ':' in part:
                    room, state = part.split(':')
                    room_lower = room.lower().replace("_", " ")
                    
                    # Маппинг названий комнат
                    room_mapping = {
                        'living room': 'living_room',
                        'kitchen': 'kitchen', 
                        'bedroom': 'bedroom',
                        'bathroom': 'bathroom',
                        'hallway': 'hallway'
                    }
                    
                    if room_lower in room_mapping:
                        room_key = room_mapping[room_lower]
                        self.room_states[room_key] = (state == '1')
            
            print(f"✓ Статус обновлен: {self.room_states}")
            self._notify_callbacks('status_updated', self.room_states)
            
        except Exception as e:
            print(f"Ошибка парсинга статуса: {e}")
    
    def add_callback(self, callback):
        """Добавить callback-функцию для уведомлений"""
        self.callbacks.append(callback)
    
    def _notify_callbacks(self, event_type, *args, **kwargs):
        """Уведомить все callback-функции"""
        for callback in self.callbacks:
            try:
                callback(event_type, *args, **kwargs)
            except Exception as e:
                print(f"Ошибка в callback: {e}")