#include "aws_iot.h"

// ============================================
// YOUR AWS CERTIFICATES
// ============================================

// AWS Root CA Certificate
const char AWS_CERT_CA[] PROGMEM = R"EOF(
-----BEGIN CERTIFICATE-----
MIIDQTCCAimgAwIBAgITBmyfz5m/jAo54vB4ikPmljZbyjANBgkqhkiG9w0BAQsF
ADA5MQswCQYDVQQGEwJVUzEPMA0GA1UEChMGQW1hem9uMRkwFwYDVQQDExBBbWF6
b24gUm9vdCBDQSAxMB4XDTE1MDUyNjAwMDAwMFoXDTM4MDExNzAwMDAwMFowOTEL
MAkGA1UEBhMCVVMxDzANBgNVBAoTBkFtYXpvbjEZMBcGA1UEAxMQQW1hem9uIFJv
b3QgQ0EgMTCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBALJ4gHHKeNXj
ca9HgFB0fW7Y14h29Jlo91ghYPl0hAEvrAIthtOgQ3pOsqTQNroBvo3bSMgHFzZM
9O6II8c+6zf1tRn4SWiw3te5djgdYZ6k/oI2peVKVuRF4fn9tBb6dNqcmzU5L/qw
IFAGbHrQgLKm+a/sRxmPUDgH3KKHOVj4utWp+UhnMJbulHheb4mjUcAwhmahRWa6
VOujw5H5SNz/0egwLX0tdHA114gk957EWW67c4cX8jJGKLhD+rcdqsq08p8kDi1L
93FcXmn/6pUCyziKrlA4b9v7LWIbxcceVOF34GfID5yHI9Y/QCB/IIDEgEw+OyQm
jgSubJrIqg0CAwEAAaNCMEAwDwYDVR0TAQH/BAUwAwEB/zAOBgNVHQ8BAf8EBAMC
AYYwHQYDVR0OBBYEFIQYzIU07LwMlJQuCFmcx7IQTgoIMA0GCSqGSIb3DQEBCwUA
A4IBAQCY8jdaQZChGsV2USggNiMOruYou6r4lK5IpDB/G/wkjUu0yKGX9rbxenDI
U5PMCCjjmCXPI6T53iHTfIUJrU6adTrCC2qJeHZERxhlbI1Bjjt/msv0tadQ1wUs
N+gDS63pYaACbvXy8MWy7Vu33PqUXHeeE6V/Uq2V8viTO96LXFvKWlJbYK8U90vv
o/ufQJVtMVT8QtPHRh8jrdkPSHCa2XV4cdFyQzR1bldZwgJcJmApzyMZFo6IQ6XU
5MsI+yMRQ+hDKXJioaldXgjUkK642M4UwtBV8ob2xJNDd2ZhwLnoQdeXeGADbkpy
rqXRfboQnoZsG4q5WTP468SQvvG5
-----END CERTIFICATE-----
)EOF";

// Device Certificate
const char AWS_CERT_CRT[] PROGMEM = R"KEY(
-----BEGIN CERTIFICATE-----
MIIDWTCCAkGgAwIBAgIUeNCtVlmDIKN0QCg96WJXrL3+5tMwDQYJKoZIhvcNAQEL
BQAwTTFLMEkGA1UECwxCQW1hem9uIFdlYiBTZXJ2aWNlcyBPPUFtYXpvbi5jb20g
SW5jLiBMPVNlYXR0bGUgU1Q9V2FzaGluZ3RvbiBDPVVTMB4XDTI2MDIyNTE5Mjgy
NFoXDTQ5MTIzMTIzNTk1OVowHjEcMBoGA1UEAwwTQVdTIElvVCBDZXJ0aWZpY2F0
ZTCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBAKRXq11b8XXgzBLeAsrf
l1RqWAyPTg/j5Xya+KaD6NZKF9d4cKYx5zoDMifx6a+vtcNo+1gfstaUe1pVeP3m
iEPMKbBAss39QZUDkxWxJVHRPImm2aOD+pInmpq+QpUGoQt7yFEpyXurHzZqVOJs
B8Ef2JJ/o9IEKX10CPK3kWQSlNgngZ3vYL4nDhKCjCbeMF7kcZUR+hDtiPnfqTU0
EkmSjKEJBmLKC7LnRPHfiV2kBdbrCLz+h3bRwv7F+5pYvNRJleGG8Pr8OVW/KRP/
JLceEDswc1kSpvQETpjdIRlrklzY9Ty5Uv1ZW2Sx5WQWXm17S6WWXVC4Ae+y7vzG
XwcCAwEAAaNgMF4wHwYDVR0jBBgwFoAUUEPTBll2y7K0I0WKMODtI9YG3gMwHQYD
VR0OBBYEFHbICCoJ8b2Mjn20LjDUXUHesxD0MAwGA1UdEwEB/wQCMAAwDgYDVR0P
AQH/BAQDAgeAMA0GCSqGSIb3DQEBCwUAA4IBAQCAXDdzQP4SLU3iKaGzdAW4tRXY
8QsSLA+NCkGK5OWDo25UsDbgOajVU15DR65Rxf1Xs6K6UN+vrWiumJDzOv7Jo61/
7ShfmkC97k13XAHidXCqMF+AajoKDk4K2Ff+g8UYPwkSSIaAAxWUMezWuRcsCA++
AyWRF6EitJcHClfDm6wStkTWbxEKJK9LNq3ojTTCp7BLimXqgqagSBPE7+wQvBGU
Br9V1Rk/ZoS7bo+IsRTjPvQntBo5Ax19oMHodkyE5cLwSTxds8ZSZzbocTMr4NbZ
5akQS0keClpNXkICPeHQyXeudG8Sd/D+YOAiEMQRKi12LVsaAKNj6wyrNdgZ
-----END CERTIFICATE-----
)KEY";

