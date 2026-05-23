cmake_minimum_required(VERSION 3.8)
project(resqube_ros2)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)

ament_python_install_package(${PROJECT_NAME})

install(PROGRAMS
  resqube_ros2/corridor_follower.py
  resqube_ros2/teleop_joy.py
  resqube_ros2/alert_monitor.py
  DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY launch config
  DESTINATION share/${PROJECT_NAME}
)

ament_package()
