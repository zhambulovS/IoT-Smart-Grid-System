from flask import Flask, redirect, render_template_string, jsonify, url_for, request, session
import time
import random
import threading
from datetime import datetime, timedelta
import json
import os
import hashlib
from functools import wraps
from arduino_connector import ArduinoConnector
app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Замените на свой секретный ключ

arduino = ArduinoConnector('COM3', 9600)
arduino_connected = arduino.connect()

# Добавьте callback для обновления состояния в веб-интерфейсе
def arduino_callback(event_type, *args):
    if event_type == 'room_changed':
        room_name, state = args
        if room_name in current_state['lamps']:
            current_state['lamps'][room_name]['state'] = state
            print(f"✓ Комната {room_name} обновлена: {state}")
    elif event_type == 'status_updated':
        rooms_state = args[0]
        for room_name, state in rooms_state.items():
            if room_name in current_state['lamps']:
                current_state['lamps'][room_name]['state'] = state

arduino.add_callback(arduino_callback)

current_state = {
    'lamps': {
        'living_room': {'state': False, 'power': 0.1, 'name': 'Гостиная', 'icon': 'fa-couch', 'color': '#2196F3'},
        'kitchen': {'state': False, 'power': 0.15, 'name': 'Кухня', 'icon': 'fa-utensils', 'color': '#FF9800'},
        'bedroom': {'state': False, 'power': 0.08, 'name': 'Спальня', 'icon': 'fa-bed', 'color': '#9C27B0'},
        'bathroom': {'state': False, 'power': 0.06, 'name': 'Ванная', 'icon': 'fa-bath', 'color': '#00BCD4'},
        'hallway': {'state': False, 'power': 0.05, 'name': 'Коридор', 'icon': 'fa-door-closed', 'color': '#795548'}
    },
    'energy': {
        'total_today': 0.0,
        'total_month': 0.0,
        'current_power': 0.0,
        'peak_today': 0.0,
        'cost_today': 0.0,
        'cost_month': 0.0,
        'tariff': 25.0
    },
    'stats': {
        'hours_on_today': {room: 0.0 for room in ['living_room', 'kitchen', 'bedroom', 'bathroom', 'hallway']},
        'savings_today': 0.0
    },
    'system': {
        'auto_save': True,
        'data_interval': 5,
        'theme': 'dark',
        'language': 'ru',
        'notifications': True
    }
}

# Простые настройки для демо
DEMO_USERS = {
    'admin': hashlib.sha256('admin123'.encode()).hexdigest(),
    'user': hashlib.sha256('user123'.encode()).hexdigest()
}

# Конфигурация
CONFIG = {
    'base_consumption': 0.05,
    'data_file': 'energy_data.json',
    'settings_file': 'system_settings.json'
}

def load_data():
    """Загрузка данных из файлов"""
    # Загрузка данных энергии
    if os.path.exists(CONFIG['data_file']):
        try:
            with open(CONFIG['data_file'], 'r') as f:
                data = json.load(f)
                if 'energy' in data:
                    current_state['energy']['total_month'] = data['energy'].get('total_month', 0.0)
                    current_state['energy']['cost_month'] = data['energy'].get('cost_month', 0.0)
                    current_state['energy']['tariff'] = data['energy'].get('tariff', 25.0)
            print("✓ Данные энергии загружены")
        except:
            print("⚠ Ошибка загрузки данных энергии")
    
    # Загрузка настроек системы
    if os.path.exists(CONFIG['settings_file']):
        try:
            with open(CONFIG['settings_file'], 'r') as f:
                settings = json.load(f)
                current_state['system'].update(settings.get('system', {}))
                
                # Обновление настроек комнат
                for room_id, room_data in settings.get('lamps', {}).items():
                    if room_id in current_state['lamps']:
                        current_state['lamps'][room_id].update(room_data)
            print("✓ Настройки системы загружены")
        except:
            print("⚠ Ошибка загрузки настроек системы")

def save_data():
    """Сохранение всех данных"""
    try:
        # Сохраняем данные энергии
        with open(CONFIG['data_file'], 'w') as f:
            json.dump(current_state, f, indent=2)
        
        # Сохраняем настройки отдельно
        settings_to_save = {
            'lamps': current_state['lamps'],
            'system': current_state['system'],
            'energy': {'tariff': current_state['energy']['tariff']}
        }
        
        with open(CONFIG['settings_file'], 'w') as f:
            json.dump(settings_to_save, f, indent=2)
            
        print("✓ Данные сохранены")
    except Exception as e:
        print(f"⚠ Ошибка сохранения данных: {e}")

