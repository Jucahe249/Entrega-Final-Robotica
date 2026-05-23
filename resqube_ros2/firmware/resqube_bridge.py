#!/usr/bin/env python3
"""
RESQUBE Web Bridge
Conecta el navegador del celular con ROS2
Puerto: 8080

ESTRUCTURA DE ARCHIVOS:
  ~/resqube/
    web_bridge.py        ← este archivo
    static/
      socket.io.min.js   ← descargar con:
                            wget -O ~/resqube/static/socket.io.min.js \
                            https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.6.0/socket.io.min.js
"""

import threading
import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Bool
from flask import Flask, render_template_string
from flask_socketio import SocketIO, emit

# ─── Flask + SocketIO ─────────────────────────────────
# ✅ static_folder apunta a la carpeta con socket.io.min.js
app = Flask(__name__)
app.config['SECRET_KEY'] = 'resqube2024'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# ─── Estado global ────────────────────────────────────
estado_actual   = "DESCONECTADO"
sensores_actual = ""
alerta_actual   = False

# ─── Nodo ROS2 ────────────────────────────────────────
class ResqubeNode(Node):
    def __init__(self):
        super().__init__('resqube_bridge')

        self.pub_cmd      = self.create_publisher(String, '/resqube/cmd',      10)
        self.pub_modo     = self.create_publisher(String, '/resqube/modo',     10)
        self.pub_autonomo = self.create_publisher(String, '/resqube/autonomo', 10)

        self.sub_estado   = self.create_subscription(
            String, '/resqube/estado',   self.cb_estado,   10)
        self.sub_sensores = self.create_subscription(
            String, '/resqube/sensores', self.cb_sensores, 10)
        self.sub_alerta   = self.create_subscription(
            Bool,   '/resqube/alerta',   self.cb_alerta,   10)

        self.get_logger().info('ResqubeNode iniciado')

    def publicar_cmd(self, cmd: str):
        msg = String(); msg.data = cmd
        self.pub_cmd.publish(msg)
        self.get_logger().info(f'CMD: {cmd}')

    def publicar_modo(self, modo: str):
        msg = String(); msg.data = modo
        self.pub_modo.publish(msg)
        self.get_logger().info(f'MODO: {modo}')

    def publicar_autonomo(self, accion: str):
        msg = String(); msg.data = accion
        self.pub_autonomo.publish(msg)
        self.get_logger().info(f'AUTONOMO: {accion}')

    def cb_estado(self, msg):
        global estado_actual
        estado_actual = msg.data
        socketio.emit('estado', {'data': msg.data})

    def cb_sensores(self, msg):
        global sensores_actual
        sensores_actual = msg.data
        socketio.emit('sensores', {'data': msg.data})

    def cb_alerta(self, msg):
        global alerta_actual
        alerta_actual = msg.data
        socketio.emit('alerta', {'data': msg.data})


ros_node = None

