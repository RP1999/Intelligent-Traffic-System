#include "emergency_vehicle.h"
#include <SPI.h>
#include <MFRC522.h>

// Pin definitions for Lane 1 ONLY
#define RFID_SS     15  // D8  - Slave Select
#define RFID_RST    16  // D0  - Reset

// Create RFID instance for Lane 1
MFRC522 rfid(RFID_SS, RFID_RST);

// YOUR ACTUAL EMERGENCY TAG UID (from your scan)
const byte EMERGENCY_TAG[4] = {0x51, 0xA7, 0x0E, 0x06};

// Global emergency state
EmergencyInfo emergencyState = {false, "", 0, 0};

// Statistics
unsigned long readerReads = 0;
unsigned long emergencyDetects = 0;
unsigned long unknownDetects = 0;

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

// Initialize RFID reader for Lane 1
void initRFID() {
  Serial.println(F("\n🔷 Initializing RFID Reader for Lane 1..."));
  
  // Configure pins
  pinMode(RFID_SS, OUTPUT);
  digitalWrite(RFID_SS, HIGH);
  
  // Initialize SPI
  SPI.begin();
  SPI.setFrequency(1000000);
  delay(100);
  
  // Initialize RFID
  rfid.PCD_Init();
  delay(100);
  
  // Test communication
  byte version = rfid.PCD_ReadRegister(MFRC522::VersionReg);
  
  if (version == 0x00 || version == 0xFF) {
    Serial.println(F("❌ RFID Reader NOT DETECTED!"));
    Serial.println(F("   Check wiring:"));
    Serial.println(F("   • D8 (GPIO15) → SDA/SS"));
    Serial.println(F("   • D5 (GPIO14) → SCK"));
    Serial.println(F("   • D7 (GPIO13) → MOSI"));
    Serial.println(F("   • D6 (GPIO12) → MISO"));
    Serial.println(F("   • D0 (GPIO16) → RST"));
    Serial.println(F("   • 3.3V/5V → VCC"));
    Serial.println(F("   • GND → GND"));
  } else {
    Serial.println(F("✅ RFID Reader OK!"));
    Serial.print(F("   Firmware Version: 0x"));
    Serial.println(version, HEX);
    
    // Enable antenna
    rfid.PCD_SetRegisterBitMask(MFRC522::TxControlReg, 0x03);
    rfid.PCD_SetAntennaGain(MFRC522::RxGain_max);
    
    Serial.println(F("\n✅ Emergency detection active on Lane 1"));
    Serial.print(F("   Emergency Tag UID: "));
    Serial.println(uidToString((byte*)EMERGENCY_TAG, 4));
    Serial.println(F("   Waiting for RFID tags...\n"));
  }
}

// Check RFID for emergency vehicle
void checkRFID(unsigned long currentTime) {
  static unsigned long lastCheck = 0;
  const unsigned long checkInterval = 100; // Check every 100ms
  
  if (currentTime - lastCheck < checkInterval) return;
  lastCheck = currentTime;
  
  // Check for new card
  if (rfid.PICC_IsNewCardPresent() && rfid.PICC_ReadCardSerial()) {
    readerReads++;
    
    String tagId = uidToString(rfid.uid.uidByte, rfid.uid.size);
    
    Serial.println(F("\n📌 ───────────────────────────"));
    Serial.println(F("📌 RFID TAG DETECTED!"));
    Serial.println(F("📌 ───────────────────────────"));
    Serial.print(F("   Lane: 1\n"));
    Serial.print(F("   UID: "));
    Serial.println(tagId);
    Serial.print(F("   Size: "));
    Serial.print(rfid.uid.size);
    Serial.println(F(" bytes"));
    
    // Check if emergency vehicle
    if (isEmergencyVehicle(rfid.uid.uidByte, rfid.uid.size)) {
      emergencyDetects++;
      
      // Update emergency state
      emergencyState.detected = true;
      emergencyState.tagId = tagId;
      emergencyState.laneNumber = 1;
      emergencyState.detectionTime = currentTime;
      
      Serial.println(F("\n   🚨 VEHICLE TYPE: EMERGENCY!"));
      Serial.println(F("   ✅ MATCH FOUND!"));
      Serial.println(F("   ⚡ ACTION: TURNING LANE 1 GREEN"));
      
    } else {
      unknownDetects++;
      Serial.println(F("\n   🚗 VEHICLE TYPE: Regular"));
      Serial.println(F("   ❌ Not an emergency vehicle"));
      Serial.print(F("   Expected: "));
      Serial.println(uidToString((byte*)EMERGENCY_TAG, 4));
    }
    
    // Show statistics
    Serial.println(F("\n📊 RFID Statistics:"));
    Serial.print(F("   Total Scans: "));
    Serial.println(readerReads);
    Serial.print(F("   Emergency: "));
    Serial.print(emergencyDetects);
    if (readerReads > 0) {
      Serial.print(F(" ("));
      Serial.print((emergencyDetects * 100) / readerReads);
      Serial.print(F("%)"));
    }
    Serial.println();
    Serial.print(F("   Unknown: "));
    Serial.print(unknownDetects);
    if (readerReads > 0) {
      Serial.print(F(" ("));
      Serial.print((unknownDetects * 100) / readerReads);
      Serial.print(F("%)"));
    }
    Serial.println();
    Serial.println(F("📌 ───────────────────────────\n"));
    
    // Halt card
    rfid.PICC_HaltA();
    rfid.PCD_StopCrypto1();
  }
  
  // Auto-clear emergency after 10 seconds
  static unsigned long lastClearMsg = 0;
  if (emergencyState.detected && (currentTime - emergencyState.detectionTime > 10000)) {
    emergencyState.detected = false;
    emergencyState.tagId = "";
    emergencyState.laneNumber = 0;
    Serial.println(F("\n🔄 Emergency mode cleared (10s timeout)\n"));
  } else if (emergencyState.detected) {
    // Show countdown every 2 seconds
    if (currentTime - lastClearMsg > 2000) {
      lastClearMsg = currentTime;
      int timeLeft = 10 - ((currentTime - emergencyState.detectionTime) / 1000);
      Serial.print(F("⏱️ Emergency active - Time left: "));
      Serial.print(timeLeft);
      Serial.println(F("s"));
    }
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
  Serial.println(F("🔄 Emergency manually cleared"));
}