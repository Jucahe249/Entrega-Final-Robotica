/*
  ============================================
  RESQUBE - ESP32 DevKit V1
  micro-ROS client para ROS2 Humble
  Transport: WiFi UDP
  ============================================
  Topics publicados:
    /scan          sensor_msgs/LaserScan  (3 rayos Sharp)
    /line_sensor   std_msgs/Int32         (QTR raw)
    /object_alert  std_msgs/Bool          (sin paredes)
    /odom          nav_msgs/Odometry      (estimación básica)

  Topics suscritos:
    /cmd_vel       geometry_msgs/Twist
    /servo_cmd     std_msgs/Bool

  Servicios:
    /set_mode      std_srvs/SetBool       (true=AUTONOMO)
  ============================================
*/

#include <micro_ros_arduino.h>
#include <stdio.h>
#include <rcl/rcl.h>
#include <rcl/error_handling.h>
#include <rclc/rclc.h>
#include <rclc/executor.h>

#include <geometry_msgs/msg/twist.h>
#include <sensor_msgs/msg/laser_scan.h>
#include <std_msgs/msg/int32.h>
#include <std_msgs/msg/bool.h>
#include <nav_msgs/msg/odometry.h>
#include <std_srvs/srv/set_bool.h>

#include <ESP32Servo.h>

// ─── WIFI / AGENTE ────────────────────────────────────
#define WIFI_SSID   "TU_RED_WIFI"
#define WIFI_PASS   "TU_PASSWORD"
#define AGENT_IP    "192.168.251.131"   // IP de tu PC con el agente
#define AGENT_PORT  8888

// ─── PINES MOTOR A ────────────────────────────────────
#define PWMA   33
#define AIN1   14
#define AIN2   27

// ─── PINES MOTOR B ────────────────────────────────────
#define PWMB   32
#define BIN1   26
#define BIN2   25

// ─── SENSORES SHARP ───────────────────────────────────
#define SENSOR_IZQ     4
#define SENSOR_FRENTE  18
#define SENSOR_DER     19

// ─── SENSOR LÍNEA ─────────────────────────────────────
#define LINEA_DEL  35

// ─── OTROS ────────────────────────────────────────────
#define STBY      12
#define LED_PIN    2
#define SERVO_PIN 13

// ─── PWM ──────────────────────────────────────────────
#define PWM_FREQ    1000
#define PWM_RES     8
#define CHANNEL_A   0
#define CHANNEL_B   1

// ─── VELOCIDADES ──────────────────────────────────────
#define VEL_AVANCE      200
#define VEL_GIRO        180
#define VEL_CORRECCION  160
#define VEL_RETRO       200

// ─── UMBRAL QTR ───────────────────────────────────────
#define UMBRAL_QTR 2000

// ─── DISTANCIAS SHARP (metros) ────────────────────────
// GP2Y0A21 detecta ~10-80 cm. HIGH = objeto detectado
#define DIST_DETECTED   0.15f   // objeto a ~15 cm
#define DIST_CLEAR      1.0f    // pasillo libre

// ─── PUBLICACIÓN ──────────────────────────────────────
#define PUB_PERIOD_MS   50      // 20 Hz

// ─── micro-ROS handles ────────────────────────────────
rcl_node_t           node;
rclc_support_t       support;
rcl_allocator_t      allocator;
rclc_executor_t      executor;
rcl_timer_t          pub_timer;

rcl_subscription_t   sub_cmdvel;
rcl_subscription_t   sub_servo;
rcl_publisher_t      pub_scan;
rcl_publisher_t      pub_line;
rcl_publisher_t      pub_alert;
rcl_publisher_t      pub_odom;
rcl_service_t        srv_setmode;

geometry_msgs__msg__Twist          msg_cmdvel;
std_msgs__msg__Bool                msg_servo;
sensor_msgs__msg__LaserScan        msg_scan;
std_msgs__msg__Int32               msg_line;
std_msgs__msg__Bool                msg_alert;
nav_msgs__msg__Odometry            msg_odom;
std_srvs__srv__SetBool_Request     req_setmode;
std_srvs__srv__SetBool_Response    res_setmode;

// Buffer para LaserScan (3 rayos)
float scan_ranges[3];
float scan_intensities[3];

// ─── ESTADO ───────────────────────────────────────────
bool modoAutonomo = false;
bool alertaObjeto = false;
Servo miServo;

// ─── MACROS RCCHECK ───────────────────────────────────
#define RCCHECK(fn) { rcl_ret_t temp_rc = fn; if(temp_rc != RCL_RET_OK){ error_loop(); }}
#define RCSOFTCHECK(fn) { rcl_ret_t temp_rc = fn; if(temp_rc != RCL_RET_OK){} }

void error_loop() {
  while(1) {
    digitalWrite(LED_PIN, !digitalRead(LED_PIN));
    delay(100);
  }
}

// ══════════════════════════════════════════════════════
//  MOTORES (igual que antes)
// ══════════════════════════════════════════════════════

