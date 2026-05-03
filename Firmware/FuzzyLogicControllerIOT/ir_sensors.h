#ifndef IR_SENSORS_H
#define IR_SENSORS_H

#include <Arduino.h>

// Function declarations
void initSensors();
byte readPCF(int addr);
int readLane1();
int readLane2();
int readLane3();
int readLane4();

#endif