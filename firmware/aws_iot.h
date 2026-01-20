#ifndef AWS_IOT_H
#define AWS_IOT_H

#include <ESP8266WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <time.h>

// WiFi credentials - define these in main.ino
extern const char* WIFI_SSID;
extern const char* WIFI_PASSWORD;

// AWS IoT Core endpoint - define this in main.ino
extern const char* AWS_IOT_ENDPOINT;

// MQTT topic - define this in main.ino
extern const char* AWS_IOT_TOPIC;

// ============================================
// YOUR AWS CERTIFICATES
// ============================================

// AWS Root CA Certificate
extern const char AWS_CERT_CA[];

// Device Certificate
extern const char AWS_CERT_CRT[];

// Private Key
extern const char AWS_CERT_PRIVATE[];

// External variables
extern WiFiClientSecure espClient;
extern PubSubClient mqttClient;
extern bool awsConnected;

// Function declarations
void connectWiFi();
void syncTime();
void connectAWS();
void maintainAWSConnection();

#endif