void motorsInit() {
  pinMode(AIN1, OUTPUT); pinMode(AIN2, OUTPUT);
  pinMode(BIN1, OUTPUT); pinMode(BIN2, OUTPUT);
  pinMode(STBY, OUTPUT);
  ledcSetup(CHANNEL_A, PWM_FREQ, PWM_RES);
  ledcAttachPin(PWMA, CHANNEL_A);
  ledcSetup(CHANNEL_B, PWM_FREQ, PWM_RES);
  ledcAttachPin(PWMB, CHANNEL_B);
  digitalWrite(STBY, HIGH);
}

void motorA_adelante(int v) { digitalWrite(AIN1,LOW);  digitalWrite(AIN2,HIGH); ledcWrite(CHANNEL_A,v); }
void motorA_atras(int v)    { digitalWrite(AIN1,HIGH); digitalWrite(AIN2,LOW);  ledcWrite(CHANNEL_A,v); }
void motorA_stop()          { digitalWrite(AIN1,LOW);  digitalWrite(AIN2,LOW);  ledcWrite(CHANNEL_A,0); }
void motorB_adelante(int v) { digitalWrite(BIN1,LOW);  digitalWrite(BIN2,HIGH); ledcWrite(CHANNEL_B,v); }
void motorB_atras(int v)    { digitalWrite(BIN1,HIGH); digitalWrite(BIN2,LOW);  ledcWrite(CHANNEL_B,v); }
void motorB_stop()          { digitalWrite(BIN1,LOW);  digitalWrite(BIN2,LOW);  ledcWrite(CHANNEL_B,0); }

void moverAdelante(int v) { motorA_atras(v);    motorB_atras(v);    }
void moverAtras(int v)    { motorA_adelante(v); motorB_adelante(v); }
void girarIzq(int v)      { motorA_atras(v);    motorB_adelante(v); }
void girarDer(int v)      { motorA_adelante(v); motorB_atras(v);    }
void stopMotors()         { motorA_stop();      motorB_stop();      }

// Convierte Twist a comandos de motor
void aplicarTwist(float linear, float angular) {
  if (linear > 0.05f)        moverAdelante(VEL_AVANCE);
  else if (linear < -0.05f)  moverAtras(VEL_AVANCE);
  else if (angular > 0.05f)  girarIzq(VEL_GIRO);
  else if (angular < -0.05f) girarDer(VEL_GIRO);
  else                       stopMotors();
}

// ══════════════════════════════════════════════════════
//  SERVO
// ══════════════════════════════════════════════════════

void toggleServo() {
  miServo.attach(SERVO_PIN, 600, 2400);
  delay(50);
  miServo.writeMicroseconds(1600);
  delay(400);
  miServo.writeMicroseconds(1500);
  delay(400);
  miServo.detach();
}

// ══════════════════════════════════════════════════════
//  CALLBACKS micro-ROS
// ══════════════════════════════════════════════════════

// Llega /cmd_vel (solo actúa en modo REMOTO)
void cmdvel_callback(const void * msgin) {
  if (modoAutonomo) return;
  const geometry_msgs__msg__Twist * msg =
    (const geometry_msgs__msg__Twist *)msgin;
  aplicarTwist(msg->linear.x, msg->angular.z);
}

// Llega /servo_cmd
void servo_callback(const void * msgin) {
  const std_msgs__msg__Bool * msg =
    (const std_msgs__msg__Bool *)msgin;
  if (msg->data) toggleServo();
}

// Servicio /set_mode (true = autónomo, false = remoto)
void setmode_callback(const void * req, void * res) {
  std_srvs__srv__SetBool_Request  * r =
    (std_srvs__srv__SetBool_Request  *)req;
  std_srvs__srv__SetBool_Response * s =
    (std_srvs__srv__SetBool_Response *)res;
  modoAutonomo = r->data;
  if (!modoAutonomo) stopMotors();
  s->success = true;
  rosidl_runtime_c__String__assignn(
    &s->message,
    modoAutonomo ? "Modo AUTONOMO" : "Modo REMOTO",
    modoAutonomo ? 13 : 12);
}

