#!/usr/bin/env python3
"""
RESQUBE Teleop — Control por teclado directo a ROS2
=====================================================
Teclas:
  W / ↑   → Adelante
  S / ↓   → Atrás
  A / ←   → Izquierda
  D / →   → Derecha
  SPACE   → STOP
  X       → Servo (disparo)
  M       → Cambiar modo REMOTO/AUTONOMO
  I       → Iniciar/Detener autónomo
  Q       → Salir

Requiere:
  pip install pynput
  source /opt/ros/humble/setup.bash
"""

import sys
import threading
import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Bool
from pynput import keyboard

# ══════════════════════════════════════════════════════
#  COLORES ANSI para la terminal
# ══════════════════════════════════════════════════════
C = {
    'reset':  '\033[0m',
    'bold':   '\033[1m',
    'cyan':   '\033[96m',
    'green':  '\033[92m',
    'yellow': '\033[93m',
    'red':    '\033[91m',
    'blue':   '\033[94m',
    'gray':   '\033[90m',
    'white':  '\033[97m',
    'bg_dark':'\033[40m',
}

# ══════════════════════════════════════════════════════
#  ESTADO GLOBAL
# ══════════════════════════════════════════════════════
estado = {
    'cmd':        'STOP',
    'modo':       'REMOTO',
    'autonomo':   False,
    'robot_estado': '--',
    'sensores':   '--',
    'alerta':     False,
    'conectado':  False,
}
lock = threading.Lock()

# ══════════════════════════════════════════════════════
#  NODO ROS2
# ══════════════════════════════════════════════════════
class ResqubeNode(Node):
    def __init__(self):
        super().__init__('resqube_teleop')

        self.pub_cmd      = self.create_publisher(String, '/resqube/cmd',      10)
        self.pub_modo     = self.create_publisher(String, '/resqube/modo',     10)
        self.pub_autonomo = self.create_publisher(String, '/resqube/autonomo', 10)

        self.create_subscription(String, '/resqube/estado',
            self._cb_estado,   10)
        self.create_subscription(String, '/resqube/sensores',
            self._cb_sensores, 10)
        self.create_subscription(Bool,   '/resqube/alerta',
            self._cb_alerta,   10)

        self.get_logger().info('ResqubeNode teleop iniciado')
        with lock:
            estado['conectado'] = True

    def enviar_cmd(self, cmd: str):
        msg = String(); msg.data = cmd
        self.pub_cmd.publish(msg)
        with lock:
            estado['cmd'] = cmd

    def enviar_modo(self, modo: str):
        msg = String(); msg.data = modo
        self.pub_modo.publish(msg)
        with lock:
            estado['modo'] = modo

    def enviar_autonomo(self, accion: str):
        msg = String(); msg.data = accion
        self.pub_autonomo.publish(msg)
        with lock:
            estado['autonomo'] = (accion == 'START')

    def _cb_estado(self, msg):
        with lock:
            estado['robot_estado'] = msg.data

    def _cb_sensores(self, msg):
        with lock:
            estado['sensores'] = msg.data

    def _cb_alerta(self, msg):
        with lock:
            estado['alerta'] = msg.data


ros_node = None

# ══════════════════════════════════════════════════════
#  INTERFAZ TERMINAL
# ══════════════════════════════════════════════════════
MAPA_DIRECCION = {
    'ADELANTE':  '  ▲  ',
    'ATRAS':     '  ▼  ',
    'IZQ':       '◀    ',
    'DER':       '    ▶',
    'STOP':      '  ■  ',
    'OBJETO':    '  !  ',
}

def limpiar():
    sys.stdout.write('\033[2J\033[H')
    sys.stdout.flush()

