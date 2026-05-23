# RESQUBE ROS2

## Estructura
```
resqube_ros2/
├── firmware/
│   ├── platformio.ini
│   └── resqube_firmware/
│       └── resqube_firmware.ino     ← flashear al ESP32
└── ros2_ws/
    └── src/resqube_ros2/
        ├── package.xml
        ├── CMakeLists.txt
        ├── resqube_ros2/
        │   ├── corridor_follower.py ← modo autónomo
        │   ├── teleop_joy.py        ← control por teclado
        │   └── alert_monitor.py     ← monitor de alertas
        ├── launch/
        │   └── resqube.launch.py    ← lanza todo
        └── config/
            └── rviz_resqube.rviz
```

## Requisitos
- ROS2 Humble
- micro-ROS Agent: `sudo apt install ros-humble-micro-ros-agent`
- PlatformIO con lib micro_ros_arduino
- ESP32 DevKit V1

## Instalación del workspace
```bash
cd ros2_ws
rosdep install --from-paths src --ignore-src -r -y
colcon build --packages-select resqube_ros2
source install/setup.bash
```

## Configurar el firmware
Editar en resqube_firmware.ino:
```cpp
#define WIFI_SSID  "TU_RED_WIFI"
#define WIFI_PASS  "TU_PASSWORD"
#define AGENT_IP   "192.168.1.100"   // IP de tu PC
#define AGENT_PORT 8888
```
Flashear con PlatformIO:
```bash
cd firmware
pio run --target upload
```

## Ejecutar
```bash
# Terminal 1 — todo de una vez:
ros2 launch resqube_ros2 resqube.launch.py

# O manualmente:
# T1 — agente
ros2 run micro_ros_agent micro_ros_agent udp4 --port 8888
# T2 — seguidor autónomo
ros2 run resqube_ros2 corridor_follower.py
# T3 — alertas
ros2 run resqube_ros2 alert_monitor.py
# T4 — teclado
ros2 run resqube_ros2 teleop_joy.py
```

## Verificar conexión
```bash
ros2 topic list          # debe mostrar /scan /cmd_vel /object_alert
ros2 topic hz /scan      # debe mostrar ~20 Hz
ros2 topic echo /scan    # ver datos en tiempo real
```

## Cambiar modo desde terminal
```bash
# Activar autónomo
ros2 service call /corridor_follower/activate std_srvs/srv/SetBool "{data: true}"
# Volver a remoto
ros2 service call /corridor_follower/activate std_srvs/srv/SetBool "{data: false}"
```

## Teleop desde teclado (en teleop_joy.py)
  W/S = adelante/atrás
  A/D = izquierda/derecha
  ESPACIO = stop
  X = activar servo
  M = toggle modo autónomo
  Q = salir
