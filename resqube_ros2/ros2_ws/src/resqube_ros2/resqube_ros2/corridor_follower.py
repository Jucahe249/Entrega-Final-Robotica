#!/usr/bin/env python3
"""
corridor_follower.py
Nodo ROS2 que replica logicoAutonomo() del firmware original.
Suscribe /scan y /line_sensor, publica /cmd_vel.
Se activa/desactiva llamando al servicio /set_mode en el ESP32.
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from sensor_msgs.msg import LaserScan
from std_msgs.msg import Int32, Bool
from std_srvs.srv import SetBool


class CorridorFollower(Node):

    # ── Parámetros de velocidad (mismo criterio que el firmware) ──
    VEL_AVANCE     = 0.20   # m/s
    VEL_GIRO       = 0.60   # rad/s
    VEL_CORRECCION = 0.45   # rad/s
    VEL_RETRO      = 0.20   # m/s

    # Umbral: distancia (m) para considerar "pared detectada"
    DIST_PARED = 0.30
    # Umbral QTR: valor raw por debajo = borde detectado
    UMBRAL_QTR = 2000

    def __init__(self):
        super().__init__('corridor_follower')

        self.activo      = False
        self.scan_data   = [1.0, 1.0, 1.0]   # [izq, frente, der]
        self.line_raw    = 4095

        # Publisher
        self.pub_cmd = self.create_publisher(Twist, '/cmd_vel', 10)

        # Subscribers
        self.create_subscription(LaserScan, '/scan',        self._scan_cb,  10)
        self.create_subscription(Int32,     '/line_sensor', self._line_cb,  10)
        self.create_subscription(Bool,      '/object_alert',self._alert_cb, 10)

        # Servicio cliente para cambiar modo en el ESP32
        self.cli_setmode = self.create_client(SetBool, '/set_mode')

        # Servicio servidor para que otros nodos activen este seguidor
        self.srv_activate = self.create_service(
            SetBool, '/corridor_follower/activate', self._activate_cb)

        # Timer de control (20 Hz)
        self.timer = self.create_timer(0.05, self._control_loop)

        self.get_logger().info('corridor_follower listo')

    # ── Callbacks sensores ────────────────────────────────────────

    def _scan_cb(self, msg: LaserScan):
        if len(msg.ranges) >= 3:
            self.scan_data = list(msg.ranges[:3])

    def _line_cb(self, msg: Int32):
        self.line_raw = msg.data

    def _alert_cb(self, msg: Bool):
        if msg.data:
            self.get_logger().warn('OBJETO DETECTADO — sin paredes visibles')

    # ── Activar / desactivar ──────────────────────────────────────

    def _activate_cb(self, request, response):
        self.activo = request.data
        # Propagar el modo al ESP32
        if self.cli_setmode.service_is_ready():
            req = SetBool.Request()
            req.data = self.activo
            self.cli_setmode.call_async(req)
        if not self.activo:
            self._stop()
        response.success = True
        response.message = 'AUTONOMO' if self.activo else 'REMOTO'
        self.get_logger().info(f'Modo cambiado a: {response.message}')
        return response

    # ── Lógica de control (replica logicoAutonomo) ────────────────

    def _control_loop(self):
        if not self.activo:
            return

        s_izq    = self.scan_data[0] < self.DIST_PARED
        s_frente = self.scan_data[1] < self.DIST_PARED
        s_der    = self.scan_data[2] < self.DIST_PARED
        borde    = self.line_raw < self.UMBRAL_QTR

        twist = Twist()

        if borde and not s_frente:
            # Borde detectado → retroceder
            self.get_logger().debug('BORDE → retroceder')
            twist.linear.x  = -self.VEL_RETRO
            twist.angular.z =  0.0

        elif s_frente:
            # Pared al frente → girar derecha
            self.get_logger().debug('PARED FRENTE → girar derecha')
            twist.linear.x  =  0.0
            twist.angular.z = -self.VEL_GIRO

        elif s_izq and not s_der:
            # Solo pared izquierda → corrección derecha
            self.get_logger().debug('PARED IZQ → corrección derecha')
            twist.linear.x  = self.VEL_AVANCE * 0.5
            twist.angular.z = -self.VEL_CORRECCION

        elif s_der and not s_izq:
            # Solo pared derecha → corrección izquierda
            self.get_logger().debug('PARED DER → corrección izquierda')
            twist.linear.x  = self.VEL_AVANCE * 0.5
            twist.angular.z =  self.VEL_CORRECCION

        elif s_izq and s_der:
            # Pasillo centrado → avanzar
            self.get_logger().debug('PASILLO → avanzar')
            twist.linear.x  = self.VEL_AVANCE
            twist.angular.z = 0.0

        else:
            # Sin paredes → avanzar (objeto no detectado por Sharp)
            self.get_logger().debug('LIBRE → avanzar')
            twist.linear.x  = self.VEL_AVANCE
            twist.angular.z = 0.0

        self.pub_cmd.publish(twist)

    def _stop(self):
        self.pub_cmd.publish(Twist())


def main(args=None):
    rclpy.init(args=args)
    node = CorridorFollower()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