# HTML шаблон с настройками
HTML = '''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IoT Smart Energy Monitor</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <link href="https://fonts.googleapis.com/css2?family=Exo+2:wght@300;400;600;700&family=Roboto:wght@300;400;500&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels"></script>
    <style>
        :root {
            --primary: #2196F3;
            --primary-dark: #1976D2;
            --secondary: #4CAF50;
            --danger: #F44336;
            --warning: #FF9800;
            --dark: #1A237E;
            --light: #E3F2FD;
            --gray: #607D8B;
            --sidebar-width: 250px;
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Roboto', 'Exo 2', sans-serif;
        }
        
        body {
            background: linear-gradient(135deg, #0d47a1 0%, #1a237e 100%);
            color: #fff;
            min-height: 100vh;
        }
        
        /* Top Navigation */
        .top-nav {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            padding: 15px 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            position: sticky;
            top: 0;
            z-index: 1000;
        }
        
        .logo {
            display: flex;
            align-items: center;
            gap: 15px;
        }
        
        .logo h1 {
            font-size: 1.8rem;
            background: linear-gradient(to right, #64B5F6, #2196F3);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .user-menu {
            display: flex;
            align-items: center;
            gap: 20px;
        }
        
        .nav-btn {
            background: rgba(255, 255, 255, 0.1);
            border: none;
            color: white;
            padding: 10px 20px;
            border-radius: 10px;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 10px;
            transition: all 0.3s;
        }
        
        .nav-btn:hover {
            background: rgba(255, 255, 255, 0.2);
            transform: translateY(-2px);
        }
        
        .user-info {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .user-avatar {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            background: var(--primary);
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        /* Main Layout */
        .main-container {
            display: flex;
            min-height: calc(100vh - 70px);
        }
        
        /* Sidebar */
        .sidebar {
            width: var(--sidebar-width);
            background: rgba(0, 0, 0, 0.2);
            padding: 20px;
            border-right: 1px solid rgba(255, 255, 255, 0.1);
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        
        .sidebar-item {
            padding: 15px;
            border-radius: 10px;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 15px;
            transition: all 0.3s;
            color: #BBDEFB;
            text-decoration: none;
        }
        
        .sidebar-item:hover {
            background: rgba(255, 255, 255, 0.1);
        }
        
        .sidebar-item.active {
            background: var(--primary);
            color: white;
        }
        
        .sidebar-section {
            margin-top: 20px;
            padding-top: 20px;
            border-top: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .sidebar-section h3 {
            font-size: 0.9rem;
            color: #90CAF9;
            margin-bottom: 10px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        /* Main Content */
        .content {
            flex: 1;
            padding: 30px;
            overflow-y: auto;
        }
        
        .content-section {
            display: none;
        }
        
        .content-section.active {
            display: block;
            animation: fadeIn 0.5s ease;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        /* Dashboard Cards */
        .dashboard-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 25px;
            margin-bottom: 30px;
        }
        
        .card {
            background: rgba(255, 255, 255, 0.08);
            backdrop-filter: blur(15px);
            border-radius: 20px;
            padding: 25px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            box-shadow: 0 15px 35px rgba(0, 0, 0, 0.2);
            transition: transform 0.3s, box-shadow 0.3s;
        }
        
        .card:hover {
            transform: translateY(-5px);
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
        }
        
        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        
        .card-title {
            font-size: 1.5rem;
            font-weight: 600;
            color: #BBDEFB;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .card-actions {
            display: flex;
            gap: 10px;
        }
        
        /* Rooms Grid */
        .rooms-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        
        .room-card {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 15px;
            padding: 20px;
            transition: all 0.3s;
            border: 2px solid transparent;
            position: relative;
        }
        
        .room-card.active {
            border-color: var(--secondary);
            background: rgba(76, 175, 80, 0.1);
        }
        
        .room-card:hover .room-actions {
            opacity: 1;
        }
        
        .room-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 15px;
        }
        
        .room-icon {
            width: 50px;
            height: 50px;
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.5rem;
            color: white;
        }
        
        .room-actions {
            position: absolute;
            top: 15px;
            right: 15px;
            opacity: 0;
            transition: opacity 0.3s;
            display: flex;
            gap: 5px;
        }
        
        .action-btn {
            background: rgba(255, 255, 255, 0.1);
            border: none;
            color: white;
            width: 35px;
            height: 35px;
            border-radius: 8px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.3s;
        }
        
        .action-btn:hover {
            background: rgba(255, 255, 255, 0.2);
            transform: scale(1.1);
        }
        
        /* Settings Page */
        .settings-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 25px;
        }
        
        .setting-group {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 15px;
            padding: 20px;
        }
        
        .setting-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .setting-item:last-child {
            border-bottom: none;
        }
        
        .setting-label {
            flex: 1;
        }
        
        .setting-label h4 {
            font-size: 1rem;
            margin-bottom: 5px;
            color: #BBDEFB;
        }
        
        .setting-label p {
            font-size: 0.9rem;
            color: #90CAF9;
        }
        
        .setting-control {
            width: 200px;
        }
        
        input[type="text"],
        input[type="number"],
        input[type="password"],
        select {
            width: 100%;
            padding: 10px 15px;
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 8px;
            color: white;
            font-size: 1rem;
        }
        
        input:focus, select:focus {
            outline: none;
            border-color: var(--primary);
            box-shadow: 0 0 0 2px rgba(33, 150, 243, 0.3);
        }
        
        /* Toggle Switch */
        .toggle {
            position: relative;
            display: inline-block;
            width: 60px;
            height: 30px;
        }
        
        .toggle input {
            opacity: 0;
            width: 0;
            height: 0;
        }
        
        .slider {
            position: absolute;
            cursor: pointer;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: #ccc;
            transition: .4s;
            border-radius: 34px;
        }
        
        .slider:before {
            position: absolute;
            content: "";
            height: 22px;
            width: 22px;
            left: 4px;
            bottom: 4px;
            background-color: white;
            transition: .4s;
            border-radius: 50%;
        }
        
        input:checked + .slider {
            background-color: var(--secondary);
        }
        
        input:checked + .slider:before {
            transform: translateX(30px);
        }
        
        /* Modal Windows */
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.8);
            z-index: 2000;
            align-items: center;
            justify-content: center;
        }
        
        .modal.active {
            display: flex;
            animation: fadeIn 0.3s ease;
        }
        
        .modal-content {
            background: linear-gradient(135deg, #1a237e 0%, #0d47a1 100%);
            border-radius: 20px;
            width: 90%;
            max-width: 500px;
            max-height: 90vh;
            overflow-y: auto;
            border: 1px solid rgba(255, 255, 255, 0.1);
            box-shadow: 0 25px 50px rgba(0, 0, 0, 0.5);
        }
        
        .modal-header {
            padding: 20px 30px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .modal-title {
            font-size: 1.5rem;
            font-weight: 600;
            color: #BBDEFB;
        }
        
        .close-modal {
            background: none;
            border: none;
            color: #90CAF9;
            font-size: 24px;
            cursor: pointer;
            width: 40px;
            height: 40px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.3s;
        }
        
        .close-modal:hover {
            background: rgba(255, 255, 255, 0.1);
        }
        
        .modal-body {
            padding: 30px;
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        .form-label {
            display: block;
            margin-bottom: 8px;
            color: #BBDEFB;
            font-weight: 500;
        }
        
        .form-row {
            display: flex;
            gap: 15px;
            margin-bottom: 15px;
        }
        
        .form-row .form-group {
            flex: 1;
            margin-bottom: 0;
        }
        
        .color-picker {
            display: flex;
            gap: 10px;
            align-items: center;
        }
        
        .color-option {
            width: 40px;
            height: 40px;
            border-radius: 8px;
            cursor: pointer;
            border: 3px solid transparent;
            transition: all 0.3s;
        }
        
        .color-option.selected {
            border-color: white;
            transform: scale(1.1);
        }
        
        .modal-footer {
            padding: 20px 30px;
            border-top: 1px solid rgba(255, 255, 255, 0.1);
            display: flex;
            justify-content: flex-end;
            gap: 15px;
        }
        
        .btn {
            padding: 12px 25px;
            border: none;
            border-radius: 10px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .btn-primary {
            background: var(--primary);
            color: white;
        }
        
        .btn-secondary {
            background: rgba(255, 255, 255, 0.1);
            color: white;
        }
        
        .btn-danger {
            background: var(--danger);
            color: white;
        }
        
        .btn-success {
            background: var(--secondary);
            color: white;
        }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.3);
        }
        
        /* Charts */
        .chart-container {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 15px;
            padding: 20px;
            margin-top: 20px;
            height: 300px;
        }
        
        /* Statistics Cards */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 25px;
        }
        
        .stat-card {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 15px;
            padding: 20px;
            text-align: center;
        }
        
        .stat-value {
            font-size: 2.2rem;
            font-weight: 700;
            margin: 10px 0;
            color: #64B5F6;
        }
        
        .stat-label {
            color: #B0BEC5;
            font-size: 0.9rem;
            margin-bottom: 5px;
        }
        
        /* Login Page */
        .login-container {
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            padding: 20px;
        }
        
        .login-box {
            background: rgba(255, 255, 255, 0.08);
            backdrop-filter: blur(15px);
            border-radius: 20px;
            padding: 40px;
            width: 100%;
            max-width: 400px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            box-shadow: 0 25px 50px rgba(0, 0, 0, 0.3);
        }
        
        .login-title {
            text-align: center;
            margin-bottom: 30px;
            color: #BBDEFB;
        }
        
        .login-form .form-group {
            margin-bottom: 25px;
        }
        
        /* Responsive */
        @media (max-width: 768px) {
            .sidebar {
                width: 70px;
                padding: 20px 10px;
            }
            
            .sidebar-item span {
                display: none;
            }
            
            .dashboard-grid {
                grid-template-columns: 1fr;
            }
            
            .rooms-grid {
                grid-template-columns: 1fr;
            }
            
            .settings-grid {
                grid-template-columns: 1fr;
            }
            
            .setting-item {
                flex-direction: column;
                align-items: flex-start;
                gap: 10px;
            }
            
            .setting-control {
                width: 100%;
            }
            
            .form-row {
                flex-direction: column;
                gap: 15px;
            }
        }
    </style>
</head>
<body>
    <!-- Login Page -->
    <div id="loginPage" class="login-container">
        <div class="login-box">
            <h1 class="login-title"><i class="fas fa-bolt"></i> Smart Energy System</h1>
            <form id="loginForm" class="login-form">
                <div class="form-group">
                    <label class="form-label">Логин</label>
                    <input type="text" id="loginUsername" required placeholder="Введите логин">
                </div>
                <div class="form-group">
                    <label class="form-label">Пароль</label>
                    <input type="password" id="loginPassword" required placeholder="Введите пароль">
                </div>
                <button type="submit" class="btn btn-primary" style="width: 100%;">
                    <i class="fas fa-sign-in-alt"></i> Войти
                </button>
            </form>
        </div>
    </div>
    
    <!-- Main Application -->
    <div id="appContainer" style="display: none;">
        <!-- Top Navigation -->
        <div class="top-nav">
            <div class="logo">
                <i class="fas fa-bolt fa-2x"></i>
                <h1>Smart Energy Monitor</h1>
            </div>
            <div class="user-menu">
                <div class="user-info">
                    <div class="user-avatar">
                        <i class="fas fa-user"></i>
                    </div>
                    <div>
                        <div id="currentUser">Администратор</div>
                        <div style="font-size: 0.8rem; color: #90CAF9;" id="currentTime">--:--:--</div>
                    </div>
                </div>
                <button class="nav-btn" onclick="logout()">
                    <i class="fas fa-sign-out-alt"></i> Выйти
                </button>
            </div>
        </div>
        
        <!-- Main Container -->
        <div class="main-container">
            <!-- Sidebar -->
            <div class="sidebar">
                <div class="sidebar-item active" onclick="showSection('dashboard')">
                    <i class="fas fa-tachometer-alt"></i>
                    <span>Панель управления</span>
                </div>
                
                <div class="sidebar-item" onclick="showSection('rooms')">
                    <i class="fas fa-home"></i>
                    <span>Управление комнатами</span>
                </div>
                
                <div class="sidebar-item" onclick="showSection('energy')">
                    <i class="fas fa-chart-line"></i>
                    <span>Энергопотребление</span>
                </div>
                
                <div class="sidebar-item" onclick="showSection('statistics')">
                    <i class="fas fa-chart-bar"></i>
                    <span>Статистика</span>
                </div>
                
                <div class="sidebar-section">
                    <h3>Настройки</h3>
                    <div class="sidebar-item" onclick="showSection('settings')">
                        <i class="fas fa-cog"></i>
                        <span>Настройки системы</span>
                    </div>
                    
                    <div class="sidebar-item" onclick="showSection('users')">
                        <i class="fas fa-users"></i>
                        <span>Пользователи</span>
                    </div>
                    
                    <div class="sidebar-item" onclick="showSection('logs')">
                        <i class="fas fa-history"></i>
                        <span>История действий</span>
                    </div>
                </div>
                
                <div class="sidebar-section">
                    <h3>Инструменты</h3>
                    <div class="sidebar-item" onclick="showReportModal()">
                        <i class="fas fa-file-export"></i>
                        <span>Экспорт отчета</span>
                    </div>
                    
                    <div class="sidebar-item" onclick="showBackupModal()">
                        <i class="fas fa-database"></i>
                        <span>Резервная копия</span>
                    </div>
                </div>
            </div>
            
            <!-- Main Content -->
            <div class="content">
                <!-- Dashboard Section -->
                <div id="dashboardSection" class="content-section active">
                    <div class="dashboard-grid">
                        <div class="card">
                            <div class="card-header">
                                <h2 class="card-title"><i class="fas fa-tachometer-alt"></i> Общая статистика</h2>
                            </div>
                            <div class="stats-grid">
                                <div class="stat-card">
                                    <div class="stat-label">Текущая мощность</div>
                                    <div class="stat-value" id="currentPower">0.00 кВт</div>
                                    <div class="stat-label" id="powerStatus">Стабильно</div>
                                </div>
                                <div class="stat-card">
                                    <div class="stat-label">Потреблено сегодня</div>
                                    <div class="stat-value" id="todayConsumption">0.0 кВт·ч</div>
                                    <div class="stat-label" id="todayCost">0 ₸</div>
                                </div>
                                <div class="stat-card">
                                    <div class="stat-label">Активные комнаты</div>
                                    <div class="stat-value" id="activeRooms">0/5</div>
                                    <div class="stat-label">В работе</div>
                                </div>
                                <div class="stat-card">
                                    <div class="stat-label">Экономия</div>
                                    <div class="stat-value" id="savings">0 ₸</div>
                                    <div class="stat-label">За сегодня</div>
                                </div>
                            </div>
                        </div>
                        
                        <div class="card">
                            <div class="card-header">
                                <h2 class="card-title"><i class="fas fa-bolt"></i> Быстрое управление</h2>
                            </div>
                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-top: 20px;">
                                <button class="btn btn-success" onclick="toggleAllRooms('on')">
                                    <i class="fas fa-power-off"></i> Включить все
                                </button>
                                <button class="btn btn-danger" onclick="toggleAllRooms('off')">
                                    <i class="fas fa-power-off"></i> Выключить все
                                </button>
                                <button class="btn btn-primary" onclick="showEnergyModal()">
                                    <i class="fas fa-chart-pie"></i> Детальный отчет
                                </button>
                                <button class="btn btn-secondary" onclick="showSettingsModal()">
                                    <i class="fas fa-cog"></i> Настройки
                                </button>
                            </div>
                        </div>
                    </div>
                    
                    <div class="card" style="margin-top: 25px;">
                        <div class="card-header">
                            <h2 class="card-title"><i class="fas fa-history"></i> Последние события</h2>
                            <button class="btn btn-secondary" onclick="refreshLogs()">
                                <i class="fas fa-sync-alt"></i> Обновить
                            </button>
                        </div>
                        <div id="recentLogs" style="max-height: 300px; overflow-y: auto;">
                            <!-- Логи будут загружены динамически -->
                        </div>
                    </div>
                </div>
                
                <!-- Rooms Section -->
                <div id="roomsSection" class="content-section">
                    <div class="card-header" style="margin-bottom: 25px;">
                        <h2 class="card-title"><i class="fas fa-home"></i> Управление комнатами</h2>
                        <button class="btn btn-primary" onclick="showRoomModal(null)">
                            <i class="fas fa-plus"></i> Добавить комнату
                        </button>
                    </div>
                    
                    <div class="rooms-grid" id="roomsContainer">
                        <!-- Комнаты будут загружены динамически -->
                    </div>
                </div>
                
                <!-- Energy Section -->
                <div id="energySection" class="content-section">
                    <div class="card">
                        <div class="card-header">
                            <h2 class="card-title"><i class="fas fa-chart-line"></i> Энергопотребление</h2>
                            <div class="card-actions">
                                <select id="timeRange" onchange="updateEnergyChart()" style="background: rgba(255,255,255,0.1); color: white; border: none; padding: 8px 15px; border-radius: 8px;">
                                    <option value="day">За день</option>
                                    <option value="week">За неделю</option>
                                    <option value="month">За месяц</option>
                                    <option value="year">За год</option>
                                </select>
                            </div>
                        </div>
                        <div class="chart-container">
                            <canvas id="energyChart"></canvas>
                        </div>
                    </div>
                    
                    <div class="card" style="margin-top: 25px;">
                        <div class="card-header">
                            <h2 class="card-title"><i class="fas fa-money-bill-wave"></i> Финансовые показатели</h2>
                        </div>
                        <div class="stats-grid">
                            <div class="stat-card">
                                <div class="stat-label">Тариф</div>
                                <div class="stat-value" id="tariffRate">25 ₸</div>
                                <div class="stat-label">за кВт·ч</div>
                            </div>
                            <div class="stat-card">
                                <div class="stat-label">Месячные затраты</div>
                                <div class="stat-value" id="monthlyCost">0 ₸</div>
                                <div class="stat-label">Прогноз</div>
                            </div>
                            <div class="stat-card">
                                <div class="stat-label">Экономия за месяц</div>
                                <div class="stat-value" id="monthlySavings">0 ₸</div>
                                <div class="stat-label">+15% к прошлому месяцу</div>
                            </div>
                            <div class="stat-card">
                                <div class="stat-label">Пиковая мощность</div>
                                <div class="stat-value" id="peakPower">0.00 кВт</div>
                                <div class="stat-label">Сегодня</div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Statistics Section -->
                <div id="statisticsSection" class="content-section">
                    <div class="card">
                        <div class="card-header">
                            <h2 class="card-title"><i class="fas fa-chart-pie"></i> Распределение потребления</h2>
                        </div>
                        <div class="chart-container">
                            <canvas id="distributionChart"></canvas>
                        </div>
                    </div>
                    
                    <div class="dashboard-grid" style="margin-top: 25px;">
                        <div class="card">
                            <div class="card-header">
                                <h2 class="card-title"><i class="fas fa-clock"></i> Время работы</h2>
                            </div>
                            <div id="hoursStats">
                                <!-- Статистика по времени будет здесь -->
                            </div>
                        </div>
                        
                        <div class="card">
                            <div class="card-header">
                                <h2 class="card-title"><i class="fas fa-calendar-alt"></i> Ежемесячная статистика</h2>
                            </div>
                            <div id="monthlyStats">
                                <!-- Месячная статистика будет здесь -->
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Settings Section -->
                <div id="settingsSection" class="content-section">
                    <div class="card-header" style="margin-bottom: 25px;">
                        <h2 class="card-title"><i class="fas fa-cog"></i> Настройки системы</h2>
                        <button class="btn btn-success" onclick="saveAllSettings()">
                            <i class="fas fa-save"></i> Сохранить все
                        </button>
                    </div>
                    
                    <div class="settings-grid">
                        <!-- Основные настройки -->
                        <div class="setting-group">
                            <h3 style="color: #BBDEFB; margin-bottom: 20px;">Основные настройки</h3>
                            
                            <div class="setting-item">
                                <div class="setting-label">
                                    <h4>Автосохранение</h4>
                                    <p>Автоматически сохранять данные каждые 5 минут</p>
                                </div>
                                <div class="setting-control">
                                    <label class="toggle">
                                        <input type="checkbox" id="autoSave" checked>
                                        <span class="slider"></span>
                                    </label>
                                </div>
                            </div>
                            
                            <div class="setting-item">
                                <div class="setting-label">
                                    <h4>Интервал обновления</h4>
                                    <p>Частота обновления данных на панели (секунды)</p>
                                </div>
                                <div class="setting-control">
                                    <input type="number" id="updateInterval" value="5" min="1" max="60">
                                </div>
                            </div>
                            
                            <div class="setting-item">
                                <div class="setting-label">
                                    <h4>Цветовая тема</h4>
                                    <p>Внешний вид интерфейса</p>
                                </div>
                                <div class="setting-control">
                                    <select id="themeSelect">
                                        <option value="dark">Темная</option>
                                        <option value="light">Светлая</option>
                                        <option value="auto">Авто</option>
                                    </select>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Настройки энергии -->
                        <div class="setting-group">
                            <h3 style="color: #BBDEFB; margin-bottom: 20px;">Настройки энергии</h3>
                            
                            <div class="setting-item">
                                <div class="setting-label">
                                    <h4>Тариф за кВт·ч</h4>
                                    <p>Стоимость 1 киловатт-часа в тенге</p>
                                </div>
                                <div class="setting-control">
                                    <input type="number" id="tariffInput" value="25" min="1" max="1000" step="0.01">
                                </div>
                            </div>
                            
                            <div class="setting-item">
                                <div class="setting-label">
                                    <h4>Базовое потребление</h4>
                                    <p>Мощность в выключенном состоянии (кВт)</p>
                                </div>
                                <div class="setting-control">
                                    <input type="number" id="baseConsumption" value="0.05" min="0" max="10" step="0.01">
                                </div>
                            </div>
                            
                            <div class="setting-item">
                                <div class="setting-label">
                                    <h4>Уведомления</h4>
                                    <p>Получать уведомления о высоком потреблении</p>
                                </div>
                                <div class="setting-control">
                                    <label class="toggle">
                                        <input type="checkbox" id="notifications" checked>
                                        <span class="slider"></span>
                                    </label>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Настройки системы -->
                        <div class="setting-group">
                            <h3 style="color: #BBDEFB; margin-bottom: 20px;">Системные настройки</h3>
                            
                            <div class="setting-item">
                                <div class="setting-label">
                                    <h4>Язык интерфейса</h4>
                                    <p>Язык меню и сообщений</p>
                                </div>
                                <div class="setting-control">
                                    <select id="languageSelect">
                                        <option value="ru">Русский</option>
                                        <option value="kk">Қазақша</option>
                                        <option value="en">English</option>
                                    </select>
                                </div>
                            </div>
                            
                            <div class="setting-item">
                                <div class="setting-label">
                                    <h4>Формат времени</h4>
                                    <p>24-часовой или 12-часовой формат</p>
                                </div>
                                <div class="setting-control">
                                    <select id="timeFormat">
                                        <option value="24">24-часовой</option>
                                        <option value="12">12-часовой</option>
                                    </select>
                                </div>
                            </div>
                            
                            <div class="setting-item">
                                <div class="setting-label">
                                    <h4>Единицы измерения</h4>
                                    <p>Система единиц для отображения</p>
                                </div>
                                <div class="setting-control">
                                    <select id="unitsSystem">
                                        <option value="metric">Метрическая (кВт, ₸)</option>
                                        <option value="imperial">Имперская (кВт, $)</option>
                                    </select>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Опасные настройки -->
                        <div class="setting-group">
                            <h3 style="color: #F44336; margin-bottom: 20px;">Опасные настройки</h3>
                            
                            <div class="setting-item">
                                <div class="setting-label">
                                    <h4>Сброс статистики</h4>
                                    <p>Обнулить всю статистику потребления</p>
                                </div>
                                <div class="setting-control">
                                    <button class="btn btn-danger" onclick="showResetConfirm()">
                                        <i class="fas fa-trash"></i> Сбросить
                                    </button>
                                </div>
                            </div>
                            
                            <div class="setting-item">
                                <div class="setting-label">
                                    <h4>Экспорт данных</h4>
                                    <p>Скачать все данные в формате JSON</p>
                                </div>
                                <div class="setting-control">
                                    <button class="btn btn-secondary" onclick="exportData()">
                                        <i class="fas fa-download"></i> Экспорт
                                    </button>
                                </div>
                            </div>
                            
                            <div class="setting-item">
                                <div class="setting-label">
                                    <h4>Резервное копирование</h4>
                                    <p>Создать резервную копию настроек</p>
                                </div>
                                <div class="setting-control">
                                    <button class="btn btn-primary" onclick="createBackup()">
                                        <i class="fas fa-copy"></i> Копия
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Users Section -->
                <div id="usersSection" class="content-section">
                    <div class="card">
                        <div class="card-header">
                            <h2 class="card-title"><i class="fas fa-users"></i> Управление пользователями</h2>
                            <button class="btn btn-primary" onclick="showUserModal(null)">
                                <i class="fas fa-user-plus"></i> Добавить пользователя
                            </button>
                        </div>
                        <div style="overflow-x: auto;">
                            <table style="width: 100%; border-collapse: collapse;">
                                <thead>
                                    <tr style="background: rgba(255,255,255,0.1);">
                                        <th style="padding: 15px; text-align: left;">Пользователь</th>
                                        <th style="padding: 15px; text-align: left;">Роль</th>
                                        <th style="padding: 15px; text-align: left;">Последний вход</th>
                                        <th style="padding: 15px; text-align: left;">Действия</th>
                                    </tr>
                                </thead>
                                <tbody id="usersTable">
                                    <!-- Пользователи будут загружены динамически -->
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
                
                <!-- Logs Section -->
                <div id="logsSection" class="content-section">
                    <div class="card">
                        <div class="card-header">
                            <h2 class="card-title"><i class="fas fa-history"></i> История действий</h2>
                            <div class="card-actions">
                                <button class="btn btn-secondary" onclick="clearLogs()">
                                    <i class="fas fa-trash"></i> Очистить
                                </button>
                                <button class="btn btn-primary" onclick="refreshLogs()">
                                    <i class="fas fa-sync-alt"></i> Обновить
                                </button>
                            </div>
                        </div>
                        <div style="max-height: 500px; overflow-y: auto;">
                            <table style="width: 100%; border-collapse: collapse;">
                                <thead>
                                    <tr style="background: rgba(255,255,255,0.1);">
                                        <th style="padding: 15px; text-align: left;">Время</th>
                                        <th style="padding: 15px; text-align: left;">Действие</th>
                                        <th style="padding: 15px; text-align: left;">Пользователь</th>
                                        <th style="padding: 15px; text-align: left;">Детали</th>
                                    </tr>
                                </thead>
                                <tbody id="logsTable">
                                    <!-- Логи будут загружены динамически -->
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Modal Windows -->
    <div id="roomModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h3 class="modal-title" id="roomModalTitle">Добавить комнату</h3>
                <button class="close-modal" onclick="hideRoomModal()">&times;</button>
            </div>
            <div class="modal-body">
                <form id="roomForm">
                    <input type="hidden" id="roomId">
                    
                    <div class="form-group">
                        <label class="form-label">Название комнаты</label>
                        <input type="text" id="roomName" required placeholder="Например: Гостиная">
                    </div>
                    
                    <div class="form-row">
                        <div class="form-group">
                            <label class="form-label">Мощность (кВт)</label>
                            <input type="number" id="roomPower" step="0.01" min="0.01" max="10" required value="0.1">
                        </div>
                        
                        <div class="form-group">
                            <label class="form-label">Иконка</label>
                            <select id="roomIcon" style="width: 100%;">
                                <option value="fa-couch">Диван</option>
                                <option value="fa-bed">Кровать</option>
                                <option value="fa-utensils">Столовые приборы</option>
                                <option value="fa-bath">Ванна</option>
                                <option value="fa-door-closed">Дверь</option>
                                <option value="fa-lightbulb">Лампочка</option>
                                <option value="fa-tv">Телевизор</option>
                                <option value="fa-desktop">Компьютер</option>
                            </select>
                        </div>
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label">Цвет</label>
                        <div class="color-picker">
                            <div class="color-option" style="background: #2196F3;" onclick="selectColor('#2196F3')"></div>
                            <div class="color-option" style="background: #FF9800;" onclick="selectColor('#FF9800')"></div>
                            <div class="color-option" style="background: #9C27B0;" onclick="selectColor('#9C27B0')"></div>
                            <div class="color-option" style="background: #00BCD4;" onclick="selectColor('#00BCD4')"></div>
                            <div class="color-option" style="background: #4CAF50;" onclick="selectColor('#4CAF50')"></div>
                            <div class="color-option" style="background: #795548;" onclick="selectColor('#795548')"></div>
                        </div>
                        <input type="hidden" id="roomColor" value="#2196F3">
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label">Описание</label>
                        <textarea id="roomDescription" rows="3" style="width: 100%; background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2); border-radius: 8px; color: white; padding: 10px;" placeholder="Описание комнаты..."></textarea>
                    </div>
                </form>
            </div>
            <div class="modal-footer">
                <button class="btn btn-secondary" onclick="hideRoomModal()">Отмена</button>
                <button class="btn btn-primary" onclick="saveRoom()">Сохранить</button>
            </div>
        </div>
    </div>
    
    <!-- User Modal -->
    <div id="userModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h3 class="modal-title" id="userModalTitle">Добавить пользователя</h3>
                <button class="close-modal" onclick="hideUserModal()">&times;</button>
            </div>
            <div class="modal-body">
                <form id="userForm">
                    <input type="hidden" id="userId">
                    
                    <div class="form-group">
                        <label class="form-label">Имя пользователя</label>
                        <input type="text" id="userUsername" required placeholder="Введите логин">
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label">Пароль</label>
                        <input type="password" id="userPassword" required placeholder="Введите пароль">
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label">Подтверждение пароля</label>
                        <input type="password" id="userPasswordConfirm" required placeholder="Повторите пароль">
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label">Роль</label>
                        <select id="userRole" style="width: 100%;">
                            <option value="admin">Администратор</option>
                            <option value="user">Пользователь</option>
                            <option value="viewer">Наблюдатель</option>
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label">Email</label>
                        <input type="email" id="userEmail" placeholder="email@example.com">
                    </div>
                </form>
            </div>
            <div class="modal-footer">
                <button class="btn btn-secondary" onclick="hideUserModal()">Отмена</button>
                <button class="btn btn-primary" onclick="saveUser()">Сохранить</button>
            </div>
        </div>
    </div>
    
    <!-- Reset Confirm Modal -->
    <div id="resetModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h3 class="modal-title" style="color: #F44336;"><i class="fas fa-exclamation-triangle"></i> Подтверждение сброса</h3>
                <button class="close-modal" onclick="hideResetModal()">&times;</button>
            </div>
            <div class="modal-body">
                <p style="margin-bottom: 20px;">Вы уверены, что хотите сбросить всю статистику? Это действие нельзя отменить.</p>
                <p style="color: #FF9800; margin-bottom: 20px;">Будут удалены все данные о потреблении энергии за текущий месяц.</p>
                <div class="form-group">
                    <label class="form-label">Для подтверждения введите "СБРОСИТЬ":</label>
                    <input type="text" id="resetConfirm" placeholder="СБРОСИТЬ" style="width: 100%;">
                </div>
            </div>
            <div class="modal-footer">
                <button class="btn btn-secondary" onclick="hideResetModal()">Отмена</button>
                <button class="btn btn-danger" onclick="resetStatistics()">Сбросить статистику</button>
            </div>
        </div>
    </div>
    
    <!-- JavaScript -->
    <script>
        // Глобальные переменные
        let currentSection = 'dashboard';
        let selectedColor = '#2196F3';
        let charts = {};
        let updateInterval = 5000;
        let timer = null;
        
        // Инициализация при загрузке
        document.addEventListener('DOMContentLoaded', function() {
            // Проверка авторизации
            checkAuth();
            
            // Загрузка начальных данных
            loadDashboardData();
            loadRooms();
            loadUsers();
            loadLogs();
            loadSettings();
            
            // Инициализация графиков
            initCharts();
            
            // Запуск таймера обновления
            startUpdateTimer();
            
            // Обновление времени
            updateTime();
            setInterval(updateTime, 1000);
        });
        
        // Проверка авторизации
        function checkAuth() {
            const token = localStorage.getItem('auth_token');
            if (token) {
                showApp();
            } else {
                showLogin();
            }
        }
        
        // Показать приложение
        function showApp() {
            document.getElementById('loginPage').style.display = 'none';
            document.getElementById('appContainer').style.display = 'block';
        }
        
        // Показать форму входа
        function showLogin() {
            document.getElementById('loginPage').style.display = 'flex';
            document.getElementById('appContainer').style.display = 'none';
        }
        
        // Вход в систему
        document.getElementById('loginForm').addEventListener('submit', function(e) {
            e.preventDefault();
            
            const username = document.getElementById('loginUsername').value;
            const password = document.getElementById('loginPassword').value;
            
            fetch('/api/login', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({username, password})
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    localStorage.setItem('auth_token', data.token);
                    localStorage.setItem('user_role', data.role);
                    localStorage.setItem('username', data.username);
                    showApp();
                    loadDashboardData();
                } else {
                    alert('Ошибка: ' + data.message);
                }
            })
            .catch(error => {
                alert('Ошибка соединения');
            });
        });
        
        // Выход из системы
        function logout() {
            localStorage.removeItem('auth_token');
            localStorage.removeItem('user_role');
            localStorage.removeItem('username');
            showLogin();
        }
        
        // Показать секцию
        function showSection(sectionId) {
            // Скрыть все секции
            document.querySelectorAll('.content-section').forEach(section => {
                section.classList.remove('active');
            });
            
            // Скрыть все активные элементы сайдбара
            document.querySelectorAll('.sidebar-item').forEach(item => {
                item.classList.remove('active');
            });
            
            // Показать выбранную секцию
            document.getElementById(sectionId + 'Section').classList.add('active');
            
            // Активировать соответствующий элемент сайдбара
            document.querySelectorAll('.sidebar-item').forEach(item => {
                if (item.textContent.includes(getSectionName(sectionId))) {
                    item.classList.add('active');
                }
            });
            
            currentSection = sectionId;
            
            // Загрузить данные для секции
            switch(sectionId) {
                case 'dashboard':
                    loadDashboardData();
                    break;
                case 'rooms':
                    loadRooms();
                    break;
                case 'energy':
                    updateEnergyChart();
                    break;
                case 'statistics':
                    updateStatistics();
                    break;
                case 'settings':
                    loadSettings();
                    break;
                case 'users':
                    loadUsers();
                    break;
                case 'logs':
                    loadLogs();
                    break;
            }
        }
        
        // Получить имя секции
        function getSectionName(sectionId) {
            const names = {
                'dashboard': 'Панель управления',
                'rooms': 'Управление комнатами',
                'energy': 'Энергопотребление',
                'statistics': 'Статистика',
                'settings': 'Настройки системы',
                'users': 'Пользователи',
                'logs': 'История действий'
            };
            return names[sectionId] || sectionId;
        }
        
        // Загрузка данных для дашборда
        function loadDashboardData() {
            fetch('/api/dashboard')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('currentPower').textContent = 
                        data.current_power.toFixed(2) + ' кВт';
                    document.getElementById('todayConsumption').textContent = 
                        data.today_usage.toFixed(1) + ' кВт·ч';
                    document.getElementById('todayCost').textContent = 
                        data.today_cost.toFixed(0) + ' ₸';
                    document.getElementById('activeRooms').textContent = 
                        data.active_rooms + '/' + data.total_rooms;
                    document.getElementById('savings').textContent = 
                        data.savings.toFixed(0) + ' ₸';
                    
                    // Обновить пользователя
                    const username = localStorage.getItem('username') || 'Администратор';
                    document.getElementById('currentUser').textContent = username;
                    
                    // Обновить логи
                    updateRecentLogs(data.recent_logs);
                });
        }
        
        // Загрузка комнат
        function loadRooms() {
            fetch('/api/rooms')
                .then(response => response.json())
                .then(rooms => {
                    const container = document.getElementById('roomsContainer');
                    container.innerHTML = '';
                    
                    Object.keys(rooms).forEach(roomId => {
                        const room = rooms[roomId];
                        const roomCard = `
                            <div class="room-card ${room.state ? 'active' : ''}">
                                <div class="room-actions">
                                    <button class="action-btn" onclick="editRoom('${roomId}')">
                                        <i class="fas fa-edit"></i>
                                    </button>
                                    <button class="action-btn" onclick="deleteRoom('${roomId}')">
                                        <i class="fas fa-trash"></i>
                                    </button>
                                </div>
                                <div class="room-header">
                                    <div class="room-icon" style="background: ${room.color};">
                                        <i class="fas ${room.icon}"></i>
                                    </div>
                                    <div class="room-status">
                                        <span class="status-indicator ${room.state ? 'on' : ''}"></span>
                                        <span>${room.state ? 'ВКЛ' : 'ВЫКЛ'}</span>
                                    </div>
                                </div>
                                <div style="margin-bottom: 15px;">
                                    <h3 style="font-size: 1.2rem; margin-bottom: 5px;">${room.name}</h3>
                                    <p style="color: #90CAF9; font-size: 0.9rem;">Мощность: ${room.power} кВт</p>
                                </div>
                                <div style="display: flex; gap: 10px;">
                                    <button class="btn ${room.state ? 'btn-danger' : 'btn-success'}" style="flex: 1;" onclick="toggleRoom('${roomId}', '${room.state ? 'off' : 'on'}')">
                                        <i class="fas fa-power-off"></i>
                                        ${room.state ? 'Выключить' : 'Включить'}
                                    </button>
                                    <button class="btn btn-secondary" onclick="showRoomDetails('${roomId}')">
                                        <i class="fas fa-info"></i>
                                    </button>
                                </div>
                            </div>
                        `;
                        container.innerHTML += roomCard;
                    });
                });
        }
        
        // Переключение комнаты
        function toggleRoom(roomId, state) {
            fetch(`/api/room/${roomId}/${state}`, {
                method: 'POST',
                headers: {'Authorization': 'Bearer ' + localStorage.getItem('auth_token')}
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    loadRooms();
                    loadDashboardData();
                    showNotification(`Комната "${data.room_name}" ${state === 'on' ? 'включена' : 'выключена'}`);
                }
            });
        }
        
        // Переключение всех комнат
        function toggleAllRooms(state) {
            fetch(`/api/all_rooms/${state}`, {
                method: 'POST',
                headers: {'Authorization': 'Bearer ' + localStorage.getItem('auth_token')}
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    loadRooms();
                    loadDashboardData();
                    showNotification(`Все комнаты ${state === 'on' ? 'включены' : 'выключены'}`);
                }
            });
        }
        
        // Показать модальное окно комнаты
        function showRoomModal(roomId) {
            const modal = document.getElementById('roomModal');
            const title = document.getElementById('roomModalTitle');
            
            if (roomId) {
                title.textContent = 'Редактировать комнату';
                // Загрузить данные комнаты
                fetch(`/api/room/${roomId}`)
                    .then(response => response.json())
                    .then(room => {
                        document.getElementById('roomId').value = roomId;
                        document.getElementById('roomName').value = room.name;
                        document.getElementById('roomPower').value = room.power;
                        document.getElementById('roomIcon').value = room.icon;
                        document.getElementById('roomColor').value = room.color;
                        document.getElementById('roomDescription').value = room.description || '';
                        selectColor(room.color);
                    });
            } else {
                title.textContent = 'Добавить комнату';
                document.getElementById('roomForm').reset();
                document.getElementById('roomId').value = '';
                document.getElementById('roomColor').value = '#2196F3';
                selectColor('#2196F3');
            }
            
            modal.classList.add('active');
        }
        
        // Скрыть модальное окно комнаты
        function hideRoomModal() {
            document.getElementById('roomModal').classList.remove('active');
        }
        
        // Выбрать цвет
        function selectColor(color) {
            selectedColor = color;
            document.getElementById('roomColor').value = color;
            
            // Убрать выделение со всех цветов
            document.querySelectorAll('.color-option').forEach(option => {
                option.classList.remove('selected');
            });
            
            // Найти и выделить выбранный цвет
            document.querySelectorAll('.color-option').forEach(option => {
                if (option.style.background === color || 
                    option.style.backgroundColor === color) {
                    option.classList.add('selected');
                }
            });
        }
        
        // Сохранить комнату
        function saveRoom() {
            const roomId = document.getElementById('roomId').value;
            const roomData = {
                name: document.getElementById('roomName').value,
                power: parseFloat(document.getElementById('roomPower').value),
                icon: document.getElementById('roomIcon').value,
                color: document.getElementById('roomColor').value,
                description: document.getElementById('roomDescription').value
            };
            
            const url = roomId ? `/api/room/${roomId}` : '/api/rooms';
            const method = roomId ? 'PUT' : 'POST';
            
            fetch(url, {
                method: method,
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + localStorage.getItem('auth_token')
                },
                body: JSON.stringify(roomData)
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    hideRoomModal();
                    loadRooms();
                    showNotification(data.message);
                }
            });
        }
        
        // Редактировать комнату
        function editRoom(roomId) {
            showRoomModal(roomId);
        }
        
        // Удалить комнату
        function deleteRoom(roomId) {
            if (confirm('Вы уверены, что хотите удалить эту комнату?')) {
                fetch(`/api/room/${roomId}`, {
                    method: 'DELETE',
                    headers: {'Authorization': 'Bearer ' + localStorage.getItem('auth_token')}
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        loadRooms();
                        showNotification(data.message);
                    }
                });
            }
        }
        
        // Загрузка пользователей
        function loadUsers() {
            fetch('/api/users')
                .then(response => response.json())
                .then(users => {
                    const table = document.getElementById('usersTable');
                    table.innerHTML = '';
                    
                    users.forEach(user => {
                        const row = `
                            <tr style="border-bottom: 1px solid rgba(255,255,255,0.1);">
                                <td style="padding: 15px;">
                                    <div style="display: flex; align-items: center; gap: 10px;">
                                        <div style="width: 40px; height: 40px; border-radius: 50%; background: #2196F3; display: flex; align-items: center; justify-content: center;">
                                            <i class="fas fa-user"></i>
                                        </div>
                                        <div>
                                            <div>${user.username}</div>
                                            <div style="font-size: 0.8rem; color: #90CAF9;">${user.email || ''}</div>
                                        </div>
                                    </div>
                                </td>
                                <td style="padding: 15px;">
                                    <span style="padding: 5px 10px; border-radius: 20px; background: ${user.role === 'admin' ? '#F44336' : '#2196F3'}; font-size: 0.8rem;">
                                        ${user.role === 'admin' ? 'Администратор' : 'Пользователь'}
                                    </span>
                                </td>
                                <td style="padding: 15px; color: #90CAF9;">${user.last_login || 'Никогда'}</td>
                                <td style="padding: 15px;">
                                    <button class="action-btn" onclick="editUser('${user.username}')">
                                        <i class="fas fa-edit"></i>
                                    </button>
                                    ${user.username !== 'admin' ? 
                                        `<button class="action-btn" onclick="deleteUser('${user.username}')">
                                            <i class="fas fa-trash"></i>
                                        </button>` : ''
                                    }
                                </td>
                            </tr>
                        `;
                        table.innerHTML += row;
                    });
                });
        }
        
        // Показать модальное окно пользователя
        function showUserModal(username) {
            const modal = document.getElementById('userModal');
            const title = document.getElementById('userModalTitle');
            
            if (username) {
                title.textContent = 'Редактировать пользователя';
                // Загрузить данные пользователя
                fetch(`/api/user/${username}`)
                    .then(response => response.json())
                    .then(user => {
                        document.getElementById('userId').value = username;
                        document.getElementById('userUsername').value = user.username;
                        document.getElementById('userUsername').readOnly = true;
                        document.getElementById('userRole').value = user.role;
                        document.getElementById('userEmail').value = user.email || '';
                        document.getElementById('userPassword').required = false;
                        document.getElementById('userPasswordConfirm').required = false;
                    });
            } else {
                title.textContent = 'Добавить пользователя';
                document.getElementById('userForm').reset();
                document.getElementById('userId').value = '';
                document.getElementById('userUsername').readOnly = false;
                document.getElementById('userPassword').required = true;
                document.getElementById('userPasswordConfirm').required = true;
            }
            
            modal.classList.add('active');
        }
        
        // Скрыть модальное окно пользователя
        function hideUserModal() {
            document.getElementById('userModal').classList.remove('active');
        }
        
        // Сохранить пользователя
        function saveUser() {
            const username = document.getElementById('userId').value;
            const password = document.getElementById('userPassword').value;
            const passwordConfirm = document.getElementById('userPasswordConfirm').value;
            
            if (password !== passwordConfirm) {
                alert('Пароли не совпадают!');
                return;
            }
            
            const userData = {
                username: document.getElementById('userUsername').value,
                password: password,
                role: document.getElementById('userRole').value,
                email: document.getElementById('userEmail').value
            };
            
            const url = username ? `/api/user/${username}` : '/api/users';
            const method = username ? 'PUT' : 'POST';
            
            fetch(url, {
                method: method,
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + localStorage.getItem('auth_token')
                },
                body: JSON.stringify(userData)
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    hideUserModal();
                    loadUsers();
                    showNotification(data.message);
                }
            });
        }
        
        // Редактировать пользователя
        function editUser(username) {
            showUserModal(username);
        }
        
        // Удалить пользователя
        function deleteUser(username) {
            if (confirm(`Вы уверены, что хотите удалить пользователя ${username}?`)) {
                fetch(`/api/user/${username}`, {
                    method: 'DELETE',
                    headers: {'Authorization': 'Bearer ' + localStorage.getItem('auth_token')}
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        loadUsers();
                        showNotification(data.message);
                    }
                });
            }
        }
        
        // Загрузка логов
        function loadLogs() {
            fetch('/api/logs')
                .then(response => response.json())
                .then(logs => {
                    updateLogsTable(logs);
                });
        }
        
        // Обновить таблицу логов
        function updateLogsTable(logs) {
            const table = document.getElementById('logsTable');
            table.innerHTML = '';
            
            logs.forEach(log => {
                const row = `
                    <tr style="border-bottom: 1px solid rgba(255,255,255,0.1);">
                        <td style="padding: 15px; color: #90CAF9;">${log.timestamp}</td>
                        <td style="padding: 15px;">
                            <span style="padding: 5px 10px; border-radius: 20px; background: ${getLogColor(log.action)}; font-size: 0.8rem;">
                                ${log.action}
                            </span>
                        </td>
                        <td style="padding: 15px;">${log.user}</td>
                        <td style="padding: 15px; color: #B0BEC5;">${log.details}</td>
                    </tr>
                `;
                table.innerHTML += row;
            });
        }
        
        // Обновить недавние логи
        function updateRecentLogs(logs) {
            const container = document.getElementById('recentLogs');
            container.innerHTML = '';
            
            logs.forEach(log => {
                const logItem = `
                    <div style="padding: 15px; border-bottom: 1px solid rgba(255,255,255,0.1); display: flex; align-items: center; gap: 15px;">
                        <div style="width: 40px; height: 40px; border-radius: 50%; background: ${getLogColor(log.action)}; display: flex; align-items: center; justify-content: center;">
                            <i class="fas ${getLogIcon(log.action)}"></i>
                        </div>
                        <div style="flex: 1;">
                            <div style="font-weight: 500;">${log.action}</div>
                            <div style="font-size: 0.9rem; color: #90CAF9;">${log.details}</div>
                        </div>
                        <div style="font-size: 0.8rem; color: #B0BEC5;">${log.timestamp}</div>
                    </div>
                `;
                container.innerHTML += logItem;
            });
        }
        
        // Очистить логи
        function clearLogs() {
            if (confirm('Вы уверены, что хотите очистить всю историю действий?')) {
                fetch('/api/logs', {
                    method: 'DELETE',
                    headers: {'Authorization': 'Bearer ' + localStorage.getItem('auth_token')}
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        loadLogs();
                        showNotification(data.message);
                    }
                });
            }
        }
        
        // Обновить логи
        function refreshLogs() {
            loadLogs();
            fetch('/api/dashboard')
                .then(response => response.json())
                .then(data => {
                    updateRecentLogs(data.recent_logs);
                });
        }
        
        // Получить цвет для типа лога
        function getLogColor(action) {
            const colors = {
                'Вход в систему': '#4CAF50',
                'Выход из системы': '#F44336',
                'Включение': '#4CAF50',
                'Выключение': '#F44336',
                'Настройка': '#2196F3',
                'Удаление': '#F44336',
                'Добавление': '#4CAF50'
            };
            return colors[action] || '#607D8B';
        }
        
        // Получить иконку для типа лога
        function getLogIcon(action) {
            const icons = {
                'Вход в систему': 'fa-sign-in-alt',
                'Выход из системы': 'fa-sign-out-alt',
                'Включение': 'fa-power-off',
                'Выключение': 'fa-power-off',
                'Настройка': 'fa-cog',
                'Удаление': 'fa-trash',
                'Добавление': 'fa-plus'
            };
            return icons[action] || 'fa-info-circle';
        }
        
        // Загрузка настроек
        function loadSettings() {
            fetch('/api/settings')
                .then(response => response.json())
                .then(settings => {
                    document.getElementById('autoSave').checked = settings.auto_save;
                    document.getElementById('updateInterval').value = settings.update_interval;
                    document.getElementById('themeSelect').value = settings.theme;
                    document.getElementById('tariffInput').value = settings.tariff;
                    document.getElementById('baseConsumption').value = settings.base_consumption;
                    document.getElementById('notifications').checked = settings.notifications;
                    document.getElementById('languageSelect').value = settings.language;
                    document.getElementById('timeFormat').value = settings.time_format;
                    document.getElementById('unitsSystem').value = settings.units_system;
                    
                    updateInterval = settings.update_interval * 1000;
                    restartUpdateTimer();
                });
        }
        
        // Сохранить все настройки
        function saveAllSettings() {
            const settings = {
                auto_save: document.getElementById('autoSave').checked,
                update_interval: parseInt(document.getElementById('updateInterval').value),
                theme: document.getElementById('themeSelect').value,
                tariff: parseFloat(document.getElementById('tariffInput').value),
                base_consumption: parseFloat(document.getElementById('baseConsumption').value),
                notifications: document.getElementById('notifications').checked,
                language: document.getElementById('languageSelect').value,
                time_format: document.getElementById('timeFormat').value,
                units_system: document.getElementById('unitsSystem').value
            };
            
            fetch('/api/settings', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + localStorage.getItem('auth_token')
                },
                body: JSON.stringify(settings)
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showNotification('Настройки сохранены');
                    updateInterval = settings.update_interval * 1000;
                    restartUpdateTimer();
                }
            });
        }
        
        // Инициализация графиков
        function initCharts() {
            // График энергопотребления
            const energyCtx = document.getElementById('energyChart').getContext('2d');
            charts.energy = new Chart(energyCtx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Потребление (кВт)',
                        data: [],
                        borderColor: '#2196F3',
                        backgroundColor: 'rgba(33, 150, 243, 0.1)',
                        borderWidth: 3,
                        fill: true,
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { labels: { color: '#fff' } }
                    },
                    scales: {
                        x: {
                            ticks: { color: '#90CAF9' },
                            grid: { color: 'rgba(255, 255, 255, 0.1)' }
                        },
                        y: {
                            beginAtZero: true,
                            ticks: { color: '#90CAF9' },
                            grid: { color: 'rgba(255, 255, 255, 0.1)' }
                        }
                    }
                }
            });
            
            // График распределения
            const distCtx = document.getElementById('distributionChart').getContext('2d');
            charts.distribution = new Chart(distCtx, {
                type: 'doughnut',
                data: {
                    labels: [],
                    datasets: [{
                        data: [],
                        backgroundColor: []
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'right',
                            labels: { color: '#fff' }
                        }
                    }
                }
            });
        }
        
        // Обновление графика энергопотребления
        function updateEnergyChart() {
            const timeRange = document.getElementById('timeRange').value;
            
            fetch(`/api/energy_chart?range=${timeRange}`)
                .then(response => response.json())
                .then(data => {
                    charts.energy.data.labels = data.labels;
                    charts.energy.data.datasets[0].data = data.data;
                    charts.energy.update();
                    
                    // Обновить финансовые показатели
                    document.getElementById('tariffRate').textContent = 
                        data.tariff.toFixed(0) + ' ₸';
                    document.getElementById('monthlyCost').textContent = 
                        data.monthly_cost.toFixed(0) + ' ₸';
                    document.getElementById('monthlySavings').textContent = 
                        data.monthly_savings.toFixed(0) + ' ₸';
                    document.getElementById('peakPower').textContent = 
                        data.peak_power.toFixed(2) + ' кВт';
                });
        }
        
        // Обновление статистики
        function updateStatistics() {
            fetch('/api/statistics')
                .then(response => response.json())
                .then(data => {
                    // Обновить график распределения
                    charts.distribution.data.labels = data.labels;
                    charts.distribution.data.datasets[0].data = data.data;
                    charts.distribution.data.datasets[0].backgroundColor = data.colors;
                    charts.distribution.update();
                    
                    // Обновить статистику времени
                    updateHoursStats(data.hours_stats);
                    
                    // Обновить месячную статистику
                    updateMonthlyStats(data.monthly_stats);
                });
        }
        
        // Обновить статистику по времени
        function updateHoursStats(stats) {
            const container = document.getElementById('hoursStats');
            container.innerHTML = '';
            
            stats.forEach(stat => {
                const item = `
                    <div style="padding: 15px; border-bottom: 1px solid rgba(255,255,255,0.1); display: flex; justify-content: space-between;">
                        <div>${stat.room}</div>
                        <div style="color: #64B5F6; font-weight: 500;">${stat.hours} ч</div>
                    </div>
                `;
                container.innerHTML += item;
            });
        }
        
        // Обновить месячную статистику
        function updateMonthlyStats(stats) {
            const container = document.getElementById('monthlyStats');
            container.innerHTML = '';
            
            stats.forEach(stat => {
                const item = `
                    <div style="padding: 15px; border-bottom: 1px solid rgba(255,255,255,0.1);">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                            <div>${stat.month}</div>
                            <div style="color: #64B5F6; font-weight: 500;">${stat.consumption} кВт·ч</div>
                        </div>
                        <div style="font-size: 0.9rem; color: #90CAF9;">${stat.cost} ₸</div>
                    </div>
                `;
                container.innerHTML += item;
            });
        }
        
        // Показать модальное окно сброса
        function showResetConfirm() {
            document.getElementById('resetModal').classList.add('active');
        }
        
        // Скрыть модальное окно сброса
        function hideResetModal() {
            document.getElementById('resetModal').classList.remove('active');
            document.getElementById('resetConfirm').value = '';
        }
        
        // Сбросить статистику
        function resetStatistics() {
            const confirmText = document.getElementById('resetConfirm').value;
            
            if (confirmText !== 'СБРОСИТЬ') {
                alert('Для подтверждения введите "СБРОСИТЬ"');
                return;
            }
            
            fetch('/api/reset_stats', {
                method: 'POST',
                headers: {'Authorization': 'Bearer ' + localStorage.getItem('auth_token')}
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    hideResetModal();
                    loadDashboardData();
                    updateEnergyChart();
                    updateStatistics();
                    showNotification(data.message);
                }
            });
        }
        
        // Экспорт данных
        function exportData() {
            fetch('/api/export')
                .then(response => response.blob())
                .then(blob => {
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `energy_data_${new Date().toISOString().split('T')[0]}.json`;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    window.URL.revokeObjectURL(url);
                });
        }
        
        // Создать резервную копию
        function createBackup() {
            fetch('/api/backup', {
                method: 'POST',
                headers: {'Authorization': 'Bearer ' + localStorage.getItem('auth_token')}
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showNotification(data.message);
                }
            });
        }
        
        // Запустить таймер обновления
        function startUpdateTimer() {
            if (timer) clearInterval(timer);
            timer = setInterval(updateDashboard, updateInterval);
        }
        
        // Перезапустить таймер обновления
        function restartUpdateTimer() {
            if (timer) clearInterval(timer);
            timer = setInterval(updateDashboard, updateInterval);
        }
        
        // Обновить дашборд
        function updateDashboard() {
            if (currentSection === 'dashboard') {
                loadDashboardData();
            }
            if (currentSection === 'energy') {
                updateEnergyChart();
            }
            if (currentSection === 'statistics') {
                updateStatistics();
            }
        }
        
        // Обновить время
        function updateTime() {
            const now = new Date();
            const timeStr = now.toLocaleTimeString('ru-RU', {hour12: false});
            document.getElementById('currentTime').textContent = timeStr;
        }
        
        // Показать уведомление
        function showNotification(message, type = 'success') {
            // Создать элемент уведомления
            const notification = document.createElement('div');
            notification.className = 'notification';
            notification.innerHTML = `
                <i class="fas fa-${type === 'success' ? 'check-circle' : 'info-circle'}"></i>
                ${message}
            `;
            
            // Стили для уведомления
            notification.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                padding: 15px 25px;
                background: ${type === 'success' ? '#4CAF50' : '#2196F3'};
                color: white;
                border-radius: 10px;
                box-shadow: 0 5px 15px rgba(0,0,0,0.3);
                z-index: 10000;
                animation: slideIn 0.3s ease;
                display: flex;
                align-items: center;
                gap: 10px;
            `;
            
            document.body.appendChild(notification);
            
            // Удалить через 3 секунды
            setTimeout(() => {
                notification.style.animation = 'slideOut 0.3s ease';
                setTimeout(() => notification.remove(), 300);
            }, 3000);
        }
        
        // Добавить стили анимации
        const style = document.createElement('style');
        style.textContent = `
            @keyframes slideIn {
                from { transform: translateX(100%); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
            @keyframes slideOut {
                from { transform: translateX(0); opacity: 1; }
                to { transform: translateX(100%); opacity: 0; }
            }
        `;
        document.head.appendChild(style);
        
        // Показать детали комнаты
        function showRoomDetails(roomId) {
            fetch(`/api/room/${roomId}`)
                .then(response => response.json())
                .then(room => {
                    alert(`
                        Название: ${room.name}
                        Мощность: ${room.power} кВт
                        Состояние: ${room.state ? 'Включена' : 'Выключена'}
                        Время работы сегодня: ${room.hours_today || 0} часов
                        Потреблено сегодня: ${(room.power * (room.hours_today || 0)).toFixed(2)} кВт·ч
                    `);
                });
        }
    </script>
</body>
</html>
'''

