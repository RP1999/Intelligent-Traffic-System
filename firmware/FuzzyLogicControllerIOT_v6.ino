#include <ESP8266WiFi.h>
#include <Wire.h>
#include "ir_sensors.h"
#include "aws_iot.h"
#include "emergency_vehicle.h"
#include "traffic_lights.h"

// WiFi credentials
const char* WIFI_SSID = "STZ";
const char* WIFI_PASSWORD = "ilet4713";

// AWS IoT Core endpoint
const char* AWS_IOT_ENDPOINT = "d01855053akr4kvlp9rjp-ats.iot.us-east-1.amazonaws.com";

// Single MQTT topic for all data
const char* AWS_IOT_TOPIC = "traffic/light/status";

// Device ID
String deviceId;

// Lane vehicle counts
int lane1_cars = 0, lane2_cars = 0, lane3_cars = 0, lane4_cars = 0;

// Lane density categories
String lane1_density = "LOW";
String lane2_density = "LOW";
String lane3_density = "LOW";
String lane4_density = "LOW";

// Timing
unsigned long lastPublishTime = 0;
const long publishInterval = 5000;
unsigned long lastPriorityCalc = 0;
const long priorityCalcInterval = 2000;

// Function prototypes
void onEmergencyDetected();
String getDensityCategory(int carCount);
void printSystemStatus();
void handleSerialCommands();
void testEmergencyLane1();
void testEmergencyLane2();
void testEmergencyLane3();
void testEmergencyLane4();
void testPCF8574();
void testAllLights();
void printPriorities();
void printRFIDLaneStatus();

void setup() {
  Serial.begin(115200);
  delay(2000);

  Serial.println(F("\n╔════════════════════════════════════════╗"));
  Serial.println(F("║    🚦 SMART TRAFFIC CONTROL SYSTEM     ║"));
  Serial.println(F("║         WITH 4-LANE RFID SCANNING       ║"));
  Serial.println(F("╚════════════════════════════════════════╝\n"));

  // Initialize I2C for IR sensors
  Wire.begin(2, 14);  // SDA=D3, SCL=D4
  initSensors();

  // Initialize traffic lights
  initTrafficLights();
  delay(1000);

  // Initialize multi-lane RFID system
  initRFID();

  // Connect to WiFi and AWS
  connectWiFi();
  connectAWS();

  // Get device ID
  deviceId = "ESP8266-" + WiFi.macAddress();
  deviceId.replace(":", "");
  Serial.print(F("📱 Device ID: "));
  Serial.println(deviceId);

  // Start with all red
  allRed();
  delay(RED_TIME);

  Serial.println(F("\n✅ SYSTEM READY!"));
  Serial.println(F("──────────────────"));
  Serial.println(F("Commands: 1-4=Emergency, T=Test All, I=Individual,"));
  Serial.println(F("          P=PCF, R=RFID Stats, S=Status, H=Help"));
  Serial.println(F("──────────────────\n"));
}

void loop() {
  unsigned long currentMillis = millis();

  maintainAWSConnection();

  // Check all RFID lanes for emergency vehicles
  checkRFID(currentMillis);

  // Emergency callback
  static bool lastEmergencyState = false;
  if (isEmergencyActive() && !lastEmergencyState) {
    onEmergencyDetected();
    lastEmergencyState = true;
  } else if (!isEmergencyActive() && lastEmergencyState) {
    lastEmergencyState = false;
  }

  // Read IR sensors for all lanes
  lane1_cars = readLane1();
  lane2_cars = readLane2();
  lane3_cars = readLane3();
  lane4_cars = readLane4();

  // Update densities
  lane1_density = getDensityCategory(lane1_cars);
  lane2_density = getDensityCategory(lane2_cars);
  lane3_density = getDensityCategory(lane3_cars);
  lane4_density = getDensityCategory(lane4_cars);

  // Update traffic lights (handles priority-based sequencing)
  updateTrafficLights();

  // Display status every 5 seconds
  static unsigned long lastDisplay = 0;
  if (currentMillis - lastDisplay > 5000) {
    lastDisplay = currentMillis;
    printSystemStatus();
  }

  // Calculate and display priority every 5 seconds
  if (currentMillis - lastPriorityCalc > 5000) {
    lastPriorityCalc = currentMillis;
    getNextGreenLane();  // This will print priority scores
    printPriorities();
  }

  // Publish to AWS IoT
  if (currentMillis - lastPublishTime >= publishInterval) {

    // Build emergency queue array
    String emergencyQueueStr = "[";
    bool first = true;
    for (int i = 0; i < NUM_LANES; i++) {
      if (lanes[i].hasEmergency) {
        if (!first) emergencyQueueStr += ",";
        emergencyQueueStr += String(i + 1);
        first = false;
      }
    }
    emergencyQueueStr += "]";

    // boolean flag
    bool hasEmergency = !first;

    String payload = "{";
    payload += "\"device_id\":\"" + deviceId + "\",";
    payload += "\"lane1\":" + String(lane1_cars) + ",";
    payload += "\"lane2\":" + String(lane2_cars) + ",";
    payload += "\"lane3\":" + String(lane3_cars) + ",";
    payload += "\"lane4\":" + String(lane4_cars) + ",";
    payload += "\"density1\":\"" + lane1_density + "\",";
    payload += "\"density2\":\"" + lane2_density + "\",";
    payload += "\"density3\":\"" + lane3_density + "\",";
    payload += "\"density4\":\"" + lane4_density + "\",";
    payload += "\"emergency\":" + String(hasEmergency ? "true" : "false") + ",";    // payload += "\"emergency_lane\":" + String(emergencyLane + 1) + ",";
    payload += "\"emergency_queue\":" + emergencyQueueStr + ",";
    payload += "\"state\":" + String(currentState) + ",";
    payload += "\"rfid_total_reads\":" + String(totalReads) + ",";
    payload += "\"rfid_emergency_detects\":" + String(emergencyDetects) + ",";
    payload += "\"timestamp\":" + String(millis());
    payload += "}";

    if (mqttClient.connected()) {
      mqttClient.publish(AWS_IOT_TOPIC, payload.c_str());
    }

    lastPublishTime = currentMillis;
  }

  handleSerialCommands();
  delay(100);
}