// Private Key
const char AWS_CERT_PRIVATE[] PROGMEM = R"KEY(
-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEApFerXVvxdeDMEt4Cyt+XVGpYDI9OD+PlfJr4poPo1koX13hw
pjHnOgMyJ/Hpr6+1w2j7WB+y1pR7WlV4/eaIQ8wpsECyzf1BlQOTFbElUdE8iabZ
o4P6kieamr5ClQahC3vIUSnJe6sfNmpU4mwHwR/Ykn+j0gQpfXQI8reRZBKU2CeB
ne9gvicOEoKMJt4wXuRxlRH6EO2I+d+pNTQSSZKMoQkGYsoLsudE8d+JXaQF1usI
vP6HdtHC/sX7mli81EmV4Ybw+vw5Vb8pE/8ktx4QOzBzWRKm9AROmN0hGWuSXNj1
PLlS/VlbZLHlZBZebXtLpZZdULgB77Lu/MZfBwIDAQABAoIBAHAtw7SLcSvUkZiD
YQaYTxT5LjcMju1704cVxYrsWcAEfXfAJ6zaPYq06cSodapN11WW0JKbuJiObBEC
bP9rIDKfJwm/cA35xI1yDjFtZRsPJzKS6Nab3StsyzS7kHlnOAC9ssPsMTMwYLLl
LCIOOdDS6yM861cNLkELNpxvP1g92sQ6pZoob07i+ohBAyW2FV2iiZt+SPN//ZY9
oA7P1V/64Z2+YDGpRDraj/b6baVD5jGFlG5b40laWB0b9jImVSJa+ZBZbuWkGQvB
7ASuF8/DSHMeaWBdD7b5OwvoKUR87cPUrVlURe0REhzUKEJAa1P4302iwkN9Gvz1
0WSrDMECgYEAzZ5FdBddIRsJl1z3GJaAgy1q10neSyQNSNAJiOMGK4YYsgwDUAIQ
/F2fWzaDpXkNPlcxXEr5Igmzs1/0zzdYYel23e7MOp/AzUplE1a+hJfcfrEzjKig
mOXVRyrz9uyGXFWz/RmtUy2//NubPLSa45F0aJ1qO2lpiqltTK1Aj+ECgYEAzJxP
JjPczL+m6YOvuYBS/fUwJuLZ4cQY3pMl5Ebw1ajqfm19n7dWXO+8GYp/StOubCKo
/hcExkMzmpi42zp0LcAsCvsnK8/kkP70+sD6KokA2EYM1Hm8LdyBmCuEIaaVx7Kh
dRtUSpArgYkR3l3iw3uMc1L3XXIWr2PLw4WR6+cCgYB3BZbOjHesIip7I6Uk5nmd
dTzTQj8a39OQwlvCkSeRKh5BchK4zXlnnAoSkovBzUCNRYudEQkFWvhabMEY8cCH
bM0RypkNlkvUiavYde3ycrV/4LMmSLYty1yZxZNS67ca28FEUQizjVgE1loV2bWO
5TOtGvHTUkF1sn1CVUd6AQKBgA7rmw3zHDfGBfrjQm4pgGPKfF9pjW/cJ+AbJNk3
nxpFfgwIGfAKo36VcMcABXZEZ2S1RlN5BD0c62drmZdK9OvdJpkKZXnZaBZ2sRCT
/+oYIXqj6Q2ZbvJ9MOoSykjV5/gu+30ZqBTj3HhOsYHgoMeWe9BxDV7AEg1qHpK8
a76jAoGBAJJaAaGTOQyrvVCeIWe060ZdYC20qX8WOY9+LHGGUeG313je5CrGpnmw
UBAYW35/NQ2CLSoBkz57F/ZDbvZ+Zr1oDH7lGnWAakEkWgWztrM9fVsEqm4TOB/p
fPpgsZDrDuf8z89pv/5WBTI4RWyCapIbir2rFeku0jMvGfrM55bM
-----END RSA PRIVATE KEY-----
)KEY";

