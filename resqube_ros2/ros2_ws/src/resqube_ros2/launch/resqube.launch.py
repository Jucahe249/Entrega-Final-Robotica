"""
resqube.launch.py
Lanza todo el sistema RESQUBE:
  1. micro-ROS Agent (UDP, puerto 8888)
  2. corridor_follower
  3. alert_monitor
  4. teleop (opcional, comentar si usas joystick físico)
"""

from launch import LaunchDescription
from launch.actions import ExecuteProcess, TimerAction
from launch_ros.actions import Node


def generate_launch_description():

    # ── micro-ROS Agent ───────────────────────────────────────────
    # Requiere tener instalado micro-ROS Agent:
    #   sudo apt install ros-humble-micro-ros-agent
    agent = ExecuteProcess(
        cmd=['ros2', 'run', 'micro_ros_agent', 'micro_ros_agent',
             'udp4', '--port', '8888'],
        output='screen',
        name='micro_ros_agent'
    )

    # ── Esperar 3 s a que el agente arranque antes de los nodos ───
    corridor = TimerAction(
        period=3.0,
        actions=[
            Node(
                package='resqube_ros2',
                executable='corridor_follower.py',
                name='corridor_follower',
                output='screen',
            )
        ]
    )

    alert = TimerAction(
        period=3.0,
        actions=[
            Node(
                package='resqube_ros2',
                executable='alert_monitor.py',
                name='alert_monitor',
                output='screen',
            )
        ]
    )

    # Teleop — comentar si no quieres control por teclado al arrancar
    teleop = TimerAction(
        period=3.0,
        actions=[
            Node(
                package='resqube_ros2',
                executable='teleop_joy.py',
                name='resqube_teleop',
                output='screen',
                prefix='xterm -e',   # abre terminal separada para el teclado
            )
        ]
    )

    return LaunchDescription([agent, corridor, alert, teleop])