# API Endpoints
@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username', '')
    password = data.get('password', '')
    
    # Хешируем пароль для сравнения
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    if username in DEMO_USERS and DEMO_USERS[username] == password_hash:
        session['username'] = username
        session['role'] = 'admin' if username == 'admin' else 'user'
        
        # Добавить лог
        add_log('Вход в систему', username, f'Пользователь {username} вошел в систему')
        
        return jsonify({
            'success': True,
            'token': 'demo-token',
            'role': session['role'],
            'username': username
        })
    
    return jsonify({'success': False, 'message': 'Неверный логин или пароль'})

# Middleware для проверки авторизации
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return jsonify({'success': False, 'message': 'Требуется авторизация'}), 401
        return f(*args, **kwargs)
    return decorated_function

@app.route('/api/dashboard')
@login_required
def get_dashboard():
    # Расчет текущей мощности
    total_power = CONFIG['base_consumption']
    active_rooms = 0
    
    for room in current_state['lamps'].values():
        if room['state']:
            total_power += room['power']
            active_rooms += 1
    
    # Добавляем случайные колебания для реалистичности
    total_power += random.uniform(-0.02, 0.02)
    total_power = max(0.05, total_power)
    
    current_state['energy']['current_power'] = total_power
    
    # Расчет стоимости
    today_cost = current_state['energy']['total_today'] * current_state['energy']['tariff']
    month_cost = current_state['energy']['total_month'] * current_state['energy']['tariff']
    
    return jsonify({
        'current_power': round(total_power, 3),
        'today_usage': round(current_state['energy']['total_today'], 2),
        'today_cost': round(today_cost, 0),
        'active_rooms': active_rooms,
        'total_rooms': len(current_state['lamps']),
        'savings': round(current_state['stats']['savings_today'], 0),
        'recent_logs': get_recent_logs(5)
    })

