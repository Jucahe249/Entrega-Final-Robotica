#!/bin/bash
# ══════════════════════════════════════════════════════
#  RESQUBE — Script de arranque completo
#  Uso: bash resqube_start.sh
# ══════════════════════════════════════════════════════

set -e

CYAN='\033[96m'
GREEN='\033[92m'
YELLOW='\033[93m'
RED='\033[91m'
RESET='\033[0m'
BOLD='\033[1m'

echo -e "${CYAN}${BOLD}"
echo "  ╔══════════════════════════════════╗"
echo "  ║     RESQUBE — SISTEMA INICIO     ║"
echo "  ╚══════════════════════════════════╝"
echo -e "${RESET}"

# ── ROS2 ──
if [ -f /opt/ros/humble/setup.bash ]; then
    source /opt/ros/humble/setup.bash
    echo -e "${GREEN}✓ ROS2 Humble cargado${RESET}"
else
    echo -e "${RED}✗ ROS2 Humble no encontrado${RESET}"
    exit 1
fi

# Workspace propio si existe
if [ -f ~/resqube_ws/install/setup.bash ]; then
    source ~/resqube_ws/install/setup.bash
    echo -e "${GREEN}✓ Workspace resqube_ws cargado${RESET}"
fi

# ── Dependencias Python ──
echo -e "${YELLOW}→ Verificando dependencias Python...${RESET}"
pip install pynput --quiet --break-system-packages 2>/dev/null || true

# ── Firewall ──
echo -e "${YELLOW}→ Abriendo puertos...${RESET}"
sudo ufw allow 8888/udp 2>/dev/null && echo -e "${GREEN}✓ Puerto 8888/udp abierto${RESET}" || true

# ── Terminar contenedor y procesos anteriores ──
echo -e "${YELLOW}→ Limpiando instancias anteriores...${RESET}"
docker stop resqube_agent 2>/dev/null && echo -e "${GREEN}✓ Contenedor anterior detenido${RESET}" || true
docker rm   resqube_agent 2>/dev/null || true
pkill -f "resqube_teleop"  2>/dev/null || true
sleep 1

# ── micro-ROS agent en terminal aparte ──
echo -e "${YELLOW}→ Abriendo terminal del micro-ROS agent...${RESET}"
if command -v gnome-terminal &>/dev/null; then
    gnome-terminal --title="micro-ROS Agent" -- bash -c \
        "docker run -it --rm --net=host --name resqube_agent \
         microros/micro-ros-agent:humble udp4 -p 8888; \
         echo -e '\n[Agente detenido — cerrando en 5s]'; sleep 5"
elif command -v xterm &>/dev/null; then
    xterm -title "micro-ROS Agent" -e \
        "docker run -it --rm --net=host --name resqube_agent \
         microros/micro-ros-agent:humble udp4 -p 8888; \
         echo '[Agente detenido — cerrando en 5s]'; sleep 5" &
else
    echo -e "${RED}✗ No se encontró gnome-terminal ni xterm${RESET}"
    exit 1
fi
sleep 3

# ── Verificar que el contenedor arrancó ──
if docker inspect -f '{{.State.Running}}' resqube_agent 2>/dev/null | grep -q true; then
    echo -e "${GREEN}✓ Agente corriendo${RESET}"
else
    echo -e "${RED}✗ El agente no arrancó — revisa la terminal del agente${RESET}"
    exit 1
fi

echo ""
echo -e "${CYAN}════════════════════════════════════${RESET}"
echo -e "${GREEN}${BOLD}  Sistema listo.${RESET}"
echo -e "  Enciende el ESP32 y espera conexión."
echo -e "  Luego presiona ENTER para abrir el teleop."
echo -e "${CYAN}════════════════════════════════════${RESET}"
echo ""
read -p "  [ENTER para iniciar teleop]"

# ── Teleop ──
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
python3 "$SCRIPT_DIR/resqube_teleop.py"

# ── Limpieza al salir ──
echo -e "\n${YELLOW}→ Deteniendo servicios...${RESET}"
docker stop resqube_agent 2>/dev/null || true
docker rm   resqube_agent 2>/dev/null || true
echo -e "${GREEN}✓ Sistema detenido.${RESET}"
