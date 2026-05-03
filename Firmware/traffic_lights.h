#ifndef TRAFFIC_LIGHTS_H
#define TRAFFIC_LIGHTS_H

#include <Arduino.h>
#include "config.h"

// Lane definitions
#define LANE1 0
#define LANE2 1
#define LANE3 2
#define LANE4 3

// Light states
#define LIGHT_OFF 0
#define LIGHT_RED 1
#define LIGHT_YELLOW 2
#define LIGHT_GREEN 3

// Bit positions in shift registers (16 bits total)
// First 595 (Lanes 1-2)
#define LANE1_RED_BIT     0
#define LANE1_YELLOW_BIT  1
#define LANE1_GREEN_BIT   2
#define LANE2_RED_BIT     3
#define LANE2_YELLOW_BIT  4
#define LANE2_GREEN_BIT   5

// Second 595 (Lanes 3-4) - bits 8-15
#define LANE3_RED_BIT     8
#define LANE3_YELLOW_BIT  9
#define LANE3_GREEN_BIT   10
#define LANE4_RED_BIT     11
#define LANE4_YELLOW_BIT  12
#define LANE4_GREEN_BIT   13

// Timing constants
#define GREEN_TIME_NORMAL 5000
#define GREEN_TIME_MEDIUM 8000
#define GREEN_TIME_HIGH   12000
#define YELLOW_TIME       2000
#define RED_TIME          1000
#define EMERGENCY_GREEN_TIME 15000

// Traffic light state machine
enum TrafficState {
  STATE_ALL_RED,
  STATE_LANE1_GREEN,
  STATE_LANE1_YELLOW,
  STATE_LANE2_GREEN,
  STATE_LANE2_YELLOW,
  STATE_LANE3_GREEN,
  STATE_LANE3_YELLOW,
  STATE_LANE4_GREEN,
  STATE_LANE4_YELLOW,
  STATE_PRIORITY_SELECT
};

// Global variables (declare as extern)
extern TrafficState currentState;
extern bool emergencyMode;
extern int emergencyLane;
extern unsigned long emergencyStartTime;
extern unsigned long stateStartTime;
extern uint16_t shiftData;
extern int lanePriority[4];

// Function declarations
void initTrafficLights();
void sendData(byte sn1Data, byte sn2Data);
void setLight(int lane, int light, bool state);
void setLaneColor(int lane, int color);
void allRed();
void triggerEmergency(int lane);
void updateTrafficLights();
void testIndividualLights();
int calculateLanePriority(int lane);
int getNextGreenLane();
int getDynamicGreenTime(int lane);

#endif