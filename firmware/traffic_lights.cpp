#include "traffic_lights.h"
#include "config.h"

// Global variables
TrafficState currentState = STATE_ALL_RED;
bool emergencyMode = false;
int emergencyLane = 0;
unsigned long emergencyStartTime = 0;
unsigned long stateStartTime = 0;
uint16_t shiftData = 0;
int lanePriority[4] = {0, 0, 0, 0};

// External variables from main
extern int lane1_cars, lane2_cars, lane3_cars, lane4_cars;

// Initialize traffic lights
void initTrafficLights() {
  pinMode(DATA, OUTPUT);
  pinMode(CLOCK, OUTPUT);
  pinMode(LATCH, OUTPUT);
  pinMode(OE, OUTPUT);
  pinMode(MR, OUTPUT);
  
  digitalWrite(OE, LOW);      // Enable outputs
  digitalWrite(MR, HIGH);      // Disable reset
  
  shiftData = 0;
  sendData(0, 0);
  
  Serial.println(F("✅ Traffic lights initialized"));
}

// Send data to both shift registers
void sendData(byte sn1Data, byte sn2Data) {
  digitalWrite(LATCH, LOW);
  delayMicroseconds(5);
  
  // First 595 (Lanes 1-2), then second 595 (Lanes 3-4)
  shiftOut(DATA, CLOCK, MSBFIRST, sn1Data);
  shiftOut(DATA, CLOCK, MSBFIRST, sn2Data);
  
  delayMicroseconds(5);
  digitalWrite(LATCH, HIGH);
  delayMicroseconds(5);
  digitalWrite(LATCH, LOW);
}

// Set specific light
void setLight(int lane, int light, bool state) {
  int bitPos = -1;
  
  switch(lane) {
    case 0: // Lane 1
      if (light == LIGHT_RED) bitPos = LANE1_RED_BIT;
      else if (light == LIGHT_YELLOW) bitPos = LANE1_YELLOW_BIT;
      else if (light == LIGHT_GREEN) bitPos = LANE1_GREEN_BIT;
      break;
    case 1: // Lane 2
      if (light == LIGHT_RED) bitPos = LANE2_RED_BIT;
      else if (light == LIGHT_YELLOW) bitPos = LANE2_YELLOW_BIT;
      else if (light == LIGHT_GREEN) bitPos = LANE2_GREEN_BIT;
      break;
    case 2: // Lane 3
      if (light == LIGHT_RED) bitPos = LANE3_RED_BIT;
      else if (light == LIGHT_YELLOW) bitPos = LANE3_YELLOW_BIT;
      else if (light == LIGHT_GREEN) bitPos = LANE3_GREEN_BIT;
      break;
    case 3: // Lane 4
      if (light == LIGHT_RED) bitPos = LANE4_RED_BIT;
      else if (light == LIGHT_YELLOW) bitPos = LANE4_YELLOW_BIT;
      else if (light == LIGHT_GREEN) bitPos = LANE4_GREEN_BIT;
      break;
  }
  
  if (bitPos >= 0) {
    if (state) {
      shiftData |= (1 << bitPos);
    } else {
      shiftData &= ~(1 << bitPos);
    }
    
    byte sn1Data = shiftData & 0xFF;        // Lower 8 bits - First 595
    byte sn2Data = (shiftData >> 8) & 0xFF; // Upper 8 bits - Second 595
    
    sendData(sn1Data, sn2Data);
  }
}

// Set lane color (one color per lane)
void setLaneColor(int lane, int color) {
  // Turn off all lights for this lane first
  setLight(lane, LIGHT_RED, false);
  setLight(lane, LIGHT_YELLOW, false);
  setLight(lane, LIGHT_GREEN, false);
  
  // Turn on the requested color
  if (color != LIGHT_OFF) {
    setLight(lane, color, true);
  }
}

// Set all lanes to specific colors (for debugging)
void setAllLanes(int color1, int color2, int color3, int color4) {
  setLaneColor(0, color1);
  setLaneColor(1, color2);
  setLaneColor(2, color3);
  setLaneColor(3, color4);
}

// All red - ALL LANES RED
void allRed() {
  setAllLanes(LIGHT_RED, LIGHT_RED, LIGHT_RED, LIGHT_RED);
  currentState = STATE_ALL_RED;
  Serial.println(F("🔴 ALL RED"));
}

// Calculate priority score for a lane (higher = more priority)
int calculateLanePriority(int lane) {
  int carCount;
  
  switch(lane) {
    case 0: carCount = lane1_cars; break;
    case 1: carCount = lane2_cars; break;
    case 2: carCount = lane3_cars; break;
    case 3: carCount = lane4_cars; break;
    default: return 0;
  }
  
  // Priority based on vehicle count
  if (carCount >= 3) return 100;  // HIGH density - highest priority
  if (carCount == 2) return 70;   // MEDIUM density
  if (carCount == 1) return 40;   // LOW density
  return 10;                       // EMPTY - lowest priority
}