// Timer de publicación (50 ms)
void pub_timer_callback(rcl_timer_t * timer, int64_t last_call_time) {
  RCLC_UNUSED(last_call_time);
  if (timer == NULL) return;

  int64_t stamp_ns = rmw_uros_epoch_nanos();

  // ── /scan ──────────────────────────────────────────
  bool sIzq    = digitalRead(SENSOR_IZQ)    == HIGH;
  bool sFrente = digitalRead(SENSOR_FRENTE) == HIGH;
  bool sDer    = digitalRead(SENSOR_DER)    == HIGH;

  scan_ranges[0] = sIzq    ? DIST_DETECTED : DIST_CLEAR;
  scan_ranges[1] = sFrente ? DIST_DETECTED : DIST_CLEAR;
  scan_ranges[2] = sDer    ? DIST_DETECTED : DIST_CLEAR;

  msg_scan.header.stamp.sec     = (int32_t)(stamp_ns / 1000000000LL);
  msg_scan.header.stamp.nanosec = (uint32_t)(stamp_ns % 1000000000LL);
  msg_scan.angle_min    = -1.5708f;  // -90°
  msg_scan.angle_max    =  1.5708f;  //  90°
  msg_scan.angle_increment = 1.5708f;// 90° entre rayos
  msg_scan.range_min    = 0.10f;
  msg_scan.range_max    = 1.00f;
  msg_scan.ranges.data  = scan_ranges;
  msg_scan.ranges.size  = 3;
  msg_scan.ranges.capacity = 3;
  RCSOFTCHECK(rcl_publish(&pub_scan, &msg_scan, NULL));

  // ── /line_sensor ───────────────────────────────────
  msg_line.data = analogRead(LINEA_DEL);
  RCSOFTCHECK(rcl_publish(&pub_line, &msg_line, NULL));

  // ── /object_alert ──────────────────────────────────
  alertaObjeto = (!sIzq && !sFrente && !sDer);
  msg_alert.data = alertaObjeto;
  RCSOFTCHECK(rcl_publish(&pub_alert, &msg_alert, NULL));

  // ── LED heartbeat ──────────────────────────────────
  digitalWrite(LED_PIN, !digitalRead(LED_PIN));
}

// ══════════════════════════════════════════════════════
//  SETUP
// ══════════════════════════════════════════════════════

void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN,       OUTPUT);
  pinMode(SENSOR_IZQ,    INPUT);
  pinMode(SENSOR_FRENTE, INPUT);
  pinMode(SENSOR_DER,    INPUT);
  pinMode(LINEA_DEL,     INPUT);

  miServo.attach(SERVO_PIN, 600, 2400);
  miServo.writeMicroseconds(1500);
  delay(300);
  miServo.detach();

  motorsInit();

  // Conectar al agente micro-ROS vía WiFi
  set_microros_wifi_transports((char*)WIFI_SSID, (char*)WIFI_PASS, (char*)AGENT_IP, AGENT_PORT);
  delay(2000);

  allocator = rcl_get_default_allocator();
  RCCHECK(rclc_support_init(&support, 0, NULL, &allocator));
  RCCHECK(rclc_node_init_default(&node, "resqube", "", &support));

  // Sincronizar tiempo con el agente
  RCCHECK(rmw_uros_sync_session(1000));

  // ── Publishers ──────────────────────────────────────
  RCCHECK(rclc_publisher_init_default(&pub_scan,  &node,
    ROSIDL_GET_MSG_TYPE_SUPPORT(sensor_msgs, msg, LaserScan), "/scan"));
  RCCHECK(rclc_publisher_init_default(&pub_line,  &node,
    ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, Int32), "/line_sensor"));
  RCCHECK(rclc_publisher_init_default(&pub_alert, &node,
    ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, Bool), "/object_alert"));
  RCCHECK(rclc_publisher_init_default(&pub_odom,  &node,
    ROSIDL_GET_MSG_TYPE_SUPPORT(nav_msgs, msg, Odometry), "/odom"));

  // ── Subscribers ─────────────────────────────────────
  RCCHECK(rclc_subscription_init_default(&sub_cmdvel, &node,
    ROSIDL_GET_MSG_TYPE_SUPPORT(geometry_msgs, msg, Twist), "/cmd_vel"));
  RCCHECK(rclc_subscription_init_default(&sub_servo, &node,
    ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, Bool), "/servo_cmd"));

  // ── Servicio ────────────────────────────────────────
  RCCHECK(rclc_service_init_default(&srv_setmode, &node,
    ROSIDL_GET_SRV_TYPE_SUPPORT(std_srvs, srv, SetBool), "/set_mode"));

  // ── Timer de publicación ────────────────────────────
  RCCHECK(rclc_timer_init_default2(&pub_timer, &support,
    RCL_MS_TO_NS(PUB_PERIOD_MS), pub_timer_callback, true));

  // ── Executor (1 timer + 2 subs + 1 srv = 4 handles) ─
  RCCHECK(rclc_executor_init(&executor, &support.context, 4, &allocator));
  RCCHECK(rclc_executor_add_timer(&executor, &pub_timer));
  RCCHECK(rclc_executor_add_subscription(&executor, &sub_cmdvel,
    &msg_cmdvel, &cmdvel_callback, ON_NEW_DATA));
  RCCHECK(rclc_executor_add_subscription(&executor, &sub_servo,
    &msg_servo, &servo_callback, ON_NEW_DATA));
  RCCHECK(rclc_executor_add_service(&executor, &srv_setmode,
    &req_setmode, &res_setmode, &setmode_callback));

  // Parpadeo OK
  for (int i = 0; i < 5; i++) {
    digitalWrite(LED_PIN, HIGH); delay(100);
    digitalWrite(LED_PIN, LOW);  delay(100);
  }
  Serial.println("[RESQUBE] micro-ROS listo");
}

// ══════════════════════════════════════════════════════
//  LOOP
// ══════════════════════════════════════════════════════

void loop() {
  rclc_executor_spin_some(&executor, RCL_MS_TO_NS(10));
}