@app.route('/api/rooms')
@login_required
def get_rooms():
    rooms = {}
    for room_id, room_data in current_state['lamps'].items():
        rooms[room_id] = {
            'name': room_data['name'],
            'state': room_data['state'],
            'power': room_data['power'],
            'icon': room_data['icon'],
            'color': room_data['color'],
            'hours_today': current_state['stats']['hours_on_today'].get(room_id, 0)
        }
    return jsonify(rooms)

@app.route('/api/room/<room_id>')
@login_required
def get_room(room_id):
    if room_id in current_state['lamps']:
        room_data = current_state['lamps'][room_id].copy()
        room_data['hours_today'] = current_state['stats']['hours_on_today'].get(room_id, 0)
        return jsonify(room_data)
    return jsonify({'success': False, 'message': 'Комната не найдена'}), 404

# Обновите функцию toggle_room в API
@app.route('/api/room/<room_id>/<state>', methods=['POST'])
@login_required
def toggle_room(room_id, state):
    if room_id in current_state['lamps']:
        new_state = (state == 'on')
        
        # Обновляем состояние в Arduino
        if arduino_connected:
            if new_state:
                success = arduino.turn_on_room(room_id)
            else:
                success = arduino.turn_off_room(room_id)
            
            if success:
                current_state['lamps'][room_id]['state'] = new_state
            else:
                print(f"⚠ Не удалось отправить команду на Arduino")
        else:
            current_state['lamps'][room_id]['state'] = new_state
        
        # Добавить лог
        username = session.get('username', 'system')
        action = 'Включение' if new_state else 'Выключение'
        add_log(action, username, f'Комната "{current_state["lamps"][room_id]["name"]}" {state}')
        
        return jsonify({
            'success': True,
            'room_name': current_state['lamps'][room_id]['name'],
            'new_state': state
        })
    return jsonify({'success': False, 'message': 'Комната не найдена'}), 404

