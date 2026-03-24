#include "emergency_vehicle.h"
#include <SPI.h>
#include <MFRC522.h>
#include <Wire.h>

// Shared RFID instance
MFRC522 rfid(RFID_SS, RFID_RST);

// Emergency tag UID
const byte EMERGENCY_TAG[4] = {0x51, 0xA7, 0x0E, 0x06};


// Global emergency state
EmergencyInfo emergencyState = {false, "", 0, 0};

// Lane-specific detection data
LaneDetection lanes[NUM_LANES];

// Statistics
unsigned long totalReads = 0;
unsigned long emergencyDetects = 0;

// Current active lane being scanned
int currentScanLane = 0;
unsigned long lastLaneSwitch = 0;
const unsigned long LANE_SCAN_INTERVAL = 150; // ms per lane

// ============================================
// MUX CONTROL VIA PCF8574 (using FREE P6, P7 on PCF1 at 0x20)
// ============================================
#define PCF_MUX_ADDR   0x20     // Using PCF1 free pins P6 and P7
#define MUX_S0_BIT     6        // P6 on PCF1 - FREE
#define MUX_S1_BIT     7        // P7 on PCF1 - FREE

// Write to PCF8574 for MUX control
void writePCFForMUX(byte data) {
  Wire.beginTransmission(PCF_MUX_ADDR);
  Wire.write(data);
  Wire.endTransmission();
  delayMicroseconds(50);
}

// Select CD4051 multiplexer channel (using PCF8574)
void selectMuxChannel(int channel) {
  // Read current PCF state first (preserve other pins like IR sensors)
  Wire.requestFrom(PCF_MUX_ADDR, 1);
  byte currentPins = 0xFF;
  if (Wire.available()) {
    currentPins = Wire.read();
  }
  
  // Clear MUX control bits (P6 and P7)
  currentPins &= ~(0b11000000);  // Clear bits 6 and 7
  
  // Set new MUX channel bits
  if (channel & 0x01) currentPins |= (1 << MUX_S0_BIT);  // S0 bit
  if (channel & 0x02) currentPins |= (1 << MUX_S1_BIT);  // S1 bit
  
  // Write back
  writePCFForMUX(currentPins);
  
  // Small delay for mux to settle
  delayMicroseconds(100);
}

// Convert UID to string
String uidToString(byte *buffer, byte bufferSize) {
  String uid = "";
  for (byte i = 0; i < bufferSize; i++) {
    if (buffer[i] < 0x10) uid += "0";
    uid += String(buffer[i], HEX);
    uid.toUpperCase();
  }
  return uid;
}

// Compare two UIDs
bool compareUID(byte *uid1, const byte *uid2, byte size) {
  for (byte i = 0; i < size; i++) {
    if (uid1[i] != uid2[i]) return false;
  }
  return true;
}

// Check if UID matches emergency vehicle
bool isEmergencyVehicle(byte *uid, byte size) {
  if (size == 4) {
    return compareUID(uid, EMERGENCY_TAG, 4);
  }
  return false;
}