def dibujar_interfaz():
    with lock:
        s = dict(estado)

    color_modo    = C['cyan']   if s['modo'] == 'REMOTO' else C['yellow']
    color_estado  = C['green']  if s['robot_estado'] not in ('--', 'STOP') else C['gray']
    color_alerta  = C['red']    if s['alerta'] else C['gray']
    color_conexion= C['green']  if s['conectado'] else C['red']
    dir_visual    = MAPA_DIRECCION.get(s['cmd'], '  ?  ')

    lineas = [
        f"{C['cyan']}{C['bold']}╔══════════════════════════════════════╗{C['reset']}",
        f"{C['cyan']}{C['bold']}║       RESQUBE — CONTROL TECLADO      ║{C['reset']}",
        f"{C['cyan']}{C['bold']}╚══════════════════════════════════════╝{C['reset']}",
        "",
        f"  {C['gray']}ROS2:{C['reset']} {color_conexion}{'● CONECTADO' if s['conectado'] else '○ DESCONECTADO'}{C['reset']}",
        f"  {C['gray']}MODO:{C['reset']} {color_modo}{C['bold']}{s['modo']}{C['reset']}",
        f"  {C['gray']}AUTO:{C['reset']} {'🟢 ACTIVO' if s['autonomo'] else '⚫ INACTIVO'}",
        "",
        f"  {C['gray']}──────────── DIRECCIÓN ────────────{C['reset']}",
        f"  {C['white']}{C['bold']}       {dir_visual}      {C['reset']}",
        f"  {C['gray']}Estado robot:{C['reset']} {color_estado}{s['robot_estado']}{C['reset']}",
        "",
        f"  {C['gray']}──────────── SENSORES ─────────────{C['reset']}",
        f"  {C['white']}{s['sensores']}{C['reset']}",
        "",
        f"  {color_alerta}{C['bold']}{'⚠  ALERTA: OBJETO DETECTADO  ⚠' if s['alerta'] else '   Sin alertas'}{C['reset']}",
        "",
        f"  {C['gray']}──────────── CONTROLES ────────────{C['reset']}",
        f"  {C['cyan']}W/↑{C['reset']} Adelante   {C['cyan']}S/↓{C['reset']} Atrás",
        f"  {C['cyan']}A/←{C['reset']} Izquierda  {C['cyan']}D/→{C['reset']} Derecha",
        f"  {C['cyan']}SPC{C['reset']} STOP       {C['cyan']}X{C['reset']}   Servo",
        f"  {C['cyan']}M{C['reset']}   Modo       {C['cyan']}I{C['reset']}   Iniciar auto",
        f"  {C['red']}Q{C['reset']}   Salir",
        "",
    ]

    limpiar()
    print('\n'.join(lineas))

def hilo_interfaz():
    import time
    while True:
        dibujar_interfaz()
        time.sleep(0.2)

# ══════════════════════════════════════════════════════
#  TECLADO
# ══════════════════════════════════════════════════════
teclas_presionadas = set()

def on_press(key):
    global ros_node
    if ros_node is None:
        return

    try:
        k = key.char.lower() if hasattr(key, 'char') else None
    except AttributeError:
        k = None

    # Movimiento — solo envía si es tecla nueva
    if key == keyboard.Key.up    or k == 'w':
        if 'move' not in teclas_presionadas:
            teclas_presionadas.add('move')
            ros_node.enviar_cmd('F')

    elif key == keyboard.Key.down  or k == 's':
        if 'move' not in teclas_presionadas:
            teclas_presionadas.add('move')
            ros_node.enviar_cmd('B')

    elif key == keyboard.Key.left  or k == 'a':
        if 'move' not in teclas_presionadas:
            teclas_presionadas.add('move')
            ros_node.enviar_cmd('L')

    elif key == keyboard.Key.right or k == 'd':
        if 'move' not in teclas_presionadas:
            teclas_presionadas.add('move')
            ros_node.enviar_cmd('R')

    elif key == keyboard.Key.space:
        ros_node.enviar_cmd('S')

    elif k == 'x':
        ros_node.enviar_cmd('X')

    elif k == 'm':
        with lock:
            modo_actual = estado['modo']
        nuevo = 'AUTONOMO' if modo_actual == 'REMOTO' else 'REMOTO'
        ros_node.enviar_modo(nuevo)

    elif k == 'i':
        with lock:
            auto = estado['autonomo']
        ros_node.enviar_autonomo('STOP' if auto else 'START')

    elif k == 'q':
        ros_node.enviar_cmd('S')
        return False  # detiene el listener

def on_release(key):
    global ros_node
    if ros_node is None:
        return

    # Al soltar tecla de movimiento → STOP
    mov_keys = {keyboard.Key.up, keyboard.Key.down,
                keyboard.Key.left, keyboard.Key.right}
    try:
        char = key.char.lower() if hasattr(key, 'char') else None
    except AttributeError:
        char = None

    if key in mov_keys or char in ('w', 'a', 's', 'd'):
        teclas_presionadas.discard('move')
        if ros_node:
            ros_node.enviar_cmd('S')

# ══════════════════════════════════════════════════════
#  HILOS
# ══════════════════════════════════════════════════════
def hilo_ros():
    global ros_node
    rclpy.init()
    ros_node = ResqubeNode()
    rclpy.spin(ros_node)
    ros_node.destroy_node()
    rclpy.shutdown()

# ══════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════
if __name__ == '__main__':
    # Hilo ROS2
    t_ros = threading.Thread(target=hilo_ros, daemon=True)
    t_ros.start()

    # Hilo interfaz
    t_ui = threading.Thread(target=hilo_interfaz, daemon=True)
    t_ui.start()

    print("Iniciando RESQUBE Teleop...")
    import time; time.sleep(1)

    # Listener de teclado (bloqueante)
    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()

    print("\nResqube Teleop cerrado.")