# Обновите функцию toggle_all_rooms
@app.route('/api/all_rooms/<state>', methods=['POST'])
@login_required
def toggle_all_rooms(state):
    new_state = (state == 'on')
    
    # Обновляем состояние в Arduino
    if arduino_connected:
        if new_state:
            success = arduino.all_on()
        else:
            success = arduino.all_off()
        
        if success:
            for room_id, room_data in current_state['lamps'].items():
                room_data['state'] = new_state
        else:
            print(f"⚠ Не удалось отправить команду на Arduino")
    else:
        for room_id, room_data in current_state['lamps'].items():
            room_data['state'] = new_state
    
    # Добавить лог
    username = session.get('username', 'system')
    action = 'Включение' if new_state else 'Выключение'
    add_log(action, username, f'Все комнаты {state}')
    
    return jsonify({
        'success': True,
        'rooms_updated': len(current_state['lamps']),
        'new_state': state
    })

@app.route('/api/rooms', methods=['POST'])
@login_required
def create_room():
    data = request.json
    room_id = f'room_{len(current_state["lamps"]) + 1}'
    
    current_state['lamps'][room_id] = {
        'name': data.get('name', 'Новая комната'),
        'state': False,
        'power': data.get('power', 0.1),
        'icon': data.get('icon', 'fa-lightbulb'),
        'color': data.get('color', '#2196F3'),
        'description': data.get('description', '')
    }
    
    # Добавить лог
    username = session.get('username', 'system')
    add_log('Добавление', username, f'Добавлена комната: {data.get("name")}')
    
    save_data()
    
    return jsonify({'success': True, 'message': 'Комната добавлена', 'room_id': room_id})