// WiFi client and MQTT client
WiFiClientSecure espClient;
PubSubClient mqttClient(espClient);

// Flags
bool awsConnected = false;

// Connect to WiFi
void connectWiFi() {
  if (strlen(WIFI_SSID) == 0) {
    Serial.println(F("WiFi credentials not set - skipping WiFi"));
    return;
  }

  Serial.print(F("Connecting to WiFi"));
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(F("."));
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println(F("\n✅ WiFi connected"));
    Serial.print(F("IP: "));
    Serial.println(WiFi.localIP());
  } else {
    Serial.println(F("\n❌ WiFi connection failed - continuing without AWS"));
  }
}

// Time synchronization function (CRITICAL for AWS)
void syncTime() {
  Serial.print(F("Synchronizing time with NTP"));

  // Configure NTP servers
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");

  // Wait for time to be set
  time_t now = time(nullptr);
  int attempts = 0;
  while (now < 8 * 3600 * 2 && attempts < 30) {  // Wait until time is after 1970
    delay(500);
    Serial.print(F("."));
    now = time(nullptr);
    attempts++;
  }

  if (now > 8 * 3600 * 2) {
    struct tm timeinfo;
    gmtime_r(&now, &timeinfo);
    Serial.print(F("\n✅ Time synchronized: "));
    Serial.print(asctime(&timeinfo));
  } else {
    Serial.println(F("\n⚠️ Time sync failed - AWS may not work"));
  }
}

// Connect to AWS IoT
void connectAWS() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println(F("WiFi not connected - skipping AWS"));
    awsConnected = false;
    return;
  }

  if (strlen(AWS_IOT_ENDPOINT) == 0) {
    Serial.println(F("AWS endpoint not set - skipping AWS"));
    awsConnected = false;
    return;
  }

  // CRITICAL: Sync time before connecting to AWS
  syncTime();

  Serial.println(F("Configuring AWS certificates..."));

  // Configure certificates
  espClient.setTrustAnchors(new BearSSL::X509List(AWS_CERT_CA));
  espClient.setClientRSACert(new BearSSL::X509List(AWS_CERT_CRT), new BearSSL::PrivateKey(AWS_CERT_PRIVATE));

  mqttClient.setServer(AWS_IOT_ENDPOINT, 8883);

  Serial.print(F("Connecting to AWS IoT"));

  int attempts = 0;
  while (!mqttClient.connected() && attempts < 20) {
    String clientId = "ESP8266-" + String(WiFi.macAddress());

    if (mqttClient.connect(clientId.c_str())) {
      Serial.println(F("\n✅ Connected to AWS IoT"));
      awsConnected = true;
    } else {
      Serial.print(F("."));
      attempts++;
      delay(1000);
    }
  }

  if (!mqttClient.connected()) {
    Serial.println(F("\n❌ AWS IoT connection failed"));
    Serial.print(F("MQTT State: "));
    Serial.println(mqttClient.state());

    // Detailed error messages
    switch (mqttClient.state()) {
      case -4:
        Serial.println(F("Error: MQTT_CONNECTION_TIMEOUT"));
        break;
      case -3:
        Serial.println(F("Error: MQTT_CONNECTION_LOST"));
        break;
      case -2:
        Serial.println(F("Error: MQTT_CONNECT_FAILED - Check endpoint, certificates, and time sync"));
        break;
      case -1:
        Serial.println(F("Error: MQTT_DISCONNECTED"));
        break;
      case 1:
        Serial.println(F("Error: MQTT_CONNECT_BAD_PROTOCOL"));
        break;
      case 2:
        Serial.println(F("Error: MQTT_CONNECT_BAD_CLIENT_ID"));
        break;
      case 3:
        Serial.println(F("Error: MQTT_CONNECT_UNAVAILABLE"));
        break;
      case 4:
        Serial.println(F("Error: MQTT_CONNECT_BAD_CREDENTIALS - Certificate issue"));
        break;
      case 5:
        Serial.println(F("Error: MQTT_CONNECT_UNAUTHORIZED - Check AWS policy"));
        break;
      default:
        Serial.println(F("Error: Unknown MQTT error"));
        break;
    }

    awsConnected = false;
  }
}

// Maintain AWS connection
void maintainAWSConnection() {
  if (!awsConnected) return;

  if (!mqttClient.connected()) {
    Serial.println(F("Reconnecting to AWS IoT..."));
    connectAWS();
  }

  if (mqttClient.connected()) {
    mqttClient.loop();
  }
}