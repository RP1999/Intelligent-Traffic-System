#ifndef EMERGENCY_VEHICLE_H
#define EMERGENCY_VEHICLE_H

#include <Arduino.h>

// Emergency vehicle structure
struct EmergencyInfo {
  bool detected;
  String tagId;
  int laneNumber;
  unsigned long detectionTime;
};

// Global variables (declare as extern)
extern EmergencyInfo emergencyState;
extern unsigned long readerReads;
extern unsigned long emergencyDetects;
extern unsigned long unknownDetects;

// Function declarations
void initRFID();
void checkRFID(unsigned long currentTime);
bool isEmergencyActive();
int getEmergencyLane();
void clearEmergency();
String uidToString(byte *buffer, byte bufferSize);
bool compareUID(byte *uid1, const byte *uid2, byte size);
bool isEmergencyVehicle(byte *uid, byte size);

#endif