// Emergency callback
void onEmergencyDetected() {
  Serial.println(F("\n🚨 EMERGENCY DETECTED!"));
  if (isEmergencyActive()) {
    int lane = getEmergencyLane();
    triggerEmergency(lane - 1);  // Convert to 0-based index
  }
}

// Get density category based on vehicle count
String getDensityCategory(int carCount) {
  if (carCount >= 3) return "HIGH";
  if (carCount == 2) return "MEDIUM";
  if (carCount == 1) return "LOW";
  return "EMPTY";
}

// Print system status
void printSystemStatus() {
  Serial.println(F("\n📊 SYSTEM STATUS:"));
  Serial.print(F("🚦 State: "));
  if (emergencyMode) {
    Serial.print(F("EMERGENCY Lane "));
    Serial.println(emergencyLane + 1);
  } else {
    switch (currentState) {
      case STATE_ALL_RED: Serial.println(F("ALL RED")); break;
      case STATE_PRIORITY_SELECT: Serial.println(F("SELECTING")); break;
      case STATE_LANE1_GREEN: Serial.println(F("LANE 1 GREEN")); break;
      case STATE_LANE2_GREEN: Serial.println(F("LANE 2 GREEN")); break;
      case STATE_LANE3_GREEN: Serial.println(F("LANE 3 GREEN")); break;
      case STATE_LANE4_GREEN: Serial.println(F("LANE 4 GREEN")); break;
      case STATE_LANE1_YELLOW: Serial.println(F("LANE 1 YELLOW")); break;
      case STATE_LANE2_YELLOW: Serial.println(F("LANE 2 YELLOW")); break;
      case STATE_LANE3_YELLOW: Serial.println(F("LANE 3 YELLOW")); break;
      case STATE_LANE4_YELLOW: Serial.println(F("LANE 4 YELLOW")); break;
      default: Serial.println(F("OTHER")); break;
    }
  }

  Serial.println(F("🚗 Vehicle Counts:"));
  Serial.print(F("   Lane1: "));
  Serial.print(lane1_cars);
  Serial.print(F(" ("));
  Serial.print(lane1_density);
  Serial.print(F(")  "));

  Serial.print(F("Lane2: "));
  Serial.print(lane2_cars);
  Serial.print(F(" ("));
  Serial.print(lane2_density);
  Serial.print(F(")  "));

  Serial.print(F("Lane3: "));
  Serial.print(lane3_cars);
  Serial.print(F(" ("));
  Serial.print(lane3_density);
  Serial.print(F(")  "));

  Serial.print(F("Lane4: "));
  Serial.print(lane4_cars);
  Serial.print(F(" ("));
  Serial.print(lane4_density);
  Serial.println(F(")"));

  // Show RFID status
  if (totalReads > 0) {
    Serial.println(F("📡 RFID Status:"));
    Serial.print(F("   Total Scans: "));
    Serial.print(totalReads);
    Serial.print(F(" | Emergency: "));
    Serial.print(emergencyDetects);
    if (totalReads > 0) {
      Serial.print(F(" ("));
      Serial.print((emergencyDetects * 100) / totalReads);
      Serial.print(F("%)"));
    }
    Serial.println();
  }
}