@app.route('/api/room/<room_id>', methods=['PUT'])
@login_required
def update_room(room_id):
    if room_id in current_state['lamps']:
        data = request.json
        
        old_name = current_state['lamps'][room_id]['name']
        current_state['lamps'][room_id].update({
            'name': data.get('name', current_state['lamps'][room_id]['name']),
            'power': data.get('power', current_state['lamps'][room_id]['power']),
            'icon': data.get('icon', current_state['lamps'][room_id]['icon']),
            'color': data.get('color', current_state['lamps'][room_id]['color']),
            'description': data.get('description', current_state['lamps'][room_id].get('description', ''))
        })
        
        # Добавить лог
        username = session.get('username', 'system')
        add_log('Настройка', username, f'Изменена комната: {old_name} -> {data.get("name", old_name)}')
        
        save_data()
        
        return jsonify({'success': True, 'message': 'Комната обновлена'})
    
    return jsonify({'success': False, 'message': 'Комната не найдена'}), 404

@app.route('/api/room/<room_id>', methods=['DELETE'])
@login_required
def delete_room(room_id):
    if room_id in current_state['lamps']:
        room_name = current_state['lamps'][room_id]['name']
        del current_state['lamps'][room_id]
        
        # Добавить лог
        username = session.get('username', 'system')
        add_log('Удаление', username, f'Удалена комната: {room_name}')
        
        save_data()
        
        return jsonify({'success': True, 'message': 'Комната удалена'})
    
    return jsonify({'success': False, 'message': 'Комната не найдена'}), 404

