/*
 * AquaSense AI - IoT Device Sketch
 *
 * This sketch reads data from various environmental sensors and sends it to the
 * AquaSense AI backend API via HTTP POST.
 *
 * Hardware: ESP32 / ESP8266
 * Sensors:
 * - DHT11 (Temperature & Humidity)
 * - pH Sensor (Analog)
 * - TDS Sensor (Analog)
 * - MQ135 (Air Quality)
 * - Rain Sensor (Digital/Analog)
 */

#ifdef ESP32
#include <HTTPClient.h>
#include <WiFi.h>

#else
#include <ESP8266HTTPClient.h>
#include <ESP8266WiFi.h>
#include <WiFiClient.h>

#endif
#include "DHT.h"
#include <ArduinoJson.h>

// Configuration
const char *ssid = "ubswifi";
const char *password = ""; // Add your WiFi password here
const char *apiKey = "UR93G83TW4W55ZU2";
const char *serverUrl = "http://10.0.30.6:5000/api/data";

// Pin Definitions
#define DHTPIN 4
#define DHTTYPE DHT11
#define PH_PIN 34
#define TDS_PIN 35
#define MQ135_PIN 32
#define RAIN_PIN 33

DHT dht(DHTPIN, DHTTYPE);

void setup() {
  Serial.begin(115200);
  dht.begin();

  // WiFi Connection
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi Connected");
}

void loop() {
  if (WiFi.status() == WL_CONNECTED) {
    WiFiClient client;
    HTTPClient http;

#ifdef ESP32
    http.begin(serverUrl);
#else
    http.begin(client, serverUrl);
#endif

    http.addHeader("Content-Type", "application/json");

    // Sensor Readings
    float temp = dht.readTemperature();
    float humidity = dht.readHumidity();
    int phRaw = analogRead(PH_PIN);
    float phValue =
        map(phRaw, 0, 4095, 0, 14); // Simple mapping, calibration needed
    int tdsRaw = analogRead(TDS_PIN);
    float tdsValue = tdsRaw * 0.5; // Placeholder calibration
    int mqValue = analogRead(MQ135_PIN);
    int rainRaw = analogRead(RAIN_PIN);
    String rainStatus = (rainRaw < 2000)   ? "Heavy Rain"
                        : (rainRaw < 3500) ? "Moderate"
                                           : "No Rain";

    // Prepare JSON payload
    StaticJsonDocument<512> doc; // Increased size to accommodate API key
    doc["api_key"] = apiKey;
    doc["device_id"] = "ESP32_AQUA_01";
    doc["temp"] = temp;
    doc["humidity"] = humidity;
    doc["ph"] = phValue;
    doc["tds"] = tdsValue;
    doc["mq135"] = mqValue;
    doc["rain"] = rainStatus;
    doc["lat"] = 40.7128;
    doc["lng"] = -74.0060;

    String jsonPayload;
    serializeJson(doc, jsonPayload);

    // Send POST request
    int httpResponseCode = http.POST(jsonPayload);

    if (httpResponseCode > 0) {
      String response = http.getString();
      Serial.println("Response: " + response);
    } else {
      Serial.print("Error on sending POST: ");
      Serial.println(httpResponseCode);
    }

    http.end();
  }

  delay(60000); // Send data every minute
}
