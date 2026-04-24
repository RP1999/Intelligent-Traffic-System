#include "ir_sensors.h"
#include <Wire.h>

// First PCF8574 (0x20) - Lanes 1 & 2
#define PCF1_ADDR 0x20

// Second PCF8574 (0x21) - Lanes 3 & 4
#define PCF2_ADDR 0x21

// Initialize I2C and PCF8574 chips
void initSensors() {
  Wire.begin(2, 0);  // SDA=D3, SCL=D4
  
  // Configure first PCF8574
  Wire.beginTransmission(PCF1_ADDR);
  Wire.write(0xFF);  // All pins HIGH = inputs with pull-ups
  byte error1 = Wire.endTransmission();
  
  // Configure second PCF8574
  Wire.beginTransmission(PCF2_ADDR);
  Wire.write(0xFF);
  byte error2 = Wire.endTransmission();
  
  if(error1 == 0) {
    Serial.println(F("PCF8574 #1 (0x20) - Lanes 1 & 2 - OK"));
  } else {
    Serial.println(F("PCF8574 #1 not found!"));
  }
  
  if(error2 == 0) {
    Serial.println(F("PCF8574 #2 (0x21) - Lanes 3 & 4 - OK"));
  } else {
    Serial.println(F("PCF8574 #2 not found!"));
  }
}

// Read from specific PCF8574
byte readPCF(int addr) {
  Wire.requestFrom(addr, 1);
  if (Wire.available()) {
    return Wire.read();
  }
  return 0xFF;
}

// Read Lane 1 sensors (returns car count 0-3)
int readLane1() {
  byte data = readPCF(PCF1_ADDR);
  
  int e = ((data >> 0) & 1) == 0 ? 1 : 0;  // L1_ENTRY at P0
  int m = ((data >> 1) & 1) == 0 ? 1 : 0;  // L1_MEDIUM at P1
  int x = ((data >> 2) & 1) == 0 ? 1 : 0;  // L1_EXIT at P2
  
  return e + m + x;
}

// Read Lane 2 sensors (returns car count 0-3)
int readLane2() {
  byte data = readPCF(PCF1_ADDR);
  
  int e = ((data >> 3) & 1) == 0 ? 1 : 0;  // L2_ENTRY at P3
  int m = ((data >> 4) & 1) == 0 ? 1 : 0;  // L2_MEDIUM at P4
  int x = ((data >> 5) & 1) == 0 ? 1 : 0;  // L2_EXIT at P5
  
  return e + m + x;
}

// Read Lane 3 sensors (returns car count 0-3)
int readLane3() {
  byte data = readPCF(PCF2_ADDR);
  
  int e = ((data >> 0) & 1) == 0 ? 1 : 0;  // L3_ENTRY at P0
  int m = ((data >> 1) & 1) == 0 ? 1 : 0;  // L3_MEDIUM at P1
  int x = ((data >> 2) & 1) == 0 ? 1 : 0;  // L3_EXIT at P2
  
  return e + m + x;
}

// Read Lane 4 sensors (returns car count 0-3)
int readLane4() {
  byte data = readPCF(PCF2_ADDR);
  
  int e = ((data >> 3) & 1) == 0 ? 1 : 0;  // L4_ENTRY at P3
  int m = ((data >> 4) & 1) == 0 ? 1 : 0;  // L4_MEDIUM at P4
  int x = ((data >> 5) & 1) == 0 ? 1 : 0;  // L4_EXIT at P5
  
  return e + m + x;
}