@app.route('/api/energy_chart')
@login_required
def get_energy_chart():
    time_range = request.args.get('range', 'day')
    
    # Генерируем демо-данные для графика
    if time_range == 'day':
        labels = [f'{h}:00' for h in range(24)]
        data = [random.uniform(0.1, 1.5) for _ in range(24)]
    elif time_range == 'week':
        labels = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
        data = [random.uniform(5, 15) for _ in range(7)]
    elif time_range == 'month':
        labels = ['Неделя 1', 'Неделя 2', 'Неделя 3', 'Неделя 4']
        data = [random.uniform(20, 80) for _ in range(4)]
    else:  # year
        labels = ['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн', 'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек']
        data = [random.uniform(100, 300) for _ in range(12)]
    
    return jsonify({
        'labels': labels,
        'data': data,
        'tariff': current_state['energy']['tariff'],
        'monthly_cost': current_state['energy']['total_month'] * current_state['energy']['tariff'],
        'monthly_savings': current_state['stats']['savings_today'] * 30,
        'peak_power': current_state['energy']['peak_today']
    })

@app.route('/api/statistics')
@login_required
def get_statistics():
    # Данные для графика распределения
    labels = []
    data = []
    colors = []
    
    for room_id, room_data in current_state['lamps'].items():
        if room_data['state']:
            labels.append(room_data['name'])
            data.append(room_data['power'])
            colors.append(room_data['color'])
    
    # Статистика по времени работы
    hours_stats = []
    for room_id, hours in current_state['stats']['hours_on_today'].items():
        if room_id in current_state['lamps']:
            hours_stats.append({
                'room': current_state['lamps'][room_id]['name'],
                'hours': round(hours, 1)
            })
    
    # Месячная статистика (демо)
    monthly_stats = [
        {'month': 'Январь', 'consumption': 150, 'cost': 3750},
        {'month': 'Февраль', 'consumption': 140, 'cost': 3500},
        {'month': 'Март', 'consumption': 130, 'cost': 3250},
        {'month': 'Апрель', 'consumption': 120, 'cost': 3000},
        {'month': 'Май', 'consumption': 110, 'cost': 2750},
        {'month': 'Июнь', 'consumption': 100, 'cost': 2500}
    ]
    
    return jsonify({
        'labels': labels,
        'data': data,
        'colors': colors,
        'hours_stats': hours_stats,
        'monthly_stats': monthly_stats
    })

