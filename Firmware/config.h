#ifndef CONFIG_H
#define CONFIG_H

#include <Arduino.h>

// WiFi credentials
extern const char* WIFI_SSID;
extern const char* WIFI_PASSWORD;

// AWS IoT Core endpoint
extern const char* AWS_IOT_ENDPOINT;
extern const char* AWS_IOT_TOPIC;

// SN74HC595 Pin mapping
#define DATA    13  // D7 (MOSI) - GPIO13
#define CLOCK   14  // D5 (SCK)  - GPIO14
#define LATCH   12  // D6 (MISO) - GPIO12
#define OE      5   // D1        - GPIO5
#define MR      4   // D2        - GPIO4

// Lane data structure
struct LaneData {
  int entryCount = 0;
  int midCount = 0;
  int exitCount = 0;
  int totalVehicles = 0;
  bool vehicleAtEntry = false;
  bool vehicleAtMid = false;
  bool vehicleAtExit = false;
  int densityLevel = 0;
  String densityCategory = "LOW";
  unsigned long allocatedGreenTime = 5000;
  unsigned long lastEntryDetection = 0;
  unsigned long lastMidDetection = 0;
  unsigned long lastExitDetection = 0;
  bool emergencyWaiting = false;
};

// Emergency vehicle structure
struct EmergencyVehicle {
  bool detected = false;
  unsigned long detectionTime = 0;
  int laneNumber = 0;
  byte uid[4] = {0, 0, 0, 0};
  bool priorityOverride = false;
  unsigned long overrideStartTime = 0;
  int requestedGreenLane = 0;
};

#endif