// Get next lane for green light based on priority
int getNextGreenLane() {
  // Calculate priorities for all lanes
  for (int i = 0; i < 4; i++) {
    lanePriority[i] = calculateLanePriority(i);
  }
  
  // Find lane with highest priority
  int highestLane = 0;
  int highestPriority = lanePriority[0];
  
  for (int i = 1; i < 4; i++) {
    if (lanePriority[i] > highestPriority) {
      highestPriority = lanePriority[i];
      highestLane = i;
    }
  }
  
  // Debug output
  Serial.print("Vehicle counts: L1=");
  Serial.print(lane1_cars);
  Serial.print(" L2=");
  Serial.print(lane2_cars);
  Serial.print(" L3=");
  Serial.print(lane3_cars);
  Serial.print(" L4=");
  Serial.println(lane4_cars);
  
  Serial.print("Priority scores: ");
  for(int i=0; i<4; i++) {
    Serial.print("Lane"); Serial.print(i+1); 
    Serial.print("="); Serial.print(lanePriority[i]);
    Serial.print(" ");
  }
  Serial.print(" → Selected Lane "); 
  Serial.println(highestLane + 1);
  
  return highestLane;
}

// Get dynamic green time based on lane density
int getDynamicGreenTime(int lane) {
  int carCount;
  
  switch(lane) {
    case 0: carCount = lane1_cars; break;
    case 1: carCount = lane2_cars; break;
    case 2: carCount = lane3_cars; break;
    case 3: carCount = lane4_cars; break;
    default: return GREEN_TIME_NORMAL;
  }
  
  if (carCount >= 3) return GREEN_TIME_HIGH;    // 12 seconds for HIGH density
  if (carCount == 2) return GREEN_TIME_MEDIUM;  // 8 seconds for MEDIUM density
  return GREEN_TIME_NORMAL;                      // 5 seconds for LOW density
}

// Emergency mode - force a specific lane to green
void triggerEmergency(int lane) {
  if (lane < 0 || lane > 3) return;
  
  emergencyMode = true;
  emergencyLane = lane;
  emergencyStartTime = millis();
  
  // Force all red first, then green for emergency lane
  allRed();
  delay(RED_TIME);
  setLaneColor(lane, LIGHT_GREEN);
  
  Serial.print(F("\n🚨 EMERGENCY Lane "));
  Serial.print(lane + 1);
  Serial.print(F(" GREEN for "));
  Serial.print(EMERGENCY_GREEN_TIME / 1000);
  Serial.println(F("s"));
}

// Main traffic light update function
void updateTrafficLights() {
  unsigned long currentTime = millis();
  
  // Emergency mode check
  if (emergencyMode) {
    if (currentTime - emergencyStartTime > EMERGENCY_GREEN_TIME) {
      emergencyMode = false;
      allRed();
      currentState = STATE_PRIORITY_SELECT;
      stateStartTime = currentTime;
      Serial.println(F("🔄 Emergency ended"));
    }
    return;
  }
  
  // Normal traffic light state machine
  switch(currentState) {
    case STATE_ALL_RED:
      delay(RED_TIME);
      currentState = STATE_PRIORITY_SELECT;
      stateStartTime = currentTime;
      break;
      
    case STATE_PRIORITY_SELECT:
      {
        int nextLane = getNextGreenLane();
        switch(nextLane) {
          case 0: currentState = STATE_LANE1_GREEN; break;
          case 1: currentState = STATE_LANE2_GREEN; break;
          case 2: currentState = STATE_LANE3_GREEN; break;
          case 3: currentState = STATE_LANE4_GREEN; break;
        }
        stateStartTime = currentTime;
      }
      break;
      
    case STATE_LANE1_GREEN:
      // Lane 1 GREEN, all others RED
      setAllLanes(LIGHT_GREEN, LIGHT_RED, LIGHT_RED, LIGHT_RED);
      
      if (currentTime - stateStartTime > getDynamicGreenTime(0)) {
        currentState = STATE_LANE1_YELLOW;
        stateStartTime = currentTime;
      }
      break;
      
    case STATE_LANE1_YELLOW:
      // Lane 1 YELLOW, all others RED
      setAllLanes(LIGHT_YELLOW, LIGHT_RED, LIGHT_RED, LIGHT_RED);
      
      if (currentTime - stateStartTime > YELLOW_TIME) {
        currentState = STATE_PRIORITY_SELECT;
        stateStartTime = currentTime;
      }
      break;
      
    case STATE_LANE2_GREEN:
      // Lane 2 GREEN, all others RED
      setAllLanes(LIGHT_RED, LIGHT_GREEN, LIGHT_RED, LIGHT_RED);
      
      if (currentTime - stateStartTime > getDynamicGreenTime(1)) {
        currentState = STATE_LANE2_YELLOW;
        stateStartTime = currentTime;
      }
      break;
      
    case STATE_LANE2_YELLOW:
      // Lane 2 YELLOW, all others RED
      setAllLanes(LIGHT_RED, LIGHT_YELLOW, LIGHT_RED, LIGHT_RED);
      
      if (currentTime - stateStartTime > YELLOW_TIME) {
        currentState = STATE_PRIORITY_SELECT;
        stateStartTime = currentTime;
      }
      break;
      
    case STATE_LANE3_GREEN:
      // Lane 3 GREEN, all others RED
      setAllLanes(LIGHT_RED, LIGHT_RED, LIGHT_GREEN, LIGHT_RED);
      
      if (currentTime - stateStartTime > getDynamicGreenTime(2)) {
        currentState = STATE_LANE3_YELLOW;
        stateStartTime = currentTime;
      }
      break;
      
    case STATE_LANE3_YELLOW:
      // Lane 3 YELLOW, all others RED
      setAllLanes(LIGHT_RED, LIGHT_RED, LIGHT_YELLOW, LIGHT_RED);
      
      if (currentTime - stateStartTime > YELLOW_TIME) {
        currentState = STATE_PRIORITY_SELECT;
        stateStartTime = currentTime;
      }
      break;
      
    case STATE_LANE4_GREEN:
      // Lane 4 GREEN, all others RED
      setAllLanes(LIGHT_RED, LIGHT_RED, LIGHT_RED, LIGHT_GREEN);
      
      if (currentTime - stateStartTime > getDynamicGreenTime(3)) {
        currentState = STATE_LANE4_YELLOW;
        stateStartTime = currentTime;
      }
      break;
      
    case STATE_LANE4_YELLOW:
      // Lane 4 YELLOW, all others RED
      setAllLanes(LIGHT_RED, LIGHT_RED, LIGHT_RED, LIGHT_YELLOW);
      
      if (currentTime - stateStartTime > YELLOW_TIME) {
        currentState = STATE_PRIORITY_SELECT;
        stateStartTime = currentTime;
      }
      break;
  }
}