@app.route('/api/settings')
@login_required
def get_settings():
    return jsonify({
        'auto_save': current_state['system']['auto_save'],
        'update_interval': current_state['system']['data_interval'],
        'theme': current_state['system']['theme'],
        'tariff': current_state['energy']['tariff'],
        'base_consumption': CONFIG['base_consumption'],
        'notifications': current_state['system']['notifications'],
        'language': current_state['system']['language'],
        'time_format': '24',
        'units_system': 'metric'
    })

@app.route('/api/settings', methods=['POST'])
@login_required
def update_settings():
    data = request.json
    
    # Обновляем настройки системы
    current_state['system']['auto_save'] = data.get('auto_save', True)
    current_state['system']['data_interval'] = data.get('update_interval', 5)
    current_state['system']['theme'] = data.get('theme', 'dark')
    current_state['system']['notifications'] = data.get('notifications', True)
    current_state['system']['language'] = data.get('language', 'ru')
    
    # Обновляем настройки энергии
    current_state['energy']['tariff'] = data.get('tariff', 25.0)
    CONFIG['base_consumption'] = data.get('base_consumption', 0.05)
    
    # Добавить лог
    username = session.get('username', 'system')
    add_log('Настройка', username, 'Обновлены настройки системы')
    
    save_data()
    
    return jsonify({'success': True, 'message': 'Настройки сохранены'})

@app.route('/api/users')
@login_required
def get_users():
    # Демо-пользователи
    users = [
        {
            'username': 'admin',
            'role': 'admin',
            'email': 'admin@example.com',
            'last_login': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        },
        {
            'username': 'user',
            'role': 'user',
            'email': 'user@example.com',
            'last_login': '2024-01-15 14:30:00'
        }
    ]
    return jsonify(users)

@app.route('/api/user/<username>')
@login_required
def get_user(username):
    # Демо-данные
    users = {
        'admin': {'username': 'admin', 'role': 'admin', 'email': 'admin@example.com'},
        'user': {'username': 'user', 'role': 'user', 'email': 'user@example.com'}
    }
    
    if username in users:
        return jsonify(users[username])
    
    return jsonify({'success': False, 'message': 'Пользователь не найден'}), 404

@app.route('/api/logs')
@login_required
def get_logs():
    # Читаем логи из файла
    logs = []
    log_file = 'system_logs.json'
    
    if os.path.exists(log_file):
        try:
            with open(log_file, 'r') as f:
                logs = json.load(f)
        except:
            logs = []
    
    return jsonify(logs)

@app.route('/api/logs', methods=['DELETE'])
@login_required
def clear_logs():
    # Очищаем файл логов
    with open('system_logs.json', 'w') as f:
        json.dump([], f)
    
    # Добавить лог об очистке
    username = session.get('username', 'system')
    add_log('Очистка', username, 'Очищена история действий')
    
    return jsonify({'success': True, 'message': 'История очищена'})

@app.route('/api/reset_stats', methods=['POST'])
@login_required
def reset_stats():
    # Сбросить статистику
    current_state['energy']['total_today'] = 0.0
    current_state['energy']['cost_today'] = 0.0
    current_state['energy']['peak_today'] = 0.0
    current_state['stats']['savings_today'] = 0.0
    
    for room_id in current_state['stats']['hours_on_today']:
        current_state['stats']['hours_on_today'][room_id] = 0.0
    
    # Добавить лог
    username = session.get('username', 'system')
    add_log('Сброс', username, 'Сброшена статистика потребления')
    
    save_data()
    
    return jsonify({'success': True, 'message': 'Статистика сброшена'})

@app.route('/api/export')
@login_required
def export_data():
    # Экспорт всех данных
    export_data = {
        'lamps': current_state['lamps'],
        'energy': current_state['energy'],
        'stats': current_state['stats'],
        'system': current_state['system'],
        'export_date': datetime.now().isoformat()
    }
    
    return jsonify(export_data)

@app.route('/api/backup', methods=['POST'])
@login_required
def create_backup():
    # Создаем резервную копию
    backup_file = f'backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    
    try:
        with open(backup_file, 'w') as f:
            json.dump(current_state, f, indent=2)
        
        # Добавить лог
        username = session.get('username', 'system')
        add_log('Резервная копия', username, f'Создана резервная копия: {backup_file}')
        
        return jsonify({'success': True, 'message': f'Резервная копия создана: {backup_file}'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Ошибка: {str(e)}'})

# Вспомогательные функции
def add_log(action, user, details):
    """Добавить запись в лог"""
    log_entry = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'action': action,
        'user': user,
        'details': details
    }
    
    # Читаем существующие логи
    logs = []
    log_file = 'system_logs.json'
    
    if os.path.exists(log_file):
        try:
            with open(log_file, 'r') as f:
                logs = json.load(f)
        except:
            logs = []
    
    # Добавляем новую запись
    logs.insert(0, log_entry)
    
    # Сохраняем (ограничиваем до 1000 записей)
    logs = logs[:1000]
    
    with open(log_file, 'w') as f:
        json.dump(logs, f, indent=2)
    
    return True

def get_recent_logs(limit=5):
    """Получить последние записи логов"""
    logs = []
    log_file = 'system_logs.json'
    
    if os.path.exists(log_file):
        try:
            with open(log_file, 'r') as f:
                logs = json.load(f)
        except:
            logs = []
    
    return logs[:limit]

def update_energy_stats():
    """Фоновая задача для обновления статистики"""
    while True:
        time.sleep(1)
        
        # Обновляем потребление для включенных комнат
        for room_id, room_data in current_state['lamps'].items():
            if room_data['state']:
                # Увеличиваем счетчик часов работы
                current_state['stats']['hours_on_today'][room_id] += 1/3600
                
                # Рассчитываем потребление
                consumption = room_data['power'] * (1/3600)
                current_state['energy']['total_today'] += consumption
                current_state['energy']['total_month'] += consumption
                
                # Обновляем пиковое потребление
                if current_state['energy']['current_power'] > current_state['energy']['peak_today']:
                    current_state['energy']['peak_today'] = current_state['energy']['current_power']
        
        # Автосохранение каждые 5 минут
        if current_state['system']['auto_save'] and int(time.time()) % 300 == 0:
            save_data()

if __name__ == '__main__':
    # Загружаем данные
    load_data()
    
    # Запускаем фоновую задачу
    updater_thread = threading.Thread(target=update_energy_stats, daemon=True)
    updater_thread.start()
    
    print("=" * 60)
    print("🚀 IoT Smart Energy Monitor System")
    print("=" * 60)
    print("👤 Демо-пользователи:")
    print("   Логин: admin | Пароль: admin123")
    print("   Логин: user  | Пароль: user123")
    print("=" * 60)
    print(f"🌐 Сервер запущен: http://127.0.0.1:5000")
    print(f"📊 Мониторинг комнат: {len(current_state['lamps'])}")
    print(f"💰 Тариф: {current_state['energy']['tariff']} ₸/кВт·ч")
    print("=" * 60)
    
    try:
        app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
    except KeyboardInterrupt:
        print("\n👋 Завершение работы...")
        save_data()
        print("💾 Данные сохранены")