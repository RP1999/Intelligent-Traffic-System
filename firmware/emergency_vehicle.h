#ifndef EMERGENCY_VEHICLE_H
#define EMERGENCY_VEHICLE_H

#include <Arduino.h>
#include <SPI.h>
#include <MFRC522.h>

// ============================================
// MUX CONTROL VIA PCF8574 (using FREE P6, P7)
// ============================================

// CD4051 Multiplexer control - NOW USING PCF8574 PINS
// (Original GPIO pins are freed - no longer used)
#define MUX_S0     99   // Dummy - not used, handled by PCF
#define MUX_S1     99   // Dummy - not used, handled by PCF
#define MUX_S2     99   // Dummy - not used, handled by PCF

// RFID Module select channels (0-3 for lanes 1-4)
#define LANE1_MUX_CH  0
#define LANE2_MUX_CH  1
#define LANE3_MUX_CH  2
#define LANE4_MUX_CH  3

// Shared RFID pins (connected to all modules via CD4051)
#define RFID_SS     15  // D8  - Slave Select (common)
#define RFID_RST    16  // D0  - Reset (common)

// Number of lanes
#define NUM_LANES   4

// Emergency vehicle structure
struct EmergencyInfo {
  bool detected;
  String tagId;
  int laneNumber;
  unsigned long detectionTime;
};

// Lane-specific detection data
struct LaneDetection {
  bool hasEmergency = false;
  byte emergencyUID[4] = {0, 0, 0, 0};
  unsigned long lastDetectionTime = 0;
  unsigned long lastScanTime = 0;
  unsigned long totalReads = 0;
  unsigned long emergencyReads = 0;
};

// YOUR ACTUAL EMERGENCY TAG UID (from your scan)
extern const byte EMERGENCY_TAG[4];

// Global variables
extern EmergencyInfo emergencyState;
extern LaneDetection lanes[NUM_LANES];
extern MFRC522 rfid;
extern unsigned long totalReads;
extern unsigned long emergencyDetects;

// Function declarations
void initRFID();
void selectMuxChannel(int channel);
void checkRFID(unsigned long currentTime);
void checkLaneRFID(int lane, unsigned long currentTime);
bool isEmergencyVehicle(byte *uid, byte size);
String uidToString(byte *buffer, byte bufferSize);
bool compareUID(byte *uid1, const byte *uid2, byte size);
bool isEmergencyActive();
int getEmergencyLane();
void clearEmergency();
void printRFIDStats();

#endif