// Test individual lights one by one
void testIndividualLights() {
  Serial.println(F("\n🔧 Testing individual lights:"));
  
  for (int lane = 0; lane < 4; lane++) {
    for (int light = 1; light <= 3; light++) {
      Serial.print(F("Lane "));
      Serial.print(lane + 1);
      Serial.print(F(" - "));
      switch(light) {
        case 1: Serial.print(F("RED")); break;
        case 2: Serial.print(F("YELLOW")); break;
        case 3: Serial.print(F("GREEN")); break;
      }
      Serial.println();
      
      setLight(lane, light, true);
      delay(500);
      setLight(lane, light, false);
      delay(200);
    }
  }
  
  allRed();
  Serial.println(F("✅ Test complete"));
}

// Test all lanes in sequence
void testAllLights() {
  Serial.println(F("\n🔧 Testing all lanes in sequence:"));
  
  // Test Lane 1
  Serial.println(F("Lane 1 GREEN, others RED"));
  setAllLanes(LIGHT_GREEN, LIGHT_RED, LIGHT_RED, LIGHT_RED);
  delay(2000);
  
  Serial.println(F("Lane 1 YELLOW, others RED"));
  setAllLanes(LIGHT_YELLOW, LIGHT_RED, LIGHT_RED, LIGHT_RED);
  delay(1000);
  
  // Test Lane 2
  Serial.println(F("Lane 2 GREEN, others RED"));
  setAllLanes(LIGHT_RED, LIGHT_GREEN, LIGHT_RED, LIGHT_RED);
  delay(2000);
  
  Serial.println(F("Lane 2 YELLOW, others RED"));
  setAllLanes(LIGHT_RED, LIGHT_YELLOW, LIGHT_RED, LIGHT_RED);
  delay(1000);
  
  // Test Lane 3
  Serial.println(F("Lane 3 GREEN, others RED"));
  setAllLanes(LIGHT_RED, LIGHT_RED, LIGHT_GREEN, LIGHT_RED);
  delay(2000);
  
  Serial.println(F("Lane 3 YELLOW, others RED"));
  setAllLanes(LIGHT_RED, LIGHT_RED, LIGHT_YELLOW, LIGHT_RED);
  delay(1000);
  
  // Test Lane 4
  Serial.println(F("Lane 4 GREEN, others RED"));
  setAllLanes(LIGHT_RED, LIGHT_RED, LIGHT_RED, LIGHT_GREEN);
  delay(2000);
  
  Serial.println(F("Lane 4 YELLOW, others RED"));
  setAllLanes(LIGHT_RED, LIGHT_RED, LIGHT_RED, LIGHT_YELLOW);
  delay(1000);
  
  allRed();
  Serial.println(F("✅ Test complete"));
}