// Print lane priority scores
void printPriorities() {
  Serial.println(F("\n🎯 Lane Priority Scores:"));
  for (int i = 0; i < 4; i++) {
    Serial.print(F("   Lane "));
    Serial.print(i + 1);
    Serial.print(F(": "));
    Serial.print(lanePriority[i]);

    // Add visual indicator
    if (lanePriority[i] >= 100) Serial.print(F(" (HIGH - URGENT)"));
    else if (lanePriority[i] >= 70) Serial.print(F(" (MEDIUM)"));
    else if (lanePriority[i] >= 40) Serial.print(F(" (LOW)"));
    else Serial.print(F(" (EMPTY)"));

    if (emergencyMode && emergencyLane == i) Serial.print(F(" 🚨 EMERGENCY ACTIVE"));
    Serial.println();
  }
}

// Print RFID lane status
void printRFIDLaneStatus() {
  Serial.println(F("\n📡 RFID LANE STATUS:"));
  for (int i = 0; i < NUM_LANES; i++) {
    Serial.print(F("   Lane "));
    Serial.print(i + 1);
    Serial.print(F(": "));
    Serial.print(lanes[i].totalReads);
    Serial.print(F(" reads"));
    if (lanes[i].hasEmergency) {
      Serial.print(F(" 🚨 EMERGENCY DETECTED"));
    }
    Serial.println();
  }
  Serial.print(F("\n   Total Scans: "));
  Serial.println(totalReads);
  Serial.print(F("   Emergency Detects: "));
  Serial.println(emergencyDetects);
}

// Serial command handler
void handleSerialCommands() {
  if (!Serial.available()) return;

  char cmd = Serial.read();

  switch (cmd) {
    case '1': testEmergencyLane1(); break;
    case '2': testEmergencyLane2(); break;
    case '3': testEmergencyLane3(); break;
    case '4': testEmergencyLane4(); break;
    case 't':
    case 'T': testAllLights(); break;
    case 'i':
    case 'I': testIndividualLights(); break;
    case 'p':
    case 'P': testPCF8574(); break;
    case 'r':
    case 'R': printRFIDLaneStatus(); break;
    case 's':
    case 'S': printSystemStatus(); break;
    case 'h':
    case 'H':
      Serial.println(F("\n📋 Commands:"));
      Serial.println(F("  1-4 - Trigger Emergency on Lane 1-4"));
      Serial.println(F("  T   - Test all lights sequentially"));
      Serial.println(F("  I   - Test individual lights"));
      Serial.println(F("  P   - Test PCF8574 (IR sensors)"));
      Serial.println(F("  R   - Show RFID lane statistics"));
      Serial.println(F("  S   - Show system status"));
      Serial.println(F("  H   - Show this help"));
      break;
    default:
      break;
  }
}

// Emergency test functions
void testEmergencyLane1() {
  Serial.println(F("\n🧪 TEST: Simulating Emergency on Lane 1"));
  triggerEmergency(0);
}

void testEmergencyLane2() {
  Serial.println(F("\n🧪 TEST: Simulating Emergency on Lane 2"));
  triggerEmergency(1);
}

void testEmergencyLane3() {
  Serial.println(F("\n🧪 TEST: Simulating Emergency on Lane 3"));
  triggerEmergency(2);
}

void testEmergencyLane4() {
  Serial.println(F("\n🧪 TEST: Simulating Emergency on Lane 4"));
  triggerEmergency(3);
}

// Test PCF8574 IR sensors
void testPCF8574() {
  Serial.println(F("\n🔧 Testing PCF8574 IR Sensors:"));

  Wire.beginTransmission(0x20);
  byte error1 = Wire.endTransmission();
  Serial.print(F("PCF1 (0x20) - Lanes 1&2: "));
  Serial.println(error1 == 0 ? "✅ OK" : "❌ NOT FOUND");

  Wire.beginTransmission(0x21);
  byte error2 = Wire.endTransmission();
  Serial.print(F("PCF2 (0x21) - Lanes 3&4: "));
  Serial.println(error2 == 0 ? "✅ OK" : "❌ NOT FOUND");

  // Read current sensor values
  if (error1 == 0 && error2 == 0) {
    Serial.println(F("\n📊 Current IR Sensor Readings:"));
    Serial.print(F("   Lane 1: "));
    Serial.print(readLane1());
    Serial.println(F(" cars detected"));
    Serial.print(F("   Lane 2: "));
    Serial.print(readLane2());
    Serial.println(F(" cars detected"));
    Serial.print(F("   Lane 3: "));
    Serial.print(readLane3());
    Serial.println(F(" cars detected"));
    Serial.print(F("   Lane 4: "));
    Serial.print(readLane4());
    Serial.println(F(" cars detected"));
  }
}