// Initialize RFID reader system for all 4 lanes
void initRFID() {
  Serial.println(F("\n🔷 Initializing Multi-Lane RFID System with CD4051..."));
  
  // Initialize MUX control via PCF8574
  // Set P6 and P7 as outputs (by writing to them)
  Wire.requestFrom(PCF_MUX_ADDR, 1);
  byte initialPins = 0xFF;
  if (Wire.available()) {
    initialPins = Wire.read();
  }
  // Clear P6,P7 to set them LOW initially
  initialPins &= ~(0b11000000);
  writePCFForMUX(initialPins);
  
  // Set initial mux channel
  selectMuxChannel(LANE1_MUX_CH);
  
  // Configure shared RFID pins
  pinMode(RFID_SS, OUTPUT);
  digitalWrite(RFID_SS, HIGH);
  
  // Initialize SPI
  SPI.begin();
  SPI.setFrequency(1000000);
  delay(100);
  
  // Test each RFID module
  Serial.println(F("\n🔍 Testing RFID modules on all lanes:"));
  bool anyWorking = false;
  
  for (int lane = 0; lane < NUM_LANES; lane++) {
    selectMuxChannel(lane);
    delay(50);
    
    // Re-initialize RFID for this module
    rfid.PCD_Init();
    delay(50);
    
    byte version = rfid.PCD_ReadRegister(MFRC522::VersionReg);
    
    Serial.print(F("   Lane "));
    Serial.print(lane + 1);
    Serial.print(F(": "));
    
    if (version == 0x00 || version == 0xFF) {
      Serial.println(F("❌ NOT DETECTED"));
    } else {
      Serial.print(F("✅ OK (Version: 0x"));
      Serial.print(version, HEX);
      Serial.println(F(")"));
      anyWorking = true;
      
      // Enable antenna for this module
      rfid.PCD_SetRegisterBitMask(MFRC522::TxControlReg, 0x03);
      rfid.PCD_SetAntennaGain(MFRC522::RxGain_max);
    }
  }
  
  // Select lane 1 as default
  selectMuxChannel(LANE1_MUX_CH);
  rfid.PCD_Init();
  
  if (anyWorking) {
    Serial.println(F("\n✅ Multi-lane RFID system ready!"));
    Serial.println(F("   Using PCF8574 (0x20) P6,P7 for MUX control"));
    Serial.println(F("   Scanning lanes in round-robin mode"));
    Serial.print(F("   Emergency Tag UID: "));
    Serial.println(uidToString((byte*)EMERGENCY_TAG, 4));
    Serial.println(F("\n   Lane Legend:"));
    Serial.println(F("   • Lane 1 → MUX Channel 0 (S0=0,S1=0)"));
    Serial.println(F("   • Lane 2 → MUX Channel 1 (S0=1,S1=0)"));
    Serial.println(F("   • Lane 3 → MUX Channel 2 (S0=0,S1=1)"));
    Serial.println(F("   • Lane 4 → MUX Channel 3 (S0=1,S1=1)"));
    Serial.println(F("\n   Waiting for RFID tags...\n"));
  } else {
    Serial.println(F("❌ No RFID modules detected! Check wiring."));
  }
}

// Check RFID for emergency vehicle on all lanes (round-robin)
void checkRFID(unsigned long currentTime) {
  // Round-robin through lanes
  if (currentTime - lastLaneSwitch >= LANE_SCAN_INTERVAL) {
    lastLaneSwitch = currentTime;
    
    // Move to next lane
    currentScanLane = (currentScanLane + 1) % NUM_LANES;
    
    // Switch mux to current lane
    selectMuxChannel(currentScanLane);
    delayMicroseconds(100);
    
    // Re-initialize RFID for this module (quick reset)
    rfid.PCD_Init();
    delayMicroseconds(50);
    
    // Check this lane
    checkLaneRFID(currentScanLane, currentTime);
  }
}

