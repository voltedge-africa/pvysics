// pvysics_feed.ino: an EXAMPLE of an ESP32 sending readings to the PV Digital Twin's Live Feed.
//
// NOT TESTED on hardware. It shows the shape of the program: read the sensors, post one JSON reading every few
// seconds. Check every pin, library and number against your own wiring and sensors before you rely on it.
//
// Parts it assumes: an INA219 (module voltage and current, I2C), a DS18B20 (module temperature, on the back of the
// module) and an irradiance sensor that gives a voltage on an ADC pin (a reference cell or a pyranometer).
// Libraries: "Adafruit INA219", "OneWire", "DallasTemperature".
//
// Settings in the app: Live Feed > Start listening, then copy the address and the token into the lines below.

#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <Adafruit_INA219.h>
#include <OneWire.h>
#include <DallasTemperature.h>

const char* WIFI_SSID = "your-network";
const char* WIFI_PASSWORD = "your-password";
const char* FEED_URL = "http://192.168.1.20:8765/reading";  // the address the Live Feed page shows
const char* FEED_TOKEN = "paste-the-token-here";            // the token the Live Feed page shows

const int TEMPERATURE_PIN = 4;     // DS18B20 data pin
const int IRRADIANCE_PIN = 34;     // ADC1 pin: the irradiance sensor's output
// Calibrate this with a reference instrument: W/m2 per volt at the ADC pin. 400 is only a placeholder.
const float IRRADIANCE_W_M2_PER_VOLT = 400.0;
const unsigned long SEND_EVERY_MS = 5000;

Adafruit_INA219 ina219;
OneWire oneWire(TEMPERATURE_PIN);
DallasTemperature temperature(&oneWire);

void connectWifi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.printf("\nWiFi connected, IP %s\n", WiFi.localIP().toString().c_str());
}

void setup() {
  Serial.begin(115200);
  if (!ina219.begin()) {
    Serial.println("INA219 not found: check the wiring");
  }
  temperature.begin();
  analogReadResolution(12);
  connectWifi();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    connectWifi();
  }

  temperature.requestTemperatures();
  float moduleTemperatureC = temperature.getTempCByIndex(0);
  float busVoltageV = ina219.getBusVoltage_V();
  float currentA = ina219.getCurrent_mA() / 1000.0;
  float adcVolts = analogReadMilliVolts(IRRADIANCE_PIN) / 1000.0;
  float irradianceWm2 = max(0.0f, adcVolts * IRRADIANCE_W_M2_PER_VOLT);

  if (moduleTemperatureC == DEVICE_DISCONNECTED_C) {
    Serial.println("DS18B20 not found: reading skipped");
  } else {
    // No time is sent: the app stamps each reading with its own clock when it arrives.
    char body[160];
    snprintf(body, sizeof(body), "{\"g\":%.1f,\"t\":%.2f,\"v\":%.3f,\"i\":%.4f}",
             irradianceWm2, moduleTemperatureC, busVoltageV, currentA);

    HTTPClient http;
    http.begin(FEED_URL);
    http.addHeader("Content-Type", "application/json");
    http.addHeader("X-Api-Key", FEED_TOKEN);
    int status = http.POST(body);
    Serial.printf("POST %s -> %d\n", body, status);  // 202 is accepted; 401 wrong token; 422 refused
    http.end();
  }
  delay(SEND_EVERY_MS);
}
