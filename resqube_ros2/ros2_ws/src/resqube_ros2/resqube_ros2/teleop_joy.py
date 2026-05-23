#!/usr/bin/env python3
"""
teleop_joy.py
Control remoto desde teclado o joystick.
Publica /cmd_vel y /servo_cmd.
También puede llamar /corridor_follower/activate para cambiar de modo.

Teclas (modo interactivo):
  W/S  → adelante / atrás
  A/D  → izquierda / derecha
  X    → activar servo
  M    → toggle modo autónomo
  Q    → salir
"""

import sys
import tty
import termios
import threading
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from std_msgs.msg import Bool
from std_srvs.srv import SetBool


KEY_MAP = {
    'w': ( 0.20,  0.00),
    's': (-0.20,  0.00),
    'a': ( 0.00,  0.60),
    'd': ( 0.00, -0.60),
    ' ': ( 0.00,  0.00),  # espacio = stop
}


class TeleopNode(Node):

    def __init__(self):
        super().__init__('resqube_teleop')

        self.pub_cmd   = self.create_publisher(Twist, '/cmd_vel',   10)
        self.pub_servo = self.create_publisher(Bool,  '/servo_cmd', 10)

        self.cli_mode = self.create_client(SetBool, '/corridor_follower/activate')

        self.modo_autonomo = False
        self.running       = True

        self.get_logger().info(
            'Teleop RESQUBE\n'
            '  W/S = adelante/atrás  |  A/D = izquierda/derecha\n'
            '  ESPACIO = stop        |  X = servo\n'
            '  M = toggle autónomo   |  Q = salir'
        )

    def get_key(self):
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            return sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)

    def set_mode(self, autonomo: bool):
        if not self.cli_mode.service_is_ready():
            self.get_logger().warn('corridor_follower no disponible')
            return
        req = SetBool.Request()
        req.data = autonomo
        future = self.cli_mode.call_async(req)
        future.add_done_callback(
            lambda f: self.get_logger().info(f'Modo: {f.result().message}'))

    def run(self):
        while self.running:
            key = self.get_key().lower()

            if key == 'q':
                self.running = False
                self.pub_cmd.publish(Twist())
                break

            elif key == 'm':
                self.modo_autonomo = not self.modo_autonomo
                self.set_mode(self.modo_autonomo)
                print(f'\rModo: {"AUTÓNOMO" if self.modo_autonomo else "REMOTO"}   ')

            elif key == 'x':
                msg = Bool()
                msg.data = True
                self.pub_servo.publish(msg)
                print('\rServo activado   ')

            elif key in KEY_MAP:
                if self.modo_autonomo:
                    print('\rEn modo autónomo — presiona M para volver a remoto   ')
                    continue
                twist = Twist()
                twist.linear.x, twist.angular.z = KEY_MAP[key]
                self.pub_cmd.publish(twist)
                print(f'\r{key.upper()} → lin={twist.linear.x:.2f} ang={twist.angular.z:.2f}   ', end='')


def main(args=None):
    rclpy.init(args=args)
    node = TeleopNode()

    spin_thread = threading.Thread(target=rclpy.spin, args=(node,), daemon=True)
    spin_thread.start()

    node.run()
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