// Check a specific lane for RFID tags
void checkLaneRFID(int lane, unsigned long currentTime) {
  // Check for new card
  if (!rfid.PICC_IsNewCardPresent()) return;
  if (!rfid.PICC_ReadCardSerial()) return;
  
  // Update lane statistics
  lanes[lane].totalReads++;
  lanes[lane].lastDetectionTime = currentTime;
  totalReads++;
  
  String tagId = uidToString(rfid.uid.uidByte, rfid.uid.size);
  
  // Print detection (only if not repeated too quickly)
  if (currentTime - lanes[lane].lastScanTime > 1000) {
    lanes[lane].lastScanTime = currentTime;
    
    Serial.println(F("\n📌 ───────────────────────────"));
    Serial.println(F("📌 RFID TAG DETECTED!"));
    Serial.println(F("📌 ───────────────────────────"));
    Serial.print(F("   Lane: "));
    Serial.println(lane + 1);
    Serial.print(F("   UID: "));
    Serial.println(tagId);
    Serial.print(F("   Size: "));
    Serial.print(rfid.uid.size);
    Serial.println(F(" bytes"));
    
    // Check if emergency vehicle
    if (isEmergencyVehicle(rfid.uid.uidByte, rfid.uid.size)) {
      lanes[lane].hasEmergency = true;
      memcpy(lanes[lane].emergencyUID, rfid.uid.uidByte, 4);
      lanes[lane].emergencyReads++;
      emergencyDetects++;
      
      // Update global emergency state
      emergencyState.detected = true;
      emergencyState.tagId = tagId;
      emergencyState.laneNumber = lane + 1;
      emergencyState.detectionTime = currentTime;
      
      Serial.println(F("\n   🚨 VEHICLE TYPE: EMERGENCY!"));
      Serial.println(F("   ✅ MATCH FOUND!"));
      Serial.print(F("   ⚡ ACTION: TURNING LANE "));
      Serial.print(lane + 1);
      Serial.println(F(" GREEN"));
      
    } else {
      Serial.println(F("\n   🚗 VEHICLE TYPE: Regular"));
      Serial.println(F("   ❌ Not an emergency vehicle"));
    }
    
    printRFIDStats();
    Serial.println(F("📌 ───────────────────────────\n"));
  }
  
  // Halt card
  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();
  
  // Auto-clear emergency after 10 seconds of no detection
  static unsigned long lastClearMsg = 0;
  if (emergencyState.detected) {
    // Check if any lane still has active emergency
    bool anyEmergency = false;
    for (int i = 0; i < NUM_LANES; i++) {
      if (lanes[i].hasEmergency && (currentTime - lanes[i].lastDetectionTime < 10000)) {
        anyEmergency = true;
        break;
      } else if (lanes[i].hasEmergency && (currentTime - lanes[i].lastDetectionTime >= 10000)) {
        lanes[i].hasEmergency = false;
      }
    }
    
    if (!anyEmergency && emergencyState.detected) {
      emergencyState.detected = false;
      emergencyState.tagId = "";
      emergencyState.laneNumber = 0;
      Serial.println(F("\n🔄 Emergency mode cleared (10s timeout)\n"));
    } else if (emergencyState.detected && currentTime - lastClearMsg > 2000) {
      lastClearMsg = currentTime;
      int timeLeft = 10 - ((currentTime - emergencyState.detectionTime) / 1000);
      if (timeLeft > 0) {
        Serial.print(F("⏱️ Emergency active - Lane "));
        Serial.print(emergencyState.laneNumber);
        Serial.print(F(" - Time left: "));
        Serial.print(timeLeft);
        Serial.println(F("s"));
      }
    }
  }
}

// Print RFID statistics
void printRFIDStats() {
  Serial.println(F("\n📊 RFID Statistics:"));
  Serial.print(F("   Total Scans: "));
  Serial.println(totalReads);
  Serial.print(F("   Emergency Detects: "));
  Serial.print(emergencyDetects);
  if (totalReads > 0) {
    Serial.print(F(" ("));
    Serial.print((emergencyDetects * 100) / totalReads);
    Serial.print(F("%)"));
  }
  Serial.println();
  
  Serial.println(F("   Per Lane:"));
  for (int i = 0; i < NUM_LANES; i++) {
    Serial.print(F("     Lane "));
    Serial.print(i + 1);
    Serial.print(F(": "));
    Serial.print(lanes[i].totalReads);
    Serial.print(F(" reads"));
    if (lanes[i].hasEmergency) {
      Serial.print(F(" 🚨"));
    }
    Serial.println();
  }
}

// Check if emergency is active
bool isEmergencyActive() {
  return emergencyState.detected;
}

// Get emergency lane
int getEmergencyLane() {
  return emergencyState.laneNumber;
}

// Clear emergency manually
void clearEmergency() {
  emergencyState.detected = false;
  emergencyState.tagId = "";
  emergencyState.laneNumber = 0;
  
  for (int i = 0; i < NUM_LANES; i++) {
    lanes[i].hasEmergency = false;
  }
  
  Serial.println(F("🔄 Emergency manually cleared"));
}