# ─── HTML ─────────────────────────────────────────────
HTML = """
<!DOCTYPE html>
<html>
<head>
  <meta charset='UTF-8'>
  <meta name='viewport' content='width=device-width,initial-scale=1,user-scalable=no'>
  <title>RESQUBE</title>

  <!-- ✅ Servido localmente desde carpeta static/ -->
  <script src='https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.6.0/socket.io.min.js'></script>

  <style>
    *{margin:0;padding:0;box-sizing:border-box}
    body{background:#0d0d0d;color:#fff;font-family:Arial,sans-serif;
    display:flex;flex-direction:column;align-items:center;
    min-height:100vh;gap:12px;padding:16px}
    .logo{font-size:28px;font-weight:bold;color:#00d4ff;letter-spacing:4px;margin-top:8px}
    .subtitle{font-size:11px;color:#666;letter-spacing:2px}
    .cam-container{width:100%;max-width:400px;background:#111;border-radius:12px;
    overflow:hidden;border:2px solid #222;position:relative}
    .cam-container img{width:100%;display:block}
    .cam-overlay{position:absolute;top:8px;left:8px;background:rgba(0,0,0,0.6);
    padding:4px 10px;border-radius:20px;font-size:12px;color:#0f0}
    #alerta{display:none;background:#ff3300;color:#fff;font-weight:bold;
    font-size:16px;padding:10px 24px;border-radius:20px;
    width:100%;max-width:400px;text-align:center}
    .modos{display:flex;gap:10px;width:100%;max-width:400px}
    .btn-modo{flex:1;padding:12px;border:2px solid #333;border-radius:12px;
    background:#1a1a1a;color:#666;font-size:14px;font-weight:bold;cursor:pointer}
    .btn-modo.activo{border-color:#00d4ff;background:#001f2e;color:#00d4ff}
    #estado{font-size:14px;color:#0f0;background:#1a1a1a;padding:6px 20px;
    border-radius:20px;width:100%;max-width:400px;text-align:center}
    #sensores{font-size:11px;color:#666;background:#111;padding:4px 12px;
    border-radius:10px;width:100%;max-width:400px;text-align:center}
    #panelRemoto{display:flex;flex-direction:column;align-items:center;gap:10px;
    width:100%;max-width:400px}
    .grid{display:grid;grid-template-columns:repeat(3,90px);
    grid-template-rows:repeat(3,90px);gap:10px}
    .btn{width:90px;height:90px;border-radius:16px;border:2px solid #333;
    font-size:30px;cursor:pointer;background:#1a1a1a;color:#fff}
    .btn:active{background:#00d4ff;border-color:#00d4ff;color:#000}
    .btn-stop{background:#2a0000;border-color:#c00;font-size:13px;
    font-weight:bold;color:#f55}
    .btn-stop:active{background:#c00;color:#fff}
    .btn-servo{width:100%;height:55px;font-size:15px;font-weight:bold;
    background:#1a1a2e;border:2px solid #00d4ff;border-radius:12px;
    color:#00d4ff;cursor:pointer}
    .btn-servo:active{background:#00d4ff;color:#000}
    .empty{visibility:hidden}
    #panelAutonomo{display:none;flex-direction:column;align-items:center;
    gap:12px;width:100%;max-width:400px}
    .info-box{background:#1a1a1a;border:1px solid #333;border-radius:12px;
    padding:14px;width:100%;font-size:13px;line-height:2;color:#aaa}
    .info-box span{color:#00d4ff;font-weight:bold}
    .btn-iniciar{width:100%;height:65px;font-size:18px;font-weight:bold;
    border:none;border-radius:12px;cursor:pointer}
    .iniciar{background:#005500;color:#0f0;border:2px solid #0f0}
    .detener{background:#550000;color:#f55;border:2px solid #f55}
    .ros-status{font-size:11px;color:#444;margin-top:8px}
  </style>
</head>
<body>
  <div class='logo'>RESQUBE</div>
  <div class='subtitle'>RESCUE ROBOT SYSTEM - ROS2</div>

  <div class='cam-container'>
    <img src='http://ESPCAM_IP/stream' alt='Camara no disponible'>
    <div class='cam-overlay'>REC</div>
  </div>

  <div id='alerta'>OBJETO DETECTADO</div>

  <div class='modos'>
    <button class='btn-modo activo' id='btnRemoto'
      onclick='cambiarModo("REMOTO")'>Modo Remoto</button>
    <button class='btn-modo' id='btnAutonomo'
      onclick='cambiarModo("AUTONOMO")'>Modo Autonomo</button>
  </div>

  <div id='estado'>Conectando...</div>
  <div id='sensores'>Sensores: --</div>

  <div id='panelRemoto'>
    <div class='grid'>
      <div class='empty'></div>
      <button class='btn'
        ontouchstart='cmd("F")' ontouchend='cmd("S")'
        onmousedown='cmd("F")' onmouseup='cmd("S")'>&#9650;</button>
      <div class='empty'></div>
      <button class='btn'
        ontouchstart='cmd("L")' ontouchend='cmd("S")'
        onmousedown='cmd("L")' onmouseup='cmd("S")'>&#9664;</button>
      <button class='btn btn-stop'
        ontouchstart='cmd("S")' onmousedown='cmd("S")'>STOP</button>
      <button class='btn'
        ontouchstart='cmd("R")' ontouchend='cmd("S")'
        onmousedown='cmd("R")' onmouseup='cmd("S")'>&#9654;</button>
      <div class='empty'></div>
      <button class='btn'
        ontouchstart='cmd("B")' ontouchend='cmd("S")'
        onmousedown='cmd("B")' onmouseup='cmd("S")'>&#9660;</button>
      <div class='empty'></div>
    </div>
    <button class='btn-servo'
      ontouchstart='cmd("X")' onmousedown='cmd("X")'>SERVO</button>
  </div>

  <div id='panelAutonomo'>
    <div class='info-box'>
      <span>Pared al frente</span> Gira derecha<br>
      <span>Pared izquierda</span> Corrige derecha<br>
      <span>Pared derecha</span> Corrige izquierda<br>
      <span>Sin paredes</span> OBJETO detectado<br>
      <span>Borde detectado</span> Retrocede
    </div>
    <button class='btn-iniciar iniciar' id='btnIniciar'
      onclick='toggleAuto()'>INICIAR</button>
  </div>

  <div class='ros-status' id='rosStatus'>ROS2: conectando...</div>

  <script>
    var socket = io();
    var autoActivo = false;

    socket.on('connect', function() {
      document.getElementById('rosStatus').innerText = 'ROS2: conectado';
      document.getElementById('rosStatus').style.color = '#0f0';
    });
    socket.on('disconnect', function() {
      document.getElementById('rosStatus').innerText = 'ROS2: desconectado';
      document.getElementById('rosStatus').style.color = '#f00';
    });
    socket.on('estado', function(d) {
      document.getElementById('estado').innerText = d.data;
    });
    socket.on('sensores', function(d) {
      document.getElementById('sensores').innerText = 'Sensores: ' + d.data;
    });
    socket.on('alerta', function(d) {
      document.getElementById('alerta').style.display = d.data ? 'block' : 'none';
    });

    function cmd(c)  { socket.emit('cmd',  {data: c}); }
    function cambiarModo(m) {
      socket.emit('modo', {data: m});
      if (m === 'REMOTO') {
        document.getElementById('panelRemoto').style.display   = 'flex';
        document.getElementById('panelAutonomo').style.display = 'none';
        document.getElementById('btnRemoto').className   = 'btn-modo activo';
        document.getElementById('btnAutonomo').className = 'btn-modo';
        autoActivo = false;
      } else {
        document.getElementById('panelRemoto').style.display   = 'none';
        document.getElementById('panelAutonomo').style.display = 'flex';
        document.getElementById('btnRemoto').className   = 'btn-modo';
        document.getElementById('btnAutonomo').className = 'btn-modo activo';
      }
    }
    function toggleAuto() {
      autoActivo = !autoActivo;
      var btn = document.getElementById('btnIniciar');
      if (autoActivo) {
        btn.textContent = 'DETENER';
        btn.className   = 'btn-iniciar detener';
        socket.emit('autonomo', {data: 'START'});
      } else {
        btn.textContent = 'INICIAR';
        btn.className   = 'btn-iniciar iniciar';
        socket.emit('autonomo', {data: 'STOP'});
      }
    }
  </script>
</body>
</html>
"""

# ─── Rutas Flask ──────────────────────────────────────
@app.route('/')
def index():
    return render_template_string(HTML)

# ─── SocketIO eventos ─────────────────────────────────
@socketio.on('cmd')
def handle_cmd(data):
    if ros_node: ros_node.publicar_cmd(data['data'])

@socketio.on('modo')
def handle_modo(data):
    if ros_node: ros_node.publicar_modo(data['data'])

@socketio.on('autonomo')
def handle_autonomo(data):
    if ros_node: ros_node.publicar_autonomo(data['data'])

# ─── Hilo ROS2 ────────────────────────────────────────
def ros_thread():
    global ros_node
    rclpy.init()
    ros_node = ResqubeNode()
    rclpy.spin(ros_node)
    ros_node.destroy_node()
    rclpy.shutdown()

# ─── Main ─────────────────────────────────────────────
if __name__ == '__main__':
    t = threading.Thread(target=ros_thread, daemon=True)
    t.start()
    print("=" * 48)
    print("  RESQUBE Bridge → http://0.0.0.0:8080")
    print("=" * 48)
    socketio.run(app, host='0.0.0.0', port=8080, debug=False)
