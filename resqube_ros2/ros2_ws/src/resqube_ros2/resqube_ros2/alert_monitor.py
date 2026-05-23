#!/usr/bin/env python3
"""
alert_monitor.py
Monitorea /object_alert y /scan.
Loguea alertas con timestamp y puede publicar
una parada de emergencia si se configura.
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool
from sensor_msgs.msg import LaserScan
from geometry_msgs.msg import Twist
import time


class AlertMonitor(Node):

    # Si True, publica stop automático al detectar objeto
    PARADA_AUTOMATICA = False

    def __init__(self):
        super().__init__('alert_monitor')

        self.pub_cmd = self.create_publisher(Twist, '/cmd_vel', 10)

        self.create_subscription(Bool,      '/object_alert', self._alert_cb, 10)
        self.create_subscription(LaserScan, '/scan',         self._scan_cb,  10)

        self.en_alerta    = False
        self.t_alerta     = 0.0
        self.scan_data    = [1.0, 1.0, 1.0]

        self.get_logger().info('alert_monitor activo')

    def _alert_cb(self, msg: Bool):
        ahora = time.time()
        if msg.data and not self.en_alerta:
            self.en_alerta = True
            self.t_alerta  = ahora
            self.get_logger().warn(
                f'[ALERTA] Objeto detectado sin paredes — '
                f'scan=[{self.scan_data[0]:.2f}, '
                f'{self.scan_data[1]:.2f}, '
                f'{self.scan_data[2]:.2f}]')
            if self.PARADA_AUTOMATICA:
                self.pub_cmd.publish(Twist())

        elif not msg.data and self.en_alerta:
            duracion = ahora - self.t_alerta
            self.get_logger().info(
                f'[ALERTA] Resuelta — duró {duracion:.1f}s')
            self.en_alerta = False

    def _scan_cb(self, msg: LaserScan):
        if len(msg.ranges) >= 3:
            self.scan_data = list(msg.ranges[:3])


def main(args=None):
    rclpy.init(args=args)
    node = AlertMonitor()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
